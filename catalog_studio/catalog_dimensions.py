"""Actual millimetre measurements and draggable catalogue-only annotation layout."""
import copy
import math
import re

KEY='catalog_dimension_layouts'
PATTERN=re.compile(r'(?:extent:[XYZ]|points:\d+:\d+)\Z')
COLOR='#126c94'


def validate(data):
    layouts=data.get(KEY,{})
    if not isinstance(layouts,dict) or len(layouts)>5000:raise ValueError('寸法線配置の形式・件数が不正です。')
    for ident,rows in layouts.items():
        if not isinstance(ident,str) or not ident or len(ident)>1000 or not isinstance(rows,dict) or len(rows)>32:raise ValueError('SCOMの寸法線配置が不正です。')
        for key,offset in rows.items():
            if not isinstance(key,str) or len(key)>80 or not PATTERN.fullmatch(key) or not isinstance(offset,(list,tuple)) or len(offset)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>2 for v in offset):raise ValueError('寸法線の位置は有限の画面比率2個で指定してください。')


def measurements(scene,outer=True,connections=True):
    if not scene.actual:return []
    points=[p for mesh in scene.meshes if not mesh.negative for p in mesh.vertices]
    if not points:return []
    result=[]
    lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
    if outer:
        for i,axis in enumerate('XYZ'):
            distance=hi[i]-lo[i]
            if distance<=0 or not math.isfinite(distance):continue
            start=tuple(lo);end=list(lo);end[i]=hi[i]
            result.append(dict(key='extent:'+axis,label='表示外形 '+axis,start=start,end=tuple(end),value=distance))
    if connections:
        pairs=([(1,2)] if 1 in scene.points and 2 in scene.points else [])
        pairs.extend((0,n) for n in sorted(scene.points) if n>=3 and 0 in scene.points)
        for a,b in pairs[:8]:
            start,end=scene.points[a][0],scene.points[b][0];distance=math.dist(start,end)
            if distance>0 and math.isfinite(distance):result.append(dict(key=f'points:{a}:{b}',label=f'P{a}–P{b}',start=start,end=end,value=distance))
    return result


def context(view):
    from . import project,pairing
    e=view.editor;definition=e.definition();scom=project.get(e.data,'scoms',e.preview_scom_id)
    pt=pairing.resolve(e.data,definition)['pointset'] if definition else None
    return copy.deepcopy((scom,definition,pt))


def offsets(view):
    saved=view.editor.data.get(KEY,{}).get(view.editor.preview_scom_id,{})
    result=dict(saved)
    drag=getattr(view,'dimension_drag',None)
    if drag:result[drag['key']]=drag['candidate']
    return result


def description(view,dimension):
    japanese=dimension['label'] if dimension['key'].startswith('extent:') else dimension['label']+' 接続点間距離'
    if not view.dimension_stext.get():return japanese
    # Only use explicit PARAM provenance; never guess by coincident numeric values.
    from . import pairing,presets,expressions,element_schema as schema
    e=view.editor
    from . import project
    scom=project.get(e.data,'scoms',e.preview_scom_id) or {}
    pt=pairing.resolve(e.data,e.definition())['pointset'] if e.definition() else None
    ids=set()
    if pt and dimension['key'].startswith('points:'):
        numbers={int(n) for n in dimension['key'].split(':')[1:]}
        for index,node in enumerate(schema.walk(pt['elements'])):
            try:number=int(node['attrs'].get('NUMB',index+1))
            except (ValueError,TypeError):continue
            if number not in numbers:continue
            try:
                ids.update(pid for family,pid in expressions.refs(expressions.parse(node['attrs'].get('PDIS','0'),presets.rules(e.data,scom))) if family=='PARAM')
            except ValueError:pass
    texts=[]
    for record in e.data.get('texts',[]):
        source=record.get('parameter_text_source',{})
        if record.get('type')!='TEXT' or record.get('parent_id')!=scom.get('cate_id'):continue
        if source.get('preset_id')!=presets.selected_id(e.data,scom):continue
        if set(source.get('parameters','').split(', '))!=ids or not ids:continue
        value=record.get('attrs',{}).get('STEXT','').strip()
        if value and value not in texts:texts.append(value)
    return texts[0] if len(texts)==1 else japanese+'（対応STEXTなし）'


def draw(view):
    c=view.canvas;c.delete('catalog-dimension');view.dimension_items={};view.dimension_measurements=[]
    if not view.actual or not view.dimension_lines.get():return
    dimensions=measurements(view.scene,True,view.connection_dimensions.get());view.dimension_measurements=dimensions
    width,height=c.winfo_width(),c.winfo_height()
    saved=offsets(view)
    vertices=[p for m in view.scene.meshes if not m.negative for p in m.vertices]
    if not vertices:return
    center=tuple((min(p[i] for p in vertices)+max(p[i] for p in vertices))/2 for i in range(3))
    cx,cy=view.camera.project(center,width,height)
    for i,dimension in enumerate(dimensions):
        key=dimension['key'];a=view.camera.project(dimension['start'],width,height);b=view.camera.project(dimension['end'],width,height)
        vx,vy=b[0]-a[0],b[1]-a[1];length=math.hypot(vx,vy)
        if length<8:continue
        nx,ny=-vy/length,vx/length;mx,my=(a[0]+b[0])/2,(a[1]+b[1])/2
        if nx*(mx-cx)+ny*(my-cy)<0:nx,ny=-nx,-ny
        base=34+i*11;extra=saved.get(key,(0,0))
        dx,dy=nx*base+extra[0]*width,ny*base+extra[1]*height
        # Keep extension arrows and labels inside the canvas while dragging.
        dx=max(18-min(a[0],b[0]),min(width-18-max(a[0],b[0]),dx))
        dy=max(48-min(a[1],b[1]),min(height-24-max(a[1],b[1]),dy))
        q=(a[0]+dx,a[1]+dy);r=(b[0]+dx,b[1]+dy)
        tags=('catalog-dimension','dimension:'+key)
        for p,t in ((a,q),(b,r)):c.create_line(*p,*t,fill=COLOR,width=1,dash=(3,2),tags=tags)
        c.create_line(*q,*r,fill=COLOR,width=1.5,arrow='both',arrowshape=(7,9,3),tags=tags)
        label=f"{dimension['value']:.6g} mm\n{description(view,dimension)}"
        tx,ty=(q[0]+r[0])/2,(q[1]+r[1])/2
        text=c.create_text(tx,ty,text=label,fill=COLOR,font=(view.editor.host.ui_font,10,'bold'),tags=tags)
        box=c.bbox(text)
        if box:
            shiftx=max(8-box[0],min(width-8-box[2],0));shifty=max(45-box[1],min(height-8-box[3],0))
            if shiftx or shifty:c.move(text,shiftx,shifty);box=c.bbox(text)
            background=c.create_rectangle(box[0]-4,box[1]-3,box[2]+4,box[3]+3,fill='#ffffff',outline='#b7d4e3',tags=tags)
            c.tag_lower(background,text)
        view.dimension_items[key]=dict(text=text,label=label,offset=extra)


def hit(view,x,y):
    for item in reversed(view.canvas.find_overlapping(x-5,y-5,x+5,y+5)):
        for tag in view.canvas.gettags(item):
            if tag.startswith('dimension:'):return tag[len('dimension:'):]
    return None


def start(view,key,event):
    view.orbit=None
    view.dimension_drag=dict(key=key,data=view.editor.data,scom_id=view.editor.preview_scom_id,
        context=context(view),origin=(event.x,event.y),old=list(offsets(view).get(key,(0,0))),candidate=list(offsets(view).get(key,(0,0))))


def move(view,event):
    d=view.dimension_drag
    if not d:return
    if d['data'] is not view.editor.data or d['scom_id']!=view.editor.preview_scom_id or not view.actual or d['context']!=context(view):
        view.dimension_drag=None;view.redraw();return
    width,height=max(1,view.canvas.winfo_width()),max(1,view.canvas.winfo_height())
    d['candidate']=[max(-2,min(2,d['old'][i]+delta/size)) for i,(delta,size) in enumerate(((event.x-d['origin'][0],width),(event.y-d['origin'][1],height)))]
    view.redraw()


def release(view):
    d=view.dimension_drag;view.dimension_drag=None
    if not d:return
    if d['data'] is view.editor.data and d['scom_id']==view.editor.preview_scom_id and view.actual and d['context']==context(view) and d['old']!=d['candidate']:
        view.editor.data.setdefault(KEY,{}).setdefault(d['scom_id'],{})[d['key']]=d['candidate']
        view.editor.host.mark('寸法線の表示位置を変更しました。モデルの寸法は変更していません。')
    view.redraw()
