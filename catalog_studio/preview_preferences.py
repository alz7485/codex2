"""User-level preview defaults, separate from catalogue/project data."""
import copy
import json
import math
import os
from pathlib import Path
import tempfile
import weakref
from tkinter import ttk

FACTORY=dict(version=1,shared=dict(show_grid=True,show_axes=True,show_labels=True),
             point=dict(show_relations=True),geometry=dict(render_mode='ソリッド',transparency=0,
             show_points=True,show_negative=True,representation_mode='全形状',
             rep_options=dict(tube=True,cl=False,obst=False,level=0,obst_bypass=False)))


def settings_path():
    if os.name=='nt':base=Path(os.environ.get('APPDATA') or Path.home()/'AppData'/'Roaming')
    else:base=Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')
    return base/'CatalogStudio'/'preview-defaults.json'


def normalize(value):
    if not isinstance(value,dict) or value.get('version')!=1:raise ValueError('表示初期値の形式が不正です。')
    result=copy.deepcopy(FACTORY)
    for section in ('shared','point','geometry'):
        part=value.get(section,{})
        if not isinstance(part,dict):raise ValueError('表示初期値の形式が不正です。')
        result[section].update({k:copy.deepcopy(part[k]) for k in result[section] if k in part})
    for part,keys in ((result['shared'],('show_grid','show_axes','show_labels')),(result['point'],('show_relations',)),(result['geometry'],('show_points','show_negative'))):
        if any(type(part[k]) is not bool for k in keys):raise ValueError('表示初期値のON/OFFが不正です。')
    g=result['geometry'];v=g['transparency'];rep=g['rep_options']
    if g['render_mode'] not in ('ソリッド','ワイヤー','面＋線') or g['representation_mode'] not in ('全形状','属性確認'):raise ValueError('描画方式が不正です。')
    if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=100:raise ValueError('透過率が不正です。')
    if not isinstance(rep,dict) or any(type(rep.get(k)) is not bool for k in ('tube','cl','obst','obst_bypass')) or type(rep.get('level')) is not int:raise ValueError('表示条件が不正です。')
    return result


def load():
    path=settings_path()
    try:
        if path.stat().st_size>65536:raise ValueError('設定ファイルが大きすぎます。')
        return normalize(json.loads(path.read_text(encoding='utf-8'))),''
    except FileNotFoundError:return copy.deepcopy(FACTORY),''
    except (OSError,ValueError,UnicodeError) as exc:return copy.deepcopy(FACTORY),'初期値を読み込めないため標準設定を使用：'+str(exc)


def save(value):
    value=normalize(value);path=settings_path();path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix=path.name+'.',suffix='.tmp',delete=False) as out:
            temporary=Path(out.name);json.dump(value,out,ensure_ascii=False,indent=2);out.flush();os.fsync(out.fileno())
        os.replace(temporary,path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def root_for(view):
    root=view._root()
    if not hasattr(root,'_preview_defaults'):
        root._preview_defaults,root._preview_defaults_error=load();root._preview_views=weakref.WeakSet();root._preview_hosts=weakref.WeakSet()
    return root


def apply(view,values):
    if hasattr(view,'actual'):view.cancel(redraw=False)
    else:view.cancel()
    for key,value in values['shared'].items():
        if hasattr(view,key):getattr(view,key).set(value)
    if hasattr(view,'actual'):
        for key,value in values['geometry'].items():
            if key=='rep_options':view.rep_options=copy.deepcopy(value)
            elif hasattr(view,key):getattr(view,key).set(value)
        host=view.editor.host;g=values['geometry']
        host.gmset_display_settings=dict(mode=g['render_mode'],transparency=g['transparency'])
        host.gmset_representation=dict(g['rep_options'],mode=g['representation_mode'])
    else:view.show_relations.set(values['point']['show_relations'])
    view.redraw()


def attach(view):
    root=root_for(view);root._preview_views.add(view);root._preview_hosts.add(view.editor.host);values=copy.deepcopy(root._preview_defaults)
    if hasattr(view,'actual'):
        host=view.editor.host;cached=getattr(host,'gmset_display_settings',{})
        for source,target in (('mode','render_mode'),('transparency','transparency')):
            if source in cached:values['geometry'][target]=cached[source]
        rep=getattr(host,'gmset_representation',{})
        values['geometry']['rep_options'].update({k:v for k,v in rep.items() if k!='mode'})
        if 'mode' in rep:values['geometry']['representation_mode']=rep['mode']
    apply(view,values)
    footer=ttk.Frame(view.details);footer.pack(side='bottom',fill='x',pady=(8,0))
    view.defaults_button=ttk.Button(footer,text='現在の設定を初期値にする',command=lambda:save_current(view),style='AttributeTool.TButton')
    view.defaults_button.pack(fill='x',pady=(12,4))
    view.defaults_notice=ttk.Label(footer,text=root._preview_defaults_error.strip(),wraplength=185,style='Muted.TLabel')
    view.defaults_notice.pack(fill='x')


def save_current(view):
    root=root_for(view);values=copy.deepcopy(root._preview_defaults)
    values['shared']={key:getattr(view,key).get() for key in FACTORY['shared']}
    if hasattr(view,'actual'):
        values['geometry']={key:getattr(view,key).get() for key in FACTORY['geometry'] if key!='rep_options'}
        values['geometry']['rep_options']=copy.deepcopy(view.rep_options)
    else:values['point']['show_relations']=view.show_relations.get()
    try:save(values)
    except (OSError,ValueError) as exc:
        view.defaults_notice.configure(text='保存できませんでした：'+str(exc));return False
    root._preview_defaults=values;root._preview_defaults_error=''
    for host in list(root._preview_hosts):
        if host.winfo_exists():
            g=values['geometry'];host.gmset_display_settings=dict(mode=g['render_mode'],transparency=g['transparency'])
            host.gmset_representation=dict(g['rep_options'],mode=g['representation_mode'])
    for other in list(root._preview_views):
        if other.winfo_exists():apply(other,values)
    view.defaults_notice.configure(text='全プレビューに適用しました。次回起動時も使用します。')
    return True
