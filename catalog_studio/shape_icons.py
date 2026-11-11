"""Small synthetic shape silhouettes using the chooser's actual sample meshes."""
from functools import lru_cache
from . import element_schema as schema, geometry_scene as geo
from .element_guide import GuideResolver
from .surface_render import feature_edges


@lru_cache(maxsize=48)
def geometry(kind):
    node=dict(id='icon',name=kind,type=kind,attrs=schema.default_attrs(kind))
    if kind=='SDSH':node['attrs'].update(PHEI='.22',PDIA='1.0')
    if kind=='SREV':node['attrs']['PANGLE']='360'
    if kind=='SEXT':
        coords=[(0,0),(.9,0),(.9,.3),(.35,.3),(.35,.8),(0,.8)]
        node['children']=[dict(type='SLOO',children=[dict(type='SVER',attrs={'PX':str(x),'PY':str(y)}) for x,y in coords])]
    if kind=='SREV':
        coords=[(-.6,.25),(.5,.25),(.5,.65),(.1,.65),(-.6,.45)]
        node['children']=[dict(type='SLOO',children=[dict(type='SVER',attrs={'PX':str(x),'PY':str(y)}) for x,y in coords])]
    resolver=GuideResolver({'parameters':[]},{},None,None,False,geo.Scene())
    mesh=geo.build_mesh(node,resolver)
    camera=geo.FitCamera();camera.yaw=-35;camera.pitch=28
    if kind in ('SCTO','SRTO'):camera.yaw=15;camera.pitch=65
    camera.fit(mesh.vertices,28,22,padding=2)
    projected=[camera.project(p,28,22) for p in mesh.vertices]
    faces=[]
    for face in sorted(mesh.faces,key=lambda f:sum(camera.depth(mesh.vertices[i]) for i in f)/len(f)):
        vertices=[mesh.vertices[i] for i in face]
        normal=geo.cross(geo.sub(vertices[1],vertices[0]),geo.sub(vertices[2],vertices[0]))
        length=geo.dot(normal,normal)**.5
        light=abs(geo.dot(geo.mul(normal,1/length),(.3,-.4,.86))) if length else .5
        shade=int(184+48*light)
        faces.append(([projected[i] for i in face],f'#{shade-22:02x}{shade-8:02x}{min(255,shade+12):02x}'))
    edges=[(projected[a],projected[b]) for a,b in feature_edges(mesh,geo.cross(*camera.basis()),visible_only=True)]
    return faces,edges


def draw(c,kind,x,y,color,background):
    base=schema.positive(kind);negative=kind in schema.NEGATIVE_BASE
    def line(*p,**kw):return c.create_line(*(v for a,b in zip(p[::2],p[1::2]) for v in (x+a,y+b)),fill=color,**kw)
    def oval(a,b,d,e,**kw):return c.create_oval(x+a,y+b,x+d,y+e,outline=color,**kw)
    def polygon(coords,fill):c.create_polygon(*(v for a,b in coords for v in (x+a,y+b)),outline=color,fill=fill,width=.9)
    if kind in schema.PT_TYPES:
        if kind in ('PTCAR','PTMIX'):
            line(3,18,13,18,13,7,23,7,dash=(2,1))
        else:line(3,18,18,8,dash=(2,1))
        oval(1,16,5,20,fill=background);oval(16,6,20,10,fill=color)
        line(18,8,26,2,arrow='last',arrowshape=(4,5,2))
        if kind=='PTPOS':oval(9,13,12,16,fill=color)
        if kind=='PTMIX':line(3,21,3,3,arrow='last',arrowshape=(4,5,2))
    elif base in ('LINE','SLINE'):
        points=[(3,18),(24,4)] if base=='SLINE' else [(3,18),(10,6),(18,16),(25,4)]
        line(*(v for p in points for v in p),width=1.3)
        for a,b in points:oval(a-1.7,b-1.7,a+1.7,b+1.7,fill=background)
    elif base=='BOXI':
        polygon([(2,9),(18,2),(27,6),(11,14)],'#d3e1f1')
        polygon([(11,14),(27,6),(27,15),(11,22)],'#b9cde4')
        polygon([(2,9),(11,14),(11,22),(2,17)],'#e4edf7')
        polygon([(4,11),(9,14),(9,19),(4,16)],background)
    elif base=='TUBE':
        polygon([(6,11),(23,3),(27,7),(10,20)],'#c7d9ed')
        oval(2,8,13,22,fill='#dce8f5');oval(5,11,10,19,fill=background)
        c.create_arc(x+17,y+1,x+28,y+13,start=-45,extent=220,outline=color,style='arc')
    elif base is None:
        c.create_text(x+14,y+12,text='?',fill=color)
    else:
        try:
            faces,edges=geometry(base)
            for points,fill in faces:
                c.create_polygon(*(v for a,b in points for v in (x+a,y+b)),fill=fill,outline='')
            for a,b in edges:line(*a,*b,width=.9)
            if base=='SSPH':
                oval(10,2,18,20,dash=(2,1))
        except (ValueError,TypeError,KeyError):
            c.create_text(x+14,y+12,text='?',fill=color)
    if negative:
        c.create_rectangle(x+20,y+15,x+28,y+22,fill='#fff1ef',outline='#ba514d')
        c.create_line(x+22,y+18.5,x+26,y+18.5,fill='#ba514d',width=1.2)
