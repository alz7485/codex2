"""Separate piping point and geometry presets, with shared parameter dictionaries."""
import copy
from . import element_schema as schema

PARAMETERS = {
    'PIPE': [('呼び径','NOM SIZE','number'),('管外径','PIPE O/D','number'),('接続形式','CONN TYPE','word')],
    'WELD': [('呼び径','NOMINAL BORE','number'),('入口接続形式','ARR CONN TYPE','word'),('出口接続形式','LEA CONN TYPE','word')],
    'BEND': [('呼び径','NOMINAL SIZE','number'),('管外径','PIPE OD','number'),('接続形式','CONN TYPE','word'),('曲げ半径','RAD','number')],
}


def add_presets(data):
    """Atomically add missing builtins; do not create catalogue or live definitions."""
    candidate=copy.deepcopy(data);added=0
    def unique(records,name):
        base=name;n=2
        while any(r['name'].casefold()==name.casefold() for r in records):
            name=base+' '+str(n);n+=1
        return name
    for component,items in PARAMETERS.items():
        ident='builtin-piping-param-'+component.lower()
        records=candidate.setdefault('parameter_presets',[])
        if not any(r['id']==ident for r in records):
            if len(records)>=1000:raise ValueError('PARAMプリセット数の上限です。')
            records.append({'id':ident,'name':unique(records,'標準 '+component+' PARAM'),'period':'','component':component,
                            'description':'各CATEのTEXTに記載されたPARAM説明に基づく定義。寸法単位mmはツール設定。','reference_roles':{},
                            'parameters':[{'id':'P'+str(i),'role':jp,'meaning':jp,'english_name':en,
                                           'unit':'mm' if kind=='number' else '', 'value_type':kind,'description':''}
                                          for i,(jp,en,kind) in enumerate(items,1)]})
        for kind in (('PTSET','GMSET') if component=='BEND' else ('PTSET',)):
            eid='builtin-piping-'+component.lower()+'-'+kind.lower()
            library=candidate.setdefault('element_presets',[])
            if any(r['id']==eid for r in library):continue
            if len(library)>=1000:raise ValueError('要素プリセット数の上限です。')
            record={'id':eid,'name':unique([r for r in library if r['kind']==kind],'標準 '+component),
                    'kind':kind,'description':'配管用 '+component+' '+kind+'。BENDのTANF式は原文を保持し、プレビュー計算は未対応。' if component=='BEND' else '配管用 '+component+' PTSET（GMSETなし）。',
                    'parameter_preset_id':ident,'elements':[]}
            def element(typ,attrs):schema.add_element(record,typ)['attrs'].update(attrs)
            if kind=='PTSET':
                for n in range(1,2 if component=='PIPE' else 3):
                    element('PTAXI',{'NUMB':str(n),'PCON':'PARAM '+str(n+1 if component=='WELD' else 3),
                                     'PBOR':'PARAM 1','PDIS':'TANF PARAM 4 DDANGLE' if component=='BEND' else '0',
                                     'PAXI':'-X' if n==1 else ('X DDANGLE Y' if component=='BEND' else 'X')})
            else:
                element('LINE',{'OBST':'0','CLFLA':'TRUE','PTS':'P1 TO P2'})
                element('SCTO',{'TUFLA':'TRUE','PAAX':'P1','PBAX':'P2','PDIA':'SUM PARAM 2 IPARAM 1',
                                'TVISI':'FALSE','BVISI':'FALSE','NAPP':'0'})
            library.append(record);added+=1
    from . import project
    project.validate(candidate)
    data.clear();data.update(candidate)
    return added
