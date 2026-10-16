"""CPU meshes for catalogue previews. Draft sizes never become E3D attributes."""
import math
import re
from dataclasses import dataclass, field
from . import element_schema as schema, expressions, presets, pairing
from .point_geometry import schematic_position, axis_vector, Camera, coordinate_expressions

SCALE_KEY='schematic_scale'
ZERO=(0.,0.,0.)
AXES=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))


def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def mul(a,t):return tuple(x*t for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def unit(a):
    n=math.hypot(*a)
    if not n:raise ValueError('方向を決める2点・軸が重なっています。')
    return tuple(x/n for x in a)


def valid_scale(value):
    return isinstance(value,(list,tuple)) and len(value)==3 and all(type(v) in (int,float) and math.isfinite(v) and .02<=v<=50 for v in value)


def frame(axis):
    u=unit(cross(axis,min(AXES,key=lambda v:abs(dot(v,axis)))))
    return u,cross(axis,u)


@dataclass
class Mesh:
    ident:str
    name:str
    kind:str
    vertices:list=field(default_factory=list)
    faces:list=field(default_factory=list)
    lines:list=field(default_factory=list)
    negative:bool=False


@dataclass
class Scene:
    meshes:list=field(default_factory=list)
    points:dict=field(default_factory=dict)
    issues:list=field(default_factory=list)
    actual:bool=False
    hidden:dict=field(default_factory=dict)
    soft:set=field(default_factory=set)
    preview:object=field(default=None,repr=False)

    def vertices(self):return [p for mesh in self.meshes for p in mesh.vertices]+[p[0] for p in self.points.values()]


class FitCamera(Camera):
    """Uniform orthographic fit, independent of component units and magnitude."""
    def __init__(self):super().__init__();self.center=ZERO;self.span=1;self.zoom=1
    def fit(self,points,width,height,padding=48):
        points=list(points) or [ZERO]
        lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
        center=tuple(a/2+b/2 for a,b in zip(lo,hi));span=max((b-a for a,b in zip(lo,hi)),default=0) or 1
        right,up=self.basis();normalized=[tuple(x/span for x in sub(p,center)) for p in points]
        flat=[(dot(right,p),dot(up,p)) for p in normalized]
        xmin,xmax=min(p[0] for p in flat),max(p[0] for p in flat);ymin,ymax=min(p[1] for p in flat),max(p[1] for p in flat)
        self.center=center;self.span=span
        self.offset=((xmin+xmax)/2,(ymin+ymax)/2)
        if xmax==xmin and ymax==ymin:self.zoom=max(1,min(width,height)*.35)
        else:self.zoom=min(max(1,width-2*padding)/max(xmax-xmin,1e-12),max(1,height-2*padding)/max(ymax-ymin,1e-12))
    def project(self,point,width,height):
        right,up=self.basis();p=tuple(x/self.span for x in sub(point,self.center));offset=getattr(self,'offset',(0,0))
        return width/2+self.zoom*(dot(right,p)-offset[0]),height/2-self.zoom*(dot(up,p)-offset[1])
    def depth(self,point):return dot(cross(*self.basis()),tuple(x/self.span for x in sub(point,self.center)))


class Resolver:
    def __init__(self,data,definition,pointset,scom,actual,scene):
        self.data=data;self.definition=definition;self.pointset=pointset;self.scom=scom or {};self.actual=actual;self.scene=scene
        self.contexts=expressions.contexts_for(self.scom);self.attributes=dict(definition.get('model_settings',{}));self.attributes.update(self.scom.get('component_attrs',{}))
        self.parameters=presets.rules(data,definition);self.cache={0:(ZERO,AXES[2])};self.active=set();self.nodes={}
        for index,node in enumerate((pointset or {}).get('elements',[])):
            try:
                number=int(node['attrs'].get('NUMB',index+1))
                if number<=0 or number in self.nodes:raise ValueError()
                self.nodes[number]=(node,index)
            except (ValueError,TypeError):scene.issues.append(node['name']+'：ポイント番号が不正・重複しています。')
        self.schematic=None
        if not actual and pointset:
            from .point_preview import PointPreview
            self.schematic=PointPreview(data,pointset)

    def number(self,text,expected=None):
        value=expressions.evaluate(text,self.contexts,self.attributes,self.parameters,expected)
        if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>1e100:raise ValueError('表示用の有限数値が必要です（絶対値 1e100 以下）。')
        return value

    def value(self,node,key,default=0,positive=False):
        text=str(node['attrs'].get(key,''))
        if self.actual:
            if text.strip().lower() in ('','unset'):
                fallback=schema.evaluation_default(node['type'],key)
                if fallback is not None:text=fallback
            try:value=self.number(text,'ANGL' if key in ('PANGLE','PANG','PXTS','PYTS','PXBS','PYBS') else 'DIST')
            except ValueError as exc:raise ValueError(key+'：'+str(exc)) from exc
        else:
            try:value=float(text) if text.strip() in ('0','0.0') else default
            except ValueError:value=default
        if positive and value<=0:raise ValueError(key+'：正の寸法が必要です。')
        return value

    def direction(self,text):
        text=str(text).strip().upper()
        try:return axis_vector(text)
        except ValueError:pass
        if re.fullmatch(r'P\d+',text):return self.point(int(text[1:]))[1]
        # Bearing followed by optional elevation, e.g. X(ANGL / 2)Y45U.
        def cardinal(word):return axis_vector({'N':'Y','S':'-Y'}.get(word,word))
        first=re.match(r'[+-]?[XYZENWSUD]',text)
        if not first:raise ValueError('未対応の方向式：'+text)
        tail=text[first.end():];depth=0;parts=None
        for index,char in enumerate(tail):
            if char=='(':depth+=1
            elif char==')':depth-=1
            elif depth==0 and char in 'XYZENWSUD' and index:
                boundary=index-1 if tail[index-1] in '+-' else index
                second=tail[boundary:index+1] if boundary!=index else char
                try:angle=self.number(tail[:boundary],'ANGL')
                except ValueError:continue
                remaining=tail[index+1:]
                if remaining:
                    if remaining[-1] not in 'XYZENWSUD':continue
                    try:elevation=self.number(remaining[:-1],'ANGL')
                    except ValueError:continue
                    third=remaining[-1]
                else:elevation=0;third=None
                parts=(angle,second,elevation,third);break
        if not parts:raise ValueError('未対応または値が不足する方向式：'+text)
        angle,second,elevation,third=parts;a,b=cardinal(first[0]),cardinal(second)
        if dot(a,b):raise ValueError('方向式には直交する軸が必要です。')
        radians=math.radians(angle);result=add(mul(a,math.cos(radians)),mul(b,math.sin(radians)))
        if third:
            c=cardinal(third)
            if dot(c,a) or dot(c,b):raise ValueError('方向式の第3軸は直交させてください。')
            radians=math.radians(elevation);result=add(mul(result,math.cos(radians)),mul(c,math.sin(radians)))
        return unit(result)

    def axis(self,text,default=AXES[0]):
        text=str(text).strip().upper()
        try:
            match=re.fullmatch(r'(-?)P(\d+)',text)
            if match:
                origin,direction=self.point(int(match[2]));return origin,mul(direction,-1 if match[1] else 1)
            match=re.fullmatch(r'P(\d+)\s+P(\d+)',text)
            if match:
                origin=self.point(int(match[1]))[0];return origin,unit(sub(self.point(int(match[2]))[0],origin))
            return ZERO,self.direction(text)
        except ValueError:
            if self.actual:raise
            return ZERO,default

    def position_expression(self,text):
        return tuple(self.number(part) for part in coordinate_expressions(text))

    def point(self,number):
        if number in self.cache:return self.cache[number]
        if number not in self.nodes:raise ValueError('P'+str(number)+' が PTSET にありません。')
        if number in self.active:raise ValueError('PTSET の軸参照が循環しています。')
        self.active.add(number);node,index=self.nodes[number];attrs=node['attrs'];kind=node['type']
        try:
            if not self.actual:
                if self.schematic and kind in schema.PT_TYPES:
                    position,direction=self.schematic.point(number)
                else:
                    position=schematic_position(node,index)
                    direction=self.axis(attrs.get('PAXI' if kind in ('PTAXI','PTMIX') else 'PTCDIR',attrs.get('PTCD','X')))[1]
            elif kind=='PTAXI':
                origin,direction=self.axis(attrs.get('PAXI') if str(attrs.get('PAXI','')).strip().lower() not in ('','unset') else 'Y');position=add(origin,mul(direction,self.value(node,'PDIS')))
            elif kind in ('PTCAR','PTMIX','PTPOS'):
                position=self.position_expression(attrs.get('PTCPOS','')) if kind=='PTPOS' else tuple(self.value(node,k) for k in ('PX','PY','PZ'))
                text=attrs.get('PAXI','') if kind=='PTMIX' else attrs.get('PTCDIR',attrs.get('PTCD',''))
                if str(text).strip().lower() in ('','unset'):text='Y'
                direction=self.axis(text)[1] if kind=='PTMIX' else self.direction(text)
            elif kind=='point':
                direction=self.direction(attrs.get('方向',''));position=(0.,0.,self.value(node,'位置'))
            else:raise ValueError('未対応のポイント種類：'+kind)
            self.cache[number]=(position,direction);return self.cache[number]
        finally:self.active.remove(number)


def rings_mesh(mesh,rings,top=True,bottom=True):
    count=len(rings[0]);mesh.vertices=[p for ring in rings for p in ring]
    for j in range(len(rings)-1):
        for i in range(count):mesh.faces.append((j*count+i,j*count+(i+1)%count,(j+1)*count+(i+1)%count,(j+1)*count+i))
    if bottom:mesh.faces.append(tuple(reversed(range(count))))
    if top:mesh.faces.append(tuple((len(rings)-1)*count+i for i in range(count)))


def build_mesh(node,resolver):
    r=resolver;kind=schema.positive(node['type']);mesh=Mesh(node['id'],node['name'],node['type'],negative=node['type'] in schema.NEGATIVE_BASE)
    def value(key,default=0,positive=False):return r.value(node,key,default,positive)
    def axis(key='PAXI',default=AXES[0]):return r.axis(node['attrs'].get(key,''),default)
    def at(origin,direction,distance):return add(origin,mul(direction,distance))
    def circle(center,direction,radius,slopes=(0,0)):
        u,v=frame(direction);result=[]
        for i in range(24):
            a=2*math.pi*i/24;x,y=radius*math.cos(a),radius*math.sin(a)
            result.append(add(add(center,add(mul(u,x),mul(v,y))),mul(direction,x*slopes[0]+y*slopes[1])))
        return result
    top=str(node['attrs'].get('TVISI','')).upper()!='FALSE';bottom=str(node['attrs'].get('BVISI','')).upper()!='FALSE'
    if kind in ('SCYL','LCYL','SCON','SSLC','SDIS','SSPH','SDSH'):
        origin,direction=axis();diameter=value('PDIA',.65,True);radius=diameter/2
        if kind=='LCYL':low,high=value('PBDI',-.6),value('PTDI',.6)
        elif kind=='SCON':low,high=0,value('PDIS',1.2,True)
        else:low=value('PDIS',0);high=low+value('PHEI',1.2,kind!='SCYL') if kind in ('SCYL','SSLC','SDSH') else low
        if kind=='SDSH':
            if r.actual:raise ValueError('SDSH の基準面・皿形曲面の実寸表示は未対応です。')
            rings=[circle(at(origin,direction,low+(high-low)*math.sin(i*math.pi/16)),direction,radius*math.cos(i*math.pi/16)) for i in range(9)]
        elif kind=='SSPH':
            rings=[circle(at(origin,direction,low+radius*math.sin(-math.pi/2+i*math.pi/16)),direction,radius*math.cos(-math.pi/2+i*math.pi/16)) for i in range(17)]
        elif kind=='SDIS':
            mesh.vertices=circle(at(origin,direction,low),direction,radius);mesh.faces=[tuple(range(24))];return mesh
        else:
            if kind=='SCYL' and high==low:raise ValueError('円筒の高さは0以外にしてください。')
            if kind!='SCYL' and high<=low:raise ValueError('上面位置は底面位置より大きくしてください。')
            slopes=[(0,0),(0,0)]
            if kind=='SSLC':
                def tangent(key):
                    radians=math.radians(value(key,0))
                    if abs(math.cos(radians))<1e-10:raise ValueError('端面の傾斜が90度です。')
                    return math.tan(radians)
                slopes=[(tangent('PXBS'),tangent('PYBS')),(tangent('PXTS'),tangent('PYTS'))]
                if high-low<=radius*math.hypot(*(sub(slopes[1],slopes[0]))):raise ValueError('傾斜した上下端面が交差しています。')
            rings=[circle(at(origin,direction,low),direction,0 if kind=='SCON' else radius,slopes[0]),circle(at(origin,direction,high),direction,radius,slopes[1])]
        rings_mesh(mesh,rings,top,bottom)
        if kind=='SCYL' and high<low:mesh.faces=[tuple(reversed(face)) for face in mesh.faces]
    elif kind=='SBOX':
        center=tuple(value(k,0) for k in ('PX','PY','PZ'));sizes=[value(k,.8,True) for k in ('PXLE','PYLE','PZLE')]
        rings=[[add(center,(sx*sizes[0]/2,sy*sizes[1]/2,sz*sizes[2]/2)) for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1))] for sz in (-1,1)]
        rings_mesh(mesh,rings)
    elif kind in ('LSNO','LPYR'):
        origin,a=axis('PAAX');_,b=axis('PBAX',AXES[1])
        if abs(dot(a,b))>1e-6:raise ValueError('A軸とB軸を直交させてください。')
        low,high=value('PBDI',0),value('PTDI',1.2)
        if high<=low:raise ValueError('上面位置は底面位置より大きくしてください。')
        if kind=='LSNO':
            def radius(diameter,radius):
                if str(node['attrs'].get(radius,'')).strip() and not str(node['attrs'].get(diameter,'')).strip():return value(radius,.3,True)
                return value(diameter,.6,True)/2
            rings=[circle(at(origin,a,low),a,radius('PBDM','PBRA')),circle(add(at(origin,a,high),mul(b,value('POFF',0))),a,radius('PTDM','PTRA'))]
        else:
            _,c=axis('PCAX',AXES[2])
            if abs(dot(a,c))>1e-6 or abs(dot(b,c))>1e-6:raise ValueError('A・B・C軸を相互に直交させてください。')
            rings=[]
            for distance,bkey,ckey,offset in ((low,'PBBT','PCBT',ZERO),(high,'PBTP','PCTP',add(mul(b,value('PBOF',0)),mul(c,value('PCOF',0))))):
                center=add(at(origin,a,distance),offset);width,height=value(bkey,.8,True),value(ckey,.6,True)
                rings.append([add(center,add(mul(b,x*width/2),mul(c,y*height/2))) for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))])
        rings_mesh(mesh,rings,top,bottom)
    elif kind in ('SEXT','SREV'):
        origin=tuple(value(k,0) for k in ('PX','PY','PZ'));_,a=axis('PAAX');_,b=axis('PBAX',AXES[1])
        if abs(dot(a,b))>1e-6:raise ValueError('輪郭のA軸とB軸を直交させてください。')
        loop=next((e for e in node.get('children',[]) if e['type']=='SLOO'),None)
        vertices=(loop or {}).get('children',[])
        if len(vertices)<3:
            if r.actual:raise ValueError('SLOO に3頂点以上の SVER が必要です。')
            coords=[(-.5,0),(.5,0),(.5,.7),(-.5,.7)]
        else:
            coords=[]
            for child in vertices:
                if r.actual and r.value(child,'PRAD')!=0:raise ValueError('輪郭頂点のフィレット実寸表示は未対応です。')
                coords.append((r.value(child,'PX',-.4 if len(coords)%3==0 else .4),r.value(child,'PY',.2 if len(coords)<2 else .8)))
        normal=unit(cross(a,b));rings=[]
        if kind=='SEXT':
            height=value('PHEI',1.2,True)
            for offset in (0,height):rings.append([add(origin,add(add(mul(a,x),mul(b,y)),mul(normal,offset))) for x,y in coords])
        else:
            angle=value('PANGLE',270)
            if not -360<=angle<=360 or angle==0:raise ValueError('回転角度は0以外の−360〜360度です。')
            for step in range(33):
                theta=math.radians(angle)*step/32;radial=add(mul(b,math.cos(theta)),mul(normal,math.sin(theta)))
                rings.append([add(origin,add(mul(a,x),mul(radial,y))) for x,y in coords])
        rings_mesh(mesh,rings,kind=='SEXT' or abs(angle)!=360,kind=='SEXT' or abs(angle)!=360)
    elif kind in ('LINE','SLINE'):
        if kind=='LINE':
            tokens=str(node['attrs'].get('PTS','')).upper().split()
            if not 2<=len(tokens)<=6 or any(not re.fullmatch(r'[PT]\d+',t) for t in tokens):raise ValueError('LINE の点列は2〜6個の P/T 番号で指定してください。')
            if r.actual and any(t.startswith('T') for t in tokens):raise ValueError('LINE の接線点 T の曲線表示は未対応です。')
            mesh.vertices=[r.point(int(t[1:]))[0] for t in tokens]
        elif r.actual:mesh.vertices=[r.position_expression(node['attrs'].get(k,'')) for k in ('PTSPOS','PTEPOS')]
        else:mesh.vertices=[r.position_expression(node['attrs'][k]) if str(node['attrs'].get(k,'')).strip().lower() not in ('','unset') else default for k,default in (('PTSPOS',(-.7,0,0)),('PTEPOS',(.7,0,0)))]
        mesh.lines=[tuple(range(len(mesh.vertices)))]
    elif kind in ('SCTO','SRTO'):
        start,tangent_a=axis('PAAX');end,tangent_b=axis('PBAX',AXES[1])
        if not r.actual and all(str(node['attrs'].get(key,'')).strip().lower() in ('','unset') for key in ('PAAX','PBAX')):start,tangent_a,end,tangent_b=(1.,0.,0.),(0.,-1.,0.),(0.,1.,0.),(-1.,0.,0.)
        normal=unit(cross(tangent_a,tangent_b));ra=cross(normal,tangent_a);rb=cross(normal,tangent_b)
        denominator=dot(cross(ra,rb),normal)
        if abs(denominator)<1e-10:raise ValueError('トーラスの端面軸から円弧を決定できません。')
        center=add(start,mul(ra,dot(cross(sub(end,start),rb),normal)/denominator))
        a,b=sub(start,center),sub(end,center);radius=math.hypot(*a)
        if not radius or abs(math.hypot(*b)-radius)>radius*1e-6 or abs(dot(sub(end,start),normal))>radius*1e-6:raise ValueError('トーラスの端点と方向が同じ円弧上にありません。')
        angle=math.atan2(dot(normal,cross(unit(a),unit(b))),dot(unit(a),unit(b)))
        if abs(angle)<1e-10:raise ValueError('トーラスの端点が重なっています。')
        width=value('PDIA',.35,True);height=value('PHEI',.3,True) if kind=='SRTO' else width
        if width/2>=radius:raise ValueError('トーラスの断面幅が曲率半径に対して大きすぎます。')
        u=unit(a);v=cross(normal,u);rings=[]
        for step in range(25):
            theta=angle*step/24;radial=add(mul(u,math.cos(theta)),mul(v,math.sin(theta)));path=add(center,mul(radial,radius))
            if kind=='SCTO':ring=[add(path,add(mul(radial,width/2*math.cos(i*math.pi/12)),mul(normal,width/2*math.sin(i*math.pi/12)))) for i in range(24)]
            else:ring=[add(path,add(mul(radial,x*width/2),mul(normal,y*height/2))) for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))]
            rings.append(ring)
        rings_mesh(mesh,rings,top,bottom)
    elif kind in ('TUBE','BOXI'):
        if r.actual:raise ValueError('暗黙チューブの長さには設計側の前後部品の配置情報が必要です。')
        origin,direction=axis();radius=value('PDIAM' if kind=='TUBE' else 'PDIA',.65,True)/2
        if kind=='BOXI':
            u,v=frame(direction);width,height=value('PXLE',.7,True),value('PZLE',.5,True)
            rings=[[add(at(origin,direction,distance),add(mul(u,x*width/2),mul(v,y*height/2))) for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))] for distance in (0,1.2)]
        else:rings=[circle(origin,direction,radius),circle(at(origin,direction,1.2),direction,radius)]
        rings_mesh(mesh,rings,top,bottom)
    elif kind in ('cone','cylinder','box'):
        # Compatibility with the original, synthetic project format.
        origin=ZERO;direction=r.direction(node['attrs'].get('方向','Z'))
        if kind=='box':raise ValueError('旧形式の箱は SBOX に置き換えてください。')
        height=value('長さ',1.2,True);center=value('位置',height/2)
        radii=[value('大径' if kind=='cone' else '直径',.7,True)/2,value('小径' if kind=='cone' else '直径',.4,True)/2]
        rings_mesh(mesh,[circle(at(origin,direction,center-height/2),direction,radii[0]),circle(at(origin,direction,center+height/2),direction,radii[1])])
    else:raise ValueError('この種類の3D形状は未対応です。')
    if not r.actual and not (getattr(r,'has_dimensions',lambda _:False)(node)):
        scale=node.get(SCALE_KEY,(1,1,1))
        if valid_scale(scale) and mesh.vertices:
            center=tuple((min(p[i] for p in mesh.vertices)+max(p[i] for p in mesh.vertices))/2 for i in range(3))
            mesh.vertices=[add(center,tuple((p[i]-center[i])*scale[i] for i in range(3))) for p in mesh.vertices]
    return mesh


def build_scene(data,definition,scom=None,actual=False,preview_state=None,representation_settings=None):
    scene=Scene(actual=actual)
    if not definition:return scene
    pt=pairing.resolve(data,definition)['pointset']
    if actual:
        try:
            if not scom:raise ValueError('寸法に使う SCOM を選択してください。')
            if scom.get('gmset_id')!=definition['id']:raise ValueError('SCOM の GMSET と表示中の GMSET が異なります。')
            if pt and scom.get('ptset_id')!=pt['id']:raise ValueError('SCOM の PTSET と適用する PTSET が異なります。')
            if not pt and scom.get('ptset_id'):raise ValueError('適用する PTSET を選択してください。')
            presets.require_compatible(data,scom,definition)
            if pt:presets.require_compatible(data,scom,pt)
        except ValueError as exc:scene.issues.append(str(exc));return scene
    if actual:resolver=Resolver(data,definition,pt,scom,True,scene)
    else:
        from .geometry_preview import GeometryPreview
        resolver=GeometryPreview(data,definition,preview_state);scene.preview=resolver
        scene.issues.extend(resolver.scene.issues)
        if pt and not resolver.pointset:scene.issues.append('PTSET と GMSET の PARAM プリセットが異なるため、仮値を共有できません。')
    scene.points[0]=(ZERO,AXES[2],'P0')
    for number,(node,_) in resolver.nodes.items():
        try:scene.points[number]=(*resolver.point(number),node['name'])
        except ValueError as exc:scene.issues.append(node['name']+'：'+str(exc))
    for node in schema.walk(definition['elements']):
        if node['type'] in schema.CHILD_TYPES:continue
        from .representation import visibility
        visible,reason,soft=visibility(node,representation_settings)
        if not visible:scene.hidden[node['id']]=node['name']+'：'+reason;continue
        if soft:scene.soft.add(node['id'])
        try:scene.meshes.append(build_mesh(node,resolver))
        except (ValueError,OverflowError) as exc:scene.issues.append(node['name']+'：'+str(exc))
    return scene
