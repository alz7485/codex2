"""Synthetic manual valve, isolated from users' existing parameter rules."""
import copy
import uuid
from . import element_schema as schema, presets, project


VALUES = {'P1':80., 'P2':89.1, 'P3':240., 'P4':140., 'P5':190.,
          'P6':18., 'P7':325., 'P8':24., 'P9':180., 'P10':12., 'P11':'BWD'}
ROLES = ('呼び径', '管外径', '面間長さ', '弁本体径', 'フランジ外径', 'フランジ厚さ',
         '全高', '弁棒径', 'ハンドル径', 'ハンドル厚さ', '接続形式')


def prepare(data):
    """Return a validated candidate and IDs; never overwrite existing records."""
    candidate = copy.deepcopy(data)
    used = {record['name'].casefold() for key in ('definitions','cates','scoms','texts','tables','specs','catalog_details','catalog_props','parameter_presets') for record in candidate.get(key, [])}

    def name(base):
        value = base; number = 2
        while value.casefold() in used:
            value = base + '-' + str(number); number += 1
        used.add(value.casefold()); return value

    rule = presets.add(candidate, name('手動弁サンプルのPARAM'), empty=True)
    rule.update(component='手動弁', description='形状確認用の自作参考値。規格品の寸法・接続条件を示すものではありません。')
    rule['parameters'] = [dict(id='P'+str(i), role=role, unit='mm' if i < 11 else '', value_type='number' if i < 11 else 'word') for i, role in enumerate(ROLES, 1)]

    def definition(kind):
        return dict(id=uuid.uuid4().hex, kind=kind, name=name('/SAMPLE-VALVE-'+kind), revision='01',
                    parameter_preset_id=rule['id'], sample='manual-valve', elements=[])

    pt, gm = definition('PTSET'), definition('GMSET')
    pt['attrs'] = {'DESC':'手動弁サンプル：配管接続点2点とハンドル上端の補助点'}
    for number, axis, distance, label in ((1,'-X','(PARAM[3] / 2)','P1 配管接続点'), (2,'X','(PARAM[3] / 2)','P2 配管接続点'), (3,'Z','(PARAM[7] - PARAM[5] / 2)','P3 ハンドル上端')):
        node=schema.add_element(pt,'PTAXI');node['name']=label
        node['attrs'].update(NUMB=str(number),PAXI=axis,PDIS=distance)
        if number < 3:node['attrs'].update(PBOR='(PARAM[1])',PCON='(PARAM[11])')
    # Tool-only schematic dimensions: proportional reference values, never SCOM data.
    pt['schematic_dimensions'] = {'scale': .01, 'values': {'PARAM':{key:value for key,value in VALUES.items() if isinstance(value,float)}}, 'expressions':[]}
    gm['paired_ptset_id'] = pt['id']
    gm['schematic_dimensions'] = copy.deepcopy(pt['schematic_dimensions'])
    shapes = [
        ('SCYL','接続管',dict(PAXI='-X',PDIS='(PARAM[3] / 2)',PHEI='(-PARAM[3])',PDIA='(PARAM[2])')),
        ('SSPH','弁本体',dict(PAXI='Z',PDIS='0',PDIA='(PARAM[4])')),
        ('SCYL','P1側フランジ',dict(PAXI='-X',PDIS='(PARAM[3] / 2)',PHEI='(-PARAM[6])',PDIA='(PARAM[5])')),
        ('SCYL','P2側フランジ',dict(PAXI='X',PDIS='(PARAM[3] / 2)',PHEI='(-PARAM[6])',PDIA='(PARAM[5])')),
        ('SCYL','ボンネット',dict(PAXI='Z',PDIS='(PARAM[4] / 4)',PHEI='(PARAM[4] / 2)',PDIA='(PARAM[4] / 2)')),
        ('SCYL','弁棒',dict(PAXI='Z',PDIS='(PARAM[4] / 2)',PHEI='(PARAM[7] - PARAM[5] / 2 - PARAM[10] - PARAM[4] / 2)',PDIA='(PARAM[8])')),
        ('SCYL','操作ハンドル（円盤で簡略化）',dict(PAXI='Z',PDIS='(PARAM[7] - PARAM[5] / 2 - PARAM[10])',PHEI='(PARAM[10])',PDIA='(PARAM[9])')),
    ]
    for kind, label, attrs in shapes:
        node=schema.add_element(gm,kind);node['name']=label
        node['attrs'].update(attrs, LEVEL='0 10', CLFLA='FALSE', TUFLA='TRUE', OBST='2')
    candidate['definitions'].extend((pt,gm))
    cate=dict(id=uuid.uuid4().hex, name=name('/SAMPLE-VALVE-CATE'), revision='01', description='手動弁の形状確認用サンプル')
    candidate['cates'].append(cate)
    scom=dict(id=uuid.uuid4().hex, name=name('/SAMPLE-VALVE-80'), cate_id=cate['id'], revision='01', size='80（自作参考値）',
              ptset_id=pt['id'],gmset_id=gm['id'],parameter_preset_id=rule['id'],values=copy.deepcopy(VALUES))
    candidate['scoms'].append(scom)
    project.validate(candidate)
    return candidate, {'ptset_id':pt['id'], 'gmset_id':gm['id'], 'scom_id':scom['id'], 'preset_id':rule['id']}


def standalone():
    data=project.sample()
    for key in ('parameters','cates','definitions','scoms','specs','books','texts','tables'):data[key]=[]
    data['name']='手動弁サンプル'
    data, ids=prepare(data)
    data['active_parameter_preset_id']=ids['preset_id']
    return data
