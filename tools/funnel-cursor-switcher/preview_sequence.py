"""Finite, preview-only demonstrations with an isolated configuration and clock."""
from copy import deepcopy
import math
from effect_engine import ClickEvent
from effect_settings import BUTTONS,MODIFIERS,SPECIAL

ACTIONS=(('move','移動','flight'),('fire','射撃','fire'),('charge','溜め射撃','charge'),
         ('idle','待機回転','rotate'),('followers','随伴','followers'),('special','特殊','shield'))

class Sequence:
    def __init__(self,kind,config,special):
        self.kind=kind;self.special=special;self.time=0.;self.previous=-1.;self.seen_special=False
        self.config=deepcopy(config)
        c=self.config
        for group in c:c[group]['enabled']=False
        if kind in ('move','followers'):
            c['boost']['enabled']=True;c['trail']['enabled']=True
        if kind=='idle':
            c['idle'].update(enabled=True,motion='横回転',delay=.15)
        if kind=='followers':
            c['followers'].update(enabled=True,count=max(1,c['followers']['count']))
        if special:
            c[special]['click_fire_enabled']=kind in ('fire','charge')
            c[special]['enabled']=kind=='special'
        self.duration={'move':2.3,'fire':2.5,'charge':3.,'followers':2.7,
                       'idle':.15+c['idle']['turn_period']+.45,'special':30.}[kind]

    def sample(self,center,extent):
        t=self.time;pos=center;events=[]
        if self.kind in ('move','followers'):
            u=max(0.,min(1.,(t-.15)/1.7))
            x,y=center;w,h=extent
            pos=(x+min(65,w*.20)*math.sin(2*math.pi*u),y+min(30,h*.20)*math.sin(4*math.pi*u))
        times=[]
        if self.kind in ('fire','charge'):
            times=[(.15,'left',0),(.20 if self.kind=='fire' else 1.15,'left_up',0)]
        elif self.kind=='special' and self.special:
            opts=self.config[self.special]
            times=[(.15,BUTTONS[opts['button']],MODIFIERS[opts['modifiers']]),(.20,'left_up',0)]
        for when,kind,mods in times:
            if self.previous<when<=t:events.append(ClickEvent(kind,pos,when,mods))
        self.previous=t
        return pos,events

    def advance(self,dt):self.time+=min(.05,max(0.,dt))

    def finished(self,engine):
        if self.kind!='special':return self.time>=self.duration
        active=False
        if hasattr(engine,'runtime'):active=engine.runtime.effect.active
        elif hasattr(engine,'volley'):active=engine.volley.active
        elif hasattr(engine,'fx'):active=engine.fx.barrier.active_at(self.time)
        elif hasattr(engine,'control'):active=getattr(engine.control,'special',None) is not None
        self.seen_special |= active
        return (self.seen_special and not active) or self.time>=self.duration
