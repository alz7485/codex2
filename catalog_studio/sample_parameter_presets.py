"""Text transcription of the supplied 29-item parameter list; no source photo."""
ITEMS=(
 ('NOM BORE','呼び径1'),('NOM BORE','呼び径2'),('NOM BORE','呼び径3'),
 ('CONN TYPE','接続形式1'),('CONN TYPE','接続形式2'),('CONN TYPE','接続形式3'),
 ('LAY LENGTH','面間長さ1'),('LAY LENGTH','面間長さ2'),('LAY LENGTH','面間長さ3'),
 ('FLAN THICKNESS','フランジ厚さ1'),('FLAN THICKNESS','フランジ厚さ2'),
 ('FLAN DIA','フランジ外径1'),('FLAN DIA','フランジ外径2'),
 ('CENTER TO TOP','中心から上端までの高さ'),('PIPE OD','管外径'),('BODY DIA','弁本体径'),
 ('INSERTION DEPTH','挿入深さ'),('INSERTION DIA','挿入径'),
 ('BONNET DIA','ボンネット径'),('BONNET HIGHT','ボンネット高さ'),('BONNET THICKNESS','ボンネット厚さ'),
 ('OP LENGTH','操作部長さ'),('OP WIDTH','操作部幅'),('OP HEIGHT','操作部高さ'),
 ('SPACE','スペース'),('MAINT SP XLEN','保守スペースX方向長さ'),('MAINT SP YLEN','保守スペースY方向長さ'),
 ('MAINT SP DOWN','保守スペース下方寸法'),('MAINT SP HEIGHT','保守スペース高さ'),
)

def valve_reference_preset():
    parameters=[]
    for number,(english,japanese) in enumerate(ITEMS,1):
        note='写真の英語名を保持。'
        if number==20:note+='HIGHTは写真の表記で、HEIGHTへ自動訂正しません。'
        if 22<=number<=24:note+='OPは操作部として仮訳。詳細は要確認。'
        if number==25:note+='SPACEの具体的な用途・方向は未確認。'
        parameters.append({'id':'P'+str(number),'role':japanese,'meaning':japanese,'english_name':english,
                           'unit':'' if 4<=number<=6 else 'mm','value_type':'word' if 4<=number<=6 else 'number','description':note})
    return {'id':'sample-valve-reference-29','name':'弁用PARAM参考表（29項目）','period':'','component':'弁・配管部品',
            'description':'提示写真の1〜29番をテキスト化。30番は「以下、追加パラメータ」のため固定項目には含めません。寸法のmmはツールの初期設定で写真記載の単位ではありません。',
            'parameters':parameters,'reference_roles':{}}


def add_reference_preset(data):
    from . import presets
    existing=presets.get(data,'sample-valve-reference-29')
    if existing:return existing,False
    record=valve_reference_preset();base=record['name'];number=2
    while any(p['name'].casefold()==record['name'].casefold() for p in data.get('parameter_presets',[])):
        record['name']=base+' '+str(number);number+=1
    if len(data.get('parameter_presets',[]))>=1000:raise ValueError('プリセット数の上限です。')
    data.setdefault('parameter_presets',[]).append(record)
    return record,True
