"""Persistent, unitless PARAM dimensions shared by every referencing p-point."""
import copy
import math
import re
from . import expressions, element_schema as schema
from .point_geometry import LAYOUT_KEY, DIMENSIONS_KEY, PLANES, schematic_position, valid_layout, coordinate_expressions, validate_dimensions
from .geometry_scene import Resolver, Scene, ZERO, add, sub, mul, dot, unit


def empty(text):return str(text).strip().lower() in ('','unset')


class PointPreview(Resolver):
    def __init__(self,data,definition):
        # Use the strict expression/axis interpreter with private preview values.
        # No SCOM or design context is supplied or modified.
        super().__init__(data,definition,definition,None,True,Scene())
        self.seeds={n:schematic_position(node,index) for n,(node,index) in self.nodes.items()}
        self.forms={};self.owners={};self.values={};self.exact={};self.scale=1.;self.problems={};self.root_text={}
        saved=definition.get(DIMENSIONS_KEY)
        if DIMENSIONS_KEY in definition:
            validate_dimensions(saved);self.scale=saved['scale']
            self.values={(family,pid):value for family,group in saved['values'].items() for pid,value in group.items()}
            for item in saved['expressions']:
                root=expressions.parse(item['expression']);self.exact[root]=item['value'];self.root_text[root]=item['expression']
        for number,(node,_) in self.nodes.items():
            if node['type'] not in schema.PT_TYPES:continue
            try:
                for key,text in self.fields(node).items():
                    try:root=expressions.parse(text,self.parameters)
                    except ValueError:continue
                    self.forms[(number,key)]=root
                    self.root_text[root]=expressions.normalized(text,self.parameters)
                    for ref in expressions.refs(root):self.owners.setdefault(ref,number)
            except ValueError as exc:self.problems[number]=str(exc)
        # Literal dimensions establish only a common display scale, never mm.
        for number,key in (() if saved is not None else self.forms):
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
        missing=expressions.attribute_refs(root)-self.attributes.keys()
        if missing:raise ValueError(', '.join(sorted(missing))+' の確認用設計値は未設定です。')
        try:return self.run_scalar(root)
        except ValueError:
            if root not in self.exact:raise
            return self.exact[root]

    def run_scalar(self,root):
        kind=root[0]
        if kind in ('number','quantity'):return root[1]
        if kind=='ref':
            if root[1:] not in self.values:raise ValueError('仮寸法が未定：'+root[1]+' '+root[2][1:])
            return self.values[root[1:]]
        if kind=='attr':
            if root[1] not in self.attributes:raise ValueError(root[1]+' の確認用設計値は未設定です。')
            return self.attributes[root[1]]
        if kind=='word':raise ValueError('位置には数値の式が必要です。')
        if kind=='unary':return self.scalar(root[2])*(1 if root[1]=='+' else -1)
        if kind in ('tan','func'):
            from .units import Quantity, function
            return function('TAN' if kind=='tan' else root[1],Quantity(self.scalar(root[1] if kind=='tan' else root[2]))).value
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

    def number(self,text,expected=None):
        root=expressions.parse(text,self.parameters)
        try:value=self.scalar(root)
        except ValueError:
            if root not in self.exact:raise
            value=self.exact[root]
        if not math.isfinite(value) or abs(value)>1e100:raise ValueError('仮寸法の計算結果が大きすぎます。')
        return value

    def value(self,node,key,default=0,positive=False):
        text=node['attrs'].get(key,'')
        return self.number(text)*self.scale
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
        return [(family,pid,self.values.get((family,pid))) for family,pid in sorted(refs)]

    def references(self,number,seen=None):
        seen=set() if seen is None else seen
        if number in seen or number not in self.nodes:return set()
        seen.add(number);result=set()
        for (n,_),root in self.forms.items():
            if n==number:result.update(expressions.refs(root))
        node=self.nodes[number][0]
        for key in ('PAXI','PTCDIR','PTCD'):
            for match in re.finditer(r'\bP(\d+)\b',str(node['attrs'].get(key,'')),re.IGNORECASE):
                result.update(self.references(int(match[1]),seen))
        return result

    def moved(self,working,ident,plane):
        """Invert a dragged point's position into changes to shared preview values."""
        working[DIMENSIONS_KEY]=self.snapshot();result=PointPreview(self.data,working)
        number=result.number_for(ident);node=result.nodes[number][0];target=node[LAYOUT_KEY]
        refs=result.references(number)
        variables=[ref for ref in sorted(refs) if ref in result.values]
        variables += [('EXPR',root) for root in result.exact if expressions.refs(root)&refs and not (expressions.refs(root)<=result.values.keys())]
        if not variables:return result
        rows=range(3) if node['type']=='PTAXI' else PLANES[plane]
        complete=False
        try:complete=all(not empty(text) for text in result.fields(node).values())
        except ValueError:pass
        nonnegative=set()
        for (n,key),root in result.forms.items():
            if key=='PDIS':
                term=root[2] if root[0]=='unary' else root
                if term[0]=='ref':nonnegative.add(term[1:])
        def get(var):return result.exact[var[1]] if var[0]=='EXPR' else result.values[var]
        def put(var,value):
            if not math.isfinite(value) or abs(value)>1e100:raise ValueError('共有仮寸法の範囲を超えています。')
            if var[0]=='EXPR':result.exact[var[1]]=value
            else:result.values[var]=max(0.,value) if var in nonnegative else value
        def position():
            result.cache={0:(ZERO,(0.,0.,1.))};result.problems={}
            point=result.point(number)[0]
            if complete and number in result.problems:raise ValueError(result.problems[number])
            if not valid_layout(point):raise ValueError('仮寸法の表示範囲を超えています。')
            return point
        for _ in range(8):
            current=position();columns=[];active=[]
            for var in variables:
                old=get(var);step=max(1.,abs(old))*1e-5
                put(var,old+step)
                try:changed=position()
                finally:put(var,old)
                column=[(changed[i]-current[i])/step for i in rows]
                if max(map(abs,column),default=0)>1e-12:columns.append(column);active.append(var)
            if not active:break
            residual=[target[i]-current[i] for i in rows]
            delta=least_squares(columns,residual)
            if max(map(abs,delta),default=0)<1e-9:break
            for var,value in zip(active,delta):put(var,get(var)+value)
        position();result.cache={0:(ZERO,(0.,0.,1.))};result.problems={}
        for n in result.nodes:result.point(n)
        working[DIMENSIONS_KEY]=result.snapshot();return result

    def snapshot(self):
        values={}
        for (family,pid),value in self.values.items():values.setdefault(family,{})[pid]=value
        result={'scale':self.scale,'values':values,'expressions':[{'expression':self.root_text[root],'value':value} for root,value in self.exact.items() if root in self.root_text]}
        validate_dimensions(result);return result


def remember(data,definition):
    """Persist current shared values during an edit, never as a redraw side effect."""
    if definition.get('kind')!='PTSET':return
    model=PointPreview(data,definition);state=model.snapshot()
    positions=[(node,model.location(node['id'])) for node,_ in model.nodes.values()]
    definition[DIMENSIONS_KEY]=state
    for node,position in positions:
        if valid_layout(position):node[LAYOUT_KEY]=list(position)
    return model


def merged_dimensions(first,second):
    """Keep existing values when adding another element group to the set."""
    validate_dimensions(first);validate_dimensions(second);result=copy.deepcopy(first)
    factor=second['scale']/first['scale']
    for family,group in second['values'].items():
        target=result['values'].setdefault(family,{})
        for pid,value in group.items():target.setdefault(pid,value*factor)
    known={expressions.parse(item['expression']) for item in result['expressions']}
    for item in second['expressions']:
        root=expressions.parse(item['expression'])
        if root not in known:result['expressions'].append(dict(item,value=item['value']*factor));known.add(root)
    validate_dimensions(result);return result


def least_squares(columns,target):
    """Small full-rank solve (at most three position coordinates)."""
    size=len(columns)
    if size>len(target):raise ValueError('複数の共有 PARAM の変更量を一意に決められません。属性の式を分けてください。')
    matrix=[[sum(a*b for a,b in zip(left,right)) for right in columns]+[sum(a*b for a,b in zip(left,target))] for left in columns]
    tolerance=max((abs(v) for row in matrix for v in row[:-1]),default=0)*1e-10
    for column in range(size):
        pivot=max(range(column,size),key=lambda row:abs(matrix[row][column]))
        if abs(matrix[pivot][column])<=tolerance:raise ValueError('複数の共有 PARAM の変更量を一意に決められません。属性の式を分けてください。')
        matrix[column],matrix[pivot]=matrix[pivot],matrix[column];value=matrix[column][column]
        matrix[column]=[v/value for v in matrix[column]]
        for row in range(size):
            if row==column:continue
            factor=matrix[row][column];matrix[row]=[v-factor*x for v,x in zip(matrix[row],matrix[column])]
    return [matrix[i][-1] for i in range(size)]
