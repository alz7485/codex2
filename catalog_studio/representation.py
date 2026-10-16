"""Explicit inspection policy, not an assertion of E3D runtime defaults."""
import re


def visibility(node,settings=None):
    if not settings or settings.get('mode','全形状')=='全形状':return True,'編集用：全形状',False
    attrs=node.get('attrs',{});level=int(settings.get('level',0))
    obstacle=bool(settings.get('obst')) and str(attrs.get('OBST','')) in ('1','2')
    soft=obstacle and str(attrs.get('OBST'))=='1'
    level_text=str(attrs.get('LEVEL','')).strip()
    if level_text.lower() not in ('','unset'):
        values=level_text.split()
        if len(values)!=2 or any(not re.fullmatch(r'[+-]?\d+',v) for v in values):return False,'LEVEL は下限・上限の2整数が必要です。',False
        lo,hi=map(int,values)
        if lo>hi:return False,'LEVEL の上下限が逆です。',False
        if not lo<=level<=hi and not (obstacle and settings.get('obst_bypass')):
            return False,f'表示 LEVEL {level} は範囲 {lo}〜{hi} の外です。',False
    tube=bool(settings.get('tube')) and str(attrs.get('TUFLA','')).upper()=='TRUE'
    centre=bool(settings.get('cl')) and str(attrs.get('CLFLA','')).upper()=='TRUE'
    routes=[name for name,active in (('TUBE',tube),('CL',centre),('OBST',obstacle)) if active]
    return (True,' / '.join(routes),soft) if routes else (False,'TUBE・CL・OBST の表示条件を満たしていません。',False)


def edit(view):
    settings=view.representation_settings()
    fields=[('tube','TUBE', 'ON' if settings['tube'] else 'OFF',['ON','OFF']),
            ('cl','CL','ON' if settings['cl'] else 'OFF',['ON','OFF']),
            ('obst','OBST','ON' if settings['obst'] else 'OFF',['ON','OFF']),
            ('level','表示 LEVEL（整数）',str(settings['level']),None),
            ('policy','OBST と LEVEL の比較条件','OBST を優先' if settings['obst_bypass'] else 'LEVEL 範囲を適用',['LEVEL 範囲を適用','OBST を優先'])]
    def apply(values):
        if not re.fullmatch(r'[+-]?\d+',str(values['level']).strip()):raise ValueError('表示 LEVEL は整数です。')
        view.rep_options={key:values[key]=='ON' for key in ('tube','cl','obst')}
        view.rep_options.update(level=int(values['level']),obst_bypass=values['policy']=='OBST を優先')
        view.representation_mode.set('属性確認');view.representation_changed()
    view.editor.host.form('表示条件の確認（実機の既定値ではありません）',fields,apply)
