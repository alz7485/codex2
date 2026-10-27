"""Point geometry and parameter-relative placement; no E3D command generation."""
import math
import re
from fractions import Fraction
from . import expressions

PLANES={'XY':(0,1),'XZ':(0,2),'YZ':(1,2)}
LAYOUT_KEY='schematic_position'
DIMENSIONS_KEY='schematic_dimensions'


def validate_dimensions(state):
    def finite(value):return type(value) in (int,float) and math.isfinite(value) and abs(value)<=1e100
    if not isinstance(state,dict) or not finite(state.get('scale')) or state['scale']<=0:raise ValueError('共有仮寸法の表示倍率が不正です。')
    values=state.get('values');items=state.get('expressions')
    if not isinstance(values,dict) or any(family not in expressions.FAMILIES or not isinstance(group,dict) for family,group in values.items()):raise ValueError('共有仮寸法の PARAM 種類が不正です。')
    if sum(len(group) for group in values.values())>2000:raise ValueError('共有仮寸法が多すぎます。')
    for group in values.values():
        if any(not isinstance(pid,str) or not re.fullmatch(r'P[1-9]\d*',pid) or not finite(value) for pid,value in group.items()):raise ValueError('共有仮寸法の番号・値が不正です。')
    if not isinstance(items,list) or len(items)>600:raise ValueError('共有式の仮寸法が不正です。')
    seen=set()
    for item in items:
        if not isinstance(item,dict) or not finite(item.get('value')) or not isinstance(item.get('expression'),str):raise ValueError('共有式の仮寸法が不正です。')
        root=expressions.parse(item['expression'])
        if root in seen:raise ValueError('共有式が重複しています。')
        seen.add(root)


def valid_layout(value):
    return isinstance(value,(list,tuple)) and len(value)==3 and all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=10000 for v in value)


def schematic_position(element,index=0):
    """Tool-only, unitless layout. Never evaluate PARAM or SCOM distances."""
    saved=element.get(LAYOUT_KEY)
    if valid_layout(saved):return tuple(saved)
    attrs=element['attrs'];size=.8+min(index,4)*.25
    def sign(text):
        text=str(text).strip()
        try:return 0 if float(text)==0 else (-1 if float(text)<0 else 1)
        except ValueError:return -1 if text.startswith('-') else 1
    if element['type']=='PTAXI':
        try:return tuple(size*sign(attrs.get('PDIS',''))*v for v in axis_vector(attrs.get('PAXI','')))
        except ValueError:pass
    if element['type'] in ('PTCAR','PTMIX'):
        return tuple(size*sign(attrs.get(key,'')) for key in ('PX','PY','PZ'))
    angle=index*2.4
    return (size*math.cos(angle),size*math.sin(angle),0)


def schematic_placement(kind,point,attrs=None,plane=None):
    """Infer basic direction/zero coordinates, leaving distances for the user."""
    previous=attrs or {};point=[0.0 if abs(v)<.035 else float(v) for v in point]
    if not valid_layout(point):raise ValueError('画面の配置範囲を超えています。ズームを戻してください。')
    changes={};index=max(range(3),key=lambda i:abs(point[i]));direction=('-' if point[index]<0 else '')+'XYZ'[index]
    direction_key='PAXI' if kind in ('PTAXI','PTMIX') else 'PTCDIR'
    if kind=='PTPOS' and 'PTCD' in previous and 'PTCDIR' not in previous:direction_key='PTCD'
    old=previous.get(direction_key,'')
    unset=not str(old).strip() or str(old).lower()=='unset'
    if any(point) and unset:changes[direction_key]=direction
    if kind=='PTAXI':
        if not unset:
            vector=axis_vector(old);distance=sum(p*v for p,v in zip(point,vector))
            point=[distance*v for v in vector]
        else:point=[point[i] if i==index else 0.0 for i in range(3)]
        if str(previous.get('PDIS','')).strip().lower() in ('','unset'):
            changes['PDIS']='0' if not any(point) else ''
    elif kind in ('PTCAR','PTMIX'):
        for i,key in enumerate(('PX','PY','PZ')):
            if plane and i not in PLANES[plane]:continue
            if str(previous.get(key,'')).strip().lower() in ('','unset'):
                changes[key]='0' if not point[i] else ''
    elif kind!='PTPOS':raise ValueError('この種類の仮配置は未対応です。')
    return tuple(point),changes


def axis_vector(text):
    text=str(text).strip().upper()
    aliases={'E':'X','W':'-X','U':'Z','D':'-Z'}
    text=aliases.get(text,text).replace('+','')
    if text not in ('X','Y','Z','-X','-Y','-Z'):raise ValueError('この軸式の座標計算は未対応です。')
    result=[0,0,0];result['XYZ'.index(text[-1])]=-1 if text.startswith('-') else 1
    return tuple(result)


def coordinate_expressions(text):
    """Split an explicit XYZ position into scalar expressions, without evaluating."""
    text=str(text).strip()
    if text.startswith('(') and text.endswith(')'):text=text[1:-1].strip()
    pieces=[];depth=0
    for index,char in enumerate(text):
        if char in '([':depth+=1
        elif char in ')]':depth-=1
        elif depth==0 and char.upper() in 'XYZ' and (index==0 or text[index-1].isspace()):pieces.append(index)
    if not pieces or text[:pieces[0]].strip():raise ValueError('未対応の位置式：XYZ 座標を明示してください。')
    result=['0','0','0'];used=set()
    for i,start in enumerate(pieces):
        axis=text[start].upper();end=pieces[i+1] if i+1<len(pieces) else len(text)
        if axis in used:raise ValueError('位置式の座標が重複しています。')
        used.add(axis);result['XYZ'.index(axis)]=text[start+1:end].strip()
    return tuple(result)


def position(element,contexts,attributes,parameters):
    attrs=element['attrs'];kind=element['type']
    def value(key):return expressions.evaluate(attrs.get(key,''),contexts,attributes,parameters)
    if kind=='PTAXI':
        axis=axis_vector(attrs.get('PAXI',''));distance=value('PDIS')
        return tuple(distance*v for v in axis)
    if kind in ('PTCAR','PTMIX'):return tuple(value(k) for k in ('PX','PY','PZ'))
    raise ValueError('PTCPOS の位置式の座標計算は未対応です。属性欄で編集してください。')


def formula(pid,coefficient):
    if not re.fullmatch(r'P[1-9]\d*',pid):raise ValueError('基準 PARAM を選択してください。')
    value=Fraction(coefficient)
    if value==0:return '0'
    prefix='-' if value<0 else '';value=abs(value)
    text=prefix+'PARAM['+pid[1:]+']'
    if value.numerator!=1:text+=' * '+str(value.numerator)
    if value.denominator!=1:text+=' / '+str(value.denominator)
    return text


def placement(kind,coefficients,pid,axis='X',plane=None):
    if kind=='PTAXI':
        vector=axis_vector(axis);index=next(i for i,v in enumerate(vector) if v)
        if plane is not None and index not in PLANES[plane]:raise ValueError('この点の軸を含む配置面に切り替えてください。')
        return {'PDIS':formula(pid,coefficients[index]*vector[index])}
    if kind not in ('PTCAR','PTMIX'):raise ValueError('PTPOS の位置式は属性欄で編集してください。')
    indices=range(3) if plane is None else PLANES[plane]
    return {'P'+'XYZ'[i]:formula(pid,coefficients[i]) for i in indices}


class Camera:
    def __init__(self):self.yaw=-40;self.pitch=30;self.zoom=125
    def basis(self):
        a,b=math.radians(self.yaw),math.radians(self.pitch)
        return (math.cos(a),math.sin(a),0),(-math.sin(a)*math.sin(b),math.cos(a)*math.sin(b),math.cos(b))
    def project(self,point,width,height):
        right,up=self.basis()
        return width/2+self.zoom*sum(v*x for v,x in zip(right,point)),height/2-self.zoom*sum(v*x for v,x in zip(up,point))
    def unproject(self,x,y,width,height,plane,fixed=0):
        a,b=PLANES[plane];c=next(i for i in range(3) if i not in (a,b));right,up=self.basis()
        sx=(x-width/2)/self.zoom-right[c]*fixed;sy=-(y-height/2)/self.zoom-up[c]*fixed
        determinant=right[a]*up[b]-right[b]*up[a]
        if abs(determinant)<1e-6:raise ValueError('作図面が横向きです。視点のXY・XZ・YZから作図面と同じ面を選んでください。')
        result=[0,0,0];result[c]=fixed
        result[a]=(sx*up[b]-right[b]*sy)/determinant
        result[b]=(right[a]*sy-sx*up[a])/determinant
        return result
    def unproject_axis(self,x,y,width,height,origin,vector):
        start=self.project(origin,width,height)
        end=self.project(tuple(a+b for a,b in zip(origin,vector)),width,height)
        dx,dy=end[0]-start[0],end[1]-start[1];length=dx*dx+dy*dy
        if length<1e-8:raise ValueError('軸が視線と重なっています。視点を変えてください。')
        distance=((x-start[0])*dx+(y-start[1])*dy)/length
        return tuple(a+distance*b for a,b in zip(origin,vector))
    def face(self,plane):
        self.yaw,self.pitch={'XY':(0,90),'XZ':(0,0),'YZ':(90,0)}[plane]
