"""Independent visual escort controller, adapted from Trial77 escort_trial65.
Positions and bounds use physical viewport pixels; no input hooks or firing.
Call projected for each member after projecting its actual 3D nozzles.
"""
import math
from collections import deque
from dataclasses import dataclass, replace
from .flight_trial87 import Flight, Pose, clamp, wrap
from .escort_trail_trial98 import Trail
PARAMS=((.68,.08,220,-1.05,6.8,2.9,.34),(.61,.16,265,1.05,5.8,3.7,.40),(.54,.24,300,0.,4.9,4.6,.47))

def limit(x,y,m):
    n=math.hypot(x,y);return (x*m/n,y*m/n) if n>m else (x,y)
def inside(p,b,r):
    if b is None:return tuple(p)
    l,t,hx,hy=b
    return (clamp(p[0],min(l+r,(l+hx)/2),max(hx-r,(l+hx)/2)),clamp(p[1],min(t+r,(t+hy)/2),max(hy-r,(t+hy)/2)))
@dataclass(frozen=True)
class Member:
    id:int; xy:tuple; velocity:tuple; ratio:float; pose:Pose; opacity:float
class EscortFleet:
    def __init__(self,count=3,size_percent=100):
        self.size_percent=self.validate_size(size_percent)
        self.count=None;self.set_count(count)
    @staticmethod
    def validate_size(value):
        if type(value) is not int or not 50<=value<=120:raise ValueError('escort size must be integer 50..120 percent')
        return value
    @property
    def multiplier(self):return self.size_percent/100
    def ratio(self,i):return PARAMS[i][0]*self.multiplier
    def gap(self,i,j,scale):
        # Preserve Trial97 distances at 100%; adjust for changes in approximate body radius.
        delta=110*scale*(self.ratio(i)-PARAMS[i][0])
        if j is None:return 155*scale+delta
        return 140*scale+delta+110*scale*(self.ratio(j)-PARAMS[j][0])
    def set_size_percent(self,value):
        value=self.validate_size(value)
        if value==self.size_percent:return
        self.size_percent=value;self.make_trails();self.reset()
    def make_trails(self):
        self.trails=[Trail(lifetime=p[-1],max_length=76*self.multiplier,size_multiplier=self.multiplier) for p in PARAMS[:self.count]]
    def set_count(self,count):
        if type(count) is not int or not 0<=count<=3:raise ValueError('escort count must be 0..3')
        if count!=self.count:
            self.count=count;self.flights=[Flight() for _ in range(count)];self.make_trails();self.reset()
    def reset(self):
        self.last=None;self.hist=deque(maxlen=128);self.members=[];self.heading=-3*math.pi/4;self.idle=0.;self.speed=0.;self.fade=0.;self.clock=0.;self.result=()
        for f in self.flights:f.reset()
        for tr in self.trails:tr.reset()
    def lag(self,t):
        a=self.hist[0]
        for b in self.hist:
            if b[0]>=t:
                u=clamp((t-a[0])/max(1e-9,b[0]-a[0]),0,1);return tuple(a[j]+u*(b[j]-a[j]) for j in (1,2))
            a=b
        return a[1:]
    def target(self,i,t,xy,scale,bounds):
        ratio,lag,radius,offset,w,period,life=PARAMS[i];ratio=self.ratio(i);q=self.clock*math.tau/period+i*2.1
        hx,hy=self.lag(t-lag);a=self.heading+math.pi+offset;rad=(radius+110*(ratio-PARAMS[i][0]))*scale*(1+.20*clamp(self.speed/(600*scale),0,1));moving=(hx+rad*math.cos(a),hy+rad*math.sin(a));a+=.22*math.sin(q*.63);rad=(radius+110*(ratio-PARAMS[i][0]))*scale*(1+.085*math.sin(q));hover=(xy[0]+rad*math.cos(a),xy[1]+rad*math.sin(a));p=tuple(moving[j]+(hover[j]-moving[j])*self.idle for j in range(2));r=110*scale*ratio
        if bounds and inside(p,bounds,r)!=p:
            candidates=[inside(p,bounds,r)]
            for k in range(1,13):
                for sign in (-1,1):
                    aa=a+sign*k*math.pi/12;c=(xy[0]+rad*math.cos(aa),xy[1]+rad*math.sin(aa))
                    if inside(c,bounds,r)==c:candidates.append(c)
            def score(c):
                near=sum(max(0,(self.gap(i,j,scale)+15*scale)-math.dist(c,s[:2]))**2*4 for j,s in enumerate(self.members) if j!=i)
                return math.dist(c,p)**2+near+max(0,(self.gap(i,None,scale)+15*scale)-math.dist(c,xy))**2*9
            p=min(candidates,key=score)
        return p
    def update(self,t,xy,scale=1.,bounds=None,visible=True,context=None):
        xy=tuple(xy);bounds=tuple(bounds) if bounds is not None else None
        if len(xy)!=2 or not all(math.isfinite(v) for v in (t,*xy,scale)) or not 0<scale<=4:raise ValueError('invalid input')
        if bounds is not None and (len(bounds)!=4 or not all(math.isfinite(v) for v in bounds) or bounds[0]>=bounds[2] or bounds[1]>=bounds[3]):raise ValueError('invalid bounds')
        key=(t,xy,scale,bounds,bool(visible),context);old=self.last
        if old==key:return self.result
        if not visible or not self.count:self.reset();return ()
        if old and (t<=old[0] or t-old[0]>.25 or math.dist(xy,old[1])>500 or key[2:]!=old[2:]):self.reset();old=None
        dt=t-old[0] if old else 0.;self.last=key;self.clock+=dt;self.hist.append((t,*xy))
        while len(self.hist)>2 and t-self.hist[1][0]>.6:self.hist.popleft()
        if old:
            dx,dy=xy[0]-old[1][0],xy[1]-old[1][1];speed=math.hypot(dx,dy)/dt;self.speed+=(speed-self.speed)*(1-math.exp(-dt/.12))
            if speed>12*scale:self.heading=wrap(self.heading+wrap(math.atan2(dy,dx)-self.heading)*(1-math.exp(-dt/.14)))
            self.idle+=(float(self.speed<18*scale)-self.idle)*(1-math.exp(-dt/.65));self.fade=min(1,self.fade+dt/.40)
        else:
            for i in range(self.count):self.members.append([*self.target(i,t,xy,scale,bounds),0.,0.,self.heading])
        steps=max(1,math.ceil(dt*120));targets=[self.target(i,t,xy,scale,bounds) for i in range(self.count)]
        for _ in range(steps):
            h=dt/steps;positions=[tuple(s[:2]) for s in self.members]
            for i,s in enumerate(self.members):
                ratio,lag,radius,offset,w,period,life=PARAMS[i];ratio=self.ratio(i);x,y,vx,vy,hd=s;tx,ty=targets[i];ax=w*w*(tx-x)-1.9*w*vx;ay=w*w*(ty-y)-1.9*w*vy
                for j,o in enumerate([*positions,xy]):
                    if j==i:continue
                    gap=self.gap(i,None if j==self.count else j,scale);dx,dy=x-o[0],y-o[1];dist=math.hypot(dx,dy)
                    if dist<gap:
                        if dist<1e-7:dx,dy=math.cos(i*2.4),math.sin(i*2.4);dist=1
                        strength=3900*scale*(1-dist/gap)**2;ax+=strength*dx/dist;ay+=strength*dy/dist
                ax,ay=limit(ax,ay,2400*scale);vx,vy=limit(vx+ax*h,vy+ay*h,780*scale);nx,ny=inside((x+vx*h,y+vy*h),bounds,110*scale*ratio)
                if nx!=x+vx*h:vx=0.
                if ny!=y+vy*h:vy=0.
                s[:]=[nx,ny,vx,vy,hd]
        # Positional separation as a final guard, not a geometry collision solver.
        # Limited iterations; crowded/tiny bounds may make all distances impossible.
        for _ in range(8):
            for i,s in enumerate(self.members):
                others=[(None,xy,self.gap(i,None,scale))]+[(j,o[:2],self.gap(i,j,scale)) for j,o in enumerate(self.members) if j>i]
                for j,o,gap in others:
                    dx,dy=s[0]-o[0],s[1]-o[1];dist=math.hypot(dx,dy)
                    if dist>=gap:continue
                    if dist<1e-8:dx,dy=math.cos(i*2.4),math.sin(i*2.4);dist=0.;ux,uy=dx,dy
                    else:ux,uy=dx/dist,dy/dist
                    correction=(gap-dist)/(1 if j is None else 2)
                    s[:2]=inside((s[0]+ux*correction,s[1]+uy*correction),bounds,110*scale*self.ratio(i))
                    if j is not None:
                        other=self.members[j];other[:2]=inside((other[0]-ux*correction,other[1]-uy*correction),bounds,110*scale*self.ratio(j))
                    # Remove inward velocity component to avoid repeated pushes.
                    dot=s[2]*ux+s[3]*uy
                    if dot<0:s[2]-=dot*ux;s[3]-=dot*uy
                    if j is not None:
                        dot=other[2]*ux+other[3]*uy
                        if dot>0:other[2]-=dot*ux;other[3]-=dot*uy
        result=[]
        for i,(s,f) in enumerate(zip(self.members,self.flights)):
            ratio,lag,radius,offset,w,period,life=PARAMS[i];ratio=self.ratio(i);x,y,vx,vy,hd=s;st=f.update(t,(x,y),context=context);q=self.clock*math.tau/period+i*2.1
            target=st.heading if math.hypot(vx,vy)>9*scale else hd;hover=self.heading+offset+.65*math.sin(q*.7);target+=wrap(hover-target)*self.idle;hd=wrap(hd+wrap(target-hd)*(1-math.exp(-dt/(.18+i*.055))));s[4]=hd
            power=clamp(st.power*(1-.75*self.idle)+self.idle*(.06+.055*max(0,math.sin(q*2.3))),0,1)
            result.append(Member(i,(x,y),(vx,vy),ratio,replace(st,heading=hd,power=power,bank=st.bank*(1-.7*self.idle)+3*math.sin(q)*self.idle),self.fade))
        self.result=tuple(result);return self.result
    def projected(self,t,member,nozzles):
        if self.last is None or self.last[0]!=t or not 0<=member.id<len(self.result) or self.result[member.id]!=member:return ()
        return self.trails[member.id].update(t,member.xy,member.pose,nozzles,context=self.last[5])
