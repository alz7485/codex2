"""PTSET/GMSET creation shell: editable fields, not an E3D expression engine."""
import copy
import tkinter as tk
import uuid
from tkinter import messagebox, ttk
from . import element_schema as schema, project, expressions, catalogue, presets

BLUE = '#2269de'
MUTED = '#738499'


class ConstructionEditor(ttk.Frame):
    def __init__(self, host, kind):
        super().__init__(host.content)
        self.host, self.kind = host, kind
        self.busy = True
        self.field = None
        self.element_id = None
        self.section = 'main'
        self.preview_scom_id = host.scom_id
        self.pack(fill='both', expand=True)
        definitions = [d for d in host.data['definitions'] if d['kind'] == kind]
        preferred = project.get(host.data, 'definitions', host.definition_id)
        draft=host.data.get('creation_draft',{})
        staged=project.get(host.data,'definitions',draft.get('ptset_id' if kind=='PTSET' else 'gmset_id'))
        if staged and staged['kind']!=kind:staged=None
        demo = next((d for d in definitions if d['id'] == ('ui-ptset' if kind == 'PTSET' else 'ui-gmset')), None)
        self.definition_id = preferred['id'] if preferred and preferred['kind'] == kind else (staged or demo or (definitions[0] if definitions else {})).get('id')
        self.build()
        self.refresh()
        self.busy = False

    @property
    def data(self): return self.host.data
    def definition(self): return project.get(self.data, 'definitions', self.definition_id)
    def element(self): return next((e for e in schema.walk((self.definition() or {}).get('elements', [])) if e['id'] == self.element_id), None)

    def build(self):
        if self.kind in ('PTSET','GMSET'):
            from .construction_layout import build_simple
            build_simple(self)
            return
        top = ttk.Frame(self); top.pack(fill='x', pady=(0, 10))
        block = ttk.Frame(top); block.pack(side='left', fill='x', expand=True)
        ttk.Label(block, text=({'PTSET':'1. PTSET','GMSET':'2. GMSET'}.get(self.kind,self.kind)) + ' を作成・編集', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(block, text='1. 名前を付けて PTSET を作成 → 2. 種類を選んで要素を作成 → 3. 属性を入力' if self.kind=='PTSET' else '要素・属性・式を編集します。プレビューは構成模式図です。', style='Muted.TLabel', wraplength=690).pack(anchor='w', pady=4)
        for text, command in [('保存', self.host.save_project), ('出力を確認', self.review), ('新しい '+self.kind+' を作る', self.add_definition)]:
            button=ttk.Button(top,text=text,command=command);button.pack(side='right',padx=3)
            if command==self.add_definition:self.new_set_button=button
        metadata = ttk.Frame(self); metadata.pack(fill='x', pady=(0, 10))
        ttk.Label(metadata, text=self.kind + ' 名').pack(side='left')
        self.def_name = tk.StringVar()
        self.name_entry = ttk.Entry(metadata, textvariable=self.def_name, width=32); self.name_entry.pack(side='left', padx=8)
        self.name_entry.bind('<FocusOut>', lambda _: self.commit_name()); self.name_entry.bind('<Return>', lambda _: self.commit_name())
        if schema.PARENT_FIELDS[self.kind]:ttk.Button(metadata, text='親属性・中立軸', command=self.edit_parent).pack(side='left', padx=4)
        self.usage_label = ttk.Label(metadata, text='', style='Muted.TLabel'); self.usage_label.pack(side='left', padx=10)
        ttk.Button(metadata, text='複製して作成', command=self.duplicate_definition).pack(side='right')
        preset_bar=ttk.Frame(self);preset_bar.pack(fill='x',pady=(0,8))
        ttk.Label(preset_bar,text='PARAM プリセット').pack(side='left')
        self.preset_choice=ttk.Combobox(preset_bar,state='readonly',width=36);self.preset_choice.pack(side='left',padx=8)
        self.preset_choice.bind('<<ComboboxSelected>>',self.assign_preset)
        ttk.Button(preset_bar,text='プリセットを管理',command=lambda:self.host.switch('rules')).pack(side='left')
        if self.kind in ('PTSET','GMSET'):
            flow=ttk.Frame(preset_bar if self.kind=='PTSET' else self)
            if self.kind=='PTSET':flow.pack(side='right')
            else:flow.pack(fill='x',pady=(0,8))
            self.workflow_label=ttk.Label(flow,text='PTSET → GMSET → SCOM → スペック',style='Muted.TLabel',wraplength=600)
            if self.kind!='PTSET':self.workflow_label.pack(side='left')
            self.create_part_button=ttk.Button(flow,text='PTSET の編集を終えて GMSET へ' if self.kind=='PTSET' else '次へ：この GMSET で SCOM を登録',style='TButton' if self.kind=='PTSET' else 'Primary.TButton',command=self.create_part)
            self.create_part_button.pack(side='right')
        split = ttk.Panedwindow(self, orient='horizontal'); split.pack(fill='both', expand=True)
        left = ttk.Frame(split, padding=8); center = ttk.Frame(split, padding=10); right = ttk.Frame(split, padding=10)
        for frame, weight in ((left, 2), (center, 5), (right, 3)): split.add(frame, weight=weight)
        self.host.balance(split,(.24,.70) if self.kind=='PTSET' else (.23,.71))
        ttk.Label(left, text='定義を選択', style='Heading.TLabel').pack(anchor='w', pady=4)
        self.def_choice = ttk.Combobox(left, state='readonly'); self.def_choice.pack(fill='x', pady=5)
        self.def_choice.bind('<<ComboboxSelected>>', self.select_definition)
        ttk.Label(left, text='作成済みのポイント' if self.kind == 'PTSET' else '形状の構成', style='Heading.TLabel').pack(anchor='w', pady=(12, 5))
        self.elements = ttk.Treeview(left, columns=('number','type') if self.kind=='PTSET' else ('type',), show='tree headings', selectmode='browse', height=5)
        self.elements.heading('#0', text='要素名'); self.elements.heading('type', text='種類')
        self.elements.column('#0', width=130, minwidth=70); self.elements.column('type', width=75, minwidth=60)
        if self.kind=='PTSET':
            self.elements.heading('number',text='番号');self.elements.column('number',width=45,minwidth=40)
        self.elements.pack(fill='both', expand=True); self.elements.bind('<<TreeviewSelect>>', self.select_element)
        buttons = ttk.Frame(left); buttons.pack(fill='x', pady=8)
        for text, fn in [('複製', self.duplicate_element), ('削除', self.delete_element)]: ttk.Button(buttons, text=text, command=fn).pack(side='left', padx=2)
        outline = ttk.Frame(left); outline.pack(fill='x')
        for text,fn in (([('子を追加',self.add_child)] if self.kind!='PTSET' else [])+[('↑',lambda:self.move_element(-1)),('↓',lambda:self.move_element(1))]): ttk.Button(outline,text=text,command=fn,width=7).pack(side='left',padx=2)
        p0=None
        if self.kind == 'PTSET':
            p0=ttk.Label(left,text='P0：原点 / +Z（自動生成・編集不可）',style='Muted.TLabel',wraplength=250);p0.pack(anchor='w',pady=5)
        if self.kind=='PTSET':ttk.Label(right,text='2. 種類を選んで要素を作成',style='Heading.TLabel').pack(anchor='w',pady=(0,6))
        library = ttk.LabelFrame(right if self.kind=='PTSET' else left,text='ポイントの種類' if self.kind=='PTSET' else '要素ライブラリ',padding=8);library.pack(fill='x',pady=6)
        self.negative = tk.BooleanVar(value=False)
        if self.kind == 'GMSET':
            ttk.Checkbutton(library, text='ネガティブ（15種類）', variable=self.negative, command=self.populate_library).pack(anchor='w')
            ttk.Label(library, text='ポジティブ：18種類', style='Muted.TLabel').pack(anchor='w')
        elif self.kind=='PTSET':ttk.Label(library,text='選択すると、指定方法を下に表示します。',style='Muted.TLabel',wraplength=310).pack(anchor='w')
        else: ttk.Label(library,text=' / '.join(schema.TYPES_BY_SET[self.kind]),style='Muted.TLabel').pack(anchor='w')
        library_list=ttk.Frame(library);library_list.pack(fill='x',pady=5)
        self.library = tk.Listbox(library_list, height=4 if self.kind=='PTSET' else 3, exportselection=False, font=(self.host.ui_font, 10), relief='flat', selectbackground='#e4efff', selectforeground=BLUE)
        self.library.pack(side='left',fill='x',expand=True)
        scroll=ttk.Scrollbar(library_list,orient='vertical',command=self.library.yview);scroll.pack(side='right',fill='y');self.library.configure(yscrollcommand=scroll.set)
        if self.kind=='PTSET':
            self.library.bind('<<ListboxSelect>>',self.describe_selected_type)
            self.type_help=ttk.Label(library,text='',wraplength=310,justify='left');self.type_help.pack(anchor='w',fill='x',pady=(6,8))
        else:self.library.bind('<Double-1>',lambda _:self.add_element())
        self.create_element_button=ttk.Button(library,text='作成' if self.kind=='PTSET' else '＋ 選択した要素を追加',command=self.add_element,style='Primary.TButton' if self.kind=='PTSET' else 'TButton');self.create_element_button.pack(fill='x')
        self.populate_library()
        if self.kind!='PTSET':library.pack(side='bottom',fill='x',pady=6,before=self.elements)
        if p0:p0.pack(side='bottom',anchor='w',pady=5,before=self.elements)
        outline.pack(side='bottom',fill='x',before=self.elements)
        buttons.pack(side='bottom',fill='x',pady=8,before=self.elements)
        if self.kind=='PTSET':ttk.Label(center,text='3. ポイントを選んで属性を入力',style='Heading.TLabel').pack(anchor='w',pady=(0,6))
        title = ttk.Frame(center); title.pack(fill='x')
        self.element_name = tk.StringVar(); self.element_name_entry = ttk.Entry(title, textvariable=self.element_name)
        self.element_name_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))
        self.element_name.trace_add('write', self.rename_element)
        self.type_choice = ttk.Combobox(title, state='readonly', width=10); self.type_choice.pack(side='right'); self.type_choice.bind('<<ComboboxSelected>>', self.change_type)
        self.element_note = ttk.Label(center, text='', style='Muted.TLabel', wraplength=530); self.element_note.pack(anchor='w', pady=6)
        self.tabs = ttk.Notebook(center); self.tabs.pack(fill='both', expand=True, pady=(3, 8))
        self.tables = {}
        sections = [('main', '基本・位置' if self.kind == 'PTSET' else '形状・位置')]
        sections += [('detail', '詳細属性')] if self.kind == 'PTSET' else [('common', '共通属性'), ('negative', 'ネガティブ属性')]
        sections += [('extra', '保持した追加属性')]
        for key, label in sections:
            frame = ttk.Frame(self.tabs, padding=3); self.tabs.add(frame, text=label)
            table = self.host.table(frame, [('attr', '属性', 90), ('meaning', '説明', 180), ('value', '設定値・式', 260)], height=4)
            table.bind('<<TreeviewSelect>>',lambda event,s=key:self.select_field(s))
            table.bind('<Double-1>',lambda _:self.focus_value_input())
            self.tables[key] = table
        self.section_order = [s[0] for s in sections]
        self.tabs.bind('<<NotebookTabChanged>>', self.tab_changed)
        editor = ttk.LabelFrame(center, text='属性値・式の入力', padding=10); editor.pack(side='bottom',fill='x',before=self.tabs)
        self.field_label = ttk.Label(editor, text='', style='Heading.TLabel'); self.field_label.pack(anchor='w', pady=(0, 6))
        self.expression = tk.StringVar(); self.expression.trace_add('write', self.edit_expression)
        self.expression_entry = ttk.Entry(editor, textvariable=self.expression, font=(self.host.ui_font, 13)); self.expression_entry.pack(fill='x')
        self.choice_entry = ttk.Combobox(editor, textvariable=self.expression, state='normal')
        reference = self.reference_frame = ttk.Frame(editor); reference.pack(fill='x', pady=8)
        self.ref_kind = ttk.Combobox(reference, values=schema.REFERENCE_TYPES, state='readonly', width=14); self.ref_kind.set('PARAM'); self.ref_kind.pack(side='left')
        self.ref_kind.bind('<<ComboboxSelected>>', lambda _: self.update_role())
        self.ref_number = tk.StringVar(value='1')
        self.number_entry = ttk.Spinbox(reference, from_=1, to=999, width=5, textvariable=self.ref_number); self.number_entry.pack(side='left', padx=5)
        self.ref_number.trace_add('write', lambda *_: self.update_role())
        ttk.Button(reference, text='式へ挿入', command=self.insert_reference).pack(side='left', padx=3)
        ttk.Button(reference, text='÷ 2', command=self.half).pack(side='left')
        self.role_label = ttk.Label(editor, text='', style='Muted.TLabel'); self.role_label.pack(anchor='w')
        if self.kind=='PTSET':ttk.Button(reference,text='式を整理',command=self.normalize_expression).pack(side='left',padx=3)
        else:
            helpers=ttk.Frame(editor);helpers.pack(fill='x',pady=4)
            for text,fn in [('式を読みやすく整理',self.normalize_expression),('NAPP 適用先',self.edit_napp),('直径／半径',self.edit_sizes),('LINE の点列',self.edit_points)]:ttk.Button(helpers,text=text,command=fn).pack(side='left',padx=2)
        ttk.Label(editor,text='四則演算・SUM・TIMES・TAN に対応。ANGL は度。',style='Muted.TLabel',wraplength=520).pack(anchor='w',pady=5)
        self.validation_note = ttk.Label(editor, text='', foreground='#bb6440', wraplength=520); self.validation_note.pack(anchor='w')
        self.canvas=None
        if self.kind!='PTSET':
            ttk.Label(right,text='構成プレビュー',style='Heading.TLabel').pack(anchor='w')
            ttk.Label(right,text='模式図：寸法・式・方向は未反映',style='Muted.TLabel',wraplength=310).pack(anchor='w',pady=5)
            self.canvas=tk.Canvas(right,width=320,height=235,bg='#f2f6fc',highlightthickness=0);self.canvas.pack(fill='both',expand=True,pady=8)
            self.canvas.bind('<Configure>',lambda _:self.draw())
        ttk.Label(right,text='確認用 SCOM（任意）' if self.kind=='PTSET' else '確認用 SCOM',style='Heading.TLabel').pack(anchor='w',pady=(8,3))
        self.scom_choice = ttk.Combobox(right, state='readonly'); self.scom_choice.pack(fill='x', pady=5)
        self.scom_choice.bind('<<ComboboxSelected>>', self.select_scom)
        self.values_label = ttk.Label(right, text='', style='Muted.TLabel', wraplength=300); self.values_label.pack(anchor='w', pady=8)
        ttk.Button(right, text='SCOM の値・ANGL を編集', command=self.open_scom).pack(fill='x', pady=8)
        ttk.Label(right, text='確認値は PTSET に保存されません。' if self.kind=='PTSET' else '読み取り専用。点・形状の定義には保存されません。\n設計側のコンテキストを推測せず、未設定参照は計算不可と表示します。', style='Muted.TLabel', wraplength=310).pack(anchor='w')

    def assign_preset(self,_=None):
        if self.busy or not self.definition():return
        try:presets.bind(self.data,self.definition(),self.preset_options[self.preset_choice.get()])
        except ValueError as exc:self.validation_note.configure(text=str(exc));self.refresh();return
        self.host.mark();self.refresh()

    def populate_library(self):
        items = schema.TYPES_BY_SET[self.kind]
        if self.kind == 'GMSET' and self.negative.get(): items = schema.NEGATIVE_BASE
        self.library.delete(0, 'end')
        for kind in items:
            label=schema.LABELS.get(kind,'負 '+schema.LABELS.get(schema.positive(kind),'未確認'))
            self.library.insert('end',kind+'  '+label)
        if items:self.library.selection_set(0)
        self.describe_selected_type()

    def describe_selected_type(self,_=None):
        if self.kind!='PTSET' and not getattr(self,'simple_layout',False):return
        selection=self.library.curselection()
        if not selection:
            self.type_help.configure(text='作成する種類を選んでください。')
            self.create_element_button.configure(text='種類を選択して作成',state='disabled');return
        kind=self.library.get(selection[0]).split()[0]
        if kind in schema.PT_GUIDES:
            guide=schema.PT_GUIDES[kind]
            text=guide['position']+'\n'+guide['direction']
            if not getattr(self,'simple_layout',False):text+='\n'+guide['usage']
        else:
            text=schema.LABELS.get(kind,'負 '+schema.LABELS.get(schema.positive(kind),'未確認'))
            text+='\n'+('ネガティブ形状。NAPP で適用先を指定します。' if kind in schema.NEGATIVE_BASE else '形状を作成してから、寸法・位置の式を入力します。')
        self.type_help.configure(text=text)
        self.create_element_button.configure(text=kind+' を作成',state='normal' if self.definition() else 'disabled')

    def toggle_create(self):
        self.creating=not self.creating
        if self.creating:self.creation_frame.pack(fill='x',pady=(0,10),before=self.tree_holder)
        else:self.creation_frame.pack_forget()
        self.add_button.configure(text='閉じる' if self.creating else '＋ 追加')

    def toggle_settings(self):
        self.settings_open=not self.settings_open
        if self.settings_open:self.settings_frame.pack(fill='x',pady=(0,14),before=self.main_split)
        else:self.commit_name();self.settings_frame.pack_forget()
        self.settings_button.configure(text='設定を閉じる' if self.settings_open else '設定・確認')

    def toggle_references(self):
        self.references_open=not self.references_open
        if self.references_open:self.reference_controls.pack(fill='x',pady=4)
        else:self.reference_controls.pack_forget()
        self.reference_button.configure(text='PARAM 選択を閉じる' if self.references_open else 'PARAM を選ぶ…')

    def open_preview(self):
        existing=getattr(self,'preview_window',None)
        if existing and existing.winfo_exists():existing.lift();return
        win=tk.Toplevel(self.host);self.preview_window=win;win.title('構成プレビュー');win.geometry('520x480');win.transient(self.host)
        ttk.Label(win,text='構成の模式図。寸法・位置・方向は未反映です。',padding=12).pack(anchor='w')
        self.canvas=tk.Canvas(win,bg='#f2f6fc',highlightthickness=0);self.canvas.pack(fill='both',expand=True,padx=12,pady=8)
        self.canvas.bind('<Configure>',lambda _:self.draw())
        def close():self.canvas=None;win.destroy()
        win.protocol('WM_DELETE_WINDOW',close);ttk.Button(win,text='閉じる',command=close).pack(pady=10)
        self.bind('<Destroy>',lambda event:close() if event.widget is self and win.winfo_exists() else None,add='+')
        self.draw()

    def focus_value_input(self):
        if not self.element() or not self.field:return
        entry=self.choice_entry if self.choice_entry.winfo_ismapped() else self.expression_entry
        entry.focus_set();entry.selection_range(0,'end')

    def refresh(self):
        self.busy = True
        self.definition_names = {d['name']: d['id'] for d in self.data['definitions'] if d['kind'] == self.kind}
        self.def_choice['values'] = list(self.definition_names)
        d=self.definition()
        self.describe_selected_type()
        if getattr(self,'simple_layout',False):
            self.add_button.configure(state='normal' if d else 'disabled')
            self.preset_summary.configure(text='PARAM：'+presets.label(self.data,d) if d else '')
        if hasattr(self,'create_part_button'):
            self.create_part_button.configure(state='normal' if d else 'disabled')
            pointset=project.get(self.data,'definitions',self.data.get('creation_draft',{}).get('ptset_id'))
            self.workflow_label.configure(text=('使用する PTSET：'+pointset['name']) if self.kind=='GMSET' and pointset else ('' if getattr(self,'simple_layout',False) else 'PTSET → GMSET → SCOM → スペック'))
        self.def_choice.set(d['name'] if d else '')
        self.def_name.set(d['name'] if d else '')
        self.elements.delete(*self.elements.get_children())
        self.preset_options=presets.choices(self.data)
        current=presets.selected_id(self.data,self.definition()) if self.definition() else ''
        if current and current not in self.preset_options.values():self.preset_options['参照先不明：'+current]=current
        self.preset_choice['values']=list(self.preset_options);self.preset_choice.set(presets.label(self.data,self.definition()) if self.definition() else '')
        if d:
            self.host.definition_id = d['id']
            def insert(items,parent=''):
                for e in items:
                    self.elements.insert(parent,'end',iid=e['id'],text=e['name'],values=(e['attrs'].get('NUMB',''),e['type']) if self.kind=='PTSET' else (e['type'],),open=True)
                    insert(e.get('children',[]),e['id'])
            insert(d['elements'])
            if not any(e['id'] == self.element_id for e in schema.walk(d['elements'])): self.element_id = next((e['id'] for e in d['elements']), None)
            if self.element_id: self.elements.selection_set(self.element_id)
            usage = sum(d['id'] in (s.get('gmset_id'), s.get('ptset_id'), s.get('ngmset_id'), s.get('gmsset_id'), s.get('ptsset_id')) for s in self.data['scoms'])
            self.usage_label.configure(text=f'使用先 SCOM：{usage} 件')
        else: self.element_id = None; self.usage_label.configure(text='定義を追加してください。')
        self.scom_names = {s['name']: s['id'] for s in self.data['scoms']}
        self.scom_choice['values'] = list(self.scom_names)
        current = project.get(self.data, 'scoms', self.preview_scom_id)
        self.scom_choice.set(current['name'] if current else '')
        self.refresh_element()
        self.busy = False
        self.refresh_values(); self.draw()

    def refresh_element(self):
        e = self.element()
        if getattr(self,'simple_layout',False):
            for button,match in self.helper_buttons:
                button.pack_forget()
                if e and (match=='negative' and e['type'] in schema.NEGATIVE_BASE or schema.positive(e['type'])==match):button.pack(side='left',pady=6,padx=(0,6))
            self.child_button.pack_forget()
            if e and schema.child_kind(e['type']):self.child_button.pack(side='right')
        self.element_name.set(e['name'] if e else '')
        available = list(schema.TYPES_BY_SET[self.kind])
        if self.kind == 'GMSET': available += list(schema.NEGATIVE_BASE)
        if e and e['type'] in schema.CHILD_TYPES: available = [e['type']]
        if e and e['type'] not in available: available += [e['type']]
        self.type_choice.set(e['type'] if e else '')
        if not getattr(self,'simple_layout',False):
            self.type_choice['values']=available
            self.type_choice.configure(state='readonly' if e else 'disabled')
            self.element_name_entry.configure(state='normal' if e else 'disabled')
        for table in self.tables.values(): table.delete(*table.get_children())
        if not e:
            if getattr(self,'simple_layout',False):self.element_details.configure(text='')
            self.field = None; self.load_field(); self.element_note.configure(text='左の「＋ 追加」から要素を作成してください。' if self.definition() else '「新しい '+self.kind+' を作る」から名前を登録してください。'); return
        if schema.known(e['type']):
            listed = set()
            for section, table in self.tables.items():
                if section == 'extra': continue
                for key in schema.fields(e['type'], section):
                    listed.add(key); table.insert('', 'end', iid=key, values=(key, schema.meaning(e['type'],key), schema.value(e, key)))
            for key, value in e['attrs'].items():
                if key not in listed and not (key == 'PTCD' and 'PTCDIR' in listed):
                    self.tables['extra'].insert('', 'end', iid=key, values=(key, '元データを保持', str(value)))
            note = '通常は PSKEY・DESC・PURP を非表示。新規値は unset。' if self.kind == 'PTSET' else '固有属性と共通属性を分けて編集します。OBST：0 対象外 / 1 ソフト / 2 ハード。'
            if e['type'] in schema.NEGATIVE_BASE:
                note = 'NAPP：1 Attached / 2 Owner / 4 Self の組み合わせ。対象の実体は設計側の文脈に依存します。'
                if e['type'] == 'NSRU': note += ' NSRU の固有属性は未確認です。'
        else:
            for key, value in e['attrs'].items(): self.tables['extra'].insert('', 'end', iid=key, values=(key, '旧仮要素・未対応の原文', str(value)))
            note = '旧仮要素・未対応要素です。追加属性で原文を確認できます。正式要素への変更時も原文を保持します。'
        note = schema.LABELS.get(e['type'],'負 '+schema.LABELS.get(schema.positive(e['type']),''))+' / '+note
        note += '\n' + schema.NOTES.get(schema.positive(e['type']),'')
        if getattr(self,'simple_layout',False):
            self.element_details.configure(text=note)
            note=schema.LABELS.get(e['type'],'負 '+schema.LABELS.get(schema.positive(e['type']),'未対応'))
        self.element_note.configure(text=note)
        if getattr(self,'simple_layout',False):
            if 'negative' in self.tab_frames:
                if e['type'] in schema.NEGATIVE_BASE:self.tabs.add(self.tab_frames['negative'])
                else:
                    if self.section=='negative':self.section='main';self.tabs.select(0)
                    self.tabs.hide(self.tab_frames['negative'])
            extra=self.tab_frames['extra']
            if self.tables['extra'].get_children():self.tabs.add(extra)
            else:
                if self.section=='extra':self.section='main';self.tabs.select(0)
                self.tabs.hide(extra)
        table = self.tables[self.section]
        keys = table.get_children()
        if self.field not in keys: self.field = keys[0] if keys else None
        if self.field: table.selection_set(self.field)
        self.load_field()

    def select_definition(self, _=None):
        if self.busy: return
        self.commit_name(); self.definition_id = self.definition_names.get(self.def_choice.get()); self.element_id = None
        self.refresh()

    def select_element(self, _=None):
        if self.busy: return
        selected = self.elements.selection()
        if selected and selected[0] != self.element_id:
            self.element_id = selected[0]; self.field = None
            self.busy = True; self.refresh_element(); self.busy = False; self.draw()

    def select_field(self, section):
        if self.busy or section != self.section: return
        selected = self.tables[section].selection()
        if selected and selected[0] != self.field:
            self.field = selected[0]; self.busy = True; self.load_field(); self.busy = False

    def tab_changed(self, _=None):
        if self.busy: return
        index = self.tabs.index('current'); self.section = self.section_order[index]; self.field = None
        self.busy = True; self.refresh_element(); self.busy = False

    def load_field(self):
        e = self.element()
        self.choice_entry.pack_forget(); self.expression_entry.pack_forget()
        self.field_label.configure(text=(self.field + ' / ' + schema.meaning(e['type'],self.field) if e else '') if self.field else '属性を選択してください')
        self.expression.set(schema.value(e, self.field) if e and self.field else '')
        choices = ()
        if self.field == 'OBST': choices = tuple(schema.OBST_CHOICES)
        elif self.field in ('PAXI', 'PAAX', 'PBAX', 'PCAX', 'PLAXI', 'PTCDIR'): choices = schema.DIRECTIONS
        elif self.field in ('CLFLA','TUFLA','TVISI','BVISI'): choices = ('','TRUE','FALSE')
        elif self.field == 'NAPP': choices = tuple(str(i) for i in range(8))
        if choices:
            self.choice_entry['values'] = choices
            if self.field == 'OBST': self.expression.set(next((key for key, val in schema.OBST_CHOICES.items() if val == schema.value(e, self.field)), schema.value(e, self.field)))
            self.choice_entry.pack(fill='x', before=self.reference_frame)
        else: self.expression_entry.pack(fill='x', before=self.reference_frame)
        self.expression_entry.configure(state='normal' if e and self.field and schema.known(e['type']) and self.section != 'extra' else 'readonly')
        self.choice_entry.configure(state='normal' if e and self.field else 'disabled')
        if getattr(self,'simple_layout',False):
            available=bool(e and self.field and self.field not in ('NUMB','DESC','PURP','PSKEY','GTYP','LEVEL','OBST','CLFLA','TUFLA','TVISI','BVISI','NAPP') and self.section!='extra')
            self.reference_button.configure(state='normal' if available else 'disabled')
            if not available and self.references_open:self.toggle_references()
        self.update_role(); self.update_validation()

    def update_validation(self):
        if not self.field or not self.element(): self.validation_note.configure(text=''); return
        e = self.element(); key = self.field; expr = schema.value(e,key)
        if key == 'NUMB':
            text = 'P0 は自動生成。正の整数で、同じ PTSET 内の番号を重複させません。'
        elif key == 'LEVEL': text = '下限 上限 の 2 数値。描画フラグと REPRESENTATION の設定にも依存します。'
        elif key == 'NAPP':
            try:
                val=int(expr); text='適用先：' + (' / '.join(name for bit,name in ((1,'Attached'),(2,'Owner'),(4,'Self')) if val & bit) or 'なし')
            except ValueError: text='適用先を 0〜7 で指定してください。'
        elif key in ('TVISI','BVISI','CLFLA','TUFLA'): text='TRUE / FALSE の描画フラグです。'
        elif key in ('PAXI','PAAX','PBAX','PCAX','PLAXI','PTCDIR','PTCPOS','PTSPOS','PTEPOS','PTS','DESC','PURP','PSKEY','GTYP','PKEY'):
            text='原文を保持。複合方向・位置式の座標計算は未対応です。' if key in ('PAXI','PAAX','PBAX','PCAX','PLAXI','PTCDIR','PTCPOS','PTSPOS','PTEPOS') else schema.meaning(e['type'],key)
        elif not expr.strip(): text='未入力'
        elif key=='PCON' and expr.isidentifier() and expr not in {p['role'] for p in presets.rules(self.data,self.definition())} and expr.upper() not in ('PARAM','PARA','ANGL'):text='固定の接続コード：'+expr
        else:
            try:
                scom=project.get(self.data,'scoms',self.preview_scom_id)
                if scom:presets.require_compatible(self.data,scom,self.definition())
                value=expressions.evaluate(expr,expressions.contexts_for(scom or {}),(scom or {}).get('component_attrs',{}),presets.rules(self.data,self.definition()))
                text='確認結果：' + str(value) + ('（選択 SCOM）' if scom else '（定数）')
            except ValueError as exc: text=str(exc)
        self.validation_note.configure(text=text)

    def edit_expression(self, *_):
        if self.busy or not self.element() or not self.field or self.section == 'extra' or not schema.known(self.element()['type']): return
        value = self.expression.get()
        if self.field == 'OBST': value = schema.OBST_CHOICES.get(value, value)
        schema.set_value(self.element(), self.field, value)
        self.tables[self.section].item(self.field, values=(self.field, schema.meaning(self.element()['type'],self.field), value))
        if self.kind=='PTSET' and self.field=='NUMB':self.elements.item(self.element_id,values=(value,self.element()['type']))
        self.host.mark(); self.update_validation()

    def rename_element(self, *_):
        if not self.busy and self.element():
            self.element()['name'] = self.element_name.get(); self.elements.item(self.element_id, text=self.element_name.get()); self.host.mark(); self.draw()

    def change_type(self, _=None):
        e = self.element(); kind = self.type_choice.get()
        if not e or kind == e['type']: return
        if not messagebox.askyesno('要素型を変更', '要素型を変更しますか？ 元の属性と型の履歴は保持します。', parent=self.host): self.type_choice.set(e['type']); return
        schema.change_type(e, kind); self.field = None; self.section = 'main'
        self.tabs.select(0); self.host.mark(); self.refresh()

    def insert_reference(self):
        e = self.element()
        if not e or not self.field or self.field == 'NUMB' or self.section == 'extra' or not schema.known(e['type']): return
        try: number = int(self.ref_number.get())
        except ValueError: self.validation_note.configure(text='参照番号は正の整数を指定してください。'); return
        if number < 1: self.validation_note.configure(text='参照番号は正の整数を指定してください。'); return
        ref = self.ref_kind.get() + '[' + str(number) + ']'
        entry = self.expression_entry if self.expression_entry.winfo_ismapped() else self.choice_entry
        try: a, b = entry.index('sel.first'), entry.index('sel.last')
        except tk.TclError: a = b = entry.index('insert')
        text = self.expression.get(); self.expression.set(text[:a] + ref + text[b:]); entry.focus_set(); entry.icursor(a + len(ref))

    def half(self):
        if self.element() and schema.known(self.element()['type']) and self.field and self.section != 'extra': self.expression.set('(' + self.expression.get() + ') / 2')

    def update_role(self):
        kind = self.ref_kind.get()
        pid = 'P' + self.ref_number.get()
        param = next((p for p in presets.rules(self.data,self.definition()) if p['id']==pid),None) if kind == 'PARAM' else None
        self.role_label.configure(text=schema.REFERENCE_LABELS.get(kind, kind) + ' / 役割：' + ((param.get('description') or param['role']) if param else presets.reference_roles(self.data,self.definition()).get(kind,{}).get(pid,'未設定（参照種類ごとに区別）')))

    def commit_name(self):
        d = self.definition()
        if not d: return
        name = self.def_name.get().strip()
        if name == d['name']: return
        if not name or any(x['id'] != d['id'] and x['name'] == name for x in self.data['definitions']):
            self.host.status.configure(text='定義名が空か重複しています。'); self.def_name.set(d['name']); return
        d['name'] = name; self.host.mark()
        self.definition_names = {x['name']: x['id'] for x in self.data['definitions'] if x['kind'] == self.kind}
        self.def_choice['values'] = list(self.definition_names); self.def_choice.set(name)

    def create_part(self):
        d=self.definition()
        if not d:return
        self.commit_name()
        if self.kind=='PTSET':self.host.component_from_ptset(d['id'])
        elif self.kind=='GMSET':self.host.component_from_gmset(d['id'])

    def add_definition(self):
        if self.kind in ('PTSET','GMSET'):
            self.host.definition_form(self.kind);return
        def apply(values):
            name=self.host.required(values['name'],'定義名')
            if any(d['name']==name for d in self.data['definitions']):raise ValueError('定義名が重複しています。')
            if len(self.data['definitions'])>=1000:raise ValueError('定義数の上限です。')
            d={'id':uuid.uuid4().hex,'name':name,'kind':self.kind,'revision':'01','elements':[]}
            presets.stamp(self.data,d);self.data['definitions'].append(d);self.host.definition_id=d['id']
        self.host.form(self.kind+' を追加',[('name','定義名','/NEW-'+self.kind,None)],apply)

    def duplicate_definition(self):
        d = self.definition()
        if not d: return
        copied = copy.deepcopy(d); copied['id'] = uuid.uuid4().hex
        names = {x['name'] for x in self.data['definitions']}; name = d['name'] + '-COPY'; n = 1
        while name in names: n += 1; name = d['name'] + '-COPY' + str(n)
        copied['name'] = name
        remap={}
        for e in schema.walk(copied['elements']):
            old=e['id'];e['id']=uuid.uuid4().hex;remap[old]=e['id']
        if copied.get('attrs',{}).get('NAREF') in remap: copied['attrs']['NAREF']=remap[copied['attrs']['NAREF']]
        self.data['definitions'].append(copied); self.definition_id = copied['id']; self.element_id = None
        self.host.mark(); self.refresh()

    def add_element(self):
        d = self.definition(); selected = self.library.curselection()
        if not d: self.validation_note.configure(text='先に定義を追加してください。'); return
        if not selected: return
        try: e = schema.add_element(d, self.library.get(selected[0]).split()[0])
        except ValueError as exc: messagebox.showerror('追加できません', str(exc), parent=self.host); return
        self.element_id = e['id']; self.section = 'main'; self.tabs.select(0); self.field = None
        self.host.mark();self.refresh();self.elements.see(e['id'])
        if getattr(self,'simple_layout',False) and self.creating:self.toggle_create()
        self.host.status.configure(text=e['type']+' を作成しました。中央の属性行を選んで、値・式を入力してください。')

    def duplicate_element(self):
        e, d = self.element(), self.definition()
        if not e:return
        siblings=self.siblings(e)
        if len(siblings)>=200 or e['type']=='SLOO': self.validation_note.configure(text='輪郭は 1 つ。頂点を追加・複製してください。');return
        copied = copy.deepcopy(e)
        for node in schema.walk([copied]): node['id']=uuid.uuid4().hex
        name = e['name'] + ' コピー'; n = 1
        names = {x['name'] for x in siblings}
        while name in names: n += 1; name = e['name'] + ' コピー ' + str(n)
        copied['name'] = name
        if 'NUMB' in copied['attrs']:
            numbers = [int(x['attrs']['NUMB']) for x in d['elements'] if str(x['attrs'].get('NUMB', '')).isdigit()]
            copied['attrs']['NUMB'] = str(max(numbers + [0]) + 1)
        self.siblings(e).append(copied); self.element_id = copied['id']; self.host.mark(); self.refresh()

    def delete_element(self):
        e = self.element()
        if e and messagebox.askyesno('要素を削除', '要素を削除しますか？ 使用先にも影響します。', parent=self.host):
            self.siblings(e).remove(e); self.element_id = None; self.host.mark(); self.refresh()

    def select_scom(self, _=None):
        self.preview_scom_id = self.scom_names.get(self.scom_choice.get()); self.refresh_values(); self.update_validation()

    def refresh_values(self):
        s = project.get(self.data, 'scoms', self.preview_scom_id)
        if self.kind=='PTSET' or getattr(self,'simple_layout',False):
            self.values_label.configure(text=presets.label(self.data,s)+' / '+str(len(s['values']))+' 項目を確認に使用' if s else '確認用 SCOM を選択してください。')
            return
        self.values_label.configure(text=('読み取り専用 / ' + s['name'] + '\n'+presets.label(self.data,s)+'\n\n' + '\n'.join(p['id'] + ' ' + presets.caption(p) + '：' + str(s['values'].get(p['id'], '未入力')) + ' ' + p.get('unit', '') for p in presets.rules(self.data,s)[:6])) if s else '確認用 SCOM を選択してください。')

    def open_scom(self):
        s = project.get(self.data, 'scoms', self.preview_scom_id)
        if s: self.host.scom_id = s['id']; self.host.cate_id = s['cate_id']; self.host.switch('catalog')

    def edit_parent(self):
        d=self.definition()
        if not d: return
        keys=schema.PARENT_FIELDS[self.kind]
        if not keys: messagebox.showinfo('親属性','このセットには形状用の固有親属性はありません。',parent=self.host);return
        options={'未設定':''}
        if self.kind == 'PTSSET': options.update({e['name']:e['id'] for e in d['elements'] if e['type']=='PLINE'})
        fields=[]
        for key in keys:
            raw=d.get('attrs',{}).get(key,'')
            if key == 'NAREF':
                if raw and raw not in options.values(): options['参照先不明：'+raw]=raw
                initial=next((name for name,ident in options.items() if ident==raw),'未設定')
                fields.append((key,schema.DESCRIPTIONS[key],initial,list(options)))
            else: fields.append((key,schema.DESCRIPTIONS.get(key,key),raw,None))
        def apply(v):
            d.setdefault('attrs',{}).update({key:options[v[key]] if key=='NAREF' else v[key] for key in keys})
        self.host.form(self.kind+' の親属性',fields,apply)

    def siblings(self,element):
        d=self.definition()
        if element in d['elements']: return d['elements']
        return next(node['children'] for node in schema.walk(d['elements']) if element in node.get('children',[]))

    def add_child(self):
        e=self.element()
        if not e: return
        try: child=schema.add_child(e)
        except ValueError as exc: self.validation_note.configure(text=str(exc));return
        self.element_id=child['id'];self.field=None;self.section='main';self.tabs.select(0)
        self.host.mark();self.refresh()

    def move_element(self,delta):
        e=self.element()
        if not e: return
        siblings=self.siblings(e);index=siblings.index(e);target=index+delta
        if 0 <= target < len(siblings):
            siblings[index],siblings[target]=siblings[target],siblings[index];self.host.mark();self.refresh()

    def normalize_expression(self):
        e=self.element()
        if not e or not self.field or self.section == 'extra': return
        try: value=expressions.normalized(self.expression.get(),presets.rules(self.data,self.definition()))
        except ValueError as exc: self.validation_note.configure(text=str(exc));return
        e.setdefault('expression_sources',{}).setdefault(self.field,self.expression.get())
        self.expression.set(value)

    def edit_napp(self):
        e=self.element()
        if not e or e['type'] not in schema.NEGATIVE_BASE: self.validation_note.configure(text='ネガティブ要素を選択してください。');return
        win=tk.Toplevel(self.host);win.title('NAPP：除去する適用先');win.transient(self.host);win.grab_set()
        try: value=int(e['attrs'].get('NAPP','1'))
        except ValueError: value=0
        flags=[]
        for bit,label in ((1,'Attached（接続先）'),(2,'Owner（所有元）'),(4,'Self（部品自身）')):
            var=tk.BooleanVar(value=bool(value&bit));flags.append((bit,var))
            ttk.Checkbutton(win,text=label,variable=var).pack(anchor='w',padx=20,pady=8)
        ttk.Label(win,text='全て OFF：0 / 全て ON：7。対象の実体は設計側の文脈に依存します。',wraplength=360).pack(padx=20,pady=10)
        def apply():
            e['attrs']['NAPP']=str(sum(bit for bit,var in flags if var.get()));self.host.mark();win.destroy();self.refresh()
        ttk.Button(win,text='適用',command=apply).pack(pady=12)

    def edit_sizes(self):
        e=self.element()
        if not e or schema.positive(e['type']) != 'LSNO': self.validation_note.configure(text='LSNO / NLSN を選択してください。');return
        fields=[]
        for face,d,r in (('top','PTDM','PTRA'),('bottom','PBDM','PBRA')):
            fields.extend([(face+'mode',face+' 入力モード','半径' if e['attrs'].get(r) and not e['attrs'].get(d) else '直径',['直径','半径']),
                           (face+'value',face+' 値・式',e['attrs'].get(d) or e['attrs'].get(r,''),None)])
        def apply(v):
            e.setdefault('size_history',[]).append(copy.deepcopy(e['attrs']))
            for face,d,r in (('top','PTDM','PTRA'),('bottom','PBDM','PBRA')):
                radius=v[face+'mode']=='半径';e['attrs'][r if radius else d]=v[face+'value'];e['attrs'][d if radius else r]=''
        self.host.form('LSNO：面ごとの寸法を選択',fields,apply)

    def edit_points(self):
        e=self.element()
        if not e or e['type'] != 'LINE': self.validation_note.configure(text='LINE を選択してください。');return
        values=str(e['attrs'].get('PTS','')).split()
        fields=[(str(i),'点 '+str(i+1)+'（P1 / T2、空欄は省略）',values[i] if i<len(values) else '',None) for i in range(6)]
        def apply(v):
            points=[v[str(i)].upper().strip() for i in range(6) if v[str(i)].strip()]
            import re
            if any(not re.fullmatch(r'[PT]\d+',p) for p in points): raise ValueError('P1 / T2 形式で指定してください。')
            e['attrs']['PTS']=' '.join(points)
        self.host.form('LINE：点の順序',fields,apply)

    def draw(self):
        if self.canvas is None:return
        c = self.canvas; c.delete('all'); w, h = max(c.winfo_width(), 100), max(c.winfo_height(), 120)
        d = self.definition()
        if not d or not d['elements']:
            c.create_text(w/2, h/2, text='要素を追加すると構成を表示します', width=w-25, fill=MUTED); return
        for x in range(0, w, 25): c.create_line(x, 0, x, h, fill='#e6edf6')
        for y in range(0, h, 25): c.create_line(0, y, w, y, fill='#e6edf6')
        items = d['elements'][:6]
        spacing = max(35, min(60, (h-45)/len(items)))
        for i, e in enumerate(items):
            y = 22+i*spacing; chosen = e['id'] == self.element_id
            color = BLUE if chosen else ('#b87c30' if e['type'] in schema.NEGATIVE_BASE else '#8395ad')
            if self.kind == 'PTSET':
                c.create_oval(22, y, 38, y+16, outline=color, fill='#dceafe' if chosen else 'white', width=2)
                c.create_line(38, y+8, 64, y+8, arrow='last', fill=color)
            else: c.create_rectangle(20, y, 55, y+22, outline=color, fill='#dceafe' if chosen else '#e6ecf4', width=2, dash=(3,2) if e['type'] in schema.NEGATIVE_BASE else ())
            c.create_text(70, y+10, text=e['name']+'\n'+e['type'], anchor='w', fill=color, width=max(60,w-90), font=(self.host.ui_font,9))
        c.create_text(w/2, h-12, text='構成のみ表示 / 位置・寸法は未計算', fill=MUTED, font=(self.host.ui_font,9))

    def review(self):
        d = self.definition()
        if not d: return
        win = tk.Toplevel(self.host); win.title('定義の出力確認'); win.transient(self.host)
        ttk.Label(win, text='構成確認用のコメント表示です。E3D 実行用ではありません。', padding=12).pack()
        text = tk.Text(win, width=82, height=25, font=('Consolas',10)); text.pack(fill='both', expand=True, padx=12, pady=8)
        report=copy.deepcopy(self.data);report['definitions']=[d];report['cates']=[];report['scoms']=[];report['specs']=[];report['tables']=[];report['texts']=[]
        lines=project.macro_text(report).splitlines()
        text.insert('1.0','\n'.join(lines)); text.configure(state='disabled')
        ttk.Button(win, text='閉じる', command=win.destroy).pack(pady=8)
