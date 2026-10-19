"""Observed ALP spellings and selectors; no command execution."""
TYPE_NAMES = {'SCYL': 'SCYLINDER', 'LSNO': 'LSNOUT', 'SSPH': 'SSPHERE'}
ATTR_NAMES = {'CLFLA': 'CLFL', 'TUFLA': 'TUFL', 'PTS': 'SETP'}


def resolve_old(words, root, aliases):
    """Resolve type-specific member ordinals only inside this input block."""
    def resolve(parts):
        if len(parts) < 2:
            raise ValueError('OLDの要素指定が不完全です。')
        kind = aliases.get(parts[0].upper(), parts[0].upper())
        if len(parts) == 2:
            if kind == root['kind'] and parts[1] == root['name']:
                return root
            raise ValueError('OLDの参照先が現在のINPUTセットと一致しません。')
        if len(parts) < 5 or parts[2].upper() != 'OF' or not parts[1].isdecimal() or int(parts[1]) < 1:
            raise ValueError('OLDは要素型・順番号・OF・親の形式で指定してください。')
        parent = resolve(parts[3:])
        candidates = [child for child in parent.get('elements', parent.get('children', [])) if child['type'] == kind]
        number = int(parts[1])
        if number > len(candidates):
            raise ValueError('OLDで指定した型のメンバーが見つかりません。')
        return candidates[number - 1]
    return resolve(words)
