"""Synthetic explanatory diagrams for the element chooser; no user geometry is edited."""
import tkinter as tk
import math
from . import element_schema as schema,geometry_scene as geo


class GuideResolver(geo.Resolver):
    def value(self,node,key,default=0,positive=False):
        samples={'LSNO':{'PBDM':.95,'PTDM':.45},
                 'LPYR':{'PBBT':.95,'PCBT':.7,'PBTP':.5,'PCTP':.35},
                 'SSLC':{'PXTS':20,'PYTS':0,'PXBS':-10,'PYBS':0}}
        return samples.get(schema.positive(node['type']),{}).get(key,super().value(node,key,default,positive))


def draw_points(c,kind,w,h,text,color):
    point=(.8,.55,.5);origin=geo.ZERO
    direction=geo.unit(point) if kind=='PTAXI' else geo.unit((.8,-.25,.6))
    tip=geo.add(point,geo.mul(direction,.28))
    anchors=[origin,point,tip,(1.3,0,0),(0,1.1,0),(0,0,1.1)]
    for index,title in enumerate(('立体図','平面図（XY）')):
        x0=12+index*(w/2);pw=w/2-24;ph=h-100
        c.create_rectangle(x0,48,x0+pw,h-40,outline='#d7e1ed',fill='#f8faff')
        text(x0+pw/2,65,title)
        camera=geo.FitCamera()
        if index:camera.face('XY')
        camera.fit(anchors,pw,ph,padding=42)
        def xy(p):
            x,y=camera.project(p,pw,ph);return x+x0,y+70
        for vector,label in (((1.3,0,0),'X'),((0,1.1,0),'Y'),((0,0,1.1),'Z')):
            if index and label=='Z':continue
            a,b=xy(origin),xy(vector)
            c.create_line(*a,*b,fill='#b3c3d5',arrow='last');text(b[0]+8,b[1],label)
        c.create_line(*xy(origin),*xy(point),fill=color,dash=(4,3),width=2)
        if kind in ('PTCAR','PTMIX'):
            chain=[origin,(point[0],0,0),(point[0],point[1],0),point]
            for a,b,label in zip(chain,chain[1:],('PX','PY','PZ')):
                if index and label=='PZ':continue
                pa,pb=xy(a),xy(b);c.create_line(*pa,*pb,fill='#93acc7',dash=(3,3))
                text((pa[0]+pb[0])/2,(pa[1]+pb[1])/2+12,label)
        px,py=xy(point);tx,ty=xy(tip)
        c.create_oval(px-4,py-4,px+4,py+4,fill=color,outline=color)
        c.create_line(px,py,tx,ty,fill=color,width=2,arrow='last')
        text(px-8,py+20,'P1',anchor='e')
        text(tx,ty-14,'PAXI' if kind in ('PTAXI','PTMIX') else 'PTCDIR')
        if kind=='PTAXI':
            ox,oy=xy(origin);text((ox+px)/2-12,(oy+py)/2-12,'PDIS')
        text(*xy(origin),'P0',anchor='ne')
    text(w/2,h-18,'同じP1を2視点で表示（平面図ではZ方向を投影）')


def annotate_mesh(c,base,camera,w,h,text,color):
    def point(position,label):
        x,y=camera.project(position,w,h)
        c.create_oval(x-4,y-4,x+4,y+4,fill='#fff',outline=color,width=2)
        text(x+9,y-13,label,anchor='w')
    def axis(origin,tip,label):
        a=camera.project(origin,w,h);b=camera.project(tip,w,h)
        c.create_line(*a,*b,fill=color,width=2,arrow='last');text(b[0]+7,b[1]-10,label,anchor='w')
    if base in ('SCYL','SSLC','LCYL','LSNO','LPYR','SCON','BOXI','TUBE'):
        low=-.6 if base=='LCYL' else 0.;high=.6 if base=='LCYL' else 1.2
        point((low,0,0),'P1（下端）' if base!='SCON' else 'P1（頂点）')
        point((high,0,0),'P2（上端）')
        axis((low,0,0),(high+.18,0,0),'PAAX' if base in ('LSNO','LPYR') else 'PAXI')
        if base in ('LSNO','LPYR'):axis((high,0,0),(high,.55,0),'PBAX')
    elif base in ('SSPH','SDIS'):
        point((0,0,0),'P1（中心）');axis((0,0,0),(.65,0,0),'PAXI')
    elif base in ('SCTO','SRTO'):
        point((1,0,0),'P1');point((0,1,0),'P2')
        axis((1,0,0),(1,-.3,0),'PAAX');axis((0,1,0),(-.3,1,0),'PBAX')
    else:
        point((0,0,0),'P0（原点）')
    # Point references are one possible setup, not required numbered points.
    text(w/2,h-40,'P1・P2は参照点の例（点番号は任意）')


def draw(editor):
    c=editor.guide_canvas;c.delete('all');selection=editor.library.curselection()
    if not selection:return
    kind=editor.library.get(selection[0]).split()[0];base=schema.positive(kind)
    w=max(340,c.winfo_width());h=max(240,c.winfo_height());color='#b75252' if kind in schema.NEGATIVE_BASE else '#306da5'
    def text(x,y,value,**kw):c.create_text(x,y,text=value,font=(editor.host.ui_font,10),fill='#40556d',**kw)
    text(w/2,20,kind+'  '+schema.LABELS.get(kind,schema.LABELS.get(base,'未対応')))
    if kind in schema.PT_TYPES:
        draw_points(c,kind,w,h,text,color);return
    if base in ('LINE','SLINE'):
        pts=[(60,h-70),(w/2,90),(w-55,h-100)] if base=='LINE' else [(65,h-65),(w-65,85)]
        c.create_line(*(v for p in pts for v in p),fill=color,width=3)
        for i,(x,y) in enumerate(pts):c.create_oval(x-4,y-4,x+4,y+4,fill=color);text(x,y+20,'P'+str(i+1) if base=='LINE' else ('開始点' if i==0 else '終了点'))
        return
    if base is None:
        text(w/2,h/2,'形状定義が未確認のため図を表示できません');return
    node={'id':'guide','type':kind,'name':kind,'attrs':schema.default_attrs(kind)}
    resolver=GuideResolver({'parameters':[]}, {},None,None,False,geo.Scene())
    try:mesh=geo.build_mesh(node,resolver)
    except (ValueError,TypeError,KeyError):
        text(w/2,h/2,'この種類の説明図は準備中です');return
    camera=geo.FitCamera();camera.fit(mesh.vertices,w,h,padding=60)
    faces=sorted(mesh.faces,key=lambda face:sum(camera.depth(mesh.vertices[i]) for i in face)/len(face))
    for face in faces:
        points=[camera.project(mesh.vertices[i],w,h) for i in face]
        if not mesh.negative:
            vertices=[mesh.vertices[i] for i in face]
            normal=geo.cross(geo.sub(vertices[1],vertices[0]),geo.sub(vertices[2],vertices[0]))
            length=math.hypot(*normal)
            light=abs(geo.dot(geo.mul(normal,1/length),(.3,-.4,.86))) if length else .5
            shade=min(1,.72+.25*light)
            fill='#'+''.join(f'{int(v*shade):02x}' for v in (210,226,241))
            c.create_polygon(*(v for p in points for v in p),fill=fill,outline='',tags='guide-surface')
    from .surface_render import feature_edges
    for a,b in feature_edges(mesh,geo.cross(*camera.basis()),visible_only=not mesh.negative):
        c.create_line(*camera.project(mesh.vertices[a],w,h),*camera.project(mesh.vertices[b],w,h),fill=color,width=1.4,dash=(4,2) if mesh.negative else (),tags='guide-contour')
    annotate_mesh(c,base,camera,w,h,text,color)
    text(w/2,h-20,'負形状：切り欠き用の体積' if mesh.negative else '形状の説明図（寸法・向きは設定できます）')
