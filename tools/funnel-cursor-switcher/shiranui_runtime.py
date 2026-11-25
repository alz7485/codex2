"""Trial160 adapter for the shared preview and Windows desktop overlay."""
from pathlib import Path
import sys, math
from PIL import Image
from cursor_art import anchors,load_sprite
from effect_settings import BUTTONS,MODIFIERS
from idle_motion import MOTION
from trial_runtime import TrialDisplay

class ShiranuiDisplay(TrialDisplay):
    special='dragoon'
    def __init__(self,path,config):
        base=Path(__file__).parent
        for directory in (base/'hinu122',base/'akatsuki160'):
            if str(directory) not in sys.path:sys.path.insert(0,str(directory))
        from shiranui_render import Renderer
        from runtime159 import Runtime
        from fleet153 import Fleet,Settings
        from flight150 import Flight
        from special158 import SpecialPolyhedron
        from shiranui_idle import ConfiguredIdle
        from combat151 import CombatFrame
        class HostFlight(Flight):
            def reset(self):
                super().reset();self.heading=math.pi*3/4
        class HostFleet(Fleet):
            def reset(self):
                super().reset()
                self.main.flight=HostFlight()
                self.idle=ConfiguredIdle(config['idle'])
        class HostSpecial(SpecialPolyhedron):
            def trigger(self,t,center,size,context=None):
                # The cinematic has its own fixed logical stage; normal cursor size stays stable.
                return super().trigger(t,center,74.,context)
        self.runtime=Runtime()
        self.runtime.fleet=HostFleet()
        self.runtime.effect=HostSpecial()
        self.settings_type=Settings
        self.combat_frame=CombatFrame
        self.renderer=Renderer()
        self.config=config
        self.hot=anchors(load_sprite(path),path)[0]
        self.frame_origin=(0,0)
        self.base_size=42.
        self.pressed=False
        self.reset()

    def reset(self):
        self.runtime.reset()
        self.runtime.block=self.pressed
        self.wait_release=getattr(self,"wait_release",False) or self.pressed
        self.context=None
        self.last_time=None
        self.pos=None

    def cancel_fire(self):
        self.reset();self.wait_release=True

    def close(self):self.renderer.close()

    def settings(self):
        f=self.config['followers'];idle=self.config['idle']
        return self.settings_type(f['count'] if f['enabled'] else 0,f['size_percent'],f['fire_enabled'],
                                  idle['enabled'] and idle['motion']==MOTION)

    def step(self,pos,now,events,viewport,scale=1,show_primary=True):
        if pos is None:
            self.reset();return None
        context=(viewport,scale)
        if self.context!=context or (self.last_time is not None and (now<self.last_time or now-self.last_time>.25)):
            self.reset();self.context=context
        opts=self.config[self.special]
        def update(t,position,request=False):
            return self.runtime.update(t,position,self.pressed and not self.wait_release and opts['click_fire_enabled'],
                    special_requested=request,special_center=(320.,192.),size=self.base_size*scale,
                    context=context,settings=self.settings())
        for event in events:
            button='left' if event.kind=='double' else event.kind
            if button=='left':self.pressed=True
            elif button=='left_up':self.pressed=False;self.wait_release=False
            if self.runtime.last is None or event.time>=self.runtime.last[0]:
                request=opts['enabled'] and button==BUTTONS[opts['button']] and event.modifiers==MODIFIERS[opts['modifiers']]
                update(event.time,event.pos,request)
        result=update(now,pos)
        if result.mode=='special':
            states=tuple((identity,self.combat_frame(frame,0.,False,None,0,0.)) for identity,frame in result.special)
            image=self.renderer.draw(states,(640,384),field=result.field)
            factor=min(scale,(viewport[2]-viewport[0])/640,(viewport[3]-viewport[1])/384)
            target=(max(1,round(640*factor)),max(1,round(384*factor)))
            if image.size!=target:image=image.resize(target,Image.Resampling.LANCZOS)
            origin=(viewport[0]+(viewport[2]-viewport[0]-image.width)//2,
                    viewport[1]+(viewport[3]-viewport[1]-image.height)//2)
        elif result.mode=='normal':
            side=max(1,round(640*scale))
            origin=(round(pos[0]-side/2),round(pos[1]-side/2))
            units=(result.normal.main,*result.normal.escorts)
            image=self.renderer.draw(tuple(enumerate(units)),(side,side),origin)
        else:return None
        self.last_time=now;self.pos=pos
        box=image.getbbox()
        if box:
            self.frame_origin=(origin[0]+box[0],origin[1]+box[1]);return image.crop(box)
        if result.mode=='special':
            self.frame_origin=(round(pos[0]),round(pos[1]));return Image.new('RGBA',(1,1))
        return None
