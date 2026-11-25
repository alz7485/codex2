"""Dark desktop theme and small vector icons, with no extra runtime assets."""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk

BG='#090c11'
PANEL='#111720'
TEXT='#f1f5f9'
MUTED='#97a6b8'
ACCENT='#69e2cd'

def install(root):
    root.configure(background=BG)
    for option,value in {'Background':BG,'Foreground':TEXT,'insertBackground':TEXT,
                         'selectBackground':'#245951','selectForeground':TEXT,
                         'Listbox.background':PANEL,'Listbox.foreground':TEXT}.items():
        root.option_add('*'+option,value)
    style=ttk.Style(root)
    style.theme_use('clam')
    style.configure('.',font=('Yu Gothic UI',9),background=BG,foreground=TEXT,fieldbackground=PANEL,
                    bordercolor='#293340',lightcolor='#293340',darkcolor='#293340',focuscolor=ACCENT)
    style.configure('TFrame',background=BG)
    style.configure('TLabel',background=BG,foreground=TEXT)
    style.configure('Muted.TLabel',foreground=MUTED)
    style.configure('Title.TLabel',font=('Segoe UI',20,'bold'))
    style.configure('Section.TLabel',font=('Segoe UI',9,'bold'),foreground=ACCENT)
    style.configure('TButton',background='#1a2430',foreground=TEXT,padding=(10,7),borderwidth=1,anchor='center')
    style.map('TButton',background=[('disabled','#111720'),('pressed','#28584f'),('active','#263847')],
              foreground=[('disabled','#667384')],bordercolor=[('focus',ACCENT),('active','#506779')])
    style.configure('Accent.TButton',background='#69e2cd',foreground='#071410',font=('Yu Gothic UI',9,'bold'))
    style.map('Accent.TButton',background=[('pressed','#39ac98'),('active','#93f0df')],foreground=[('disabled','#55736d'),('!disabled','#071410')])
    style.configure('Card.TButton',background=PANEL,padding=(5,5),font=('Yu Gothic UI',9),borderwidth=1)
    style.map('Card.TButton',background=[('selected','#173b38'),('active','#1d2c39')],
              bordercolor=[('selected',ACCENT),('focus',ACCENT),('active','#647889')],
              foreground=[('selected','#ffffff'),('!disabled',TEXT)])
    style.configure('TCheckbutton',background=BG,foreground=TEXT,indicatorbackground=PANEL,indicatormargin=6,padding=(0,5))
    style.map('TCheckbutton',background=[('active',BG)],foreground=[('disabled','#667384')],
              indicatorbackground=[('selected',ACCENT),('active','#354858')])
    style.configure('TRadiobutton',background=BG,foreground=TEXT,indicatorbackground=PANEL,padding=(0,3))
    style.map('TRadiobutton',background=[('active',BG)],indicatorbackground=[('selected',ACCENT)])
    for name in ('TCombobox','TSpinbox','TEntry'):
        style.configure(name,fieldbackground=PANEL,background='#1a2430',foreground=TEXT,arrowcolor=TEXT,padding=5)
        style.map(name,fieldbackground=[('readonly',PANEL),('disabled',BG)],foreground=[('disabled','#667384'),('readonly',TEXT)],selectbackground=[('readonly','#245951')],selectforeground=[('readonly',TEXT)])
    style.configure('Horizontal.TScale',background=BG,troughcolor='#263443',sliderlength=15,sliderthickness=13)
    style.configure('Vertical.TScrollbar',background='#304252',troughcolor=BG,arrowcolor=TEXT)
    style.configure('TSeparator',background='#293340')
    def caption():
        try:
            import ctypes
            hwnd=ctypes.windll.user32.GetParent(root.winfo_id())
            value=ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd,20,ctypes.byref(value),ctypes.sizeof(value))
        except (AttributeError,OSError):
            pass
    root.after_idle(caption)


def icon(master,name,color=TEXT,size=16):
    im=Image.new('RGBA',(64,64));d=ImageDraw.Draw(im)
    c=color;w=5
    if name=='play':d.polygon([(21,12),(52,32),(21,52)],fill=c)
    elif name=='restore':
        d.arc((12,12,53,53),-70,235,fill=c,width=w);d.line((12,12,12,30,30,30),fill=c,width=w)
    elif name=='check':d.line((12,33,26,47,53,16),fill=c,width=7)
    elif name=='power':
        d.arc((12,12,52,54),-55,235,fill=c,width=w);d.line((32,6,32,33),fill=c,width=w)
    elif name=='close':d.line((16,16,48,48),fill=c,width=w);d.line((48,16,16,48),fill=c,width=w)
    elif name=='settings':
        for y in (15,32,49):d.line((8,y,56,y),fill=c,width=4)
        for x,y in ((23,15),(42,32),(26,49)):d.ellipse((x-6,y-6,x+6,y+6),fill=c)
    else:
        d.rectangle((13,13,51,51),outline=c,width=4);d.line((21,26,43,26),fill=c,width=4);d.line((21,38,39,38),fill=c,width=4)
    return ImageTk.PhotoImage(im.resize((size,size),Image.Resampling.LANCZOS),master=master)


def button(parent,text,command=None,name='settings',**kw):
    picture=icon(parent,name,'#071410' if kw.get('style')=='Accent.TButton' else TEXT)
    widget=ttk.Button(parent,text=text,image=picture,compound='left',command=command,**kw)
    widget.icon=picture
    return widget


def thumbnail(master,path):
    from cursor_art import load_sprite
    try:
        sheet=path.parents[2]/'飛行アニメ'/path.parent.name/(path.stem+'.待機回転.png')
        if sheet.is_file():
            with Image.open(sheet) as image:source=image.convert('RGBA').crop((0,0,144,144))
        else:source=load_sprite(path)
        box=source.getbbox()
        if box:source=source.crop(box)
        if max(source.size)<48:source=source.resize((source.width*2,source.height*2),Image.Resampling.NEAREST)
        source.thumbnail((68,44),Image.Resampling.LANCZOS)
        im=Image.new('RGBA',(100,50))
        im.alpha_composite(source,((100-source.width)//2,(50-source.height)//2))
    except (OSError,ValueError):
        im=Image.new('RGBA',(100,50));d=ImageDraw.Draw(im);d.polygon([(32,12),(66,29),(43,34),(38,49)],outline=ACCENT,width=2)
    return ImageTk.PhotoImage(im,master=master)
