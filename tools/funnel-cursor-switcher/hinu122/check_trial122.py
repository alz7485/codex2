"""Standalone Trial122 audit: only active models and their locked hashes required."""
import hashlib, json, math, itertools
from pathlib import Path
import numpy as np
from integrated_trial121 import FleetCombat
from integrated_trial120 import FleetCombat as Previous
from escort_settings_trial100 import EscortSettings
from idle_trial99 import visual_matrix
from nozzle_trial119 import PORTS, normal_ports
import special_trial119 as special
import special_trial114 as approach
R=Path(__file__).resolve().parent
report={}
for kind in ('HiNu','HiNu_HWS'):
    b=(R/f'{kind}_Trial119.glb').read_bytes();assert hashlib.sha256(b).hexdigest()=={'HiNu':'e06807467b555c76b5454298e94fcd7e48954538230df1c9948f18b46127b573','HiNu_HWS':'a875a6a5c2f87b7bdbe4daa6ab9cd679f1baafe9322cf4291246c8964615b95e'}[kind]
    report[kind+'_sha256']=hashlib.sha256(b).hexdigest()
assert [p.direction for p in PORTS[2:]]==[(-1,0,0),(1,0,0)]
assert [p.origin for p in PORTS[2:]]==[(-1.035,0,3.16),(1.035,0,3.16)]
for x in (-1,0,1):
    assert tuple(p[3] for p in normal_ports(np.eye(4),.4,(x,0,0)))==(.4,.4,max(0,x),max(0,-x))
count=0
for n,pct,on in itertools.product(range(4),range(50,121),(False,True)):
    st=EscortSettings(n,pct,on); assert EscortSettings.from_json(st.to_json())==st
    count+=1
report['settings_roundtrips']=count
f=FleetCombat(3,50);assert [s.max_length for s in f.side_trails]==[48.,24.,24.,24.]
f.set_size_percent(120);assert [s.max_length for s in f.side_trails]==[48.,57.6,57.6,57.6]
f.set_size_percent(100);assert all(s.max_length==48 for s in f.side_trails)
f.update_fleet(0,(100,100),context='a')
project=lambda p:(80+15*p[0],50-15*p[2])
for i in range(1,8):f.visual_jets(1,i/60,(i*10,0),np.eye(4),0,(1,0,0),(0,1,0),project)
assert any(f.side_trails[1].tracks)
f.update_fleet(.14,(100,100),visible=False,context='a');assert not any(f.side_trails[1].tracks) and f.jet_states[1].last is None
report['lateral_scale_and_hidden_reset']=True
pivot=np.array([0.,0.,-.28]);toward=np.array([1.8,10.,2.5]);toward/=np.linalg.norm(toward);right=np.cross([0,1,0],toward);right/=np.linalg.norm(right);up=np.cross(toward,right)
def axis(p,v):return visual_matrix(p,v,right,up,toward,pivot)[:3,:3]@[0.,0.,-1.]
frames=locked=0
for on,pct in itertools.product((False,True),(50,100,120)):
    a=Previous(3,pct,escort_fire_enabled=on);b=FleetCombat(3,pct,escort_fire_enabled=on)
    for k in range(100):
        t=k/40;xy=(500+65*math.sin(t*2.3),400+35*math.sin(t*3.2))
        if k in (8,48):a.down(t);b.down(t)
        if k in (35,58):a.up(t);b.up(t)
        p=a.update(t,xy);q=b.update(t,xy);assert p==q
        ma=a.update_fleet(t,xy,.48,(0,0,1000,800));mb=b.update_fleet(t,xy,.48,(0,0,1000,800));assert ma==mb
        for u in mb:
            assert a.escort_fire_pose(u)==b.escort_fire_pose(u)
            if b.aim_locked:
                assert on and np.linalg.norm(axis(q.flight,b.primary_visual)-axis(b.escort_render_pose(u),b.escort_visual(u)))<1e-9;locked+=1
            if not on:assert b.escort_render_pose(u)==u.pose
        frames+=1
report.update(normal_frames=frames,aligned_member_frames=locked)
# Sample across full timeline and boundaries; sphere approximation, not mesh CCD.
times=sorted(set(np.linspace(0,special.END-1e-6,121).tolist()+[approach.FORMATION+float(d) for d in approach.ARRIVALS]+[approach.FORMATION+approach.MOVE, special.SHOT-.01,special.SHOT,special.END-.06]))
minimum=math.inf;static=0
ref=special.sample(approach.FORMATION+approach.MOVE)
for t in times:
    units=special.sample(t);vis=[u for u in units if u.visible]
    for u in vis:
        assert np.isfinite(u.transform()).all()
    if t>=approach.REENTRY:
        for u,v in itertools.combinations(vis,2):minimum=min(minimum,float(np.linalg.norm(np.array(u.position)-v.position)))
    if approach.FORMATION+approach.MOVE<=t<special.SHOT:
        for u,v in zip(units,ref):
            assert np.array_equal(u.transform(),v.transform()) and not any(j[3] for j in u.thrusters())
        static+=1
assert minimum>2*approach.RADIUS
assert all(not u.visible for u in special.sample(special.END-.06)) and special.sample(special.END)==()
for mode in ('hidden','context','back','gap'):
    c=special.SpecialVolley();assert c.trigger(10,'a');assert not c.trigger(10.01,'a')
    assert c.update(10.02,context='a')
    if mode=='hidden':r=c.update(10.03,context='a',visible=False)
    elif mode=='context':r=c.update(10.03,context='b')
    elif mode=='back':r=c.update(9.9,context='a')
    else:r=c.update(11,context='a')
    assert not r and not c.active
report.update(special_samples=len(times),static_samples=static,minimum_sphere_gap=minimum,minimum_sphere_margin=minimum-2*approach.RADIUS,reset_cases=4,windows_tested=False)
(R/'audit122_smoke.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
