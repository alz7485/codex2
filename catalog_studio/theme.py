"""Shared desktop appearance; presentation only, with no catalogue rules."""
from tkinter import ttk

ACCENT='#2864dc'
ACCENT_HOVER='#1d52bd'
INK='#26354b'
MUTED='#718096'
CHROME='#152337'
NAV='#1d2e45'
WORKSPACE='#eef2f7'
SURFACE='#ffffff'
SUBTLE='#f6f8fc'
BORDER='#cbd5e2'
RULE='#b8c6d8'
SELECT='#eaf1ff'


def apply(root,family):
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.',font=(family,10),background=SURFACE,foreground=INK)
    style.configure('TFrame',background=SURFACE)
    style.configure('Workspace.TFrame',background=WORKSPACE)
    style.configure('Sidebar.TFrame',background=SUBTLE)
    style.configure('Card.TFrame',background=SURFACE,borderwidth=1,relief='solid',bordercolor=BORDER)
    style.configure('Header.TFrame',background=CHROME)
    style.configure('Status.TFrame',background=WORKSPACE)
    style.configure('HeaderTitle.TLabel',background=CHROME,foreground='white',font=(family,17,'bold'))
    style.configure('HeaderMeta.TLabel',background=CHROME,foreground='#a6b7ce',font=(family,9))
    style.configure('Sidebar.TLabel',background=SUBTLE,foreground=MUTED,font=(family,9))
    style.configure('SidebarTitle.TLabel',background=SUBTLE,foreground=INK,font=(family,11,'bold'))
    style.configure('Status.TLabel',background=WORKSPACE,foreground=MUTED,font=(family,9))
    style.configure('Heading.TLabel',foreground=INK,font=(family,12,'bold'))
    style.configure('PaneTitle.TLabel',font=(family,11,'bold'))
    style.configure('Title.TLabel',font=(family,16,'bold'))
    style.configure('Muted.TLabel',foreground=MUTED,font=(family,9))
    style.configure('AttributeMeaning.TLabel',foreground=MUTED,font=(family,9))
    style.configure('TButton',padding=(12,7),background=SURFACE,foreground=INK,bordercolor=BORDER,lightcolor=SURFACE,darkcolor=SURFACE,relief='flat',borderwidth=1,focusthickness=0)
    style.map('TButton',background=[('disabled',SUBTLE),('pressed',SELECT),('active',SUBTLE)],foreground=[('disabled','#9aa6b7')],bordercolor=[('focus',ACCENT),('active','#a7b8cd')])
    style.configure('Compact.TButton',padding=(8,4),font=(family,9))
    style.configure('Compact.Primary.TButton',padding=(7,3),width=0,font=(family,9))
    style.configure('Primary.TButton',background=ACCENT,foreground='white',bordercolor=ACCENT,lightcolor=ACCENT,darkcolor=ACCENT)
    style.map('Primary.TButton',background=[('disabled','#aec3e8'),('pressed',ACCENT_HOVER),('active',ACCENT_HOVER)],foreground=[('disabled','#eef3fb'),('!disabled','white')],bordercolor=[('focus','#83a9f6'),('!focus',ACCENT)])
    style.configure('Header.TButton',background=CHROME,foreground='#e0e7f2',bordercolor='#435369',lightcolor=CHROME,darkcolor=CHROME,padding=(13,6))
    style.map('Header.TButton',background=[('pressed',NAV),('active',NAV)],foreground=[('!disabled','#e0e7f2')],bordercolor=[('focus','#83a9f6'),('!focus','#435369')])
    style.configure('TEntry',padding=(7,5),fieldbackground=SURFACE,foreground=INK,bordercolor=BORDER,lightcolor=SURFACE,darkcolor=SURFACE,insertcolor=ACCENT)
    style.map('TEntry',bordercolor=[('focus',ACCENT),('disabled',BORDER)],fieldbackground=[('readonly',SUBTLE)])
    style.configure('TCombobox',padding=(6,4),fieldbackground=SURFACE,background=SUBTLE,foreground=INK,bordercolor=BORDER,lightcolor=SURFACE,darkcolor=SURFACE,arrowcolor=MUTED,arrowsize=12)
    style.map('TCombobox',fieldbackground=[('readonly',SURFACE)],foreground=[('readonly',INK)],selectbackground=[('readonly',SELECT)],selectforeground=[('readonly',INK)],bordercolor=[('focus',ACCENT)])
    style.configure('TSpinbox',padding=(6,4),fieldbackground=SURFACE,bordercolor=BORDER,lightcolor=SURFACE,darkcolor=SURFACE,arrowcolor=MUTED)
    style.map('TSpinbox',bordercolor=[('focus',ACCENT)])
    style.configure('TLabelframe',bordercolor=BORDER,relief='solid',borderwidth=1)
    style.configure('TLabelframe.Label',foreground=MUTED,font=(family,9,'bold'))
    style.configure('Preview.Toolbutton',padding=(6,4),background=SUBTLE,foreground=MUTED,bordercolor=BORDER,lightcolor=SUBTLE,darkcolor=SUBTLE,relief='flat',font=(family,9),focusthickness=0)
    style.map('Preview.Toolbutton',background=[('selected',SELECT),('active','#f0f4fb')],foreground=[('selected',ACCENT),('active',INK)],bordercolor=[('focus',ACCENT),('selected','#afc5ee')])
    style.configure('Treeview',rowheight=34,background=SURFACE,fieldbackground=SURFACE,foreground=INK,bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER,relief='solid',borderwidth=1)
    style.configure('Treeview.Heading',background=SUBTLE,foreground=MUTED,padding=(7,8),font=(family,9,'bold'),relief='flat',bordercolor=BORDER,lightcolor=SUBTLE,darkcolor=SUBTLE)
    style.map('Treeview',background=[('selected',SELECT)],foreground=[('selected',ACCENT)])
    style.map('Treeview.Heading',background=[('active',SELECT)])
    style.configure('TPanedwindow',background=WORKSPACE)
    style.configure('Sash',sashthickness=8,background=WORKSPACE,gripcount=0)
    for name in ('Horizontal.TScrollbar','Vertical.TScrollbar'):
        style.configure(name,background='#c5cfdd',troughcolor=SUBTLE,bordercolor=SUBTLE,lightcolor='#c5cfdd',darkcolor='#c5cfdd',arrowcolor=MUTED,arrowsize=11,relief='flat',borderwidth=0)
        style.map(name,background=[('active','#a6b6ca')])
    style.configure('TNotebook',background=WORKSPACE,borderwidth=0,tabmargins=(0,0,0,0))
    style.configure('TNotebook.Tab',padding=(12,7),background=SUBTLE,foreground=MUTED)
    style.map('TNotebook.Tab',background=[('selected',SURFACE)],foreground=[('selected',ACCENT)])
    for key,value in (('background',SURFACE),('foreground',INK),('activeBackground',SELECT),('activeForeground',ACCENT),('relief','solid'),('borderWidth',1),('font',(family,10))):
        root.option_add('*Menu.'+key,value)
    root.option_add('*Listbox.highlightThickness',1)
    root.option_add('*Listbox.highlightColor',ACCENT)
    root.option_add('*Listbox.highlightBackground',BORDER)
    return style
