"""Hi-Nu / HWS Trial218 bridge, shared by previews and the desktop overlay."""
from pathlib import Path
import sys
from dataclasses import replace
from PIL import Image
from cursor_art import anchors,load_sprite
from effect_settings import BUTTONS,MODIFIERS
from idle_motion import MOTION
from trial_runtime import TrialDisplay

NAMES={'Hi-νガンダム':'HiNu','Hi-νガンダムHWS':'HiNu_HWS'}

class HiNuDisplay(TrialDisplay):
    def __init__(self,path,config):
        base=Path(__file__).parent
        # Other equipment continues using the unchanged shared Trial122 VTK backend.
        if str(base/'hinu122') not in sys.path:sys.path.insert(0,str(base/'hinu122'))
        from hinu218.host_render import Renderer
        from hinu218.idle_trial192 import FleetCombat
        from hinu218.host_idle import ConfiguredIdle
        from hinu218.escort_settings_trial191 import EscortSettings
        from hinu218.special_trial215 import SpecialVolley
        self.volley_type=SpecialVolley
        self.config=config;self.special='volley';self.kind=NAMES[path.stem]
        self.pos=None;self.hot=anchors(load_sprite(path),path)[0];self.frame_origin=(0,0)
        self.renderer=Renderer(self.kind)
        f=config['followers'];idle=config['idle']
        settings=EscortSettings(f['count'] if f['enabled'] else 0,f['size_percent'],f['fire_enabled'])
        self.control=FleetCombat(settings.count,settings.size_percent,
                idle_enabled=idle['enabled'] and idle['motion']==MOTION,escort_fire_enabled=settings.fire_enabled)
        self.control.idle_motion=ConfiguredIdle(idle)
        self.context=None;self.render_origin=None;self.pressed=False;self.wait_release=False
        self.volley=self.volley_type(self.kind,1.)
        self.was_special=False

    def reset(self):
        self.control.reset();self.volley.reset();self.pos=None;self.render_origin=None;self.was_special=False
        self.wait_release=self.wait_release or self.pressed

    def cancel_fire(self):
        self.control.reset();self.render_origin=None;self.wait_release=True

    def close(self):self.renderer.close()

    def step(self,pos,now,events,viewport,scale=1,show_primary=True):
        if pos is None:self.reset();return None
        left,top,right,bottom=viewport;context=(viewport,scale)
        factor=min(1.,720*scale/max(right-left,bottom-top))
        width=max(1,round((right-left)*factor));height=max(1,round((bottom-top)*factor))
        if context!=self.context:
            self.reset();self.context=context
            self.volley=self.volley_type(self.kind,width/height)
        self.pos=pos;self.renderer.scale=scale;opts=self.config[self.special]
        was_active=self.volley.active
        for e in events:
            button='left' if e.kind=='double' else e.kind
            if button=='left':self.pressed=True
            elif button=='left_up':self.pressed=False;self.wait_release=False
            if opts['enabled'] and button==BUTTONS[opts['button']] and e.modifiers==MODIFIERS[opts['modifiers']]:
                if self.volley.trigger(e.time,context):
                    self.control.reset();self.render_origin=None
            elif opts['click_fire_enabled'] and not self.volley.active:
                if button=='left' and not self.wait_release:self.control.down(e.time)
                elif button=='left_up':self.control.up(e.time)
        self.volley.update(now,context=context)
        if self.volley.active:
            image=self.renderer.special(now-self.volley.start,(width,height))
            origin=(left+(right-left-width)//2,top+(bottom-top-height)//2)
        else:
            if was_active or self.was_special:
                self.control.reset();self.render_origin=None;self.wait_release=self.pressed
            side=max(1,round(480*scale))
            origin=(round(pos[0]-side/2),round(pos[1]-side/2))
            if self.render_origin is not None:
                rebase_projected(self.control,(self.render_origin[0]-origin[0],self.render_origin[1]-origin[1]))
            self.render_origin=origin;self.renderer.screen_origin=origin
            image=self.renderer.normal(self.control,now,pos,(side,side),viewport,
                                      opts['orientation_mode']=='fixed_upper_left',context)
            if any(shots for _,shots,_ in self.renderer.shot_layers):
                from hinu218.pulse_trial190 import draw_shots,draw_escort_shots
                dx,dy=origin[0]-left,origin[1]-top
                rays=Image.new('RGBA',(right-left,bottom-top))
                def shifted(shot):
                    p,v=shot.anchor
                    return replace(shot,anchor=((p[0]+dx,p[1]+dy),v))
                for idx,shots,root in self.renderer.shot_layers:
                    root=(root[0]+dx,root[1]+dy,root[2])
                    if idx:rays=draw_escort_shots(rays,now,[replace(s,shot=shifted(s.shot)) for s in shots],self.kind,root=root)
                    else:rays=draw_shots(rays,now,[shifted(s) for s in shots],.3*scale,self.kind,root=root)
                # The ROI contains depth-tested beams; replace it to avoid double compositing.
                rays.paste(image,(dx,dy));image=rays;origin=(left,top)
        self.was_special=self.volley.active
        box=image.getbbox()
        if box:
            self.frame_origin=(origin[0]+box[0],origin[1]+box[1]);return image.crop(box)
        if self.volley.active:
            self.frame_origin=(round(pos[0]),round(pos[1]));return Image.new('RGBA',(1,1))
        return None


def rebase_projected(control,delta):
    """Shift cached projected tracks, roots and shot origins, preserving world flight."""
    def point(p):return (p[0]+delta[0],p[1]+delta[1])
    for trail in [control.trail,*control.fleet.trails,*control.side_trails]:
        for track in trail.tracks:
            values=[replace(s,xy=point(s.xy)) if s is not None else None for s in track]
            track.clear();track.extend(values)
    def shift(s):return replace(s,anchor=(point(s.anchor[0]),s.anchor[1]))
    control.shots=[shift(s) for s in control.shots]
    control.escort_fire.shots=[[replace(s,shot=shift(s.shot)) for s in shots] for shots in control.escort_fire.shots]
    for roots in control.root_tracks:
        roots.items={key:(age,point(root),z,point(frozen) if frozen is not None else None,fz)
                     for key,(age,root,z,frozen,fz) in roots.items.items()}
