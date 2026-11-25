"""Strike Freedom Trial146 bridge, shared by preview and desktop overlay."""
from pathlib import Path
import sys
import math
from PIL import Image
from cursor_art import anchors,load_sprite
from effect_settings import BUTTONS,MODIFIERS
from idle_motion import MOTION
from trial_runtime import TrialDisplay

class DragoonDisplay(TrialDisplay):
    special='dragoon'

    def __init__(self,path,config):
        base=Path(__file__).parent
        for directory in (base/'hinu122',base/'dragoon146'):
            if str(directory) not in sys.path:sys.path.insert(0,str(directory))
        from dragoon_render import Renderer
        from fleet_trial139 import Fleet,Settings
        from special_trial144 import SpecialVolley
        from host_idle import ConfiguredIdle
        from flight_trial135 import Flight
        class HostFlight(Flight):
            def reset(self):
                super().reset()
                self.heading=math.pi*3/4
        self.home_flight=HostFlight
        self.idle_type=ConfiguredIdle
        self.settings_type=Settings
        self.control=Fleet()
        self.renderer=Renderer()
        self.volley=SpecialVolley()
        self.config=config
        self.hot=anchors(load_sprite(path),path)[0]
        self.frame_origin=(0,0)
        self.pos=None
        self.pressed=False
        self.wait_release=False
        self.context=None
        self.base_size=42.
        self.reset()

    def reset(self):
        self.control.reset()
        self.control.main.flight=self.home_flight()
        self.control.idle=self.idle_type(self.config['idle'])
        self.volley.reset()
        self.wait_release=self.pressed
        self.pos=None
        self.last_time=None

    def cancel_fire(self):
        self.reset()
        self.wait_release=True

    def close(self):
        self.renderer.close()

    def settings(self):
        f=self.config['followers'];idle=self.config['idle']
        return self.settings_type(f['count'] if f['enabled'] else 0,f['size_percent'],f['fire_enabled'],
                                  idle['enabled'] and idle['motion']==MOTION)

    def step(self,pos,now,events,viewport,scale=1,show_primary=True):
        if pos is None:
            self.reset()
            return None
        context=(viewport,scale)
        if context!=self.context or (self.last_time is not None and (now<self.last_time or now-self.last_time>.25)):
            self.reset()
            self.context=context
        opts=self.config[self.special]
        size=self.base_size*scale
        settings=self.settings()
        was_special=self.volley.active
        for e in events:
            button='left' if e.kind=='double' else e.kind
            if button=='left':self.pressed=True
            elif button=='left_up':
                self.pressed=False
                self.wait_release=False
            if opts['enabled'] and button==BUTTONS[opts['button']] and e.modifiers==MODIFIERS[opts['modifiers']]:
                if self.volley.trigger(e.time,(320,192),74,context):
                    self.control.reset()
            elif not self.volley.active and (self.last_time is None or e.time>=self.last_time):
                self.control.update(e.time,e.pos,self.pressed and not self.wait_release and opts['click_fire_enabled'],
                                    size,context=context,settings=settings)
        indexed=self.volley.update(now,context=context)
        if self.volley.active:
            image=self.renderer.draw(indexed,(640,384),special=True)
            factor=min(scale,(viewport[2]-viewport[0])/640,(viewport[3]-viewport[1])/384)
            target=(max(1,round(640*factor)),max(1,round(384*factor)))
            if image.size!=target:image=image.resize(target,Image.Resampling.LANCZOS)
            origin=(viewport[0]+(viewport[2]-viewport[0]-image.width)//2,
                    viewport[1]+(viewport[3]-viewport[1]-image.height)//2)
        else:
            if was_special:
                self.reset()
                self.context=context
            result=self.control.update(now,pos,self.pressed and not self.wait_release and opts['click_fire_enabled'],
                                       size,context=context,settings=settings)
            side=max(1,round(640*scale))
            origin=(round(pos[0]-side/2),round(pos[1]-side/2))
            units=(result.main,*result.escorts)
            image=self.renderer.draw(tuple(enumerate(units)),(side,side),origin)
        self.pos=pos
        self.last_time=now
        box=image.getbbox()
        if box:
            self.frame_origin=(origin[0]+box[0],origin[1]+box[1])
            return image.crop(box)
        if self.volley.active:
            self.frame_origin=(round(pos[0]),round(pos[1]))
            return Image.new("RGBA",(1,1))
        return None
