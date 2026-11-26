"""Trial204: pixel-preserving local FX compositing; original controllers unchanged."""
from .effects_trial189 import *
from .thrust_trial86 import clamp
from .fx_local204 import blur_over, over

def base_exhaust(background,t,power,nozzles,*,owned=False):
    """Each nozzle: (anchor_xy, rear_vector_xy per model unit, halfwidth_px).
    Draw on unobstructed rear views; other views need host depth clipping."""
    if not math.isfinite(t) or not math.isfinite(power): raise ValueError('invalid time/power')
    if owned and background.mode!='RGBA':raise ValueError('owned target must be RGBA')
    out=background if owned else background.convert('RGBA'); p=clamp(power)
    if p==0: return out
    for i,(anchor,rear,w0) in enumerate(nozzles):
        x,y=anchor; vx,vy=rear; scale=math.hypot(vx,vy)
        if not all(math.isfinite(v) for v in (x,y,vx,vy,w0)) or w0<0: raise ValueError('invalid projection')
        if scale<1e-6: continue
        dx,dy=vx/scale,vy/scale; nx,ny=-dy,dx
        pulse=.95+.05*math.sin(t*math.tau*17+i*1.4)
        length=scale*(.12+2.45*p**.82)*pulse; w=max(.65,w0)*(.76+.24*p)
        def q(a,b): return (x+dx*a+nx*b,y+dy*a+ny*b)
        def shape(layer,extent,width,color,alpha):
            d=ImageDraw.Draw(layer); prof=[(0,.73),(.12,1),(.36,.83),(.65,.48),(.86,.20),(1,0)]
            pts=[q(length*extent*u,w*width*v) for u,v in prof]+[q(length*extent*u,-w*width*v) for u,v in reversed(prof)]
            d.polygon(pts,fill=(*color,round(alpha*p)))
        # Local crop limits work to the effect footprint.
        radius=max(length*1.1, w*5)+8; l=max(0,math.floor(x-radius)); r=min(out.width,math.ceil(x+radius)); top=max(0,math.floor(y-radius)); bot=min(out.height,math.ceil(y+radius))
        if r<=l or bot<=top:continue
        x-=l;y-=top; local=out.crop((l,top,r,bot))
        for extent,width,color,alpha,blur in [(1.05,1.8,(28,108,255),110,.95),(1,1.35,(39,116,255),135,.48),(.84,.90,(35,180,255),190,.26),(.60,.54,(130,231,255),235,.15),(.32,.27,(244,255,255),255,.07)]:
            layer=Image.new('RGBA',local.size);shape(layer,extent,width,color,alpha);blur_over(local,layer,max(.25,w*blur))
        base=Image.new('RGBA',local.size);d=ImageDraw.Draw(base);d.line([q(0,-w*.65),q(0,w*.65)],fill=(216,251,255,round(245*p)),width=max(1,round(w*.28)));blur_over(local,base,max(.25,w*.15))
        out.paste(local,(l,top))
    return out

def core_exhaust(background,t,power,nozzles,*,owned=False):
    out=base_exhaust(background,t,power,nozzles,owned=owned);p=clamp(power)
    if p<=0:return out
    layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
    for idx,(a,v,w) in enumerate(nozzles):
        n=math.hypot(*v)
        if n<1e-6:continue
        dx,dy=v[0]/n,v[1]/n;nx,ny=-dy,dx
        length=n*(.12+2.45*p**.82);w=max(.65,w)
        for k in range(5):
            u=(k-2)/2.;osc=.5+.5*math.sin(t*91+k*2.13+idx)
            start=length*(.025+.08*osc);end=length*(.32+.43*osc);off=u*w*.54
            pen.line([(a[0]+dx*start+nx*off,a[1]+dy*start+ny*off),(a[0]+dx*end+nx*off*.19,a[1]+dy*end+ny*off*.19)],fill=(188,235,255,round(p*(48+85*osc))),width=max(1,round(w*.13)))
    blur_over(out,layer,.28);return out

def draw_exhaust(background,t,power,nozzles,*,owned=False):
    nozzles=[(a,tuple(EXHAUST_LENGTH*x for x in v),w) for a,v,w in nozzles]
    out=core_exhaust(background,t,power,nozzles,owned=owned);p=clamp(power)
    if p<=0:return out
    for a,v,w in nozzles:
        n=math.hypot(*v)
        if n<1e-6:continue
        dx,dy=v[0]/n,v[1]/n;length=n*(.12+2.45*p**.82)*.33
        pad=max(3,math.ceil(w*2+3));b=(a[0]+dx*length,a[1]+dy*length)
        l=max(0,math.floor(min(a[0],b[0])-pad));r=min(out.width,math.ceil(max(a[0],b[0])+pad));top=max(0,math.floor(min(a[1],b[1])-pad));bot=min(out.height,math.ceil(max(a[1],b[1])+pad))
        if l>=r or top>=bot:continue
        layer=Image.new('RGBA',(r-l,bot-top));d=ImageDraw.Draw(layer)
        d.line([(a[0]-l,a[1]-top),(b[0]-l,b[1]-top)],fill=(226,250,255,round(118*p)),width=max(1,round(w*.30)))
        out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(.35)),(l,top))
    return out

def draw_side_trails(background,t,controller):
    out=background.convert('RGBA')
    if not any(a is not None and b is not None for tr in controller.tracks for a,b in zip(tr,list(tr)[1:])):return out
    for width,color,alpha,blur in ((4,(40,110,255),72,1.4),(1.2,(177,231,255),180,.35)):
        layer=Image.new('RGBA',out.size);pen=ImageDraw.Draw(layer)
        for track in controller.tracks:
            for a,b in zip(track,list(track)[1:]):
                if a is None or b is None:continue
                fade=clamp(1-(t-(a.t+b.t)/2)/controller.lifetime)**1.7
                pen.line([a.xy,b.xy],fill=(*color,round(alpha*min(a.power,b.power)*fade)),width=max(1,round(width*(a.width+b.width)/2)))
        blur_over(out,layer,blur)
    return out

def draw_trails(background,t,controller):
    out=background.convert('RGBA')
    for track in controller.tracks:
        if len(track)<2:continue
        points=list(track);pad=14
        l=max(0,math.floor(min(s.xy[0] for s in points)-pad));r=min(out.width,math.ceil(max(s.xy[0] for s in points)+pad))
        top=max(0,math.floor(min(s.xy[1] for s in points)-pad));bot=min(out.height,math.ceil(max(s.xy[1] for s in points)+pad))
        if l>=r or top>=bot:continue
        local=out.crop((l,top,r,bot));size=local.size
        for scale,color,alpha,blur in ((3.8,(25,90,255),115,2.8),(2.0,(35,156,255),155,1.1),(.8,(158,235,255),210,.35)):
            layer=Image.new('RGBA',size);d=ImageDraw.Draw(layer)
            for a,b in zip(points,points[1:]):
                fade=max(0.,min(1.,1-(t-(a.t+b.t)/2)/controller.lifetime))**1.7
                strength=fade*(a.power+b.power)/2
                width=max(1,round(scale*(a.width+b.width)/2*(.3+.7*fade)))
                d.line([(s.xy[0]-l,s.xy[1]-top) for s in (a,b)],fill=(*color,round(alpha*strength)),width=width)
            blur_over(local,layer,blur)
        out.paste(local,(l,top))
    return out

def draw_escort_trails(background,t,controller):
    out=background.convert('RGBA')
    for track in controller.tracks:
        if len(track)<2:continue
        points=list(track);pad=math.ceil(14*controller.size_multiplier)
        l=max(0,math.floor(min(s.xy[0] for s in points)-pad));r=min(out.width,math.ceil(max(s.xy[0] for s in points)+pad))
        top=max(0,math.floor(min(s.xy[1] for s in points)-pad));bot=min(out.height,math.ceil(max(s.xy[1] for s in points)+pad))
        if l>=r or top>=bot:continue
        local=out.crop((l,top,r,bot));size=local.size
        for scale,color,alpha,blur in ((3.8,(25,90,255),115,2.8),(2.0,(35,156,255),155,1.1),(.8,(158,235,255),210,.35)):
            layer=Image.new('RGBA',size);d=ImageDraw.Draw(layer)
            for a,b in zip(points,points[1:]):
                fade=max(0.,min(1.,1-(t-(a.t+b.t)/2)/controller.lifetime))**1.7
                strength=fade*(a.power+b.power)/2
                width=max(1,round(scale*(a.width+b.width)/2*(.3+.7*fade)))
                d.line([(s.xy[0]-l,s.xy[1]-top) for s in (a,b)],fill=(*color,round(alpha*strength)),width=width)
            blur_over(local,layer,blur*controller.size_multiplier)
        out.paste(local,(l,top))
    return out
