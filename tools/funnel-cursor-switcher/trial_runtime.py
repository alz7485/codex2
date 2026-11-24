"""Bridge the two Trial58 equipment controllers to the editor and Windows overlay."""
from functools import lru_cache
from pathlib import Path
import math
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from PIL import Image

from cursor_art import APPEARANCES, anchors, load_sprite
from effect_engine import ClickEvent, EffectEngine
from effect_settings import BUTTONS, MODIFIERS
from idle_motion import MOTION, PADDING, STEPS, idle_sheet, turn_frame

UNITS = {"キュベレイ": "qubeley", "サザビー": "sazabi"}


def supported(path):
    return path and path.parent.name == "ファンネル" and path.stem in UNITS


@lru_cache(maxsize=1)
def library():
    # PyInstaller installs this signed-off copy as data beside this module.
    temp = TemporaryDirectory(prefix="FunnelTrial58-")
    root = Path(temp.name)
    with ZipFile(Path(__file__).with_name("runtime58.zip")) as archive:
        archive.extractall(root)
    sys.path.insert(0, str(root / "effects_trial58"))
    from controller58 import Coordinator
    from visual58 import render_layer
    from sprites import composite, mix
    sys.path.insert(0, str(root / "effects_trial55"))
    from hull_motion import render_hull
    return temp, root, Coordinator, render_layer, composite, mix, render_hull


@lru_cache(maxsize=36)
def sheet(path):
    with Image.open(path) as im:
        return im.convert("RGBA")


def centered(image, position):
    return image, (round(position[0] - image.width / 2), round(position[1] - image.height / 2))


def scaled(image, factor):
    return image if factor == 1 else image.resize(tuple(max(1, round(n * factor)) for n in image.size),
                                                   Image.Resampling.LANCZOS)


class TrialDisplay:
    def __init__(self, path, config):
        _, self.root, coordinator, self.beams, self.escort, self.mix, self.hull = library()
        self.unit = UNITS[path.stem]
        self.special = "spiral" if self.unit == "qubeley" else "volley"
        self.config = config
        options = config[self.special]
        count = config["followers"]["count"] if config["followers"]["enabled"] else 0
        self.control = coordinator(self.unit, count,
                                   click_fire_enabled=options["click_fire_enabled"],
                                   orientation_mode=options["orientation_mode"])
        # Keep independent existing decorations available alongside the Trial58 hull and VFX.
        groups = {"particles", "deploy", "rare", "click"}
        if config["idle"]["motion"] != MOTION:
            groups.add("idle")
        decorations = {key: dict(value, enabled=value["enabled"] and key in groups)
                       for key, value in config.items()}
        self.decorations = EffectEngine(load_sprite(path), APPEARANCES[path.stem], decorations, path)
        self.idle_sheet = idle_sheet(path)
        self.hot = anchors(load_sprite(path), path)[0]
        self.pos = None
        self.still = 0
        self.idle_turn_step = None
        self.frame_origin = (0, 0)

    def reset(self):
        self.control.reset()
        self.decorations.reset()
        self.pos = None
        self.still = 0

    def primary(self, item, effects):
        assets = self.control.m["assets"][self.unit]
        index = item["pose_index"]
        phase = item["phase_index"]
        power = item["power"] * 8 if self.config["boost"]["enabled"] else 0
        level = min(7, int(power))
        x = 144 * index
        box = (x, 0, x + 144, 144)
        layers = []
        for key in ("back", "tint"):
            parts = [sheet(self.root / assets["levels"][i][phase][key]).crop(box) for i in (level, level+1)]
            layers.append(self.mix(*parts, power-level))
        body = Image.new("RGBA", (144,144))
        body.paste(sheet(self.root / assets["body"]).crop((index*96,0,index*96+96,96)), (24,24))
        image = Image.alpha_composite(Image.alpha_composite(layers[0], body), layers[1])
        local = [e for e in effects if e["stage"] == "charge" or
                 (e["stage"] == "fire" and math.dist(e["origin"],item["muzzle"]) <= max(2,4*item["scale"]))]
        return self.hull(image, body, self.control.f["assets"][self.unit]["muzzle_anchor_px"][index],
                         assets["rear_anchor_px"][index], self.unit, local) if local else image

    def item_layer(self, item, effects, scale):
        if item["id"] == -1 and self.idle_turn_step is not None:
            image = scaled(turn_frame(self.idle_sheet,self.idle_turn_step),scale)
            return image, tuple(round(p-(v+PADDING)*scale) for p,v in zip(self.pos,self.hot))
        if item["id"] == -1:
            image = self.primary(item, effects)
        else:
            image = self.escort(self.unit,item["power"],item["phase_index"],item["attitude_index"],
                                item.get("control_jets"))
        image = scaled(image,item["scale"]).rotate(-math.degrees(item["draw_heading"]),
                                                   Image.Resampling.BICUBIC,expand=True)
        if item["opacity"] < 1:
            image.putalpha(image.getchannel("A").point(lambda a: round(a*item["opacity"])))
        return centered(image,item["draw_position"])

    def fleet_layer(self, fleet, scale):
        idx = fleet["index"]
        spec = self.control.fleet
        page = next(p for p in spec["pages"] if p["first_frame"] <= idx < p["first_frame"]+p["frame_count"])
        row,col = divmod(idx-page["first_frame"],6)
        image = sheet(self.root/page["path"]).crop((col*288,row*288,(col+1)*288,(row+1)*288))
        return scaled(image,scale), tuple(round(v-a*scale) for v,a in zip(fleet["anchor"],spec["anchor_px"]))

    def step(self, pos, now, events, viewport, scale=1, show_primary=True):
        if pos is None:
            self.reset()
            return None
        c = self.control
        options = self.config[self.special]
        for event in events:
            button = "left" if event.kind == "double" else event.kind
            if (options["enabled"] and button == BUTTONS[options["button"]]
                    and event.modifiers == MODIFIERS[options["modifiers"]]):
                c.trigger_special(event.time,event.pos)
            elif button == "left":
                c.button_down(event.time)
            elif button == "left_up":
                if not c.button_up(event.time) and c.last and event.time-c.last[0] > .15:
                    c.cancel_fire()
        result = c.update(now,pos,scale,True,viewport)
        if result["reset"] or self.pos != pos or events:
            self.last_input = now
        self.still = now-self.last_input
        self.pos = pos
        idle = self.config["idle"]
        self.idle_turn_step = None
        if (idle["enabled"] and idle["motion"] == MOTION and self.still >= idle["delay"]
                and not result["primary_effects"] and not result["fleet"]):
            direction = -1 if idle["turn_direction"] == "逆回転" else 1
            self.idle_turn_step = int((self.still-idle["delay"])*STEPS/idle["turn_period"])*direction % STEPS
        layers = []
        if self.config["trail"]["enabled"]:
            layers.extend(tr.render(viewport,scale) for tr in c.trails[:len(result["items"])])
        if self.decorations.layers:
            logical = tuple(x/scale for x in pos)
            clicks = [ClickEvent(e.kind, tuple(v/scale for v in e.pos), e.time, e.modifiers)
                      for e in events if e.kind != "left_up" and
                      not (options["click_fire_enabled"] and e.kind in ("left","double"))]
            decoration = self.decorations.step(logical,now,clicks)
            if decoration is not None:
                layers.append(centered(scaled(decoration,scale),pos))
        layers.extend(self.item_layer(i,[],scale) for i in result["departing_escorts"])
        if result["fleet"]:
            layers.append(self.fleet_layer(result["fleet"],scale))
        effects = result["primary_effects"]
        items = {i["id"]:i for i in result["items"]}
        layers.extend(self.item_layer(items[i],effects,scale) for i in result["draw_order"] if i != -1 or show_primary)
        layers.append(self.beams(self.unit,effects,viewport))
        visible = []
        for image, point in layers:
            if image is None:
                continue
            bounds = image.getbbox()
            if bounds:
                x,y = point
                l,t,r,b = bounds
                l,t = max(l,viewport[0]-x),max(t,viewport[1]-y)
                r,b = min(r,viewport[2]-x),min(b,viewport[3]-y)
                if l<r and t<b:
                    visible.append((image.crop((l,t,r,b)),x+l,y+t))
        if not visible:
            return None
        left = min(x for _,x,_ in visible)
        top = min(y for _,_,y in visible)
        width = max(x+im.width for im,x,_ in visible)-left
        height = max(y+im.height for im,_,y in visible)-top
        frame = Image.new("RGBA",(width,height))
        for image,x,y in visible:
            frame.alpha_composite(image,(x-left,y-top))
        self.frame_origin = left,top
        return frame
