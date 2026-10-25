"""Shared preview toolbar and docked appearance panel."""
import tkinter as tk
from tkinter import ttk


def build(view, row):
    bar=ttk.Frame(view);bar.grid(row=row,column=0,columnspan=2,sticky='ew',pady=(0,8))
    view.toolbar=bar
    ttk.Label(bar,text='視点',style='Muted.TLabel').grid(row=0,column=0,padx=(0,6))
    group=ttk.Frame(bar);group.grid(row=0,column=1,sticky='w')
    view.view_buttons={}
    for label in ('立体','XY','XZ','YZ'):
        b=ttk.Radiobutton(group,text=label,variable=view.view,value=label,command=view.view_changed,style='Preview.Toolbutton')
        b.pack(side='left',padx=(0,2));view.view_buttons[label]=b
    view.fit_button=ttk.Button(bar,text='全体表示',command=view.fit_all,style='AttributeTool.TButton')
    view.fit_button.grid(row=0,column=2,padx=4)
    actions=ttk.Frame(bar);actions.grid(row=0,column=3,sticky='e');bar.columnconfigure(3,weight=1)
    view.details_button=ttk.Button(actions,text='表示設定',command=view.open_details,style='AttributeTool.TButton');view.details_button.pack(side='left')
    view.focus_button=ttk.Button(actions,text='拡大',command=lambda:focus(view),style='AttributeTool.TButton');view.focus_button.pack(side='left',padx=(4,0))
    def reflow(event):
        if event.width<490:
            group.grid(row=0,column=1,columnspan=3,sticky='w')
            view.fit_button.grid(row=1,column=0,columnspan=2,sticky='w',pady=(4,0))
            actions.grid(row=1,column=2,columnspan=2,sticky='e',pady=(4,0))
        else:
            group.grid(row=0,column=1,columnspan=1,sticky='w')
            view.fit_button.grid(row=0,column=2,columnspan=1,pady=0)
            actions.grid(row=0,column=3,columnspan=1,sticky='e',pady=0)
    bar.bind('<Configure>',reflow)
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
