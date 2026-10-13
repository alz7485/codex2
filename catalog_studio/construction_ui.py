"""PTSET/GMSET creation shell: editable fields, not an E3D expression engine."""
import copy
import tkinter as tk
import uuid
from tkinter import messagebox, ttk
from . import element_schema as schema, project

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
        demo = next((d for d in definitions if d['id'] == ('ui-ptset' if kind == 'PTSET' else 'ui-gmset')), None)
        self.definition_id = preferred['id'] if preferred and preferred['kind'] == kind else (demo or (definitions[0] if definitions else {})).get('id')
        self.build()
        self.refresh()
        self.busy = False

    @property
    def data(self): return self.host.data
    def definition(self): return project.get(self.data, 'definitions', self.definition_id)
    def element(self): return next((e for e in (self.definition() or {}).get('elements', []) if e['id'] == self.element_id), None)

    def build(self):
        top = ttk.Frame(self); top.pack(fill='x', pady=(0, 10))
        block = ttk.Frame(top); block.pack(side='left', fill='x', expand=True)
        ttk.Label(block, text=self.kind + ' を作成・編集', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(block, text='要素・属性・式を保存できる UI のたたき台です。新しい要素の形状計算と実機出力は未対応。', style='Muted.TLabel', wraplength=690).pack(anchor='w', pady=4)
        for text, command in [('保存', self.host.save_project), ('出力を確認', self.review), ('定義を追加', self.add_definition)]:
            ttk.Button(top, text=text, command=command).pack(side='right', padx=3)
        metadata = ttk.Frame(self); metadata.pack(fill='x', pady=(0, 10))
        ttk.Label(metadata, text=self.kind + ' 名').pack(side='left')
        self.def_name = tk.StringVar()
        self.name_entry = ttk.Entry(metadata, textvariable=self.def_name, width=32); self.name_entry.pack(side='left', padx=8)
        self.name_entry.bind('<FocusOut>', lambda _: self.commit_name()); self.name_entry.bind('<Return>', lambda _: self.commit_name())
        self.usage_label = ttk.Label(metadata, text='', style='Muted.TLabel'); self.usage_label.pack(side='left', padx=10)
        ttk.Button(metadata, text='複製して作成', command=self.duplicate_definition).pack(side='right')
        split = ttk.Panedwindow(self, orient='horizontal'); split.pack(fill='both', expand=True)
        left = ttk.Frame(split, padding=8); center = ttk.Frame(split, padding=10); right = ttk.Frame(split, padding=10)
        for frame, weight in ((left, 2), (center, 5), (right, 3)): split.add(frame, weight=weight)
        self.host.balance(split, (.23, .71))
        ttk.Label(left, text='定義を選択', style='Heading.TLabel').pack(anchor='w', pady=4)
        self.def_choice = ttk.Combobox(left, state='readonly'); self.def_choice.pack(fill='x', pady=5)
        self.def_choice.bind('<<ComboboxSelected>>', self.select_definition)
        ttk.Label(left, text='ポイント構成' if self.kind == 'PTSET' else '形状の構成', style='Heading.TLabel').pack(anchor='w', pady=(12, 5))
        self.elements = ttk.Treeview(left, columns=('type',), show='tree headings', selectmode='browse', height=5)
        self.elements.heading('#0', text='要素名'); self.elements.heading('type', text='種類')
        self.elements.column('#0', width=130, minwidth=70); self.elements.column('type', width=75, minwidth=60)
        self.elements.pack(fill='both', expand=True); self.elements.bind('<<TreeviewSelect>>', self.select_element)
        buttons = ttk.Frame(left); buttons.pack(fill='x', pady=8)
        for text, fn in [('複製', self.duplicate_element), ('削除', self.delete_element)]: ttk.Button(buttons, text=text, command=fn).pack(side='left', padx=2)
        library = ttk.LabelFrame(left, text='要素ライブラリ', padding=8); library.pack(fill='x', pady=6)
        self.negative = tk.BooleanVar(value=False)
        if self.kind == 'GMSET':
            ttk.Checkbutton(library, text='ネガティブ（15種類）', variable=self.negative, command=self.populate_library).pack(anchor='w')
            ttk.Label(library, text='ポジティブ：18種類', style='Muted.TLabel').pack(anchor='w')
        else: ttk.Label(library, text='PTAXI / PTCAR / PTMIX / PTPOS', style='Muted.TLabel', wraplength=240).pack(anchor='w')
        library_list=ttk.Frame(library);library_list.pack(fill='x',pady=5)
        self.library = tk.Listbox(library_list, height=4 if self.kind=='PTSET' else 3, exportselection=False, font=(self.host.ui_font, 10), relief='flat', selectbackground='#e4efff', selectforeground=BLUE)
        self.library.pack(side='left',fill='x',expand=True)
        scroll=ttk.Scrollbar(library_list,orient='vertical',command=self.library.yview);scroll.pack(side='right',fill='y');self.library.configure(yscrollcommand=scroll.set)
        self.library.bind('<Double-1>', lambda _: self.add_element())
        ttk.Button(library, text='＋ 選択した要素を追加', command=self.add_element).pack(fill='x')
        self.populate_library()
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
            table = self.host.table(frame, [('attr', '属性', 90), ('meaning', '説明', 125), ('value', '設定値・式', 260)], height=6)
            table.bind('<<TreeviewSelect>>', lambda event, s=key: self.select_field(s))
            self.tables[key] = table
        self.section_order = [s[0] for s in sections]
        self.tabs.bind('<<NotebookTabChanged>>', self.tab_changed)
        editor = ttk.LabelFrame(center, text='属性値・式の入力', padding=10); editor.pack(fill='x')
        self.field_label = ttk.Label(editor, text='', style='Heading.TLabel'); self.field_label.pack(anchor='w', pady=(0, 6))
        self.expression = tk.StringVar(); self.expression.trace_add('write', self.edit_expression)
        self.expression_entry = ttk.Entry(editor, textvariable=self.expression, font=(self.host.ui_font, 13)); self.expression_entry.pack(fill='x')
        self.choice_entry = ttk.Combobox(editor, textvariable=self.expression, state='normal')
        reference = ttk.Frame(editor); reference.pack(fill='x', pady=8)
        self.ref_kind = ttk.Combobox(reference, values=schema.REFERENCE_TYPES, state='readonly', width=14); self.ref_kind.set('PARAM'); self.ref_kind.pack(side='left')
        self.ref_kind.bind('<<ComboboxSelected>>', lambda _: self.update_role())
        self.ref_number = tk.StringVar(value='1')
        self.number_entry = ttk.Spinbox(reference, from_=1, to=999, width=5, textvariable=self.ref_number); self.number_entry.pack(side='left', padx=5)
        self.ref_number.trace_add('write', lambda *_: self.update_role())
        ttk.Button(reference, text='式へ挿入', command=self.insert_reference).pack(side='left', padx=3)
        ttk.Button(reference, text='÷ 2', command=self.half).pack(side='left')
        self.role_label = ttk.Label(editor, text='', style='Muted.TLabel'); self.role_label.pack(anchor='w')
        ttk.Label(editor, text='画面用の参照表記です。原文入力も可能。ANGL は度。\nTIMES・TAN・複合方向式の計算／E3D 構文変換は未対応です。', style='Muted.TLabel', wraplength=520).pack(anchor='w', pady=5)
        self.validation_note = ttk.Label(editor, text='', foreground='#bb6440', wraplength=520); self.validation_note.pack(anchor='w')
        ttk.Label(right, text='構成プレビュー', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(right, text='模式図：寸法・式・方向は未反映', style='Muted.TLabel', wraplength=310).pack(anchor='w', pady=5)
        self.canvas = tk.Canvas(right, width=320, height=235, bg='#f2f6fc', highlightthickness=0); self.canvas.pack(fill='both', expand=True, pady=8)
        self.canvas.bind('<Configure>', lambda _: self.draw())
        ttk.Label(right, text='確認用 SCOM', style='Heading.TLabel').pack(anchor='w', pady=(8, 3))
        self.scom_choice = ttk.Combobox(right, state='readonly'); self.scom_choice.pack(fill='x', pady=5)
        self.scom_choice.bind('<<ComboboxSelected>>', self.select_scom)
        self.values_label = ttk.Label(right, text='', style='Muted.TLabel', wraplength=300); self.values_label.pack(anchor='w', pady=8)
        ttk.Button(right, text='SCOM の実数値を編集', command=self.open_scom).pack(fill='x', pady=8)
        ttk.Label(right, text='読み取り専用。点・形状の定義には保存されません。\n新しい要素の寸法計算と CAD 表示は今後追加します。', style='Muted.TLabel', wraplength=310).pack(anchor='w')

    def populate_library(self):
        items = schema.PT_TYPES if self.kind == 'PTSET' else (schema.NEGATIVE_BASE if self.negative.get() else schema.GM_TYPES)
        self.library.delete(0, 'end')
        for kind in items: self.library.insert('end', kind)
        if items: self.library.selection_set(0)

    def refresh(self):
        self.busy = True
        self.definition_names = {d['name']: d['id'] for d in self.data['definitions'] if d['kind'] == self.kind}
        self.def_choice['values'] = list(self.definition_names)
        d = self.definition()
        self.def_choice.set(d['name'] if d else '')
        self.def_name.set(d['name'] if d else '')
        self.elements.delete(*self.elements.get_children())
        if d:
            self.host.definition_id = d['id']
            for e in d['elements']: self.elements.insert('', 'end', iid=e['id'], text=e['name'], values=(e['type'],))
            if not any(e['id'] == self.element_id for e in d['elements']): self.element_id = next((e['id'] for e in d['elements']), None)
            if self.element_id: self.elements.selection_set(self.element_id)
            usage = sum(d['id'] in (s['gmset_id'], s['ptset_id']) for s in self.data['scoms'])
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
        self.element_name.set(e['name'] if e else '')
        available = list(schema.PT_TYPES) if self.kind == 'PTSET' else list(schema.GM_TYPES) + list(schema.NEGATIVE_BASE)
        if e and e['type'] not in available: available += [e['type']]
        self.type_choice['values'] = available; self.type_choice.set(e['type'] if e else '')
        for table in self.tables.values(): table.delete(*table.get_children())
        if not e:
            self.field = None; self.load_field(); self.element_note.configure(text='ライブラリから要素を追加してください。'); return
        if schema.known(e['type']):
            listed = set()
            for section, table in self.tables.items():
                if section == 'extra': continue
                for key in schema.fields(e['type'], section):
                    listed.add(key); table.insert('', 'end', iid=key, values=(key, schema.DESCRIPTIONS.get(key, '属性値・式（意味未確認）'), schema.value(e, key)))
            for key, value in e['attrs'].items():
                if key not in listed and not (key == 'PTCD' and 'PTCDIR' in listed):
                    self.tables['extra'].insert('', 'end', iid=key, values=(key, '元データを保持', str(value)))
            note = '通常は PSKEY・DESC・PURP を非表示。新規値は unset。' if self.kind == 'PTSET' else '固有属性と共通属性を分けて編集します。OBST：0 対象外 / 1 ソフト / 2 ハード。'
            if e['type'] in schema.NEGATIVE_BASE:
                note = 'ネガティブの対応属性は仮配置です。実機の作成例で確認します。'
                if e['type'] == 'NSRU': note += ' NSRU の固有属性は未確認です。'
        else:
            for key, value in e['attrs'].items(): self.tables['extra'].insert('', 'end', iid=key, values=(key, '旧仮要素・未対応の原文', str(value)))
            note = '旧仮要素・未対応要素です。追加属性で原文を確認できます。正式要素への変更時も原文を保持します。'
        self.element_note.configure(text=note)
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
        self.field_label.configure(text=(self.field + ' / ' + schema.DESCRIPTIONS.get(self.field, '属性値・式')) if self.field else '属性を選択してください')
        self.expression.set(schema.value(e, self.field) if e and self.field else '')
        choices = ()
        if self.field == 'OBST': choices = tuple(schema.OBST_CHOICES)
        elif self.field in ('PAXI', 'PAAX', 'PBAX', 'PCAX', 'PTCDIR'): choices = schema.DIRECTIONS
        if choices:
            self.choice_entry['values'] = choices
            if self.field == 'OBST': self.expression.set(next((key for key, val in schema.OBST_CHOICES.items() if val == schema.value(e, self.field)), schema.value(e, self.field)))
            self.choice_entry.pack(fill='x', before=self.choice_entry.master.winfo_children()[3])
        else: self.expression_entry.pack(fill='x', before=self.expression_entry.master.winfo_children()[3])
        self.expression_entry.configure(state='normal' if e and self.field and schema.known(e['type']) and self.section != 'extra' else 'readonly')
        self.choice_entry.configure(state='normal' if e and self.field else 'disabled')
        self.update_role(); self.update_validation()

    def update_validation(self):
        text = '保存できます。式・位置・方向の評価は未対応です。'
        if self.field == 'NUMB' and not self.expression.get().isdigit(): text = 'ポイント番号は整数で指定してください（現在は入力中の値を保持）。'
        elif self.field == 'OBST': text = '0：障害物対象外 / 1：ソフト / 2：ハード'
        elif self.field in ('TVISI', 'BVISI'): text = '表示するかどうかの設定。実機での値の形式は未確認のため原文で入力します。'
        self.validation_note.configure(text=text)

    def edit_expression(self, *_):
        if self.busy or not self.element() or not self.field or self.section == 'extra' or not schema.known(self.element()['type']): return
        value = self.expression.get()
        if self.field == 'OBST': value = schema.OBST_CHOICES.get(value, value)
        schema.set_value(self.element(), self.field, value)
        self.tables[self.section].item(self.field, values=(self.field, schema.DESCRIPTIONS.get(self.field, '属性値・式（意味未確認）'), value))
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
        if not e or not self.field or self.section == 'extra' or not schema.known(e['type']): return
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
        param = project.get(self.data, 'parameters', pid) if kind == 'PARAM' else None
        self.role_label.configure(text=schema.REFERENCE_LABELS.get(kind, kind) + ' / 役割：' + (param['role'] if param else '未設定（参照種類ごとに区別）'))

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

    def add_definition(self):
        def apply(values):
            name = self.host.required(values['name'], '定義名')
            if any(d['name'] == name for d in self.data['definitions']): raise ValueError('定義名が重複しています。')
            if len(self.data['definitions']) >= 1000: raise ValueError('定義数の上限です。')
            d = {'id': uuid.uuid4().hex, 'name': name, 'kind': self.kind, 'revision': '01', 'elements': []}
            self.data['definitions'].append(d); self.host.definition_id = d['id']
        self.host.form(self.kind + ' を追加', [('name', '定義名', '/NEW-' + self.kind, None)], apply)

    def duplicate_definition(self):
        d = self.definition()
        if not d: return
        copied = copy.deepcopy(d); copied['id'] = uuid.uuid4().hex
        names = {x['name'] for x in self.data['definitions']}; name = d['name'] + '-COPY'; n = 1
        while name in names: n += 1; name = d['name'] + '-COPY' + str(n)
        copied['name'] = name
        for e in copied['elements']: e['id'] = uuid.uuid4().hex
        self.data['definitions'].append(copied); self.definition_id = copied['id']; self.element_id = None
        self.host.mark(); self.refresh()

    def add_element(self):
        d = self.definition(); selected = self.library.curselection()
        if not d: self.validation_note.configure(text='先に定義を追加してください。'); return
        if not selected: return
        try: e = schema.add_element(d, self.library.get(selected[0]))
        except ValueError as exc: messagebox.showerror('追加できません', str(exc), parent=self.host); return
        self.element_id = e['id']; self.section = 'main'; self.tabs.select(0); self.field = None
        self.host.mark(); self.refresh()

    def duplicate_element(self):
        e, d = self.element(), self.definition()
        if not e or len(d['elements']) >= 200: return
        copied = copy.deepcopy(e); copied['id'] = uuid.uuid4().hex; name = e['name'] + ' コピー'; n = 1
        names = {x['name'] for x in d['elements']}
        while name in names: n += 1; name = e['name'] + ' コピー ' + str(n)
        copied['name'] = name
        if 'NUMB' in copied['attrs']:
            numbers = [int(x['attrs']['NUMB']) for x in d['elements'] if str(x['attrs'].get('NUMB', '')).isdigit()]
            copied['attrs']['NUMB'] = str(max(numbers + [0]) + 1)
        d['elements'].append(copied); self.element_id = copied['id']; self.host.mark(); self.refresh()

    def delete_element(self):
        e = self.element()
        if e and messagebox.askyesno('要素を削除', '要素を削除しますか？ 使用先にも影響します。', parent=self.host):
            self.definition()['elements'].remove(e); self.element_id = None; self.host.mark(); self.refresh()

    def select_scom(self, _=None):
        self.preview_scom_id = self.scom_names.get(self.scom_choice.get()); self.refresh_values()

    def refresh_values(self):
        s = project.get(self.data, 'scoms', self.preview_scom_id)
        self.values_label.configure(text=('読み取り専用 / ' + s['name'] + '\n\n' + '\n'.join(p['id'] + ' ' + p['role'] + '：' + str(s['values'].get(p['id'], '未入力')) + ' ' + p.get('unit', '') for p in self.data['parameters'][:6])) if s else '確認用 SCOM を選択してください。')

    def open_scom(self):
        s = project.get(self.data, 'scoms', self.preview_scom_id)
        if s: self.host.scom_id = s['id']; self.host.cate_id = s['cate_id']; self.host.switch('catalog')

    def draw(self):
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
        lines = ['$* ' + d['kind'] + ' ' + d['name']]
        for e in d['elements']:
            lines.extend('$* ' + line for line in (e['type']+' '+e['name']).splitlines())
            for key, value in e['attrs'].items(): lines.extend('$*   ' + line for line in (key+' = '+str(value)).splitlines())
        text.insert('1.0','\n'.join(lines)); text.configure(state='disabled')
        ttk.Button(win, text='閉じる', command=win.destroy).pack(pady=8)
