"""Pixel regression and indicative CPU timing (not Windows or full render)."""
import json,time,statistics
from pathlib import Path
from PIL import Image
from effects_trial120 import draw_side_trails as old, SideTrails
from effects_trial122 import draw_side_trails as new
from trail_trial88 import Sample
R=Path(__file__).resolve().parent
cases=0
for mode in ('RGBA','RGB'):
 for size in ((80,80),(320,240),(640,360)):
  im=Image.new(mode,size,'#233345')
  for pts in ([],[Sample(.1,(10,10),.8,1.)],[Sample(.1,(10,10),.8,1.),None,Sample(.12,(30,30),.5,1.)],[Sample(.1,(10,10),.8,1.),Sample(.12,(30,30),.5,1.)]):
   s=SideTrails();s.tracks[0].extend(pts)
   a=old(im,.14,s);b=new(im,.14,s)
   assert a.mode==b.mode=='RGBA' and a.tobytes()==b.tobytes() and b is not im
   cases+=1
bench={}
for size in ((320,240),(1920,1080),(3840,2160)):
 im=Image.new('RGBA',size,(20,30,40,255));s=SideTrails();row={}
 for name,fn in [('before',old),('after',new)]:
  times=[]
  for i in range(6):
   t=time.perf_counter();fn(im,.1,s);times.append((time.perf_counter()-t)*1000)
  row[name+'_median_ms']=round(statistics.median(times),3)
 bench['x'.join(map(str,size))]=row
report={'pixel_identical_cases':cases,'empty_trail_cpu_benchmark':bench,'scope':'Empty side-trail drawing only; Linux CPU Pillow, not whole-frame FPS or Windows.'}
(R/'audit122_effects.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
