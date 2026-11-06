"""Preview-only colours, never exported as catalogue attributes."""
import re
import tkinter as tk
from tkinter import ttk, colorchooser

DEFAULTS=dict(background='#f6f8fc',grid='#e9eef6',model='#cfdeed',outline='#58799b',
              points='#167b73',selected='#2864dc',negative='#c7812e',dimension='#ff0000')
LABELS=dict(background='背景',grid='グリッド',model='モデル',outline='輪郭線',
            points='ポイント',selected='選択中',negative='負形状',dimension='寸法文字')


def normalize(values):
    if not isinstance(values,dict):raise ValueError('表示色の形式が不正です。')
    result=dict(DEFAULTS)
    for key in DEFAULTS:
        value=values.get(key,result[key])
        if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):
            raise ValueError('表示色は#RRGGBB形式で指定してください。')
        result[key]=value.lower()
    return result


def build(view):
    view.colors={key:tk.StringVar(view,value=value) for key,value in DEFAULTS.items()}
    ttk.Label(view.settings_content,text='表示色',style='Muted.TLabel').pack(anchor='w',pady=(8,3))
    view.color_swatches={}
    keys=('background','grid','points','selected')
    if hasattr(view,'actual'):keys=tuple(DEFAULTS)
    for key in keys:
        row=ttk.Frame(view.settings_content);row.pack(fill='x',pady=2)
        swatch=tk.Label(row,width=2,background=DEFAULTS[key],relief='solid',borderwidth=1)
        swatch.pack(side='left',padx=(0,5));view.color_swatches[key]=swatch
        ttk.Button(row,text=LABELS[key],command=lambda k=key:choose(view,k),style='AttributeTool.TButton').pack(side='left',fill='x',expand=True)
    ttk.Button(view.settings_content,text='標準色に戻す',command=lambda:reset(view),style='AttributeTool.TButton').pack(fill='x',pady=(4,0))


def get(view,key):return view.colors[key].get()


def apply(view,values):
    for key,value in normalize(values).items():
        view.colors[key].set(value)
        if key in view.color_swatches:view.color_swatches[key].configure(background=value)
    view.editor.host.preview_color_settings={key:var.get() for key,var in view.colors.items()}


def choose(view,key):
    result=colorchooser.askcolor(color=get(view,key),parent=view.winfo_toplevel(),title=LABELS[key]+'の色')
    if not result or not result[1]:return
    values={name:var.get() for name,var in view.colors.items()};values[key]=result[1]
    apply(view,values);view.redraw()


def reset(view):
    apply(view,DEFAULTS);view.redraw()
