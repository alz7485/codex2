"""Shared preview toolbar and docked appearance panel."""
import tkinter as tk
from tkinter import ttk
from . import preview_icons


def build(view, row):
    view.toolbar=ttk.Frame(view);view.toolbar.grid(row=row,column=0,columnspan=2,sticky='ew',pady=(0,6))
    # Keep a single button row; narrow panes scroll instead of adding rows.
    viewport=tk.Canvas(view.toolbar,width=1,height=36,highlightthickness=0,bg='white')
    viewport.pack(fill='x')
    bar=ttk.Frame(viewport);window=viewport.create_window(0,0,anchor='nw',window=bar)
    toolbar_scroll=ttk.Scrollbar(view.toolbar,orient='horizontal',command=viewport.xview)
    view.toolbar_viewport=viewport;view.toolbar_scroll=toolbar_scroll
    viewport.configure(xscrollcommand=toolbar_scroll.set)
    def reflow(event=None):
        width=bar.winfo_reqwidth();viewport.configure(height=bar.winfo_reqheight(),scrollregion=(0,0,width,bar.winfo_reqheight()))
        viewport.itemconfigure(window,width=max(width,viewport.winfo_width()))
        if viewport.winfo_width()<width:toolbar_scroll.pack(fill='x')
        else:toolbar_scroll.pack_forget();viewport.xview_moveto(0)
    bar.bind('<Configure>',reflow);viewport.bind('<Configure>',reflow)
    ttk.Label(bar,text='視点',style='Muted.TLabel').pack(side='left',padx=(0,4))
    view.preview_icons={key:preview_icons.create(view,key) for key in ('立体','XY','XZ','YZ')}
    view.view_buttons={}
    for label in ('立体','XY','XZ','YZ'):
        b=ttk.Radiobutton(bar,text=label,image=view.preview_icons[label],compound='left',variable=view.view,value=label,command=view.view_changed,style='Preview.Toolbutton')
        b.pack(side='left',padx=(0,2));view.view_buttons[label]=b
    view.fit_button=ttk.Button(bar,text='全体表示',command=view.fit_all,style='AttributeTool.TButton')
    view.fit_button.pack(side='left',padx=(4,2))
    view.details_button=ttk.Button(bar,text='表示設定',command=view.open_details,style='AttributeTool.TButton');view.details_button.pack(side='left',padx=2)
    view.focus_button=ttk.Button(bar,text='拡大',command=lambda:focus(view),style='AttributeTool.TButton');view.focus_button.pack(side='left',padx=2)
    view.body=ttk.Frame(view);view.body.grid(row=3,column=0,columnspan=2,sticky='nsew')
    view.body.columnconfigure(0,weight=1);view.body.rowconfigure(0,weight=1)
    view.details=ttk.Frame(view.body,padding=(10,8),style='Card.TFrame')
    title=ttk.Frame(view.details);title.pack(fill='x',pady=(0,8))
    ttk.Label(title,text='表示設定',style='Heading.TLabel').pack(side='left')
    ttk.Button(title,text='×',width=2,command=view.close_details,style='AttributeTool.TButton').pack(side='right')
    scroll_area=ttk.Frame(view.details);scroll_area.pack(fill='both',expand=True)
    view.settings_viewport=tk.Canvas(scroll_area,width=190,height=1,highlightthickness=0,bg='white')
    view.settings_viewport.pack(side='left',fill='both',expand=True)
    scroll=ttk.Scrollbar(scroll_area,orient='vertical',command=view.settings_viewport.yview);scroll.pack(side='right',fill='y')
    view.settings_viewport.configure(yscrollcommand=scroll.set)
    view.settings_content=ttk.Frame(view.settings_viewport)
    win=view.settings_viewport.create_window(0,0,anchor='nw',window=view.settings_content)
    view.settings_content.bind('<Configure>',lambda _:view.settings_viewport.configure(scrollregion=view.settings_viewport.bbox('all')))
    view.settings_viewport.bind('<Configure>',lambda e:view.settings_viewport.itemconfigure(win,width=e.width))



def open_panel(view):
    if view.details.winfo_ismapped():view.close_details();return
    view.cancel(redraw=False) if hasattr(view,'actual') else view.cancel()
    view.auto_focus=view.body.winfo_width()<520 and not getattr(view,'focused',False)
    if view.auto_focus:focus(view)
    view.details.grid(row=0,column=1,sticky='ns',padx=(8,0))
    view.details_button.configure(text='設定を閉じる')
    view.editor.host.after_idle(view.redraw)


def close_panel(view):
    view.details.grid_remove()
    if getattr(view,'auto_focus',False) and getattr(view,'focused',False):focus(view)
    view.auto_focus=False
    view.details_button.configure(text='表示設定');view.editor.host.after_idle(view.redraw)


def focus(view):
    e=view.editor;split=e.main_split
    if getattr(view,'focused',False):
        split.insert(0,e.element_pane,weight=1);split.add(e.attribute_pane,weight=0)
        positions=view.focus_positions
        def restore():
            if split.winfo_exists():
                # Let reinserted panes settle before restoring their dividers.
                split.update_idletasks()
                for i,pos in enumerate(positions):split.sashpos(i,pos)
        view.editor.host.after_idle(restore);view.focused=False;view.focus_button.configure(text='拡大')
    else:
        view.focus_positions=[split.sashpos(i) for i in (0,1)]
        split.forget(e.element_pane);split.forget(e.attribute_pane)
        view.focused=True;view.focus_button.configure(text='戻す')


def zoom_buttons(view):
    box=ttk.Frame(view.body)
    box.grid(row=0,column=0,sticky='se',padx=12,pady=12)
    for text,factor in (('+',1.12),('−',1/1.12)):
        ttk.Button(box,text=text,width=2,command=lambda f=factor:view.zoom(f),style='AttributeTool.TButton').pack()
