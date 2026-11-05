"""Extensible SPEC registration table; additional columns preserve literal input."""
import re
from decimal import Decimal, InvalidOperation
import tkinter as tk
from tkinter import ttk
from . import project

# A single registry controls table headings, editing and legacy defaults.
COLUMNS = (
    ('name', '名前 / NAME', 105), ('type', '部品種別 / TYPE', 85),
    ('bore1', '呼び径1 / PBOR1', 85), ('bore2', '呼び径2 / PBOR2', 85),
    ('angle', '角度 / ANGLE', 78), ('height', '高さ / HEIGHT', 78),
    ('text', 'TEXT', 110), ('styp', '種別 / STYP', 78), ('shop', '工場製作 / SHOP', 82), ('scom_id', 'カタログ部品 / CATREF', 150),
    ('detail_id', '説明 / DETAIL', 115), ('prop_id', '物性 / 参照', 115),
    ('description', '説明文', 120), ('sdte_id', 'SDTE（従来参照）', 110),
    ('smte_id', '材質 / SMTE', 100),
)
REFERENCES = dict(scom_id='scoms', detail_id='catalog_details', prop_id='catalog_props',
                  sdte_id='texts', smte_id='texts')


def value(data, entry, key):
    if key in REFERENCES:
        return (project.get(data, REFERENCES[key], entry.get(key, '')) or {}).get('name', '未設定')
    return entry.get(key, '')


def build(host):
    finish_edit(host)
    area = ttk.Frame(host.content, padding=10)
    area.pack(fill='both', expand=True)
    bar = ttk.Frame(area); bar.pack(fill='x', pady=(0,8))
    for label, callback in (('SPEC情報', host.edit_spec), ('SPEC複製', host.duplicate_spec),
                            ('SPEC削除', host.delete_spec), ('＋ SCOMから追加', lambda:add_scoms(host)),
                            ('行複製', host.duplicate_spec_entry), ('行削除', host.delete_spec_entry)):
        ttk.Button(bar, text=label, command=callback,padding=(8,6,8,7)).pack(side='left', padx=2)
    from .project_actions import icon
    host.spec_preview_icon=icon(host,'preview',color='#2864dc')
    ttk.Button(bar, text='プレビューを別窓で表示',image=host.spec_preview_icon,compound='left', command=lambda:open_preview(host)).pack(side='right', padx=2)
    ttk.Button(bar, text='列設定', command=lambda:column_dialog(host),padding=(8,6,8,7)).pack(side='right', padx=2)
    spec = host.spec()
    if not spec:
        ttk.Button(area, text='＋ SPECを追加', command=host.add_spec).pack(pady=20)
        return
    ttk.Label(area, text=spec['name']+' / Rev.'+spec['revision'], style='Heading.TLabel').pack(anchor='w')
    filters = ttk.Frame(area); filters.pack(fill='x', pady=8)
    ttk.Label(filters, text='部品種類').pack(side='left')
    host.spec_type_filter = tk.StringVar(master=host, value='すべて')
    combo = ttk.Combobox(filters, textvariable=host.spec_type_filter, state='readonly',
                         values=['すべて']+sorted({e['type'] for e in spec['entries']}), width=16)
    combo.pack(side='left', padx=6)
    style=ttk.Style(host)
    style.configure('Spec.Treeview',font=(host.ui_font,9),rowheight=26)
    style.configure('Spec.Treeview.Heading',font=(host.ui_font,8,'bold'),padding=(3,3))
    style.configure('Spec.TEntry',font=(host.ui_font,9),padding=(2,0))
    style.configure('Spec.TCombobox',font=(host.ui_font,9),padding=(2,0))
    host.spec_table = host.table(area, COLUMNS, height=18)
    host.spec_table.configure(style='Spec.Treeview')
    host.spec_cell_hint=CellHint(host.spec_table)

    for key,_,_ in COLUMNS:
        host.spec_table.heading(key,command=lambda k=key:sort_column(host,k))
    host.spec_table_rules=host.spec_table.rules
    holder=host.spec_table.master
    for widget in holder.winfo_children():
        if isinstance(widget,ttk.Scrollbar):
            widget.bind('<ButtonPress-1>',lambda e:finish_edit(host),add='+')
            axis='x' if str(widget.cget('orient'))=='horizontal' else 'y'
            host.spec_table.configure(**{axis+'scrollcommand':lambda a,b,w=widget:(w.set(a,b),host.spec_table_rules.schedule())})
    for event in ('<MouseWheel>','<Button-4>','<Button-5>','<Configure>'):
        host.spec_table.bind(event,lambda e:finish_edit(host),add='+')
    combo.bind('<<ComboboxSelected>>', lambda e:populate(host))
    host.spec_table.bind('<<TreeviewSelect>>', host.spec_entry_select)
    host.spec_table.bind('<ButtonRelease-1>', lambda e:edit_cell(host,e))
    host.spec_table.bind('<Double-1>', lambda e:'break')
    host.spec_table.bind('<ButtonRelease-1>', lambda e:remember_widths(host), add='+')
    host.spec_tree = host.registered_browser.tree
    settings = host.data.get('spec_table_settings', {})
    for key, width in settings.get('widths', {}).items():
        if key in host.spec_table['columns'] and isinstance(width,int) and 65<=width<=1200:
            if settings.get('density_version')!=2:width=min(width,dict((k,w) for k,_,w in COLUMNS)[key])
            host.spec_table.column(key, width=width)
    visible = settings.get('visible', [c[0] for c in COLUMNS])
    visible = [c[0] for c in COLUMNS if c[0] in visible]
    host.spec_table.configure(displaycolumns=visible or [COLUMNS[0][0]])
    populate(host)


def populate(host):
    finish_edit(host)
    tree=host.spec_table
    selected=tree.selection()
    tree.delete(*tree.get_children())
    for entry in host.spec()['entries']:
        if host.spec_type_filter.get() not in ('すべて',entry['type']):continue
        tree.insert('', 'end', iid=entry['id'], values=[value(host.data,entry,c[0]) for c in COLUMNS])
    apply_sort(host)
    ids=tree.get_children()
    if ids:tree.selection_set(selected[0] if selected and selected[0] in ids else ids[0])
    host.spec_table_rules.schedule()
    host.update_spec_preview()



def sort_value(raw):
    """Numbers compare numerically; ranges/units remain literal natural text."""
    text=str(raw).strip()
    try:
        number=Decimal(text)
        if number.is_finite():return (0,number)
    except InvalidOperation:pass
    return (1,tuple((0,int(part)) if part.isdecimal() else (1,part.casefold())
                    for part in re.split(r'(\d+)',text) if part))


def sort_column(host,key):
    previous=getattr(host,'spec_sort',None)
    host.spec_sort=(key,not previous[1] if previous and previous[0]==key else False)
    populate(host)


def apply_sort(host):
    """Sort visible rows only: SPEC list order can affect default selection."""
    state=getattr(host,'spec_sort',None)
    tree=host.spec_table
    for key,label,_ in COLUMNS:
        suffix=(' ▼' if state[1] else ' ▲') if state and state[0]==key else ''
        tree.heading(key,text=label.split(' / ')[0]+suffix)
    if not state:return
    key,descending=state
    rows={e['id']:e for e in host.spec()['entries']}
    ids=list(tree.get_children())
    empty=lambda ident:not str(value(host.data,rows[ident],key)).strip() or (key in REFERENCES and not rows[ident].get(key))
    populated=[ident for ident in ids if not empty(ident)]
    blanks=[ident for ident in ids if empty(ident)]
    populated.sort(key=lambda ident:sort_value(value(host.data,rows[ident],key)),reverse=descending)
    for index,ident in enumerate(populated+blanks):tree.move(ident,'',index)


def remember_widths(host):
    widths={key:max(65,min(1200,host.spec_table.column(key,'width'))) for key,_,_ in COLUMNS}
    settings=host.data.setdefault('spec_table_settings',{})
    if settings.get('widths')!=widths:
        settings['widths']=widths;settings['density_version']=2;host.mark()


def column_dialog(host):
    if not hasattr(host,'spec_table') or not host.spec_table.winfo_exists():return
    win=tk.Toplevel(host);win.title('表示する列');win.transient(host)
    current=host.spec_table['displaycolumns'];variables={}
    for i,(key,label,_) in enumerate(COLUMNS):
        var=tk.BooleanVar(win,value=key in current);variables[key]=var
        ttk.Checkbutton(win,text=label,variable=var).grid(row=i//2,column=i%2,sticky='w',padx=12,pady=4)
    def apply():
        visible=[key for key,var in variables.items() if var.get()]
        if not visible:return
        host.spec_table.configure(displaycolumns=visible)
        host.data.setdefault('spec_table_settings',{})['visible']=visible
        host.spec_table_rules.schedule()
        host.mark();win.destroy()
    ttk.Button(win,text='適用',command=apply).grid(row=8,column=1,padx=12,pady=10)


def finish_edit(host,commit=True):
    editing=getattr(host,'spec_cell_edit',None)
    if editing is None:return True
    host.spec_cell_edit=None
    widget,var,entry,key,mapping=editing
    text=var.get()
    if commit:
        new=mapping.get(text,entry.get(key,'')) if mapping is not None else text
        if new!=entry.get(key,''):
            entry[key]=new;host.mark()
    if widget.winfo_exists():widget.destroy()
    tree=getattr(host,'spec_table',None)
    if tree is not None and tree.winfo_exists() and tree.exists(entry['id']):
        tree.item(entry['id'],values=[value(host.data,entry,c[0]) for c in COLUMNS])
        apply_sort(host);host.spec_table_rules.schedule()
        host.update_spec_preview()
    return True


def edit_cell(host,event):
    tree=host.spec_table
    if tree.identify_region(event.x,event.y)!='cell':return
    row=tree.identify_row(event.y);column=tree.identify_column(event.x)
    if not row or not column:return
    index=int(column[1:])-1
    display=tree['displaycolumns'];key=display[index]
    finish_edit(host)
    entry=next(e for e in host.spec()['entries'] if e['id']==row)
    tree.selection_set(row)
    box=tree.bbox(row,column)
    if not box:return
    mapping=None
    var=tk.StringVar(tree,value=entry.get(key,''))
    if key in REFERENCES:
        mapping={'未設定':''}
        for record in host.data.get(REFERENCES[key],[]):
            if key in ('sdte_id','smte_id') and record.get('type')!=key[:4].upper():continue
            label=record['name']
            if label in mapping:label+=' ['+record['id']+']'
            mapping[label]=record['id']
        current=entry.get(key,'')
        if current and current not in mapping.values():mapping['参照先不明：'+current]=current
        var.set(next((name for name,ident in mapping.items() if ident==current),'未設定'))
        widget=ttk.Combobox(tree,textvariable=var,values=list(mapping),state='readonly',style='Spec.TCombobox',font=(host.ui_font,9))
        widget.bind('<<ComboboxSelected>>',lambda e:finish_edit(host))
    else:
        widget=ttk.Entry(tree,textvariable=var,style='Spec.TEntry',font=(host.ui_font,9))
    host.spec_cell_edit=(widget,var,entry,key,mapping)
    widget.place(x=box[0],y=box[1],width=box[2],height=box[3])
    widget.lift();widget.focus_set()
    if mapping is None:widget.selection_range(0,'end')
    widget.bind('<Return>',lambda e:finish_edit(host))
    widget.bind('<Escape>',lambda e:finish_edit(host,False))
    def focus_out(event):
        def commit_if_outside():
            if getattr(host,'spec_cell_edit',None) is None or host.spec_cell_edit[0] is not widget:return
            focus=str(widget.tk.call('focus'))
            if focus==str(widget) or focus.startswith(str(widget)+'.'):return
            finish_edit(host)
        host.after_idle(commit_if_outside)
    widget.bind('<FocusOut>',focus_out)
    def next_cell(event):
        finish_edit(host)
        keys=list(tree['displaycolumns']);next_index=(keys.index(key)+(-1 if event.state & 1 else 1))%len(keys)
        bounds=tree.bbox(row,'#'+str(next_index+1))
        if bounds:
            from types import SimpleNamespace
            edit_cell(host,SimpleNamespace(x=bounds[0]+5,y=bounds[1]+5))
        return 'break'
    widget.bind('<Tab>',next_cell)
    widget.bind('<ISO_Left_Tab>',next_cell)


def open_preview(host):
    win=getattr(host,'spec_preview_window',None)
    if win is not None and win.winfo_exists():win.deiconify();win.lift();return
    from .catalog_geometry_preview import CatalogGeometryPreview
    win=tk.Toplevel(host);win.title('SPEC 選択行のプレビュー');win.geometry('960x720');win.minsize(640,480)
    host.spec_preview_window=win
    host.spec_preview_label=ttk.Label(win,text='',style='Heading.TLabel',padding=8)
    host.spec_preview_label.pack(fill='x')
    host.spec_preview=CatalogGeometryPreview(host,win)
    host.update_spec_preview()


def update_preview(host):
    win=getattr(host,'spec_preview_window',None)
    if win is None or not win.winfo_exists():return
    entry=host.spec_entry()
    scom=project.get(host.data,'scoms',(entry or {}).get('scom_id',''))
    host.spec_preview_label.configure(text=(entry.get('name') or (scom or {}).get('name','登録行')) if entry else '登録行を選択してください')
    host.spec_preview.load(host.data,scom)


def add_scoms(host):
    if not host.spec():return
    win=tk.Toplevel(host);win.title('SCOMから登録行を追加');win.geometry('560x440');win.transient(host)
    ttk.Label(win,text='Ctrl / Shiftで複数選択して追加',padding=10).pack(anchor='w')
    tree=host.table(win,[('name','SCOM',300),('size','サイズ',100)])
    tree.configure(selectmode='extended')
    for scom in host.data['scoms']:
        tree.insert('', 'end', iid=scom['id'],values=(scom['name'],scom.get('size','')))
    def apply():
        ids=tree.selection()
        if not ids:return
        if len(host.spec()['entries'])+len(ids)>5000:return
        for ident in ids:
            record=project.add_spec_entry(host.data,host.spec(),ident)
            scom=project.get(host.data,'scoms',ident)
            record['type']=scom.get('attrs',{}).get('GTYP','')
        host.mark();win.destroy();host.render_page()
    ttk.Button(win,text='選択したSCOMを追加',command=apply).pack(anchor='e',padx=10,pady=10)


class CellHint:
    """Full cell text on hover for compact columns; never edits data."""
    def __init__(self,tree):
        self.tree=tree;self.root=tree._root();self.cell=None;self.pending=None;self.window=None
        tree.bind('<Motion>',self.motion,add='+')
        for event in ('<Leave>','<ButtonPress>','<MouseWheel>','<Destroy>'):
            tree.bind(event,lambda e:self.hide(),add='+')
    def motion(self,event):
        region=self.tree.identify_region(event.x,event.y)
        if region not in ('cell','heading'):self.hide();return
        row=self.tree.identify_row(event.y) if region=='cell' else '@heading'
        col=self.tree.identify_column(event.x)
        if not col or col=='#0':self.hide();return
        cell=(row,col)
        if cell==self.cell:return
        self.hide();self.cell=cell;self.position=(event.x_root+12,event.y_root+18)
        self.pending=self.root.after(500,self.show)
    def show(self):
        self.pending=None
        if not self.tree.winfo_exists() or not self.cell:return
        row,col=self.cell
        key=self.tree['displaycolumns'][int(col[1:])-1]
        if row=='@heading':text=next(label for k,label,_ in COLUMNS if k==key)
        else:
            if not self.tree.exists(row):return
            text=self.tree.set(row,key)
        if not text:return
        self.window=tk.Toplevel(self.tree);self.window.overrideredirect(True)
        ttk.Label(self.window,text=text,wraplength=480,padding=6,relief='solid',borderwidth=1).pack()
        self.window.update_idletasks()
        x,y=self.position
        x=max(0,min(x,self.tree.winfo_screenwidth()-self.window.winfo_reqwidth()-8))
        y=max(0,min(y,self.tree.winfo_screenheight()-self.window.winfo_reqheight()-8))
        self.window.geometry(f'+{x}+{y}')
    def hide(self):
        if self.pending is not None:self.root.after_cancel(self.pending);self.pending=None
        if self.window is not None:self.window.destroy();self.window=None
        self.cell=None
