"""Read-only attribute helpers; point candidates never invent missing points."""
import re
from . import element_schema as schema, pairing


DIRECTION_FIELDS = ('PAXI', 'PAAX', 'PBAX', 'PCAX', 'PLAXI', 'PTCDIR', 'PTCD')
POINT_FIELDS = frozenset(DIRECTION_FIELDS) - {'PLAXI'}


def is_point_reference(key, text):
    """Distinguish point tokens from the numeric expression shorthand P1."""
    pattern = r'-?P[0-9]+(?:\s+P[0-9]+)?' if key in POINT_FIELDS else r'[PT][0-9]+(?:\s+[PT][0-9]+)*' if key == 'PTS' else None
    return bool(pattern and re.fullmatch(pattern, str(text).strip(), re.IGNORECASE))


def _pointset(data, definition):
    kind = definition.get('kind')
    if kind == 'PTSET':
        return definition
    if kind == 'GMSET':
        return pairing.resolve(data, definition)['pointset']
    if kind == 'NGMSET':
        linked = {part.get('ptset_id') for part in data.get('scoms', [])
                  if part.get('ngmset_id') == definition.get('id') and part.get('ptset_id')}
        if len(linked) == 1:
            matches = [pointset for pointset in data.get('definitions', [])
                       if pointset.get('kind') == 'PTSET' and pointset.get('id') in linked]
            if len(matches) == 1:
                return matches[0]
    return None


def point_choices(data, definition, element, key):
    """Return existing P numbers, or None when an attribute cannot use them.

    These are insertion suggestions only. Imported expressions and manually
    entered values remain the responsibility of the normal editing workflow.
    """
    if not definition or not element or definition.get('kind') not in ('PTSET', 'GMSET', 'NGMSET'):
        return None
    if key not in POINT_FIELDS and not (key == 'PTS' and schema.positive(element.get('type')) == 'LINE'):
        return None
    pointset = _pointset(data, definition)
    numbered = {}
    for point in (pointset or {}).get('elements', []):
        if point.get('type') not in schema.PT_TYPES:
            continue
        raw = str(point.get('attrs', {}).get('NUMB', '')).strip()
        if not re.fullmatch(r'[0-9]+', raw) or int(raw) <= 0:
            continue
        numbered.setdefault(int(raw), []).append(point)
    current_id = element.get('id') if definition.get('kind') == 'PTSET' else None
    numbers = [number for number, points in numbered.items() if len(points) == 1
               and points[0] is not element
               and not (current_id is not None and points[0].get('id') == current_id)]
    return ('P0',) + tuple('P' + str(number) for number in sorted(numbers))
