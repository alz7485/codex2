"""Small dimensional arithmetic layer; database lengths are mm, angles degrees."""
from dataclasses import dataclass
import math

SCALAR=(0,0)
DIST=(1,0)
ANGL=(0,1)
UNITS={}
for names,factor,dim in ((('mm','millimetre','millimeter'),1,DIST),(('cm',),10,DIST),
                         (('m','metre','meter'),1000,DIST),(('inch','inches','in'),25.4,DIST),
                         (('ft','foot','feet'),304.8,DIST),(('deg','degree','degrees'),1,ANGL),
                         (('rad','radian','radians'),180/math.pi,ANGL),(('none',),1,SCALAR)):
    for name in names:UNITS[name]=(factor,dim)


@dataclass(frozen=True)
class Quantity:
    value: float
    dimension: tuple | None = None


def dimension(unit):
    if unit is None:return None
    return UNITS.get(str(unit).strip().lower(),(1,None))[1]


def compatible(actual,expected):
    if actual is not None and expected is not None and actual!=expected:
        raise ValueError('物理次元が一致しません（距離・角度・無次元を確認してください）。')


def binary(op,a,b):
    if op in ('+','-'):
        compatible(a.dimension,b.dimension)
        return Quantity(a.value+b.value if op=='+' else a.value-b.value,a.dimension if a.dimension is not None else b.dimension)
    if op=='/' and b.value==0:raise ValueError('ゼロで除算できません。')
    da,db=a.dimension or SCALAR,b.dimension or SCALAR
    dim=tuple(x+y if op=='*' else x-y for x,y in zip(da,db))
    if a.dimension is None and b.dimension is None:dim=None
    return Quantity(a.value*b.value if op=='*' else a.value/b.value,dim)


def function(name,arg):
    if name in ('SIN','COS','TAN'):
        compatible(arg.dimension,ANGL)
        angle=math.radians(arg.value)
        if name=='TAN' and abs(math.cos(angle))<1e-12:raise ValueError('TAN が定義できない角度です。')
        return Quantity({'SIN':math.sin,'COS':math.cos,'TAN':math.tan}[name](angle),SCALAR)
    compatible(arg.dimension,SCALAR)
    if name in ('ASIN','ACOS') and not -1<=arg.value<=1:raise ValueError(name+' の値は −1〜1 です。')
    return Quantity(math.degrees({'ASIN':math.asin,'ACOS':math.acos,'ATAN':math.atan}[name](arg.value)),ANGL)
