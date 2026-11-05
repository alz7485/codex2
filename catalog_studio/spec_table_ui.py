"""Extensible SPEC registration table; additional columns preserve literal input."""
import tkinter as tk
from tkinter import ttk
from . import project

# A single registry controls table headings, editing and legacy defaults.
COLUMNS = (
    ('name', '名前 / NAME', 140), ('type', '部品種別 / TYPE', 120),
    ('bore1', '呼び径1 / PBOR1', 125), ('bore2', '呼び径2 / PBOR2', 125),
    ('angle', '角度 / ANGLE', 110), ('height', '高さ / HEIGHT', 110),
    ('text', 'TEXT', 180), ('styp', '種別 / STYP', 110), ('shop', '工場製作 / SHOP', 110), ('scom_id', 'カタログ部品 / CATREF', 190),
    ('detail_id', '説明 / DETAIL', 160), ('prop_id', '物性 / 参照', 160),
    ('description', '説明文', 170), ('sdte_id', 'SDTE（従来参照）', 150),
    ('smte_id', '材質 / SMTE', 150),
)
REFERENCES = dict(scom_id='scoms', detail_id='catalog_details', prop_id='catalog_props',
                  sdte_id='texts', smte_id='texts')


def value(data, entry, key):
    if key in REFERENCES:
        return (project.get(data, REFERENCES[key], entry.get(key, '')) or {}).get('name', '未設定')
    return entry.get(key, '')


def build(host):
    area = ttk.Frame(host.content, padding=10)
    area.pack(fill='both', expand=True)
    bar = ttk.Frame(area); bar.pack(fill='x', pady=(0,8))
    for label, callback in (('SPEC情報', host.edit_spec), ('SPEC複製', host.duplicate_spec),
                            ('SPEC削除', host.delete_spec), ('＋ SCOMから追加', lambda:add_scoms(host)),
                            ('行複製', host.duplicate_spec_entry), ('行削除', host.delete_spec_entry)):
        ttk.Button(bar, text=label, command=callback).pack(side='left', padx=2)
    ttk.Button(bar, text='▣ プレビューを別窓で表示', command=lambda:open_preview(host)).pack(side='right', padx=2)
    ttk.Button(bar, text='列設定', command=lambda:column_dialog(host)).pack(side='right', padx=2)
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
    host.spec_table = host.table(area, COLUMNS, height=18)
    combo.bind('<<ComboboxSelected>>', lambda e:populate(host))
    host.spec_table.bind('<<TreeviewSelect>>', host.spec_entry_select)
    host.spec_table.bind('<ButtonRelease-1>', lambda e:edit_cell(host,e))
    host.spec_table.bind('<Double-1>', lambda e:'break')
    host.spec_table.bind('<ButtonRelease-1>', lambda e:remember_widths(host), add='+')
    host.spec_tree = host.registered_browser.tree
    settings = host.data.get('spec_table_settings', {})
    for key, width in settings.get('widths', {}).items():
        if key in host.spec_table['columns'] and isinstance(width,int) and 65<=width<=1200:
            host.spec_table.column(key, width=width)
    visible = settings.get('visible', [c[0] for c in COLUMNS])
    visible = [c[0] for c in COLUMNS if c[0] in visible]
    host.spec_table.configure(displaycolumns=visible or [COLUMNS[0][0]])
    populate(host)


def populate(host):
    tree=host.spec_table
    selected=tree.selection()
    tree.delete(*tree.get_children())
    for entry in host.spec()['entries']:
        if host.spec_type_filter.get() not in ('すべて',entry['type']):continue
        tree.insert('', 'end', iid=entry['id'], values=[value(host.data,entry,c[0]) for c in COLUMNS])
    ids=tree.get_children()
    if ids:tree.selection_set(selected[0] if selected and selected[0] in ids else ids[0])
    host.update_spec_preview()


def remember_widths(host):
    widths={key:max(65,min(1200,host.spec_table.column(key,'width'))) for key,_,_ in COLUMNS}
    settings=host.data.setdefault('spec_table_settings',{})
    if settings.get('widths')!=widths:
        settings['widths']=widths;host.mark()


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
        host.mark();win.destroy()
    ttk.Button(win,text='適用',command=apply).grid(row=8,column=1,padx=12,pady=10)


def edit_cell(host,event):
    tree=host.spec_table
    if tree.identify_region(event.x,event.y)!='cell':return
    row=tree.identify_row(event.y);column=tree.identify_column(event.x)
    if not row or not column:return
    index=int(column[1:])-1
    display=tree['displaycolumns'];key=display[index]
    entry=next(e for e in host.spec()['entries'] if e['id']==row)
    box=tree.bbox(row,column)
    if not box:return
    # The compact existing form handles reference selection without losing IDs.
    if key in REFERENCES:
        tree.selection_set(row);host.entry_form(entry);return
    editor=tk.Toplevel(host);editor.title(next(c[1] for c in COLUMNS if c[0]==key));editor.transient(host)
    editor.geometry('360x110');editor.resizable(True,False)
    text=tk.StringVar(editor,value=entry.get(key,''))
    field=ttk.Entry(editor,textvariable=text);field.pack(fill='x',padx=12,pady=12)
    def save(event=None):
        entry[key]=text.get();host.mark();editor.destroy();populate(host)
    ttk.Button(editor,text='確定',command=save).pack(side='right',padx=12)
    ttk.Button(editor,text='取消',command=editor.destroy).pack(side='right')
    field.bind('<Return>',save);field.bind('<Escape>',lambda e:editor.destroy())
    field.focus_set();field.selection_range(0,'end')


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
