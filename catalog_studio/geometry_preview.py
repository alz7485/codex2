"""Shared, unitless PARAM dimensions for GMSET and its paired PTSET."""
import copy
import math
import re
from . import expressions, element_schema as schema, pairing, presets
from . import geometry_scene as geo
from .point_geometry import DIMENSIONS_KEY, validate_dimensions
from .point_preview import PointPreview, empty, merged_dimensions, remember as remember_points

ANGLES={'PANGLE','PXTS','PYTS','PXBS','PYBS'}


def numeric_form(root):
    if root[0]=='attr':raise ValueError(root[1]+' の仮の角度は未設定です。')
    if root[0]=='word':raise ValueError('寸法には数値の式が必要です。')
    if root[0]=='tan':numeric_form(root[1])
    elif root[0]=='unary':numeric_form(root[2])
    elif root[0]=='binary':numeric_form(root[2]);numeric_form(root[3])


def pointset_for(data,definition):
    pointset=pairing.resolve(data,definition)['pointset']
    # Identical numbers under different role presets do not describe the same PARAM.
    if pointset and presets.selected_id(data,pointset)!=presets.selected_id(data,definition):return None
    return pointset


def context(data,definition):
    """Detect edits or a changed association while a resize is pending."""
    if not definition:return None
    pointset=pairing.resolve(data,definition)['pointset']
    return copy.deepcopy((definition.get('id'),presets.selected_id(data,definition),definition['elements'],definition.get(DIMENSIONS_KEY),
                          (pointset['id'],presets.selected_id(data,pointset),pointset['elements'],pointset.get(DIMENSIONS_KEY)) if pointset else None))


class GeometryPreview(geo.Resolver):
    def __init__(self,data,definition,state=None):
        pointset=pointset_for(data,definition)
        super().__init__(data,definition,pointset,None,False,geo.Scene())
        self.forms={};self.learning=True
        self.point_definition=copy.deepcopy(pointset) if pointset else {'kind':'PTSET','elements':[],'parameter_preset_id':presets.selected_id(data,definition)}
        saved=definition.get(DIMENSIONS_KEY)
        if pointset:
            existing=PointPreview(data,pointset).snapshot()
            saved=merged_dimensions(existing,saved) if saved is not None else existing
        if state is not None:saved=state
        if saved is not None:self.point_definition[DIMENSIONS_KEY]=copy.deepcopy(saved)
        self.dimensions=PointPreview(data,self.point_definition)
        # First learn size expressions, then offsets: a provisional zero offset
        # must not establish a zero height for the same new PARAM.
        self.deferred=[]
        self.prepare()
        for node,key,default,positive in self.deferred:
            try:self.value(node,key,default,positive,learn_zero=True)
            except (ValueError,OverflowError):pass
        self.learning=False;self.reset_points()

    def prepare(self):
        for node in self.definition['elements']:
            if schema.positive(node['type'])=='SLINE':
                for key,defaults in (('PTSPOS',(-.7,0,0)),('PTEPOS',(.7,0,0))):
                    try:
                        parts=geo.coordinate_expressions(node['attrs'].get(key,''))
                        for i,part in enumerate(parts):self.value({'id':node['id'],'attrs':{key+'_'+'XYZ'[i]:part}},key+'_'+'XYZ'[i],defaults[i])
                    except ValueError:pass
            try:geo.build_mesh(node,self)
            except (ValueError,OverflowError):pass

    def reset_points(self):
        self.point_definition[DIMENSIONS_KEY]=self.dimensions.snapshot()
        self.dimensions=PointPreview(self.data,self.point_definition)
        self.schematic=self.dimensions;self.cache={0:(geo.ZERO,geo.AXES[2])}

    def number(self,text):return self.dimensions.number(text)

    def axis(self,text,default=geo.AXES[0]):
        if empty(text):return geo.ZERO,default
        text=str(text).strip().upper();match=re.fullmatch(r'(-?)P(\d+)',text)
        if match:
            origin,direction=self.point(int(match[2]));return origin,geo.mul(direction,-1 if match[1] else 1)
        match=re.fullmatch(r'P(\d+)\s+P(\d+)',text)
        if match:
            origin=self.point(int(match[1]))[0];return origin,geo.unit(geo.sub(self.point(int(match[2]))[0],origin))
        return geo.ZERO,self.direction(text)

    def value(self,node,key,default=0,positive=False,learn_zero=False):
        text=node['attrs'].get(key,'')
        if empty(text):return default
        try:
            root=expressions.parse(text,self.parameters);numeric_form(root);refs=expressions.refs(root)
            if key not in ANGLES:self.forms[(node['id'],key)]=root
            try:value=self.dimensions.scalar(root)
            except ValueError:
                if not refs or refs<=self.dimensions.values.keys():raise
                if not self.learning:raise
                if default==0 and not learn_zero:
                    self.deferred.append((node,key,default,positive));return default
                target=default if key in ANGLES else self.initial_size(node,key,default)/self.dimensions.scale
                if not math.isfinite(target) or abs(target)>1e100:raise ValueError('共有仮寸法の範囲を超えています。')
                offset,coefficients=0.,{}
                try:offset,coefficients=self.dimensions.linear(root)
                except ValueError:pass
                if len(coefficients)==1:
                    ref,coefficient=next(iter(coefficients.items()))
                    if abs(coefficient)>1e-12:
                        inferred=(target-offset)/coefficient
                        if not math.isfinite(inferred) or abs(inferred)>1e100:raise ValueError('共有仮寸法の範囲を超えています。')
                        self.dimensions.values[ref]=inferred
                self.dimensions.exact.setdefault(root,target)
                self.dimensions.root_text[root]=expressions.normalized(text,self.parameters)
                value=self.dimensions.scalar(root)
            value*=1 if key in ANGLES else self.dimensions.scale
            if not math.isfinite(value) or abs(value)>1e100:raise ValueError('仮寸法の計算結果が大きすぎます。')
            if positive and value<=0:raise ValueError('正の寸法が必要です。')
            return value
        except ValueError as exc:raise ValueError(key+'：'+str(exc)) from exc

    def initial_size(self,node,key,default):
        """Use a previously dragged draft size when a PARAM is first assigned."""
        scale=node.get(geo.SCALE_KEY)
        if not geo.valid_scale(scale):return default
        if key in ('PXLE','PYLE','PZLE'):return default*scale['XYZ'.index(key[1])]
        kind=schema.positive(node['type'])
        if key in ANGLES or key in ('PX','PY','PZ','PDIS','PBDI','POFF','PBOF','PCOF'):return default
        _,axis=self.axis(node['attrs'].get('PAAX' if kind in ('LPYR','LSNO') else 'PAXI',''))
        if kind=='SEXT':
            axis=geo.unit(geo.cross(self.axis(node['attrs'].get('PAAX',''))[1],self.axis(node['attrs'].get('PBAX',''),geo.AXES[1])[1]))
        def factor(vector):return math.hypot(*(v*s for v,s in zip(vector,scale)))
        if key in ('PHEI','PTDI'):return default*factor(axis)
        if key in ('PDIA','PDIAM','PBDM','PTDM','PTRA','PBRA'):
            u,v=geo.frame(axis);return default*math.sqrt(factor(u)*factor(v))
        return default

    def position_expression(self,text):
        return tuple(v*self.dimensions.scale for v in (self.number(part) for part in geo.coordinate_expressions(text)))

    def snapshot(self):return self.dimensions.snapshot()

    def has_dimensions(self,node):
        ids={child['id'] for child in schema.walk([node])}
        for (ident,key),root in self.forms.items():
            if ident not in ids or not expressions.refs(root):continue
            if ident==node['id'] and (key in ('PX','PY','PZ') or key=='PDIS' and schema.positive(node['type'])!='SCON'):continue
            return True
        return False

    def resize(self,ident,axis,extent):
        """Invert a handle's extent into a unique shared PARAM change."""
        node=next(n for n in self.definition['elements'] if n['id']==ident)
        ids={child['id'] for child in schema.walk([node])};refs=set()
        for (nid,_),root in self.forms.items():
            if nid in ids:refs.update(expressions.refs(root))
        variables=[ref for ref in sorted(refs) if ref in self.dimensions.values]
        variables += [('EXPR',root) for root in self.dimensions.exact if expressions.refs(root)&refs and not (expressions.refs(root)<=self.dimensions.values.keys())]
        def get(var):return self.dimensions.exact[var[1]] if var[0]=='EXPR' else self.dimensions.values[var]
        def put(var,value):
            if not math.isfinite(value) or abs(value)>1e100:raise ValueError('共有仮寸法の範囲を超えています。')
            if var[0]=='EXPR':self.dimensions.exact[var[1]]=value
            else:self.dimensions.values[var]=value
        def measure():
            self.dimensions.cache={0:(geo.ZERO,geo.AXES[2])};self.cache={0:(geo.ZERO,geo.AXES[2])}
            mesh=geo.build_mesh(node,self)
            return max(p[axis] for p in mesh.vertices)-min(p[axis] for p in mesh.vertices)
        initial=measure();derivatives=[]
        for var in variables:
            old=get(var);step=max(1.,abs(old))*1e-5;put(var,old+step)
            try:slope=(measure()-initial)/step
            finally:put(var,old)
            if abs(slope)>1e-10:derivatives.append((var,slope))
        if not derivatives:return None
        if len(derivatives)>1:raise ValueError('このハンドルでは複数の PARAM の変更量を一意に決められません。別の軸で調整してください。')
        var,slope=derivatives[0]
        for _ in range(8):
            current=measure()
            if abs(extent-current)<max(1.,abs(extent))*1e-8:break
            old=get(var);step=max(1.,abs(old))*1e-5;put(var,old+step)
            try:slope=(measure()-current)/step
            finally:put(var,old)
            if abs(slope)<1e-10:raise ValueError('この軸では共有 PARAM の仮寸法を変更できません。')
            put(var,old+(extent-current)/slope)
        if abs(measure()-extent)>max(1.,abs(extent))*1e-6:raise ValueError('共有 PARAM の変更量を決められません。')
        self.reset_points();return self.snapshot()


def store(data,definition,state):
    validate_dimensions(state)
    definition[DIMENSIONS_KEY]=copy.deepcopy(state)
    pointset=pointset_for(data,definition)
    if pointset:
        pointset[DIMENSIONS_KEY]=copy.deepcopy(state);remember_points(data,pointset)


def remember(data,definition):
    model=GeometryPreview(data,definition);store(data,definition,model.snapshot());return model
