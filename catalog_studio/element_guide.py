"""Synthetic explanatory diagrams for the element chooser; no user geometry is edited."""
import tkinter as tk
from . import element_schema as schema,geometry_scene as geo


class GuideResolver(geo.Resolver):
    def value(self,node,key,default=0,positive=False):
        samples={'LSNO':{'PBDM':.95,'PTDM':.45},
                 'LPYR':{'PBBT':.95,'PCBT':.7,'PBTP':.5,'PCTP':.35},
                 'SSLC':{'PXTS':20,'PYTS':0,'PXBS':-10,'PYBS':0}}
        return samples.get(schema.positive(node['type']),{}).get(key,super().value(node,key,default,positive))


def draw(editor):
    c=editor.guide_canvas;c.delete('all');selection=editor.library.curselection()
    if not selection:return
    kind=editor.library.get(selection[0]).split()[0];base=schema.positive(kind)
    w=max(340,c.winfo_width());h=max(240,c.winfo_height());color='#b75252' if kind in schema.NEGATIVE_BASE else '#306da5'
    def text(x,y,value,**kw):c.create_text(x,y,text=value,font=(editor.host.ui_font,10),fill='#40556d',**kw)
    text(w/2,20,kind+'  '+schema.LABELS.get(kind,schema.LABELS.get(base,'未対応')))
    if kind in schema.PT_TYPES:
        ox,oy=70,h-65;px,py=w-95,85
        c.create_line(ox,oy,w-35,oy,arrow='last',fill='#bdc9d8');text(w-25,oy,'X')
        c.create_line(ox,oy,ox,45,arrow='last',fill='#bdc9d8');text(ox,35,'Y')
        c.create_line(ox,oy,px,py,fill=color,width=2,arrow='last',dash=(5,3) if kind!='PTAXI' else ())
        if kind in ('PTCAR','PTMIX'):
            c.create_line(ox,oy,px,oy,px,py,fill='#93acc7',dash=(4,3));text((ox+px)/2,oy+15,'PX');text(px+18,(oy+py)/2,'PY')
        c.create_oval(px-5,py-5,px+5,py+5,fill=color,outline=color)
        c.create_line(px,py,px+42,py-30,arrow='last',fill=color,width=2)
        text(px,py+24,'点位置');text(px+35,py-43,'PAXI' if kind in ('PTAXI','PTMIX') else 'PTCDIR')
        if kind=='PTAXI':text((ox+px)/2-25,(oy+py)/2-15,'PDIS / PAXI')
        if kind=='PTPOS':text(w/2,h-25,'位置式（PTCPOS）で点を指定')
        return
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
        c.create_polygon(*(v for p in points for v in p),fill='' if mesh.negative else '#d2e2f1',outline=color,width=1.4,dash=(4,2) if mesh.negative else ())
    text(w/2,h-20,'負形状：切り欠き用の体積' if mesh.negative else '形状の説明図（寸法・向きは設定できます）')
