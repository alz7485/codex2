"""Traveling normal-fire pulse, shared launch attitude and tracked root until detachment.
Special volley code is intentionally not imported or modified.
"""
from dataclasses import replace
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from .integrated_trial189 import FleetCombat as Previous, charge, MUZZLE, FORWARD_POINT
from .combat_trial93 import PALETTES
from .fire_trial89 import FIRE, AFTER, smooth
from .flight_trial87 import wrap
from .integrated_trial100 import EscortShot

BUILD=.055
RECOVER=.24
LIFE=FIRE+AFTER

def span(age,channel,scale):
    length=max(0.,channel)+135*scale
    head=length*max(0.,age)/BUILD
    return max(0.,head-length),head

def release_age(channel,scale):
    return BUILD*(1+max(0.,channel)/(max(0.,channel)+135*scale))

class RootTrack:
    def __init__(self): self.items={}
    def clear(self): self.items.clear()
    def update(self,t,shots,root,depth,scale):
        active={};out=[]
        for shot in shots:
            age=max(0.,t-shot.time);cut=release_age(shot.length,scale)
            key=(shot.id,shot.time);prev=self.items.get(key)
            # Keep launch direction/depth slope; translation follows the root only until clearance.
            z=depth if depth is not None and math.isfinite(depth) else None
            if prev is None: prev=(0.,shot.anchor[0],shot.depth[0] if shot.depth else None,None,None)
            pa,pr,pz,frozen,fz=prev
            if frozen is None and age>=cut:
                q=max(0.,min(1.,(cut-pa)/max(1e-12,age-pa)))
                frozen=tuple(a+(b-a)*q for a,b in zip(pr,root))
                fz=pz+(z-pz)*q if pz is not None and z is not None else z
            active[key]=(age,tuple(root),z,frozen,fz)
            origin=tuple(root) if frozen is None else frozen
            oz=z if frozen is None else fz
            dz=(oz,shot.depth[1]) if oz is not None and shot.depth is not None else shot.depth
            out.append(replace(shot,anchor=(origin,shot.anchor[1]),depth=dz))
        self.items=active
        return tuple(out)

def _orientation(p,target,q):
    h,b,z=target
    return replace(p,heading=wrap(p.heading+q*wrap(h-p.heading)),bank=p.bank+q*(b-p.bank),pitch=p.pitch+q*(z-p.pitch))

class FleetCombat(Previous):
    def __init__(self,*args,**kwargs):
        self.root_tracks=[RootTrack() for _ in range(4)]
        self._clear_lock();super().__init__(*args,**kwargs)
    def _clear_lock(self):
        self.lock=None;self.lock_roll=0.;self.unlock=None;self.lock_t=None
    def reset(self):
        super().reset();self._clear_lock()
        for track in self.root_tracks:track.clear()
    def _clear_escort_tracks(self):
        for track in self.root_tracks[1:]:track.clear()
    def set_count(self,count):
        old=self.fleet.count;super().set_count(count)
        if old!=count:self._clear_escort_tracks()
    def set_size_percent(self,value):
        old=self.fleet.size_percent;super().set_size_percent(value)
        if old!=value:self._clear_escort_tracks()
    def set_escort_fire_enabled(self,value):
        old=self.escort_fire_enabled;super().set_escort_fire_enabled(value)
        if old!=value:self._clear_escort_tracks()
    def update(self,t,xy,enabled=True,context=None,fixed=False):
        p=super().update(t,xy,enabled,context,fixed)
        if not enabled:return p
        self.lock_t=t
        fired=self.fire.fired
        primary_busy=fired is not None and 0<=t-fired[1]<LIFE
        escort_busy=self.escort_fire_enabled and (any(self.escort_fire.pending[:self.fleet.count]) or any(e is not None and 0<=t-e[1]<LIFE for e in self.escort_fire.latest[:self.fleet.count]))
        busy=primary_busy or escort_busy
        if busy:
            if self.lock is None:
                self.lock=(p.flight.heading,p.flight.bank,p.flight.pitch);self.lock_roll=self.primary_visual.roll
            self.unlock=None
        elif self.lock is not None:
            if self.unlock is None:self.unlock=t
            elif t-self.unlock>=RECOVER:self._clear_lock();return p
        q=self._mix()
        if self.lock is not None:
            self.primary_visual=replace(self.primary_visual,roll=self.primary_visual.roll+q*wrap(self.lock_roll-self.primary_visual.roll),tilt=self.primary_visual.tilt*(1-q))
            p=replace(p,flight=_orientation(p.flight,self.lock,q))
        return p
    def _mix(self):
        if self.lock is None:return 0.
        return 1. if self.unlock is None else 1.-smooth((self.lock_t-self.unlock)/RECOVER)
    def escort_render_pose(self,member):
        if self.lock is not None and self.escort_fire_enabled:
            return _orientation(member.pose,self.lock,self._mix())
        return super().escort_render_pose(member)
    def escort_visual(self,member):
        if self.lock is not None and self.escort_fire_enabled:
            v=self.idle_motion.escort(member.id)
            return replace(v,tilt=v.tilt*(1-self._mix()))
        return super().escort_visual(member)
    def update_fleet(self,t,xy,scale=1.,bounds=None,visible=True,context=None):
        old=self.fleet.last;members=super().update_fleet(t,xy,scale,bounds,visible,context);new=self.fleet.last
        if not visible or (old and new and old[2:]!=new[2:]):self._clear_escort_tracks()
        return members
    def projected(self,t,xy,p,nozzles,muzzle,direction,enabled=True,context=None,fixed=False,*,depth_origin=None,depth_per_pixel=None,channel_pixels=None,scale=1.):
        shots=super().projected(t,xy,p,nozzles,muzzle,direction,enabled,context,fixed,depth_origin=depth_origin,depth_per_pixel=depth_per_pixel,channel_pixels=channel_pixels)
        if not enabled or self.last!=(t,tuple(xy),(context,bool(fixed))):return ()
        return self.root_tracks[0].update(t,shots,muzzle,depth_origin,scale)
    def escort_projected(self,t,member,nozzles,muzzle,direction,*,scale=1.,depth_origin=None,depth_per_pixel=None,channel_pixels=0.):
        shots=super().escort_projected(t,member,nozzles,muzzle,direction,scale=scale,depth_origin=depth_origin,depth_per_pixel=depth_per_pixel,channel_pixels=channel_pixels)
        if not shots:
            if 0<=member.id<3:self.root_tracks[member.id+1].clear()
            return ()
        updated=self.root_tracks[member.id+1].update(t,[s.shot for s in shots],muzzle,depth_origin,shots[0].scale)
        return tuple(EscortShot(s,v.scale) for s,v in zip(updated,shots))

def pulse(im,t,shot,scale,kind,depth=None):
    age=t-shot.time
    if not 0<=age<LIFE:return im
    a,b=span(age,shot.length,scale);length=b-a
    if length<=0:return im
    o,v=shot.anchor;outer,inner,white=PALETTES[kind]
    fade=1-smooth((age-.22)/.18)
    def pt(x,y=0.):return (o[0]+v[0]*x-v[1]*y,o[1]+v[1]*x+v[0]*y)
    # Finite pulse with tapered head/tail. No stationary full-length segment.
    ends=[pt(a),pt(b)];pad=math.ceil(22*scale+4);w,h=im.size
    x0=max(0,math.floor(min(p[0] for p in ends)-pad));y0=max(0,math.floor(min(p[1] for p in ends)-pad))
    x1=min(w,math.ceil(max(p[0] for p in ends)+pad));y1=min(h,math.ceil(max(p[1] for p in ends)+pad))
    if x1<=x0 or y1<=y0:return im
    layer=Image.new('RGBA',(x1-x0,y1-y0));d=ImageDraw.Draw(layer)
    def p(x,y=0):u,z=pt(x,y);return u-x0,z-y0
    for width,color,alpha in ((11,outer,135),(6.5,inner,220),(2.5,white,255)):
        r=width*scale*max(.3,fade)
        d.polygon([p(a),p(a+.10*length,-r*.65),p(a+.52*length,-r),p(b-.12*length,-r*.55),p(b),p(b-.12*length,r*.55),p(a+.52*length,r),p(a+.10*length,r*.65)],fill=(*color,round(alpha*fade)))
    glow=layer.filter(ImageFilter.GaussianBlur(max(.5,3*scale)));glow.alpha_composite(layer)
    if depth is not None and shot.depth is not None:
        dep=np.asarray(depth)
        if dep.shape!=(h,w):raise ValueError('depth size mismatch')
        arr=np.array(glow);yy,xx=np.ogrid[y0:y1,x0:x1];z,dz=shot.depth
        dist=(xx-o[0])*v[0]+(yy-o[1])*v[1]
        arr[:,:,3]=np.where(z+np.maximum(0,dist)*dz<=dep[y0:y1,x0:x1]+.0008,arr[:,:,3],0);glow=Image.fromarray(arr)
    out=im.convert('RGBA');out.alpha_composite(glow,(x0,y0));return out

def root_flash(im,t,shot,scale,kind,root,depth):
    age=t-shot.time
    if root is None or not 0<=age<.095:return im
    x,y=root[:2];w,h=im.size
    if not all(math.isfinite(v) for v in root):return im
    if depth is not None and len(root)>2 and 0<=round(x)<w and 0<=round(y)<h and root[2]>depth[round(y),round(x)]+.002:return im
    outer,inner,white=PALETTES[kind];q=(1-age/.095)**2
    r=math.ceil(15*scale+4);x0=max(0,math.floor(x-r));y0=max(0,math.floor(y-r));x1=min(w,math.ceil(x+r));y1=min(h,math.ceil(y+r))
    if x1<=x0 or y1<=y0:return im
    layer=Image.new('RGBA',(x1-x0,y1-y0));d=ImageDraw.Draw(layer);x-=x0;y-=y0
    for rad,col,alpha in ((9,outer,150),(5,inner,220),(2,white,255)):
        rr=rad*scale*math.sqrt(q);d.ellipse((x-rr,y-rr,x+rr,y+rr),fill=(*col,round(alpha*q)))
    glow=layer.filter(ImageFilter.GaussianBlur(max(.5,2*scale)));glow.alpha_composite(layer)
    out=im.convert('RGBA');out.alpha_composite(glow,(x0,y0));return out

def draw_shots(im,t,shots,scale=1.,kind='HiNu',*,depth=None,root=None):
    for s in shots:
        im=pulse(im,t,s,scale,kind,depth);im=root_flash(im,t,s,scale,kind,root,depth)
    return im

def draw_escort_shots(im,t,shots,kind='HiNu',*,depth=None,root=None):
    for s in shots:
        im=pulse(im,t,s.shot,s.scale,kind,depth);im=root_flash(im,t,s.shot,s.scale,kind,root,depth)
    return im
