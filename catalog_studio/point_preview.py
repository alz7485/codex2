"""Shared, unitless PARAM dimensions anchored by the lowest numbered p-point."""
import math
from . import expressions, element_schema as schema
from .point_geometry import LAYOUT_KEY, schematic_position, valid_layout, coordinate_expressions
from .geometry_scene import Resolver, Scene, ZERO, add, sub, mul, dot, unit


def empty(text):return str(text).strip().lower() in ('','unset')


class PointPreview(Resolver):
    def __init__(self,data,definition):
        # Use the strict expression/axis interpreter with private preview values.
        # No SCOM or design context is supplied or modified.
        super().__init__(data,definition,definition,None,True,Scene())
        self.seeds={n:schematic_position(node,index) for n,(node,index) in self.nodes.items()}
        self.forms={};self.owners={};self.values={};self.exact={};self.scale=1.;self.problems={}
        for number,(node,_) in sorted(self.nodes.items()):
            if node['type'] not in schema.PT_TYPES:continue
            try:
                for key,text in self.fields(node).items():
                    try:root=expressions.parse(text,self.parameters)
                    except ValueError:continue
                    self.forms[(number,key)]=root
                    for ref in expressions.refs(root):self.owners.setdefault(ref,number)
            except ValueError as exc:self.problems[number]=str(exc)
        # Literal dimensions establish only a common display scale, never mm.
        for number,key in self.forms:
            root=self.forms[(number,key)]
            if expressions.refs(root):continue
            try:
                value=self.scalar(root)
                target=self.target(number,key)
                if abs(value)>1e-12 and abs(target)>1e-12:
                    self.scale=abs(target/value);break
            except ValueError:pass
        for _ in range(len(self.owners)+1):
            changed=False;self.cache={0:(ZERO,(0.,0.,1.))}
            for (number,key),root in self.forms.items():
                try:
                    target=self.target(number,key)/self.scale
                    refs=expressions.refs(root)
                    if refs and all(self.owners.get(ref)==number for ref in refs):self.exact.setdefault(root,target)
                    offset,coefficients=self.linear(root)
                    if len(coefficients)!=1:continue
                    ref,coefficient=next(iter(coefficients.items()))
                    if self.owners.get(ref)!=number or abs(coefficient)<1e-12:continue
                    value=(target-offset)/coefficient
                    if key=='PDIS' and (root[0]=='ref' or root[0]=='unary' and root[2][0]=='ref'):value=max(0.,value)
                    if not math.isfinite(value) or abs(value)>1e100:continue
                    self.values[ref]=value;changed=True;self.cache={0:(ZERO,(0.,0.,1.))}
                except ValueError:continue
            if not changed:break
        self.cache={0:(ZERO,(0.,0.,1.))};self.problems={}
        for number in sorted(self.nodes):self.point(number)

    @staticmethod
    def fields(node):
        kind=node['type'];attrs=node['attrs']
        if kind=='PTAXI':return {'PDIS':attrs.get('PDIS','')}
        if kind in ('PTCAR','PTMIX'):return {k:attrs.get(k,'') for k in ('PX','PY','PZ')}
        if kind=='PTPOS':return dict(zip(('PX','PY','PZ'),coordinate_expressions(attrs.get('PTCPOS',''))))
        return {}

    def scalar(self,root):
        try:return self.run_scalar(root)
        except ValueError:
            if root not in self.exact:raise
            return self.exact[root]

    def run_scalar(self,root):
        kind=root[0]
        if kind=='number':return root[1]
        if kind=='ref':
            if root[1:] not in self.values:raise ValueError('仮寸法が未定：'+root[1]+' '+root[2][1:])
            return self.values[root[1:]]
        if kind=='attr':raise ValueError(root[1]+' の仮の角度は未設定です。')
        if kind=='word':raise ValueError('位置には数値の式が必要です。')
        if kind=='unary':return self.scalar(root[2])*(1 if root[1]=='+' else -1)
        if kind=='tan':
            angle=math.radians(self.scalar(root[1]))
            if abs(math.cos(angle))<1e-12:raise ValueError('TAN が定義できない角度です。')
            return math.tan(angle)
        a,b=self.scalar(root[2]),self.scalar(root[3])
        if root[1]=='/' and not b:raise ValueError('ゼロで除算できません。')
        return {'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a/b}[root[1]]()

    def linear(self,root):
        if root[0]=='ref' and root[1:] not in self.values:return 0.,{root[1:]:1.}
        if root[0]=='unary':
            value,coeff=self.linear(root[2]);sign=1 if root[1]=='+' else -1
            return value*sign,{ref:c*sign for ref,c in coeff.items()}
        if root[0]!='binary':return self.scalar(root),{}
        a,ac=self.linear(root[2]);b,bc=self.linear(root[3]);op=root[1]
        if op in ('+','-'):
            sign=1 if op=='+' else -1;coeff=ac.copy()
            for ref,c in bc.items():coeff[ref]=coeff.get(ref,0)+sign*c
            return a+sign*b,{ref:c for ref,c in coeff.items() if abs(c)>1e-12}
        if op=='*' and not (ac and bc):
            return a*b,({ref:c*b for ref,c in ac.items()} if ac else {ref:c*a for ref,c in bc.items()})
        if op=='/' and not bc and b:return a/b,{ref:c/b for ref,c in ac.items()}
        return self.scalar(root),{}

    def number(self,text):
        root=expressions.parse(text,self.parameters)
        try:value=self.scalar(root)
        except ValueError:
            if root not in self.exact:raise
            value=self.exact[root]
        if not math.isfinite(value) or abs(value)>1e100:raise ValueError('仮寸法の計算結果が大きすぎます。')
        return value

    def value(self,node,key,default=0,positive=False):return self.number(node['attrs'].get(key,''))*self.scale
    def position_expression(self,text):return tuple(self.number(part)*self.scale for part in coordinate_expressions(text))

    def axis(self,text,default=None):
        origin,vector=super().axis(text)
        return origin,unit(vector)

    def target(self,number,key):
        seed=self.seeds[number];node=self.nodes[number][0]
        if key!='PDIS':return seed['XYZ'.index(key[-1])]
        origin,vector=self.axis(node['attrs'].get('PAXI',''))
        target=dot(sub(seed,origin),vector)
        # Bare dimensions are nonnegative lengths; an explicit negative term
        # in PDIS can still place a point on the other side of its axis origin.
        root=self.forms.get((number,key))
        if root and root[0]=='ref':target=max(0.,target)
        return target

    def point(self,number):
        if number in self.cache:return self.cache[number]
        if number not in self.nodes:raise ValueError('P'+str(number)+' が PTSET にありません。')
        if number in self.active:raise ValueError('PTSET の軸参照が循環しています。')
        node,_=self.nodes[number]
        try:
            result=super().point(number)
            if not valid_layout(result[0]):raise ValueError('仮寸法の表示範囲を超えています。')
            return result
        except ValueError as exc:
            self.cache.pop(number,None);self.problems[number]=str(exc)
            self.active.add(number)
            try:
                seed=self.seeds[number];attrs=node['attrs'];kind=node['type'];vector=ZERO
                if kind=='PTAXI':
                    try:
                        origin,vector=self.axis(attrs.get('PAXI',''));distance=dot(sub(seed,origin),vector)
                        if empty(attrs.get('PDIS','')):distance=max(0.,distance)
                        seed=add(origin,mul(vector,distance))
                    except ValueError:pass
                else:
                    try:vector=self.axis(attrs.get('PAXI' if kind=='PTMIX' else 'PTCDIR',attrs.get('PTCD','')))[1]
                    except ValueError:pass
                    try:
                        seed=list(seed)
                        for key,text in self.fields(node).items():
                            try:seed['XYZ'.index(key[-1])]=self.number(text)*self.scale
                            except ValueError:pass
                        seed=tuple(seed)
                    except ValueError:pass
                result=(seed,vector);self.cache[number]=result;return result
            finally:self.active.remove(number)

    def number_for(self,ident):
        for number,(node,_) in self.nodes.items():
            if node['id']==ident:return number
        raise ValueError('ポイントが変更されています。選択し直してください。')
    def location(self,ident):return self.point(self.number_for(ident))[0]

    def sources(self,ident):
        number=self.number_for(ident);refs=set()
        for (n,_),root in self.forms.items():
            if n==number:refs.update(expressions.refs(root))
        return [(family,pid,self.owners[family,pid]) for family,pid in sorted(refs) if (family,pid) in self.owners]
