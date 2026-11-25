"""Bridge the two Trial58 equipment controllers to the editor and Windows overlay."""
from functools import lru_cache
from copy import deepcopy
from pathlib import Path
import math
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from PIL import Image, ImageDraw

from cursor_art import APPEARANCES, anchors, load_sprite
from effect_engine import ClickEvent, EffectEngine
from effect_settings import BUTTONS, MODIFIERS
from idle_motion import MOTION, PADDING, STEPS, idle_sheet, turn_frame

UNITS = {"キュベレイ": "qubeley", "サザビー": "sazabi"}


def supported(path):
    return path and path.parent.name == "ファンネル" and (path.stem in UNITS or path.stem in ("フィンファンネル", "Hi-νガンダム", "Hi-νガンダムHWS"))


def enabled(path, config):
    if not supported(path):
        return False
    special = {"フィンファンネル":"barrier","キュベレイ":"spiral","サザビー":"volley","Hi-νガンダム":"volley","Hi-νガンダムHWS":"volley"}[path.stem]
    return config[special]["click_fire_enabled"] or any(
        fields["enabled"] for fields in config.values()
    )


@lru_cache(maxsize=1)
def library():
    temp = None
    if getattr(sys, "frozen", False):
        root = Path(__file__).parent / "trial58"
    else:
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
        from primary_fire import PrimaryFire
        from escort_options import EscortOptions
        self.escort_options = EscortOptions(config["followers"], PrimaryFire)
        probe = coordinator(self.unit, 0).update(0, (0,0), 1, True, (-500,-500,500,500))
        item = next(i for i in probe["items"] if i["id"] == -1)
        body = scaled(self.primary(item, []), item["scale"]).rotate(
            -math.degrees(item["draw_heading"]), Image.Resampling.BICUBIC, expand=True)
        body_box = body.getchannel("A").point(lambda a: 255 if a >= 144 else 0).getbbox()
        native_box = load_sprite(path).getchannel("A").point(lambda a: 255 if a >= 144 else 0).getbbox()
        self.normal_scale = max(native_box[2]-native_box[0],native_box[3]-native_box[1]) / max(body_box[2]-body_box[0],body_box[3]-body_box[1])
        self.escort_trails = []
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
        self.escort_options.reset()
        for trail in self.escort_trails:
            trail.reset()
        self.decorations.reset()
        self.pos = None
        self.still = 0

    def cancel_fire(self):
        self.control.cancel_fire()
        self.escort_options.reset()

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
                self.escort_options.reset()
                c.trigger_special(event.time,event.pos)
            elif button == "left":
                if options["click_fire_enabled"]:
                    self.escort_options.input(button,event.time)
                c.button_down(event.time)
            elif button == "left_up":
                if options["click_fire_enabled"]:
                    self.escort_options.input(button,event.time)
                if not c.button_up(event.time) and c.last and event.time-c.last[0] > .15:
                    c.cancel_fire()
        result = c.update(now,pos,scale*self.normal_scale,True,viewport)
        primary = next((i for i in result["items"] if i["id"] == -1), None)
        if result["reset"] or result["fleet"]:
            self.escort_options.reset()
            for trail in self.escort_trails:
                trail.reset()
        if primary:
            escorts, extra = self.escort_options.transform([i for i in result["items"] if i["id"] != -1], primary, now)
            while len(self.escort_trails) < len(escorts):
                trail = deepcopy(c.trails[min(len(self.escort_trails)+1,len(c.trails)-1)])
                trail.reset()
                self.escort_trails.append(trail)
            for trail,item in zip(self.escort_trails,escorts):
                trail.update(now,item["nozzle"],item["speed"],item["power"]*item["opacity"])
            result = dict(result, items=[primary, *escorts], primary_effects=[*result["primary_effects"], *extra])
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
            layers.extend(tr.render(viewport,scale*self.normal_scale) for tr in c.trails[:1])
            layers.extend(tr.render(viewport,scale*self.normal_scale*self.escort_options.ratio) for tr in self.escort_trails)
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
        layers.extend(self.item_layer(items[i],[e for e in effects if e.get("owner",-1)==i],scale) for i in result["draw_order"] if i != -1 or show_primary)
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


@lru_cache(maxsize=1)
def fin_library():
    if getattr(sys, "frozen", False):
        return None, Path(__file__).parent / "fin77"
    temp = TemporaryDirectory(prefix="FinTrial77-")
    with ZipFile(Path(__file__).with_name("runtime77.zip")) as archive:
        archive.extractall(temp.name)
    return temp, Path(temp.name)


class FinDisplay(TrialDisplay):
    """Render Trial77 in monitor-local pixels, then place the cropped overlay globally."""
    special = "barrier"

    def __init__(self, path, config):
        _, root = fin_library()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from integrated_trial77 import Integrated
        self.config = config
        idle = config["idle"]
        opts = config[self.special]
        self.count = config["followers"]["count"] if config["followers"]["enabled"] else 0
        self.fx = Integrated(root, opts["click_fire_enabled"], self.count,
                             opts["color"] if opts["color"] != "機体色" else "purple",
                             idle["delay"], idle["turn_period"], idle["turn_direction"] == "逆回転")
        library()
        from primary_fire import PrimaryFire
        from escort_options import EscortOptions
        self.escort_options = EscortOptions(config["followers"], PrimaryFire)
        fleet = self.fx.flight.fleet
        update = fleet.update
        def update_escorts(t, xy, scale, bounds=None, visible=True):
            states = update(t, xy, scale, bounds, visible)
            if not visible:
                self.escort_options.reset()
                return states
            for state in states:
                pose = self.fx.flight.charge_poses[state["pose"]]
                cx,cy = self.fx.flight.manifest["pivot"]
                c,s = math.cos(state["heading"]),math.sin(state["heading"])
                def project(point):
                    x,y=(point[0]-cx)*state["scale"],(point[1]-cy)*state["scale"]
                    return (state["xy"][0]+c*x-s*y,state["xy"][1]+s*x+c*y)
                state["grid"] = project(pose["grid"])
                state["channel"] = [project(point) for point in pose["channel"]]
            primary = dict(heading=math.radians(-135) if opts["orientation_mode"] == "fixed_upper_left" else self.fx.flight.heading)
            return self.escort_options.transform(states, primary, t, fin=True)[0]
        fleet.update = update_escorts
        self.hot = anchors(load_sprite(path), path)[0]
        self.pos = None
        self.frame_origin = (0, 0)

    def reset(self):
        self.escort_options.reset()
        self.fx.reset()
        self.pos = None

    def cancel_fire(self):
        self.fx.cancel()
        self.escort_options.reset()

    def step(self, pos, now, events, viewport, scale=1, show_primary=True):
        if pos is None:
            self.reset()
            return None
        left, top, right, bottom = viewport
        bounds = (0, 0, right-left, bottom-top)
        opts = self.config[self.special]
        size = min(self.fx.flight.art.entries, key=lambda side: abs(side-32*scale))
        for event in events:
            button = "left" if event.kind == "double" else event.kind
            if opts["enabled"] and button == BUTTONS[opts["button"]] and event.modifiers == MODIFIERS[opts["modifiers"]]:
                self.fx.trigger_special(event.time,(event.pos[0]-left,event.pos[1]-top),bounds,
                                        opts["radius"],opts["duration"],.58*scale,opts["opacity"])
            elif button == "left":
                if opts["click_fire_enabled"]:
                    self.escort_options.input(button,event.time)
                self.fx.down(event.time)
            elif button == "left_up":
                if opts["click_fire_enabled"]:
                    self.escort_options.input(button,event.time)
                self.fx.up(event.time)
        self.pos = pos
        idle = self.config["idle"]
        state = self.fx.update(now,(pos[0]-left,pos[1]-top),size,
                               opts["orientation_mode"]=="fixed_upper_left",bounds,
                               idle_enabled=idle["enabled"] and idle["motion"]==MOTION,
                               context=(viewport,scale))
        background = Image.new("RGBA",bounds[2:])
        frame = self.fx.draw(background,state) if show_primary else self.fx.barrier.draw(background,state["special"])
        if not state["special"]:
            from escort_options import draw_fin_shots
            frame = draw_fin_shots(frame, state.get("escorts", ()))
        box = frame.getbbox()
        if box:
            self.frame_origin = left+box[0],top+box[1]
            return frame.crop(box)


def create_display(path, config):
    if path.stem in ("Hi-νガンダム", "Hi-νガンダムHWS"):
        from hinu_runtime import HiNuDisplay
        return HiNuDisplay(path, config)
    return (FinDisplay if path.stem == "フィンファンネル" else TrialDisplay)(path, config)
