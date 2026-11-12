"""User-confirmed authoring defaults; distinct from inherited old DB data."""
from . import element_schema as schema

BOOLS=('CLFLA','TUFLA','TVISI','BVISI')
POSITION_FIELDS=('PTCPOS','PTSPOS','PTEPOS')


def defaults(kind):
    if kind in schema.PT_TYPES:return dict(PSKEY='unset',DESC='unset',PURP='unset')
    if kind in schema.GM_TYPES or kind in schema.NEGATIVE_BASE:
        result=dict(LEVEL='0 10',DESC='unset',GTYP='unset',PURP='unset',CLFLA='FALSE',
                    TUFLA='FALSE',TVISI='TRUE',BVISI='TRUE',OBST='2',NAPP='2' if kind in schema.NEGATIVE_BASE else '0')
        if schema.positive(kind)=='LPYR':result.update(PAAX='Z',PBAX='X',PCAX='Y')
        return result
    return {}


def derived_axes(element):
    if schema.positive(element['type'])!='LPYR':return
    from .geometry_scene import cross,unit
    import math
    from .geometry_scene import Resolver,Scene
    try:
        resolver=Resolver({'parameters':[]},{},None,None,True,Scene())
        b=resolver.direction(element['attrs'].get('PBAX') or 'X')
        c=resolver.direction(element['attrs'].get('PCAX') or 'Y')
        a=unit(cross(b,c))
    except (ValueError,TypeError):return
    axes=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
    for vector,name in zip(axes,('X','-X','Y','-Y','Z','-Z')):
        if all(abs(x-y)<1e-8 for x,y in zip(a,vector)):
            element['attrs']['PAAX']=name;return
    # Preserve a computable general direction instead of rounding to an axis.
    element['attrs']['PAAX']=f'X{math.degrees(math.atan2(a[1],a[0])):.12g}Y{math.degrees(math.asin(a[2])):.12g}Z'
