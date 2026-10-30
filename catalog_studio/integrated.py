"""Integrated catalogue/specification authoring prototype for desktop use."""
import copy
import csv
import io
import json
import math
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font, messagebox, ttk
from . import model, project, element_schema, expressions, presets, pairing
from .app import Studio as LegacyPreview
from . import theme

BLUE = theme.ACCENT
NAVY = theme.CHROME
BG = theme.WORKSPACE
MUTED = theme.MUTED
PAGES = [('ptset', 'PTSET 作成'), ('gmset', 'GMSET 作成'), ('catalog', 'CATE作成'), ('sdte_cmpt','SDTE/CMPT作成'), ('specs', 'スペック登録'), ('structural', '構造材・NGMSET'), ('texts','説明・材質'), ('tables','共通テーブル'), ('books', 'カタログ本・PDF'), ('rules', 'PARAM プリセット'), ('checks', '確認・マクロ')]


class Preview:
    """Use the existing schematic renderer with values from one SCOM only."""
    def __init__(self, parent, family):
        self.canvas = tk.Canvas(parent, width=360, height=245, bg='#f1f6fc', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True, pady=8)
        self.view = tk.DoubleVar(value=20)
        self.points = tk.BooleanVar(value=True)
        self.ui_font = family
        self.project = {'elements': [], 'parameters': []}; self.selected = None; self.drag = None
        ttk.Scale(parent, from_=-60, to=60, variable=self.view, command=lambda _: self.draw()).pack(fill='x')
        ttk.Checkbutton(parent, text='ポイント表示（概略）', variable=self.points, command=self.draw).pack(anchor='w')
        self.canvas.bind('<Configure>', lambda _: self.draw())
        self.canvas.bind('<ButtonPress-1>', lambda e: setattr(self, 'drag', (e.x, self.view.get())))
        self.canvas.bind('<B1-Motion>', self.rotate)
        self.canvas.bind('<ButtonRelease-1>', lambda _: setattr(self, 'drag', None))
        self.message = ''

    def load(self, data, scom, selected=None):
        self.message = ''; self.project = {'elements': [], 'parameters': []}; self.selected = selected
        if scom:
            try:
                self.project['parameters'] = project.parameters_for(data, scom)
                for key in ('gmset_id', 'ptset_id'):
                    definition = project.get(data, 'definitions', scom.get(key))
                    if definition:
                        presets.require_compatible(data,scom,definition)
                        if any(e['type'] not in model.SCHEMAS for e in definition['elements']):
                            raise ValueError('未対応の要素型があります。原文を保持し、概略表示は行いません。')
                        self.project['elements'].extend(definition['elements'])
                for element in self.project['elements']:
                    for key in model.SCHEMAS[element['type']][1]:
                        expr = element['attrs'][key]
                        if key != '方向': model.evaluate(expr, self.project['parameters'])
            except ValueError as exc:
                self.message = 'プレビューを計算できません\n' + str(exc)
                self.project['elements'] = []
        else: self.message = '確認用の SCOM を選択してください'
        self.draw()

    def rotate(self, event):
        if self.drag:
            self.view.set(max(-60, min(60, self.drag[1] + (event.x-self.drag[0])/3))); self.draw()

    def draw(self):
        LegacyPreview.draw(self)
        if self.message:
            self.canvas.delete('all')
            self.canvas.create_text(max(180,self.canvas.winfo_width()/2), max(80,self.canvas.winfo_height()/2), text=self.message, width=320, fill=MUTED, font=(self.ui_font,10))


class IntegratedStudio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Catalog Studio — カタログ編集')
        from .app_icon import install as install_app_icon
        install_app_icon(self)
        self.geometry('1620x960'); self.minsize(1300,780); self.configure(bg=BG)
        families=set(font.families(self))
        self.ui_font=next((f for f in ('Yu Gothic UI','Meiryo','Noto Sans CJK JP','Hiragino Sans','Arial') if f in families),'TkDefaultFont')
        self.style=theme.apply(self,self.ui_font)
        self.data=project.sample()
        from .element_schema import demo_definitions
        self.data['definitions'].extend(demo_definitions())
        from .valve_sample import prepare as prepare_valve_sample
        self.data,_=prepare_valve_sample(self.data)
        self.path=None;self.dirty=False;self.page='ptset';self.busy=False
        self.cate_id=self.data['cates'][0]['id'];self.scom_id=self.data['scoms'][0]['id']
        self.definition_id='ui-ptset';self.spec_id=self.data['specs'][0]['id']
        self.element_id=None;self.selected_book=None;self.field=None;self.preview=None
        self.build_shell();self.render_page()
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<Control-s>',lambda _:self.save_project())
        self.bind('<Control-o>',lambda _:self.open_project())
        self.bind('<Control-n>',lambda _:self.new_project())

    def build_shell(self):
        menu_bar=tk.Frame(self,bg=theme.NAV,padx=18,pady=6);menu_bar.pack(fill='x')
        self.navigation_bar=menu_bar
        from .project_actions import build as build_project_actions
        build_project_actions(self,menu_bar)
        self.nav={}
        self.more_nav_button=tk.Menubutton(menu_bar,text='その他の管理 ▾',bg=theme.NAV,fg='#bbcadc',activebackground='#2b4160',activeforeground='white',relief='flat',borderwidth=0,font=(self.ui_font,10),cursor='hand2',padx=16,pady=8)
        self.more_nav_menu=tk.Menu(self.more_nav_button,tearoff=False)
        for key,text in PAGES:
            if key in ('ptset','gmset','catalog','sdte_cmpt','specs','books'):
                button=tk.Button(menu_bar,text=text,command=lambda k=key:self.switch(k),bg=theme.NAV,fg='#bbcadc',activebackground='#2b4160',activeforeground='white',relief='flat',borderwidth=0,highlightthickness=0,font=(self.ui_font,10),cursor='hand2',padx=16,pady=8)
                button.pack(side='left',padx=(0,5));self.nav[key]=button
            else:self.more_nav_menu.add_command(label=text,command=lambda k=key:self.switch(k))
        self.more_nav_button.configure(menu=self.more_nav_menu)
        self.more_nav_menu.add_separator()
        self.more_nav_menu.add_command(label='PTSET・GMSET の作成マクロを読み込む',command=self.import_creation_macro)
        self.more_nav_menu.add_command(label='手動弁サンプルを追加',command=self.add_valve_sample)
        self.more_nav_button.pack(side='left')
        footer=ttk.Frame(self,padding=(18,7),style='Status.TFrame');footer.pack(side='bottom',fill='x')
        ttk.Label(footer,text='Ctrl+S 保存    Ctrl+O 開く',style='Status.TLabel').pack(side='right')
        self.status=ttk.Label(footer,text='サンプルデータを表示しています',style='Status.TLabel');self.status.pack(side='left',fill='x',expand=True)
        body=ttk.Frame(self,style='Workspace.TFrame');body.pack(fill='both',expand=True)
        from .registered_ui import RegisteredBrowser
        self.registered_browser=RegisteredBrowser(self,body)
        self.content=ttk.Frame(body,padding=(10,12,12,0),style='Workspace.TFrame');self.content.pack(side='left',fill='both',expand=True)

    def mark(self,text='変更しました。Ctrl+S でプロジェクトを保存できます。'):
        self.dirty=True;self.title('Catalog Studio — '+self.data['name']+' *');self.status.configure(text=text)
        self.registered_browser.refresh()

    def switch(self,page):
        if self.page=='rules' and hasattr(self,'preset_editor') and self.preset_editor.winfo_exists() and not self.preset_editor.can_leave():return
        if self.commit_definition_name() is False:return
        if page=='catalog':
            s=project.get(self.data,'scoms',self.scom_id)
            if s:self.cate_id=s['cate_id']
        self.page=page;self.render_page()

    def render_page(self):
        self.busy=True;self.preview=None
        for child in self.content.winfo_children():child.destroy()
        for key,button in self.nav.items():button.configure(bg=BLUE if key==self.page else theme.NAV,fg='white' if key==self.page else '#bbcadc')
        additional=self.page not in self.nav
        self.more_nav_button.configure(text=(dict(PAGES).get(self.page,'その他の管理') if additional else 'その他の管理')+' ▾',bg=BLUE if additional else theme.NAV,fg='white' if additional else '#bbcadc')
        getattr(self,'build_'+self.page)()
        self.busy=False
        self.registered_browser.refresh()

    def heading(self,title,subtitle='',actions=()):
        bar=ttk.Frame(self.content);bar.pack(fill='x',pady=(0,12))
        block=ttk.Frame(bar);block.pack(side='left',fill='x',expand=True)
        ttk.Label(block,text=title,style='Heading.TLabel').pack(anchor='w')
        if subtitle:ttk.Label(block,text=subtitle,style='Muted.TLabel',wraplength=760).pack(anchor='w',pady=3)
        for text,command in actions:ttk.Button(bar,text=text,command=command).pack(side='right',padx=3)
        return bar

    def table(self,parent,columns,height=10):
        holder=ttk.Frame(parent);holder.pack(fill='both',expand=True)
        tree=ttk.Treeview(holder,columns=[c[0] for c in columns],show='headings',selectmode='browse',height=height)
        for key,title,width in columns:tree.heading(key,text=title);tree.column(key,width=width,minwidth=65)
        tree.grid(row=0,column=0,sticky='nsew')
        v=ttk.Scrollbar(holder,orient='vertical',command=tree.yview);v.grid(row=0,column=1,sticky='ns')
        h=ttk.Scrollbar(holder,orient='horizontal',command=tree.xview);h.grid(row=1,column=0,sticky='ew')
        tree.configure(yscrollcommand=v.set,xscrollcommand=h.set);holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
        return tree

    def balance(self,panes,fractions):
        initialized=False
        def apply(event=None):
            nonlocal initialized
            if initialized or not panes.winfo_exists():return
            if event is not None and event.widget is not panes:return
            width=panes.winfo_width()
            if width<600:return
            initialized=True
            for index,fraction in enumerate(fractions):panes.sashpos(index,int(width*fraction))
        panes.bind('<Configure>',apply,add='+')
        self.after_idle(apply)

    def form(self,title,fields,apply):
        """Fields: key, label, initial text, optional display choices."""
        win=tk.Toplevel(self);win.title(title);win.transient(self);win.grab_set()
        win.geometry('440x'+str(190+60*len(fields)) if len(fields)<=2 else '540x650')
        container=ttk.Frame(win,padding=14 if len(fields)<=2 else 18);container.pack(fill='both',expand=True)
        ttk.Label(container,text=title,style='Heading.TLabel').pack(anchor='w',pady=(0,6 if len(fields)<=2 else 10))
        canvas=tk.Canvas(container,highlightthickness=0,bg='white');canvas.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(container,orient='vertical',command=canvas.yview);scroll.pack(side='right',fill='y');canvas.configure(yscrollcommand=scroll.set)
        inner=ttk.Frame(canvas);window=canvas.create_window((0,0),window=inner,anchor='nw')
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        inner.bind('<Configure>',lambda _:canvas.configure(scrollregion=canvas.bbox('all')))
        variables={}
        for key,label,value,choices in fields:
            ttk.Label(inner,text=label).pack(anchor='w',pady=(8,3));var=tk.StringVar(value=str(value));variables[key]=var
            widget=ttk.Combobox(inner,textvariable=var,values=choices,state='readonly') if choices is not None else ttk.Entry(inner,textvariable=var)
            widget.pack(fill='x')
        error=ttk.Label(win,text='',foreground='#bb4949',wraplength=400 if len(fields)<=2 else 500,padding=(10,4) if len(fields)<=2 else 10);error.pack(side='bottom',fill='x',before=container)
        footer=ttk.Frame(win,padding=12);footer.pack(side='bottom',fill='x',before=error)
        def submit():
            try:apply({k:v.get().strip() for k,v in variables.items()})
            except (ValueError,KeyError,StopIteration) as exc:error.configure(text=str(exc) or '設定内容を確認してください。');return
            win.destroy();self.mark();self.render_page()
        ttk.Button(footer,text='キャンセル',command=win.destroy).pack(side='right',padx=5)
        ttk.Button(footer,text='適用',command=submit,style='Primary.TButton').pack(side='right')
        return win

    @staticmethod
    def required(value,label):
        if not value:raise ValueError(label+'を入力してください。')
        return value

    def choices(self,collection,kind=None):
        return {item['name']:item['id'] for item in self.data[collection] if kind is None or item.get('kind')==kind}

    def build_catalog(self):
        from .catalog_members_ui import CatalogMembers, bundle_form
        split=ttk.Panedwindow(self.content,orient='horizontal');split.pack(fill='both',expand=True)
        middle=ttk.Frame(split,padding=10,width=700);right=ttk.Frame(split,padding=10,width=390)
        middle.pack_propagate(False);right.pack_propagate(False)
        split.add(middle,weight=4);split.add(right,weight=2)
        self.catalog_panes=split;self.balance(split,(.65,))
        self.catalog_tree=self.registered_browser.tree
        visible_middle=right;preview_parent=middle
        # Keep the existing form controllers off screen; the inspector owns visible editing.
        legacy=ttk.Frame(middle)
        middle=legacy
        cate_tools=ttk.Frame(middle);cate_tools.pack(fill='x',pady=(0,8))
        ttk.Button(cate_tools,text='CATE の情報を編集',command=self.edit_cate).pack(side='left',padx=3)
        ttk.Button(cate_tools,text='空の CATE を削除',command=self.delete_cate).pack(side='left',padx=3)
        content=ttk.Frame(middle);content.pack(fill='both',expand=True)
        self.catalog_scom_page=scom_page=ttk.Frame(content)
        self.catalog_members_page=members_page=ttk.Frame(content)
        active=members_page if getattr(self,'catalog_tab','scom')=='members' else scom_page
        active.pack(fill='both',expand=True)
        self.catalog_members=CatalogMembers(self,members_page);self.catalog_members.pack(fill='both',expand=True)
        middle=scom_page
        top=ttk.Frame(middle);top.pack(fill='x',pady=(0,10))
        ttk.Label(top,text='SCOM の寸法・文字列',style='Heading.TLabel').pack(side='left')
        for text,cmd in [('編集',self.edit_scom),('複製',self.duplicate_scom),('削除',self.delete_scom)]:ttk.Button(top,text=text,command=cmd).pack(side='right',padx=2)
        members=[r for r in self.data['scoms'] if r['cate_id']==self.cate_id]
        self.catalog_parameter_ids=sorted({p['id'] for r in members for p in presets.rules(self.data,r)} or {p['id'] for p in presets.rules(self.data)},key=lambda pid:int(pid[1:]))
        columns=[('name','SCOM 名',170),('size','サイズ',100),('rev','改訂',65),('preset','PARAM プリセット',190)]+[(pid,pid+'（説明は選択行の右欄）',160) for pid in self.catalog_parameter_ids]
        self.scom_table=self.table(middle,columns,height=10);self.fill_scom_table()
        ttk.Label(middle,text='行をダブルクリックして、数値・文字列・参照先を編集できます。',style='Muted.TLabel').pack(anchor='w',pady=5)
        self.scom_table.bind('<<TreeviewSelect>>',self.scom_select);self.scom_table.bind('<Double-1>',lambda _:self.edit_scom())
        tools=ttk.Frame(middle);tools.pack(fill='x',pady=10)
        ttk.Button(tools,text='表からまとめて貼り付け',command=self.paste_scoms).pack(side='left',padx=3)
        ttk.Button(tools,text='PARAM プリセットを割り当て',command=self.assign_scom_preset).pack(side='left',padx=3)
        ttk.Button(tools,text='確認用の参照コンテキスト',command=self.edit_contexts).pack(side='left',padx=3)
        references=ttk.LabelFrame(middle,text='選択 SCOM の参照先',padding=12);references.pack(fill='x',pady=6)
        self.reference_label=ttk.Label(references,text='',wraplength=520);self.reference_label.pack(anchor='w')
        ttk.Button(references,text='GMSET を編集',command=lambda:self.goto_definition('gmset_id')).pack(side='left',pady=8,padx=3)
        ttk.Button(references,text='PTSET を編集',command=lambda:self.goto_definition('ptset_id')).pack(side='left',pady=8,padx=3)
        ttk.Label(preview_parent,text='プレビュー',style='Heading.TLabel').pack(anchor='w')
        from .catalog_geometry_preview import CatalogGeometryPreview
        self.preview=CatalogGeometryPreview(self,preview_parent)
        self.scom_detail=ttk.Label(legacy,text='',style='Muted.TLabel')
        self.update_scom_preview()
        from .catalog_inspector import CatalogInspector
        self.catalog_inspector=CatalogInspector(self,visible_middle)
        self.catalog_inspector.pack(fill='both',expand=True)

    def fill_scom_table(self):
        self.scom_table.delete(*self.scom_table.get_children())
        for s in self.data['scoms']:
            if s['cate_id']==self.cate_id:self.scom_table.insert('','end',iid=s['id'],values=[s['name'],s['size'],s['revision'],presets.label(self.data,s)]+[s['values'].get(pid,'未入力') for pid in self.catalog_parameter_ids])
        if self.scom_table.exists(str(self.scom_id)):self.scom_table.selection_set(self.scom_id)

    def catalog_select(self,_=None):self.registered_browser.select()

    def scom_select(self,_=None):
        if self.busy:return
        items=self.scom_table.selection()
        if items:
            changed=self.scom_id!=items[0];self.scom_id=items[0]
            if changed:self.update_scom_preview()
            if changed:
                browser=self.registered_browser;browser.catalog_target='scoms:'+self.scom_id
                browser.catalog_context=(self.cate_id,self.scom_id,'scom',getattr(self,'catalog_member_key',None),browser.catalog_target);browser.refresh()

    def update_scom_preview(self):
        s=project.get(self.data,'scoms',self.scom_id)
        self.preview.load(self.data,s)
        if not s:self.reference_label.configure(text='SCOM を追加・選択してください。');self.scom_detail.configure(text='');return
        g=project.get(self.data,'definitions',s['gmset_id']);p=project.get(self.data,'definitions',s['ptset_id'])
        self.reference_label.configure(text='GMRE → '+(g['name'] if g else '未設定')+'\nPTRE  → '+(p['name'] if p else '未設定'))
        self.scom_detail.configure(text=s['name']+'  ／  PARAM：'+presets.label(self.data,s))

    def add_cate(self):
        def apply(v):
            self.required(v['name'],'CATE 名')
            if v['name'] in self.choices('cates'):raise ValueError('CATE 名が重複しています。')
            c=project.add_cate(self.data,v['name']);c['description']=v['description'];self.cate_id=c['id'];self.scom_id=None
        self.form('CATE を追加',[('name','CATE 名','',None),('description','説明','',None)],apply)

    def edit_cate(self):
        cate=project.get(self.data,'cates',self.cate_id)
        if not cate:return
        def apply(v):
            self.required(v['name'],'CATE 名')
            if any(c['id']!=cate['id'] and c['name']==v['name'] for c in self.data['cates']):raise ValueError('CATE 名が重複しています。')
            cate.update(v)
        self.form('CATE の情報',[('name','CATE 名',cate['name'],None),('description','説明',cate['description'],None),('revision','改訂',cate['revision'],None)],apply)

    def delete_cate(self):
        from .catalog_workspace import COLLECTIONS
        if any(record['cate_id']==self.cate_id for collection in COLLECTIONS.values() for record in self.data.get(collection,[])):
            messagebox.showinfo('使用中','DETAIL または PROP が関連しています。',parent=self);return
        if any(s['cate_id']==self.cate_id for s in self.data['scoms']):messagebox.showinfo('削除できません','SCOM がある CATE は削除できません。',parent=self);return
        if not project.get(self.data,'cates',self.cate_id):return
        if any(r['parent_id']==self.cate_id for key in ('texts','tables') for r in self.data.get(key,[])):messagebox.showinfo('使用中','説明・材質または共通テーブルが所属しています。',parent=self);return
        if messagebox.askyesno('削除','空の CATE を削除しますか？',parent=self):
            self.data['cates']=[c for c in self.data['cates'] if c['id']!=self.cate_id];self.cate_id=next((c['id'] for c in self.data['cates']),None);self.mark();self.render_page()

    def scom_form(self,scom=None,*,seed=None):
        cate_choices=self.choices('cates');gm=self.choices('definitions','GMSET');pt=self.choices('definitions','PTSET')
        create_cate=not cate_choices
        if create_cate:cate_choices['新しい CATE を作成']='__new_cate__'
        for mapping in (cate_choices,gm,pt):mapping['未設定']=''
        if scom:
            for mapping,key in ((cate_choices,'cate_id'),(gm,'gmset_id'),(pt,'ptset_id')):
                ident=scom[key]
                if ident and ident not in mapping.values():mapping['参照先不明：'+ident]=ident
        def display(mapping,ident):
            return next((name for name,key in mapping.items() if key==ident),next(iter(mapping)))
        fields=[('name','SCOM 名',scom['name'] if scom else '',None),('size','サイズ表記',scom['size'] if scom else '',None),('cate','CATE',display(cate_choices,scom['cate_id'] if scom else self.cate_id),list(cate_choices)),('revision','改訂',scom['revision'] if scom else '01',None),('gm','GMRE / GMSET',display(gm,scom.get('gmset_id') if scom else (seed or {}).get('gmset_id')),list(gm)),('pt','PTRE / PTSET',display(pt,scom.get('ptset_id') if scom else (seed or {}).get('ptset_id')),list(pt))]
        rule_source=scom if scom is not None else seed
        parameters=presets.rules(self.data,rule_source)
        if create_cate:fields.append(('new_cate_name','新しい CATE 名','/NEW-CATE',None))
        fields.append(('preset_label','PARAM プリセット',presets.label(self.data,rule_source),[presets.label(self.data,rule_source)]))
        for p in parameters:fields.append((p['id'],p['id']+'：'+presets.caption(p)+' ['+p.get('unit','mm')+']',scom['values'].get(p['id'],'') if scom else '',None))
        fields.append(('angl','ANGL：部品の角度（度、空欄は未設定）',(scom or {}).get('component_attrs',{}).get('ANGL',''),None))
        for kind,key in (('NGMSET','ngmset_id'),('GMSSET','gmsset_id'),('PTSSET','ptsset_id')):
            mapping=self.choices('definitions',kind);mapping['未設定']=''
            ident=(scom or {}).get(key,'')
            if ident and ident not in mapping.values():mapping['参照先不明：'+ident]=ident
            fields.append((key,kind,next((name for name,value in mapping.items() if value==ident),'未設定'),list(mapping)))
        def apply(v):
            self.required(v['name'],'SCOM 名')
            if any(s['name']==v['name'] and (scom is None or s['id']!=scom['id']) for s in self.data['scoms']):raise ValueError('SCOM 名が重複しています。')
            known={p['id'] for p in parameters}
            values={key:value for key,value in scom['values'].items() if key not in known} if scom else {}
            for p in parameters:
                if not v[p['id']]:continue
                values[p['id']]=project.parse_value(p,v[p['id']])
            component=copy.deepcopy((scom or {}).get('component_attrs',{}))
            if v['angl']:
                component['ANGL']=project.parse_value({'id':'ANGL','unit':'degrees'},v['angl'])
            else:component.pop('ANGL',None)
            if not scom and len(self.data['scoms'])>=project.LIMITS['scoms']:raise ValueError('SCOM 数の上限です。')
            if seed is not None:
                for key,mapping,kind in (('gm',gm,'GMSET'),('pt',pt,'PTSET')):
                    definition=project.get(self.data,'definitions',mapping.get(v[key],''))
                    if not definition or definition['kind']!=kind:raise ValueError(kind+' を選択してください。')
                    presets.require_compatible(self.data,seed,definition)
            cate_id=cate_choices[v['cate']]
            if seed is not None and not cate_id:raise ValueError('所属 CATE を選択してください。')
            if cate_id=='__new_cate__':
                name=self.required(v['new_cate_name'],'CATE 名')
                if any(c['name']==name for c in self.data['cates']):raise ValueError('CATE 名が重複しています。')
                cate_id=project.add_cate(self.data,name)['id']
            obj=scom or project.add_scom(self.data,cate_id,v['name'])
            obj.update(name=v['name'],size=v['size'],cate_id=cate_id,revision=v['revision'],gmset_id=gm.get(v['gm'],''),ptset_id=pt.get(v['pt'],''),values=values)
            obj['component_attrs']=component
            if seed is not None:obj['parameter_preset_id']=presets.selected_id(self.data,seed)
            for kind,key in (('NGMSET','ngmset_id'),('GMSSET','gmsset_id'),('PTSSET','ptsset_id')):
                mapping=self.choices('definitions',kind);mapping['未設定']=''
                obj[key]=mapping.get(v[key],obj.get(key,''))
            self.scom_id=obj['id'];self.cate_id=obj['cate_id']
            self.catalog_tab='scom'
            if seed is not None:self.data['creation_draft']={key:obj[key] for key in ('ptset_id','gmset_id')} | {'scom_id':obj['id']}
        self.form('SCOM の値を登録',fields,apply)

    def add_scom(self):
        gm=project.get(self.data,'definitions',self.definition_id)
        if not gm or gm['kind']!='GMSET':self.scom_form();return
        pt=pairing.resolve(self.data,gm)['pointset']
        if pt:
            try:presets.require_compatible(self.data,gm,pt)
            except ValueError as exc:messagebox.showinfo('プリセットの確認',str(exc),parent=self);return
        self.scom_form(seed={'gmset_id':gm['id'],'ptset_id':pt['id'] if pt else '', 'parameter_preset_id':presets.selected_id(self.data,gm)})
    def edit_scom(self):
        s=project.get(self.data,'scoms',self.scom_id)
        if s:self.scom_form(s)
    def duplicate_scom(self):
        s=project.get(self.data,'scoms',self.scom_id)
        if s:self.scom_id=project.duplicate_scom(self.data,s)['id'];self.mark();self.render_page()
    def delete_scom(self):
        s=project.get(self.data,'scoms',self.scom_id)
        if not s:return
        if any(e['scom_id']==s['id'] for spec in self.data['specs'] for e in spec['entries']):messagebox.showinfo('削除できません','SPEC で参照されています。先に SPEC の登録行を変更・削除してください。',parent=self);return
        if messagebox.askyesno('削除','SCOM を削除しますか？ 発行済み冊子の内容は変わりません。',parent=self):
            self.data['scoms']=[x for x in self.data['scoms'] if x['id']!=s['id']];self.scom_id=next((x['id'] for x in self.data['scoms'] if x['cate_id']==self.cate_id),None);self.mark();self.render_page()

    def paste_scoms(self):
        if not project.get(self.data,'cates',self.cate_id):return
        win=tk.Toplevel(self);win.title('表から SCOM を追加');win.transient(self);win.grab_set()
        base=project.get(self.data,'scoms',self.scom_id)
        names=['SCOM名','サイズ']+[p['id'] for p in presets.rules(self.data,base)]
        ttk.Label(win,text='見出しを含めず、次の順序でタブ区切りの行を貼り付けてください。\n'+' / '.join(names)+'\nPARAM プリセットと参照定義は選択中の SCOM から引き継ぎます。',padding=12,wraplength=700).pack()
        text=tk.Text(win,width=90,height=15);text.pack(padx=12)
        error=ttk.Label(win,text='',foreground='#bb4949',padding=10);error.pack()
        def apply():
            try:
                candidate=self.parse_scom_paste(text.get('1.0','end'))
            except ValueError as exc:error.configure(text=str(exc));return
            self.data=candidate;self.mark();self.render_page();win.destroy()
        ttk.Button(win,text='まとめて追加',command=apply,style='Primary.TButton').pack(pady=12)

    def parse_scom_paste(self,text):
        candidate=copy.deepcopy(self.data);base=project.get(candidate,'scoms',self.scom_id)
        parameters=presets.rules(candidate,base)
        rows=list(csv.reader(io.StringIO(text.strip()),delimiter='\t'))
        if not text.strip() or len(rows)>200:raise ValueError('1〜200 行を貼り付けてください。')
        for rownum,row in enumerate(rows,1):
            if len(row)!=2+len(parameters):raise ValueError(f'{rownum} 行目の列数を確認してください。')
            if not row[0].strip() or any(s['name']==row[0].strip() for s in candidate['scoms']):raise ValueError(f'{rownum} 行目の SCOM 名が空か重複しています。')
            values={}
            for p,raw in zip(parameters,row[2:]):
                value=project.parse_value(p,raw)
                values[p['id']]=value
            s=project.add_scom(candidate,self.cate_id,row[0].strip());s.update(size=row[1],values=values)
            if base:s.update(gmset_id=base['gmset_id'],ptset_id=base['ptset_id'],parameter_preset_id=presets.selected_id(candidate,base))
        project.validate(candidate);return candidate

    def goto_definition(self,key):
        s=project.get(self.data,'scoms',self.scom_id)
        if s and s.get(key):self.definition_id=s[key];self.switch('gmset' if key=='gmset_id' else 'ptset')

    def definition_form(self,kind,*,preset_id=None,ptset_id=None,insert_after=None):
        """Create an empty set; numerical component data is entered later."""
        import uuid
        data=self.data
        source=presets.selected_id(self.data) if preset_id is None else preset_id
        options=presets.choices(self.data)
        if source and source not in options.values():raise ValueError('PARAM プリセットが見つかりません。')
        initial=next(name for name,ident in options.items() if ident==source)
        fields=[('name',kind+' 名','' if kind=='PTSET' else '/NEW-'+kind,None)]
        if ptset_id is None:fields.append(('preset','PARAM プリセット',initial,list(options)))
        else:fields.append(('preset','PTSET から引き継ぐプリセット',initial,[initial]))
        def apply(v):
            if self.data is not data:raise ValueError('プロジェクトが変更されています。追加をやり直してください。')
            name=self.required(v['name'],kind+' 名')
            if any(d['name']==name for d in self.data['definitions']):raise ValueError('定義名が重複しています。')
            if len(self.data['definitions'])>=project.LIMITS['definitions']:raise ValueError('定義数の上限です。')
            ident=options[v['preset']]
            if ptset_id is not None:
                pointset=project.get(self.data,'definitions',ptset_id)
                if not pointset or pointset['kind']!='PTSET':raise ValueError('引き継ぐ PTSET が見つかりません。')
                if presets.selected_id(self.data,pointset)!=ident:raise ValueError('PTSET のプリセットが変更されています。作成をやり直してください。')
            definition={'id':uuid.uuid4().hex,'name':name,'kind':kind,'revision':'01','elements':[],'parameter_preset_id':ident}
            if kind=='GMSET' and ptset_id is not None:pairing.assign(self.data,definition,ptset_id)
            if insert_after is not None:
                from .browser_folders import place_created
                place_created(self.data,kind.lower(),'definitions:'+definition['id'],insert_after)
            self.data['definitions'].append(definition);self.definition_id=definition['id']
            if kind=='PTSET':self.data['creation_draft']={'ptset_id':definition['id']}
            elif ptset_id is not None:self.data['creation_draft']={'ptset_id':ptset_id,'gmset_id':definition['id']}
            self.page='ptset' if kind=='PTSET' else 'gmset'
            self.registered_browser.search.set('')
        return self.form('新しい '+kind+' を作成',fields,apply)

    def component_from_ptset(self,ptset_id):
        self.commit_definition_name()
        pt=project.get(self.data,'definitions',ptset_id)
        if not pt or pt['kind']!='PTSET':return
        self.definition_form('GMSET',preset_id=presets.selected_id(self.data,pt),ptset_id=pt['id'])

    def component_from_gmset(self,gmset_id):
        self.commit_definition_name()
        gm=project.get(self.data,'definitions',gmset_id)
        if not gm or gm['kind']!='GMSET':return
        pt=pairing.resolve(self.data,gm)['pointset']
        if not pt or pt['kind']!='PTSET':
            options=self.choices('definitions','PTSET')
            if not options:messagebox.showinfo('PTSET が必要','PTSET 作成でポイントを登録してください。',parent=self);self.switch('ptset');return
            def choose(v):
                pointset=project.get(self.data,'definitions',options[v['pt']]);presets.require_compatible(self.data,gm,pointset)
                pairing.assign(self.data,gm,pointset['id'])
                self.data['creation_draft']={'ptset_id':pointset['id'],'gmset_id':gm['id']}
                self.after_idle(lambda:self.component_from_gmset(gm['id']))
            self.form('SCOM に使用する PTSET を選択',[('pt','PTSET',next(iter(options)),list(options))],choose);return
        try:presets.require_compatible(self.data,gm,pt)
        except ValueError as exc:messagebox.showinfo('プリセットの確認',str(exc),parent=self);return
        seed={'ptset_id':pt['id'],'gmset_id':gm['id'],'parameter_preset_id':presets.selected_id(self.data,pt)}
        self.switch('catalog');self.scom_form(seed=seed)

    def component_to_spec(self):
        scom=project.get(self.data,'scoms',self.scom_id)
        if not scom:messagebox.showinfo('SCOM が必要','先に SCOM を登録してください。',parent=self);return
        ident=scom['id'];self.switch('specs')
        if not self.spec():
            self.spec_form(after_create=lambda:self.entry_form(scom_id=ident))
        else:self.entry_form(scom_id=ident)

    def build_ptset(self):
        from .construction_ui import ConstructionEditor
        self.geometry_editor=ConstructionEditor(self,'PTSET')

    def build_gmset(self):
        from .construction_ui import ConstructionEditor
        self.geometry_editor=ConstructionEditor(self,'GMSET')

    def build_structural(self):
        from .construction_ui import ConstructionEditor
        bar=ttk.Frame(self.content);bar.pack(fill='x',pady=(0,8))
        for kind,label in (('NGMSET','負形状セット'),('PTSSET','構造材の基準線'),('GMSSET','構造材の断面')):
            ttk.Button(bar,text=kind+' / '+label,command=lambda k=kind:self.select_structural(k)).pack(side='left',padx=4)
        self.geometry_editor=ConstructionEditor(self,getattr(self,'structural_kind','NGMSET'))

    def select_structural(self,kind):
        self.structural_kind=kind;self.commit_definition_name();self.render_page()

    def build_sdte_cmpt(self):
        from .sdte_cmpt_ui import SdteCmptEditor
        self.sdte_cmpt_editor=SdteCmptEditor(self)

    def build_texts(self):
        from .companion_ui import CompanionEditor
        self.companion_editor=CompanionEditor(self,'texts')

    def build_tables(self):
        from .companion_ui import CompanionEditor
        self.companion_editor=CompanionEditor(self,'tables')

    def edit_contexts(self):
        from .companion_ui import json_dialog
        scom=project.get(self.data,'scoms',self.scom_id)
        if not scom:return
        def apply(value):
            candidate=copy.deepcopy(self.data)
            project.get(candidate,'scoms',scom['id'])['expression_contexts']=value
            project.validate(candidate);scom['expression_contexts']=value
        json_dialog(self,'確認用の参照値：例 IPARAM → P1 → 数値。自動で他の SCOM に結び付けません。',scom.get('expression_contexts',{}),apply)

    def build_definitions(self):
        self.heading('GMSET・PTSET の共通定義','パラメータの役割を選び、式で定義します。実数値は選択 SCOM から読み取り専用で使用します。',[('定義を追加',self.add_definition),('定義情報',self.edit_definition_info)])
        split=ttk.Panedwindow(self.content,orient='horizontal');split.pack(fill='both',expand=True)
        left=ttk.Frame(split,padding=8);middle=ttk.Frame(split,padding=12);right=ttk.Frame(split,padding=12)
        split.add(left,weight=1);split.add(middle,weight=3);split.add(right,weight=2)
        self.balance(split,(.20,.66))
        self.def_tree=ttk.Treeview(left,show='tree');self.def_tree.pack(fill='both',expand=True)
        for d in self.data['definitions']:
            self.def_tree.insert('','end',iid=d['id'],text=d['kind']+' '+d['name'],open=True)
        if self.def_tree.exists(str(self.definition_id)):self.def_tree.selection_set(self.definition_id)
        self.def_tree.bind('<<TreeviewSelect>>',self.definition_select)
        ttk.Button(left,text='定義を複製',command=self.duplicate_definition).pack(fill='x',pady=8)
        ttk.Button(left,text='未使用の定義を削除',command=self.delete_definition).pack(fill='x')
        d=project.get(self.data,'definitions',self.definition_id)
        if not d:ttk.Label(middle,text='定義を追加してください。').pack();return
        usage=[s for s in self.data['scoms'] if d['id'] in (s['gmset_id'],s['ptset_id'])]
        ttk.Label(middle,text=d['kind']+' / 参照 SCOM：'+str(len(usage))+' 件',style='Heading.TLabel').pack(anchor='w')
        self.def_name=tk.StringVar(value=d['name'])
        self.def_name_entry=ttk.Entry(middle,textvariable=self.def_name);self.def_name_entry.pack(fill='x',pady=8)
        self.def_name_entry.bind('<FocusOut>',lambda _:self.commit_definition_name());self.def_name_entry.bind('<Return>',lambda _:self.commit_definition_name())
        self.element_table=self.table(middle,[('name','要素名',160),('type','種類',100)],height=4)
        for e in d['elements']:self.element_table.insert('','end',iid=e['id'],values=(e['name'],model.SCHEMAS.get(e['type'],('未対応：'+e['type'],()))[0]))
        if not any(e['id']==self.element_id for e in d['elements']):self.element_id=next((e['id'] for e in d['elements']),None)
        if self.element_id:self.element_table.selection_set(self.element_id)
        self.element_table.bind('<<TreeviewSelect>>',self.element_select)
        actions=ttk.Frame(middle);actions.pack(fill='x',pady=7)
        for label,cmd in [('要素を追加',self.add_element),('要素名',self.rename_element),('複製',self.duplicate_element),('削除',self.delete_element)]:ttk.Button(actions,text=label,command=cmd).pack(side='left',padx=2)
        self.attr_table=self.table(middle,[('key','設定項目',100),('expr','参照・式',220),('refs','パラメータ',90)],height=5)
        self.attr_table.bind('<<TreeviewSelect>>',self.attr_select)
        formula=ttk.LabelFrame(middle,text='読みやすい式で編集',padding=10);formula.pack(fill='x',pady=10)
        self.formula=tk.StringVar();self.formula.trace_add('write',self.formula_changed)
        self.formula_entry=ttk.Entry(formula,textvariable=self.formula,font=(self.ui_font,14));self.formula_entry.pack(fill='x')
        self.direction=ttk.Combobox(formula,values=model.DIRECTIONS,state='readonly');self.direction.bind('<<ComboboxSelected>>',self.direction_changed)
        self.parambar=ttk.Frame(formula);self.parambar.pack(fill='x',pady=8)
        self.param_choice=ttk.Combobox(self.parambar,values=[p['id']+'：'+presets.meaning(p) for p in presets.rules(self.data,self.definition())],state='readonly');self.param_choice.pack(side='left',fill='x',expand=True)
        if presets.rules(self.data,self.definition()):self.param_choice.current(0)
        ttk.Button(self.parambar,text='挿入',command=self.insert_parameter).pack(side='left',padx=3)
        ttk.Button(self.parambar,text='÷ 2',command=self.half_formula).pack(side='left')
        self.formula_result=ttk.Label(formula,text='',wraplength=450);self.formula_result.pack(anchor='w')
        ttk.Label(right,text='参照 SCOM で表示確認',style='Heading.TLabel').pack(anchor='w')
        self.preview_choices={s['name']:s['id'] for s in usage}
        self.preview_choice=ttk.Combobox(right,values=list(self.preview_choices),state='readonly');self.preview_choice.pack(fill='x',pady=8)
        if usage:
            selected=next((s for s in usage if s['id']==self.scom_id),usage[0]);self.scom_id=selected['id'];self.preview_choice.set(selected['name'])
        self.preview_choice.bind('<<ComboboxSelected>>',self.preview_scom_selected)
        self.preview=Preview(right,self.ui_font)
        self.preview_values=ttk.Label(right,text='',style='Muted.TLabel',wraplength=330);self.preview_values.pack(anchor='w',pady=8)
        ttk.Button(right,text='SCOM の実数値を編集',command=lambda:self.switch('catalog')).pack(fill='x',pady=8)
        ttk.Label(right,text='ここに表示する数値は定義には保存されません。',style='Muted.TLabel',wraplength=330).pack(anchor='w')
        self.populate_attrs();self.update_definition_preview()

    def definition(self):return project.get(self.data,'definitions',self.definition_id)
    def element(self):return next((e for e in (self.definition() or {}).get('elements',[]) if e['id']==self.element_id),None)
    def commit_definition_name(self):
        if self.page=='sdte_cmpt' and hasattr(self,'sdte_cmpt_editor') and self.sdte_cmpt_editor.winfo_exists():return self.sdte_cmpt_editor.finish()
        if self.page=='catalog' and hasattr(self,'catalog_inspector') and self.catalog_inspector.winfo_exists():
            if not self.catalog_inspector.finish():return False
        if self.page=='rules' and hasattr(self,'preset_editor') and self.preset_editor.winfo_exists():return self.preset_editor.finish_cell()
        if self.page in ('ptset','gmset','structural') and hasattr(self,'geometry_editor') and self.geometry_editor.winfo_exists():
            if not self.geometry_editor.commit_inline():return False
            self.geometry_editor.commit_name()
            return
        if self.page!='definitions' or not hasattr(self,'def_name_entry') or not self.def_name_entry.winfo_exists():return
        d=self.definition();name=self.def_name.get().strip()
        if not d or name==d['name']:return
        if not name or any(x['id']!=d['id'] and x['name']==name for x in self.data['definitions']):self.status.configure(text='定義名が空か重複しています。');self.def_name.set(d['name']);return
        d['name']=name;self.def_tree.item(d['id'],text=d['kind']+' '+name);self.mark()
    def definition_select(self,_=None):
        if self.busy:return
        selection=self.def_tree.selection()
        if selection and selection[0]!=self.definition_id:self.commit_definition_name();self.definition_id=selection[0];self.element_id=None;self.render_page()
    def element_select(self,_=None):
        if self.busy:return
        selection=self.element_table.selection()
        if selection and selection[0]!=self.element_id:self.element_id=selection[0];self.field=None;self.populate_attrs();self.update_definition_preview()
    def populate_attrs(self):
        self.busy=True;self.attr_table.delete(*self.attr_table.get_children());e=self.element()
        if e:
            for k in model.SCHEMAS.get(e['type'],('',tuple(e['attrs'])))[1]:self.attr_table.insert('','end',iid=k,values=(k,e['attrs'][k],', '.join(model.references(str(e['attrs'][k]),presets.rules(self.data,self.definition()))) or '—'))
            if self.field not in e['attrs']:self.field=next(iter(model.SCHEMAS.get(e['type'],('',tuple(e['attrs'])))[1]),None)
            if self.field:self.attr_table.selection_set(self.field)
        else:self.field=None
        self.load_formula();self.busy=False
    def attr_select(self,_=None):
        if self.busy:return
        selection=self.attr_table.selection()
        if selection and selection[0]!=self.field:self.field=selection[0];self.busy=True;self.load_formula();self.busy=False
    def load_formula(self):
        e=self.element()
        if not e or not self.field:self.formula.set('');self.formula_entry.configure(state='disabled');return
        if e['type'] not in model.SCHEMAS:
            self.direction.pack_forget();self.parambar.pack_forget()
            self.formula_entry.pack(fill='x',before=self.formula_result)
            self.formula.set(str(e['attrs'][self.field]));self.formula_entry.configure(state='readonly')
            self.formula_result.configure(text='未対応要素の原文を読み取り専用で保持しています。',foreground=MUTED)
            return
        self.formula_entry.configure(state='normal')
        if self.field=='方向':
            self.formula_entry.pack_forget();self.parambar.pack_forget();self.direction.pack(fill='x',before=self.formula_result);self.direction.set(e['attrs']['方向'])
        else:
            self.direction.pack_forget();self.formula_entry.pack(fill='x',before=self.formula_result);self.parambar.pack(fill='x',pady=8,before=self.formula_result);self.formula.set(e['attrs'][self.field])
        self.calc_formula()
    def formula_changed(self,*_):
        if self.busy or not self.element() or self.element()['type'] not in model.SCHEMAS or not self.field or self.field=='方向':return
        self.element()['attrs'][self.field]=self.formula.get()
        self.attr_table.item(self.field,values=(self.field,self.formula.get(),', '.join(model.references(self.formula.get(),presets.rules(self.data,self.definition()))) or '—'))
        self.mark();self.calc_formula();self.update_definition_preview()
    def direction_changed(self,_=None):
        if self.element():self.element()['attrs']['方向']=self.direction.get();self.mark();self.populate_attrs();self.update_definition_preview()
    def calc_formula(self):
        if not self.element() or not self.field:self.formula_result.configure(text='');return
        if self.element()['type'] not in model.SCHEMAS:return
        if self.field=='方向':self.formula_result.configure(text='方向を選択してください。',foreground=MUTED);return
        s=project.get(self.data,'scoms',self.preview_choices.get(self.preview_choice.get())) if hasattr(self,'preview_choice') and self.preview_choice.winfo_exists() else None
        try:
            if not s:raise ValueError('参照 SCOM を選ぶと計算結果を確認できます。')
            presets.require_compatible(self.data,s,self.definition());val=model.evaluate(self.formula.get(),project.parameters_for(self.data,s));self.formula_result.configure(text='選択 SCOM での計算結果：'+f'{val:g}',foreground='#168168')
        except ValueError as exc:self.formula_result.configure(text=str(exc),foreground='#b94c44')
    def insert_parameter(self):
        if not self.element() or self.element()['type'] not in model.SCHEMAS or self.field=='方向':return
        i=self.param_choice.current()
        if i<0:return
        name=presets.rules(self.data,self.definition())[i]['role'];entry=self.formula_entry
        try:a,b=entry.index('sel.first'),entry.index('sel.last')
        except tk.TclError:a=b=entry.index('insert')
        text=self.formula.get();self.formula.set(text[:a]+name+text[b:]);entry.focus_set();entry.icursor(a+len(name))
    def half_formula(self):
        if self.element() and self.element()['type'] in model.SCHEMAS and self.field!='方向':self.formula.set('('+self.formula.get()+') / 2')
    def edit_definition_info(self):
        d=self.definition()
        if not d:return
        def apply(v):
            self.required(v['name'],'定義名')
            if any(x['id']!=d['id'] and x['name']==v['name'] for x in self.data['definitions']):raise ValueError('定義名が重複しています。')
            d.update(v)
        self.form('共通定義の情報',[('name','定義名',d['name'],None),('revision','改訂',d['revision'],None)],apply)
    def preview_scom_selected(self,_=None):self.scom_id=self.preview_choices.get(self.preview_choice.get());self.calc_formula();self.update_definition_preview()
    def update_definition_preview(self):
        if not self.preview:return
        s=project.get(self.data,'scoms',self.preview_choices.get(self.preview_choice.get()))
        self.preview.load(self.data,s,self.element_id)
        self.preview_values.configure(text='読み取り専用 / '+(s['name'] if s else 'SCOM 未選択')+'\n'+('\n'.join(p['id']+' '+presets.caption(p)+'：'+str(s['values'].get(p['id'],'未入力'))+' '+p.get('unit','mm') for p in presets.rules(self.data,s)) if s else ''))
    def add_definition(self):
        def apply(v):
            self.required(v['name'],'定義名')
            if v['name'] in self.choices('definitions'):raise ValueError('定義名が重複しています。')
            d=project.add_definition(self.data,v['kind'],v['name']);self.definition_id=d['id'];self.element_id=None
        self.form('共通定義を追加',[('kind','種類','GMSET',['GMSET','PTSET']),('name','定義名','',None)],apply)
    def duplicate_definition(self):
        d=self.definition()
        if not d:return
        import uuid
        copied=copy.deepcopy(d);copied['id']=uuid.uuid4().hex;name=d['name']+'-COPY';n=1
        while name in self.choices('definitions'):n+=1;name=d['name']+'-COPY'+str(n)
        copied['name']=name
        for e in copied['elements']:e['id']=uuid.uuid4().hex
        self.data['definitions'].append(copied);self.definition_id=copied['id'];self.element_id=None;self.mark();self.render_page()
    def delete_definition(self):
        d=self.definition()
        if not d:return
        if any(d['id'] in (s['gmset_id'],s['ptset_id']) for s in self.data['scoms']):messagebox.showinfo('削除できません','SCOM から参照されています。',parent=self);return
        if d['kind']=='PTSET' and pairing.users(self.data,d['id']):messagebox.showinfo('削除できません','GMSET の適用先として選択されています。',parent=self);return
        if messagebox.askyesno('削除','未使用の共通定義を削除しますか？',parent=self):self.data['definitions'].remove(d);self.definition_id=next((x['id'] for x in self.data['definitions']),None);self.mark();self.render_page()
    def add_element(self):
        d=self.definition()
        if not d:return
        choices={model.SCHEMAS[k][0]:k for k in model.SCHEMAS if (k=='point')==(d['kind']=='PTSET')}
        def apply(v):e=project.add_element(self.data,d,choices[v['kind']]);self.element_id=e['id']
        self.form('要素を追加',[('kind','要素の種類',next(iter(choices)),list(choices))],apply)
    def duplicate_element(self):
        d=self.definition();e=self.element()
        if e:
            # Legacy helper only copies metadata/expressions, never numeric parameter values.
            self.element_id=model.duplicate_element({'elements':d['elements']},e)['id'];self.mark();self.render_page()
    def rename_element(self):
        e=self.element()
        if not e:return
        def apply(v):self.required(v['name'],'要素名');e['name']=v['name']
        self.form('要素名を編集',[('name','要素名',e['name'],None)],apply)
    def delete_element(self):
        d=self.definition();e=self.element()
        if e and messagebox.askyesno('削除','要素を削除しますか？ 共通定義の使用先に影響します。',parent=self):d['elements'].remove(e);self.element_id=None;self.mark();self.render_page()

    def build_specs(self):
        self.heading('スペック登録','SCOM・DETAIL・PROP の組み合わせと口径条件を登録します。',[('SPEC を追加',self.add_spec)])
        split=ttk.Panedwindow(self.content,orient='horizontal');split.pack(fill='both',expand=True)
        middle=ttk.Frame(split,padding=12,width=620);right=ttk.Frame(split,padding=12,width=300)
        middle.pack_propagate(False);right.pack_propagate(False)
        split.add(middle,weight=4);split.add(right,weight=2);self.balance(split,(.72,))
        self.spec_tree=self.registered_browser.tree
        spec_tools=ttk.Frame(middle);spec_tools.pack(fill='x',pady=(0,8))
        for text,command in (('SPEC 情報を編集',self.edit_spec),('SPEC を複製',self.duplicate_spec),('SPEC を削除',self.delete_spec)):
            ttk.Button(spec_tools,text=text,command=command).pack(side='left',padx=3)
        spec=project.get(self.data,'specs',self.spec_id)
        if not spec:ttk.Label(middle,text='SPEC を追加してください。').pack();return
        ttk.Label(middle,text=spec['name']+' / Rev.'+spec['revision'],style='Heading.TLabel').pack(anchor='w')
        ttk.Label(middle,text=spec['description'],style='Muted.TLabel',wraplength=600).pack(anchor='w',pady=6)
        toolbar=ttk.Frame(middle);toolbar.pack(fill='x',pady=10)
        for label,cmd in [('登録行を追加',self.add_spec_entry),('編集',self.edit_spec_entry),('複製',self.duplicate_spec_entry),('削除',self.delete_spec_entry)]:ttk.Button(toolbar,text=label,command=cmd).pack(side='left',padx=3)
        self.spec_table=self.table(middle,[('scom','SCOM',170),('detail','DETAIL',160),('prop','PROP',160),('type','部品種別',90),('bore1','口径 1',80),('bore2','口径 2',80),('desc','説明',160),('sdte','SDTE（従来参照）',160),('smte','SMTE',160)],height=14)
        for entry in spec['entries']:
            scom=project.get(self.data,'scoms',entry['scom_id'])
            related=[(project.get(self.data,collection,entry.get(key,'')) or {}).get('name','未設定') for key,collection in (('detail_id','catalog_details'),('prop_id','catalog_props'))]
            self.spec_table.insert('','end',iid=entry['id'],values=(scom['name'] if scom else '[未設定]',*related,entry['type'],entry['bore1'],entry['bore2'],entry['description'],*( (project.get(self.data,'texts',entry.get(k,'')) or {}).get('name','未設定') for k in ('sdte_id','smte_id'))))
        self.spec_table.bind('<<TreeviewSelect>>',self.spec_entry_select);self.spec_table.bind('<Double-1>',lambda _:self.edit_spec_entry())
        ttk.Label(middle,text='この表は選択条件のたたき台です。実機で必要な属性や分岐条件は作成例から追加します。',style='Muted.TLabel',wraplength=580).pack(anchor='w',pady=12)
        ttk.Label(right,text='参照部品を確認',style='Heading.TLabel').pack(anchor='w')
        self.preview=Preview(right,self.ui_font)
        self.spec_detail=ttk.Label(right,text='登録行を選択してください。',style='Muted.TLabel',wraplength=320);self.spec_detail.pack(anchor='w',pady=12)
        ttk.Button(right,text='参照 SCOM を開く',command=self.goto_spec_scom).pack(fill='x',pady=8)
        ttk.Button(right,text='SPEC をカタログ本に掲載',command=lambda:self.switch('books')).pack(fill='x')
        if spec['entries']:self.spec_table.selection_set(spec['entries'][0]['id']);self.update_spec_preview()
    def spec(self):return project.get(self.data,'specs',self.spec_id)
    def spec_entry(self):
        if not hasattr(self,'spec_table') or not self.spec_table.winfo_exists() or not self.spec():return None
        selection=self.spec_table.selection();return next((e for e in self.spec()['entries'] if selection and e['id']==selection[0]),None)
    def spec_select(self,_=None):self.registered_browser.select()
    def spec_entry_select(self,_=None):
        if not self.busy:self.update_spec_preview()
    def update_spec_preview(self):
        entry=self.spec_entry();scom=project.get(self.data,'scoms',entry['scom_id']) if entry else None
        self.preview.load(self.data,scom)
        self.spec_detail.configure(text=('種別：'+entry['type']+'\n口径条件：'+entry['bore1']+' × '+entry['bore2']+'\n参照：'+(scom['name'] if scom else '未設定')+'\n\nSCOM の値や共通定義は参照先で編集します。') if entry else '登録行を選択してください。')
        if entry:
            self.spec_detail.configure(text=self.spec_detail.cget('text')+'\n\n'+'\n'.join(label+'：'+(project.get(self.data,collection,entry.get(key,'')) or {}).get('name','未設定') for key,collection,label in (('detail_id','catalog_details','DETAIL'),('prop_id','catalog_props','PROP'))))
    def goto_spec_scom(self):
        entry=self.spec_entry();s=project.get(self.data,'scoms',entry['scom_id']) if entry else None
        if s:self.scom_id=s['id'];self.cate_id=s['cate_id'];self.catalog_tab='scom';self.switch('catalog')
    def spec_form(self,spec=None,*,after_create=None):
        def apply(v):
            self.required(v['name'],'SPEC 名')
            if any(x['name']==v['name'] and (not spec or x['id']!=spec['id']) for x in self.data['specs']):raise ValueError('SPEC 名が重複しています。')
            item=spec or project.add_spec(self.data,v['name']);item.update(v);self.spec_id=item['id']
            if after_create is not None:self.after_idle(after_create)
        self.form('SPEC 情報',[('name','SPEC 名',spec['name'] if spec else '',None),('description','説明',spec['description'] if spec else '',None),('revision','改訂',spec['revision'] if spec else '01',None)],apply)
    def add_spec(self):self.spec_form()
    def edit_spec(self):
        if self.spec():self.spec_form(self.spec())
    def duplicate_spec(self):
        spec=self.spec()
        if not spec:return
        import uuid
        item=copy.deepcopy(spec);item['id']=uuid.uuid4().hex;name=spec['name']+'-COPY';n=1
        while name in self.choices('specs'):n+=1;name=spec['name']+'-COPY'+str(n)
        item['name']=name
        for entry in item['entries']:entry['id']=uuid.uuid4().hex
        self.data['specs'].append(item);self.spec_id=item['id'];self.mark();self.render_page()
    def delete_spec(self):
        spec=self.spec()
        if spec and messagebox.askyesno('削除','SPEC を削除しますか？ 発行済み冊子の内容は変わりません。',parent=self):self.data['specs'].remove(spec);self.spec_id=next((x['id'] for x in self.data['specs']),None);self.mark();self.render_page()
    def entry_form(self,entry=None,*,scom_id=None):
        spec=self.spec();scoms=self.choices('scoms')
        if not spec or not scoms:messagebox.showinfo('SCOM が必要','先に参照する SCOM を作成してください。',parent=self);return
        scoms['未設定']=''
        if entry and entry['scom_id'] and entry['scom_id'] not in scoms.values():scoms['参照先不明：'+entry['scom_id']]=entry['scom_id']
        selected=next((name for name,ident in scoms.items() if ident==(entry['scom_id'] if entry else (scom_id or self.scom_id))),next(iter(scoms)))
        fields=[('type','部品種別（仮の選択項目）',entry['type'] if entry else ('' if scom_id else 'REDU'),None),('bore1','口径条件 1',entry['bore1'] if entry else '',None),('bore2','口径条件 2',entry['bore2'] if entry else '',None),('scom','参照 SCOM',selected,list(scoms)),('description','説明',entry['description'] if entry else '',None)]
        mappings={}
        for key,collection,label in (('detail_id','catalog_details','DETAIL'),('prop_id','catalog_props','PROP')):
            mapping={r['name']:r['id'] for r in self.data.get(collection,[])};mapping['未設定']=''
            initial=(getattr(self,'catalog_'+key,None) or '') if (scom_id or self.scom_id)==getattr(self,'catalog_seed_scom_id',None) else ''
            ident=entry.get(key,'') if entry is not None else initial
            if ident and ident not in mapping.values():mapping['参照先不明：'+ident]=ident
            mappings[key]=mapping
            fields.append((key,label,next((name for name,value in mapping.items() if value==ident),'未設定'),list(mapping)))
        for key,kind in (('sdte_id','SDTE'),('smte_id','SMTE')):
            mapping={r['name']:r['id'] for r in self.data.get('texts',[]) if r['type']==kind};mapping['未設定']=''
            ident=(entry or {}).get(key,'')
            if ident and ident not in mapping.values():mapping['参照先不明：'+ident]=ident
            mappings[key]=mapping
            fields.append((key,'参照 '+kind,next((name for name,value in mapping.items() if value==ident),'未設定'),list(mapping)))
        def apply(v):
            self.required(v['type'],'部品種別');self.required(v['bore1'],'口径条件 1')
            combination_keys=('detail_id','prop_id')
            use_combination=entry is None or any(key in entry for key in combination_keys) or any(mappings[key][v[key]] for key in combination_keys)
            record=entry or project.add_spec_entry(self.data,spec,scoms[v['scom']])
            record.update(type=v['type'],bore1=v['bore1'],bore2=v['bore2'],scom_id=scoms[v['scom']],description=v['description'])
            for key,mapping in mappings.items():
                if key in combination_keys and not use_combination:continue
                record[key]=mapping[v[key]]
            if scom_id:self.data.setdefault('creation_draft',{}).update(scom_id=record['scom_id'],spec_id=spec['id'])
        self.form('SPEC の登録行',fields,apply)
    def add_spec_entry(self):self.entry_form()
    def edit_spec_entry(self):
        entry=self.spec_entry()
        if entry:self.entry_form(entry)
    def duplicate_spec_entry(self):
        entry=self.spec_entry()
        if not entry:return
        import uuid
        item=copy.deepcopy(entry);item['id']=uuid.uuid4().hex;self.spec()['entries'].append(item);self.mark();self.render_page()
    def delete_spec_entry(self):
        entry=self.spec_entry()
        if entry and messagebox.askyesno('削除','SPEC の登録行を削除しますか？',parent=self):self.spec()['entries'].remove(entry);self.mark();self.render_page()

    def build_books(self):
        self.heading('カタログ本・PDF','SCOM・共通定義・SPEC の改訂を固定して、後から同じ内容で PDF を出力できます。')
        split=ttk.Panedwindow(self.content,orient='horizontal');split.pack(fill='both',expand=True)
        left=ttk.Frame(split,padding=10);right=ttk.Frame(split,padding=14);split.add(left,weight=3);split.add(right,weight=2)
        meta=ttk.LabelFrame(left,text='新しい冊子を作成',padding=12);meta.pack(fill='x')
        ttk.Label(meta,text='タイトル').grid(row=0,column=0,sticky='w');self.book_title=tk.StringVar(value='配管部品カタログ');ttk.Entry(meta,textvariable=self.book_title).grid(row=0,column=1,sticky='ew',padx=8,pady=5)
        ttk.Label(meta,text='版').grid(row=1,column=0,sticky='w');self.book_edition=tk.StringVar(value='第 1 版');ttk.Entry(meta,textvariable=self.book_edition).grid(row=1,column=1,sticky='ew',padx=8,pady=5);meta.columnconfigure(1,weight=1)
        notebook=ttk.Notebook(left);notebook.pack(fill='both',expand=True,pady=12)
        sframe=ttk.Frame(notebook,padding=8);specframe=ttk.Frame(notebook,padding=8)
        notebook.add(sframe,text='掲載 SCOM');notebook.add(specframe,text='掲載 SPEC')
        ttk.Label(sframe,text='Ctrl / Shift で複数選択。SPEC の参照 SCOM は自動で追加されます。',style='Muted.TLabel',wraplength=600).pack(anchor='w',pady=5)
        self.book_scoms=self.table(sframe,[('name','SCOM',230),('size','サイズ',100),('revision','改訂',70)],height=9);self.book_scoms.configure(selectmode='extended')
        for s in self.data['scoms']:self.book_scoms.insert('','end',iid=s['id'],values=(s['name'],s['size'],s['revision']))
        self.book_scoms.selection_set(self.book_scoms.get_children())
        self.book_specs=self.table(specframe,[('name','SPEC',240),('rev','改訂',80)],height=9);self.book_specs.configure(selectmode='extended')
        for spec in self.data['specs']:self.book_specs.insert('','end',iid=spec['id'],values=(spec['name'],spec['revision']))
        self.book_specs.selection_set(self.book_specs.get_children())
        ttk.Button(left,text='掲載内容と改訂を固定して冊子を作成',command=self.create_book,style='Primary.TButton').pack(fill='x',pady=8)
        ttk.Label(right,text='保存した冊子',style='Heading.TLabel').pack(anchor='w',pady=6)
        self.books_table=self.table(right,[('title','タイトル',220),('edition','版',90),('date','保存日',100)],height=6)
        for book in self.data['books']:
            if isinstance(book,dict) and 'id' in book:self.books_table.insert('','end',iid=book['id'],values=(book.get('title',''),book.get('edition',''),book.get('created_at','')[:10]))
        if self.books_table.exists(str(self.selected_book)):self.books_table.selection_set(self.selected_book)
        self.books_table.bind('<<TreeviewSelect>>',self.book_select)
        self.book_info=tk.Text(right,height=12,wrap='word',font=(self.ui_font,10),relief='flat',bg='#f3f7fc');self.book_info.pack(fill='both',expand=True,pady=10)
        ttk.Button(right,text='選択した冊子を PDF に保存',command=self.export_pdf,style='Primary.TButton').pack(fill='x',pady=6)
        ttk.Button(right,text='冊子の固定データを JSON で保存',command=self.export_book_json).pack(fill='x')
        ttk.Button(right,text='選択した冊子を削除',command=self.delete_book).pack(fill='x',pady=6)
        self.update_book_info()
    def book(self):return next((b for b in self.data['books'] if isinstance(b,dict) and b.get('id')==self.selected_book),None)
    def book_select(self,_=None):
        if self.busy:return
        selection=self.books_table.selection()
        if selection:self.selected_book=selection[0];self.update_book_info()
    def update_book_info(self):
        book=self.book()
        if book:
            text=book['title']+' / '+book['edition']+'\n作成日：'+book['created_at'][:10]+'\n\nSCOM：'+str(len(book['scoms']))+' 件\nSPEC：'+str(len(book['specs']))+' 件\n共通定義：'+str(len(book['definitions']))+' 件\n\n掲載対象と改訂を固定済み。\nその後のプロジェクト編集はこの冊子に反映されません。\n\n'+('\n'.join(s['name']+' / Rev.'+s['revision'] for s in book['scoms'][:8]))
        else:text='冊子を作成・選択してください。\n\nPDF には表紙、収録一覧、寸法表、SCOM 概略図、SPEC 表、共通定義と式を掲載します。\n\nPDF 出力は reportlab を使用します。'
        self.set_text(self.book_info,text)
    def create_book(self):
        from . import booklet
        try:
            book=booklet.snapshot(self.data,list(self.book_scoms.selection()),list(self.book_specs.selection()),self.book_title.get(),self.book_edition.get())
        except (ValueError,KeyError) as exc:messagebox.showerror('冊子を作成できません',str(exc),parent=self);return
        self.data['books'].append(book);self.selected_book=book['id'];self.mark('冊子の内容・改訂を固定しました。プロジェクトも保存してください。');self.render_page()
    def export_pdf(self):
        book=self.book()
        if not book:messagebox.showinfo('冊子を選択','先に冊子を作成・選択してください。',parent=self);return
        path=filedialog.asksaveasfilename(parent=self,title='PDF カタログ本を保存',defaultextension='.pdf',initialfile='catalog-book.pdf',filetypes=[('PDF','*.pdf')])
        if not path:return
        from . import booklet
        try:booklet.generate_pdf(book,path)
        except (OSError,ValueError,RuntimeError,KeyError) as exc:messagebox.showerror('PDF を出力できません',str(exc),parent=self);return
        self.status.configure(text='PDF を保存しました：'+path)
    def export_book_json(self):
        book=self.book()
        if not book:return
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.json',initialfile='catalog-book-snapshot.json')
        if path:
            try:Path(path).write_text(json.dumps(book,ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError as exc:messagebox.showerror('保存できません',str(exc),parent=self)
    def delete_book(self):
        book=self.book()
        if book and messagebox.askyesno('冊子を削除','プロジェクト内の冊子固定データを削除しますか？ 出力済みの PDF は削除しません。',parent=self):self.data['books'].remove(book);self.selected_book=None;self.mark();self.render_page()

    def build_rules(self):
        from .preset_ui import PresetEditor
        self.preset_editor=PresetEditor(self)

    def add_parameter(self):self.preset_editor.parameter_form()
    def edit_parameter(self):self.preset_editor.edit_parameter()
    def remove_parameter(self):self.preset_editor.remove_parameter()

    def assign_scom_preset(self):
        scom=project.get(self.data,'scoms',self.scom_id)
        if not scom:return
        options=presets.choices(self.data)
        ident=presets.selected_id(self.data,scom)
        if ident and ident not in options.values():options['参照先不明：'+ident]=ident
        def apply(v):presets.bind(self.data,scom,options[v['preset']])
        self.form('SCOM の PARAM プリセットを割り当て（番号・値は変更しません）',[('preset','プリセット',presets.label(self.data,scom),list(options))],apply)

    @staticmethod
    def set_text(widget,text):widget.configure(state='normal');widget.delete('1.0','end');widget.insert('1.0',text);widget.configure(state='disabled')
    def build_checks(self):
        self.heading('確認・マクロ','参照関係、入力値、式、SPEC の条件を確認します。出力はコメントのみの構成確認用ファイルです。',[('構成確認ファイルを保存',self.export_review)])
        notebook=ttk.Notebook(self.content);notebook.pack(fill='both',expand=True)
        first=ttk.Frame(notebook,padding=12);second=ttk.Frame(notebook,padding=12);notebook.add(first,text='入力・参照の確認');notebook.add(second,text='生成内容のたたき台')
        problems=project.issues(self.data)
        check=tk.Text(first,wrap='word',font=(self.ui_font,11));check.pack(fill='both',expand=True)
        self.set_text(check,('\n\n'.join('! '+p for p in problems) if problems else '✓ 入力・参照の基本チェックに問題はありません。')+'\n\n○ E3D の実機属性、選択条件、登録コマンドは未検証です。')
        text=tk.Text(second,wrap='none',font=('Consolas',10));text.pack(fill='both',expand=True);self.set_text(text,project.macro_text(self.data))
    def export_review(self):
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.mac',initialfile='catalog-integrated-review.mac')
        if path:
            try:Path(path).write_text(project.macro_text(self.data),encoding='utf-8')
            except OSError as exc:messagebox.showerror('出力できません',str(exc),parent=self);return
            self.status.configure(text='構成確認用コメントファイルを保存しました：'+path)
    def guard(self):
        if self.commit_definition_name() is False:return False
        pending=self.page=='rules' and hasattr(self,'preset_editor') and self.preset_editor.has_changes()
        if not self.dirty and not pending:return True
        answer=messagebox.askyesnocancel('未保存の変更','変更を保存しますか？',parent=self)
        return False if answer is None else self.save_project() if answer else True
    def save_project(self):
        if self.commit_definition_name() is False:return False
        if self.page=='rules' and self.preset_editor.has_changes() and not self.preset_editor.save():return False
        path=self.path or filedialog.asksaveasfilename(parent=self,defaultextension='.json',initialfile='catalog-integrated-project.json',filetypes=[('プロジェクト JSON','*.json')])
        if not path:return False
        try:project.save(self.data,path)
        except (OSError,ValueError) as exc:messagebox.showerror('保存できません',str(exc),parent=self);return False
        self.path=path;self.dirty=False;self.title('Catalog Studio — '+self.data['name']);self.status.configure(text='保存済み：'+str(path));return True
    def reset_selection(self):
        for collection,attr in [('cates','cate_id'),('scoms','scom_id'),('definitions','definition_id'),('specs','spec_id')]:setattr(self,attr,next((x['id'] for x in self.data[collection]),None))
        self.element_id=None;self.field=None;self.selected_book=None
        self.catalog_tab='scom';self.catalog_member_key=None;self.catalog_detail_id=None;self.catalog_prop_id=None;self.catalog_seed_scom_id=None
    def add_valve_sample(self):
        if self.grab_current():
            self.grab_current().lift();return
        if self.page=='rules' and not self.preset_editor.can_leave():return
        if self.commit_definition_name() is False:return
        from .valve_sample import prepare
        try:data, ids=prepare(self.data)
        except ValueError as exc:
            messagebox.showerror('サンプルを追加できません',str(exc),parent=self);return
        self.data=data;self.definition_id=ids['gmset_id'];self.scom_id=ids['scom_id']
        self.element_id=None;self.page='gmset';self.render_page()
        self.mark('手動弁サンプルのPTSET・GMSETと確認用SCOMを追加しました。')

    def import_creation_macro(self):
        current=self.grab_current()
        if current is not None:current.focus_set();return
        from .macro_import_ui import MacroImportDialog
        return MacroImportDialog(self)
    def open_project(self):
        if not self.guard():return
        path=filedialog.askopenfilename(parent=self,title='プロジェクト JSON を読み込み（E3D 出力は未対応）',filetypes=[('プロジェクト JSON','*.json')])
        if not path:return
        try:data=project.load(path)
        except (OSError,ValueError,RecursionError) as exc:messagebox.showerror('読み込みできません',str(exc),parent=self);return
        self.data=data;self.path=path;self.dirty=False;self.reset_selection();self.render_page();self.title('Catalog Studio — '+data['name']);self.status.configure(text='読み込み済み：'+path)
    def new_project(self):
        if not self.guard():return
        def apply(v):
            self.required(v['name'],'プロジェクト名');self.data=project.sample();self.data['name']=v['name']
            for key in ('cates','scoms','definitions','specs','books','texts','tables'):self.data[key]=[]
            self.path=None;self.reset_selection();self.page='ptset'
        self.form('新規プロジェクト',[('name','プロジェクト名','新規カタログ',None)],apply)
    def destroy(self):
        # Tcl keeps scheduled layout callbacks after widget commands disappear.
        for timer in self.tk.call('after','info'):
            self.after_cancel(timer)
        super().destroy()

    def close(self):
        if self.guard():self.destroy()


def main():
    try:app=IntegratedStudio()
    except tk.TclError as exc:
        print('デスクトップ環境で起動してください。\n'+str(exc),file=sys.stderr);return 1
    app.mainloop();return 0
