"""Point geometry and parameter-relative placement; no E3D command generation."""
import math
import re
from fractions import Fraction
from . import expressions

PLANES={'XY':(0,1),'XZ':(0,2),'YZ':(1,2)}


def axis_vector(text):
    text=str(text).strip().upper()
    aliases={'E':'X','W':'-X','U':'Z','D':'-Z'}
    text=aliases.get(text,text).replace('+','')
    if text not in ('X','Y','Z','-X','-Y','-Z'):raise ValueError('この軸式の座標計算は未対応です。')
    result=[0,0,0];result['XYZ'.index(text[-1])]=-1 if text.startswith('-') else 1
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
    def __init__(self):self.yaw=40;self.pitch=30;self.zoom=125
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
        if abs(determinant)<1e-6:raise ValueError('配置面が横向きです。「面を正面」を押してください。')
        result=[0,0,0];result[c]=fixed
        result[a]=(sx*up[b]-right[b]*sy)/determinant
        result[b]=(right[a]*sy-sx*up[a])/determinant
        return result
    def face(self,plane):
        self.yaw,self.pitch={'XY':(0,90),'XZ':(0,0),'YZ':(90,0)}[plane]
