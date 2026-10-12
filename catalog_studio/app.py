"""Tk desktop UI. No third-party Python packages required."""
import math
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font, messagebox, ttk
from . import model

BLUE = '#2269de'
INK = '#243448'
MUTED = '#77879a'
BG = '#f4f7fb'


class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Catalog Studio — Python / E3D 4.0')
        self.geometry('1380x980'); self.minsize(1000, 850)
        self.configure(bg=BG)
        self.project = model.sample(); self.selected = 'shape1'; self.field = '位置'
        self.path = None; self.dirty = False; self.busy = False; self.drag = None
        families = set(font.families(self))
        self.ui_font = next((f for f in ('Yu Gothic UI', 'Meiryo', 'Noto Sans CJK JP', 'Hiragino Sans', 'Arial') if f in families), 'TkDefaultFont')
        self.style = ttk.Style(self); self.style.theme_use('clam')
        self.style.configure('.', font=(self.ui_font, 10), background='white', foreground=INK)
        self.style.configure('TButton', padding=(10, 6))
        self.style.configure('Primary.TButton', background=BLUE, foreground='white')
        self.style.map('Primary.TButton', background=[('active', '#1858bd')])
        self.style.configure('Title.TLabel', font=(self.ui_font, 19, 'bold'))
        self.style.configure('Heading.TLabel', font=(self.ui_font, 11, 'bold'))
        self.style.configure('Muted.TLabel', foreground=MUTED)
        self.style.configure('Treeview', rowheight=30, background='white', fieldbackground='white')
        self.style.configure('Treeview.Heading', background='#eff4fa', padding=(5, 7))
        self.style.map('Treeview', background=[('selected', '#e4efff')], foreground=[('selected', BLUE)])
        self.build()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Control-s>', lambda _: self.save_project())
        self.bind('<Control-o>', lambda _: self.open_project())
        self.bind('<Control-n>', lambda _: self.new_project())
        self.refresh()

    def build(self):
        header = ttk.Frame(self, padding=(20, 14)); header.pack(fill='x')
        brand = ttk.Frame(header); brand.pack(side='left')
        ttk.Label(brand, text='◇  Catalog Studio', style='Title.TLabel').pack(anchor='w')
        ttk.Label(brand, text='Python デスクトップ版 · 形状・ポイント編集', style='Muted.TLabel').pack(anchor='w')
        for text, command, style in [('マクロ出力', self.export, 'Primary.TButton'), ('保存', self.save_project, 'TButton'), ('新規作成', self.new_project, 'TButton'), ('読み込み', self.open_project, 'TButton')]:
            ttk.Button(header, text=text, command=command, style=style).pack(side='right', padx=4)
        tk.Label(self, text='操作モックアップ：要素・属性・パラメータは仮仕様です。E3D 出力の解析・実行用マクロ生成は未対応です。', bg='#eaf1fb', fg='#60738e', anchor='w', padx=22, pady=8).pack(fill='x')
        main = ttk.Panedwindow(self, orient='horizontal'); main.pack(fill='both', expand=True, padx=16, pady=12)
        left = ttk.Frame(main, padding=12); middle = ttk.Frame(main, padding=16); right = ttk.Frame(main, padding=12)
        main.add(left, weight=1); main.add(middle, weight=3); main.add(right, weight=3)
        ttk.Label(left, text='部品・構成', style='Heading.TLabel').pack(anchor='w', pady=(0, 8))
        self.project_name = tk.StringVar()
        entry = ttk.Entry(left, textvariable=self.project_name, width=22); entry.pack(fill='x', pady=(0, 10)); entry.bind('<FocusOut>', self.rename_project); entry.bind('<Return>', self.rename_project)
        self.tree = ttk.Treeview(left, show='tree', selectmode='browse', height=12)
        self.tree.pack(fill='both', expand=True); self.tree.bind('<<TreeviewSelect>>', self.select_element)
        ttk.Button(left, text='＋ 要素を追加', command=self.add_dialog).pack(fill='x', pady=10)
        ttk.Label(left, text='形状とポイントを選択すると\n編集内容が切り替わります。', style='Muted.TLabel').pack(anchor='w')
        titlebar = ttk.Frame(middle); titlebar.pack(fill='x')
        self.title_text = ttk.Label(titlebar, text='', style='Heading.TLabel'); self.title_text.pack(side='left')
        ttk.Button(titlebar, text='削除', command=self.delete).pack(side='right', padx=(4, 0))
        ttk.Button(titlebar, text='複製', command=self.duplicate).pack(side='right')
        namebar = ttk.Frame(middle); namebar.pack(fill='x', pady=12)
        ttk.Label(namebar, text='表示名').pack(side='left', padx=(0, 10))
        self.element_name = tk.StringVar()
        self.name_entry = ttk.Entry(namebar, textvariable=self.element_name); self.name_entry.pack(fill='x', expand=True)
        self.name_entry.bind('<FocusOut>', self.rename_element); self.name_entry.bind('<Return>', self.rename_element)
        self.attrs = ttk.Treeview(middle, columns=('field', 'value', 'ref'), show='headings', selectmode='browse', height=5)
        for key, text, width in [('field', '設定項目', 80), ('value', '設定値・式', 210), ('ref', '参照', 65)]:
            self.attrs.heading(key, text=text); self.attrs.column(key, width=width, minwidth=50)
        self.attrs.pack(fill='x'); self.attrs.bind('<<TreeviewSelect>>', self.select_field)
        formula = ttk.LabelFrame(middle, text='選択した属性の編集', padding=10); formula.pack(fill='x', pady=10)
        self.field_label = ttk.Label(formula, text='位置の式', style='Heading.TLabel'); self.field_label.pack(anchor='w', pady=(0, 8))
        self.expr = tk.StringVar(); self.expr.trace_add('write', self.expression_changed)
        self.expr_entry = ttk.Entry(formula, textvariable=self.expr, font=(self.ui_font, 15)); self.expr_entry.pack(fill='x')
        self.direction = ttk.Combobox(formula, values=model.DIRECTIONS, state='readonly'); self.direction.bind('<<ComboboxSelected>>', self.direction_changed)
        self.insertbar = ttk.Frame(formula); self.insertbar.pack(fill='x', pady=10)
        self.param_choice = ttk.Combobox(self.insertbar, state='readonly'); self.param_choice.pack(side='left', fill='x', expand=True)
        ttk.Button(self.insertbar, text='挿入', command=self.insert_parameter).pack(side='left', padx=5)
        ttk.Button(self.insertbar, text='÷ 2', command=self.half).pack(side='left')
        self.result = ttk.Label(formula, text='', wraplength=380); self.result.pack(anchor='w', pady=6)
        ttk.Label(formula, text='四則演算・括弧・役割名／番号を使用できます。', style='Muted.TLabel', wraplength=380).pack(anchor='w')
        self.number_expr = ttk.Label(formula, text='', style='Muted.TLabel', wraplength=380); self.number_expr.pack(anchor='w', pady=(8, 0))
        previewbar = ttk.Frame(right); previewbar.pack(fill='x')
        ttk.Label(previewbar, text='3D 概略プレビュー', style='Heading.TLabel').pack(side='left')
        self.points = tk.BooleanVar(value=True)
        ttk.Checkbutton(previewbar, text='ポイント', variable=self.points, command=self.draw).pack(side='right')
        self.canvas = tk.Canvas(right, bg='#f4f8fd', highlightthickness=0, width=460, height=310)
        self.canvas.pack(fill='both', expand=True, pady=10)
        self.canvas.bind('<Configure>', lambda _: self.draw())
        self.canvas.bind('<ButtonPress-1>', lambda e: setattr(self, 'drag', (e.x, self.view.get())))
        self.canvas.bind('<B1-Motion>', self.rotate)
        self.canvas.bind('<ButtonRelease-1>', lambda _: setattr(self, 'drag', None))
        self.view = tk.DoubleVar(value=20)
        ttk.Scale(right, from_=-60, to=60, variable=self.view, command=lambda _: self.draw()).pack(fill='x')
        ttk.Label(right, text='ドラッグで視点変更 · 正確な CAD 表示ではありません', style='Muted.TLabel').pack(anchor='w', pady=5)
        ttk.Label(right, text='サンプル寸法', style='Heading.TLabel').pack(anchor='w', pady=(10, 5))
        self.samples = ttk.Frame(right); self.samples.pack(fill='x')
        self.notebook = ttk.Notebook(self); self.notebook.pack(fill='x', padx=16, pady=(0, 10))
        param_frame = ttk.Frame(self.notebook, padding=10); check_frame = ttk.Frame(self.notebook, padding=10); macro_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(param_frame, text='パラメータ一覧'); self.notebook.add(check_frame, text='確認事項'); self.notebook.add(macro_frame, text='生成マクロ（構成確認用）')
        self.params = ttk.Treeview(param_frame, columns=('id', 'role', 'value'), show='headings', height=4)
        for key, label, width in [('id', '番号', 80), ('role', '役割・表示名', 400), ('value', 'サンプル値 [mm]', 160)]:
            self.params.heading(key, text=label); self.params.column(key, width=width)
        self.params.pack(side='left', fill='both', expand=True)
        self.params.bind('<Double-1>', lambda _: self.edit_parameter())
        scrollbar = ttk.Scrollbar(param_frame, orient='vertical', command=self.params.yview); scrollbar.pack(side='left', fill='y'); self.params.configure(yscrollcommand=scrollbar.set)
        buttons = ttk.Frame(param_frame, padding=(10, 0)); buttons.pack(side='right')
        for text, cmd in [('＋ 追加', self.add_parameter), ('役割・値を編集', self.edit_parameter), ('削除', self.remove_parameter)]:
            ttk.Button(buttons, text=text, command=cmd).pack(fill='x', pady=2)
        self.check_text = tk.Text(check_frame, height=5, wrap='word', relief='flat', font=(self.ui_font, 10)); self.check_text.pack(fill='both', expand=True)
        self.macro = tk.Text(macro_frame, height=5, wrap='none', relief='flat', font=('Consolas', 10)); self.macro.pack(fill='both', expand=True)
        self.status = ttk.Label(self, text='サンプルを表示中 · 保存は JSON ファイル', background=BG, foreground=MUTED)
        self.status.pack(fill='x', padx=20, pady=(0, 8))
        # Allocate the footer first, so it remains visible on smaller displays.
        main.pack_forget()
        self.status.pack_configure(side='bottom', before=self.notebook)
        self.notebook.pack_configure(side='bottom')
        main.pack(fill='both', expand=True, padx=16, pady=12)

    def element(self):
        return next((e for e in self.project['elements'] if e['id'] == self.selected), None)

    def mark(self):
        self.dirty = True
        self.title('Catalog Studio — ' + self.project['name'] + ' *')
        self.status.configure(text='未保存の変更があります。Ctrl+S で保存できます。')

    def refresh(self):
        self.busy = True
        self.project_name.set(self.project['name'])
        self.tree.delete(*self.tree.get_children())
        for group, name in [('geometry', '形状 · GMSET'), ('points', 'ポイント · PTSET')]:
            self.tree.insert('', 'end', iid=group, text=name, open=True)
        for e in self.project['elements']:
            self.tree.insert('points' if e['type'] == 'point' else 'geometry', 'end', iid=e['id'], text=e['name'])
        if self.element(): self.tree.selection_set(self.selected)
        self.params.delete(*self.params.get_children())
        for p in self.project['parameters']: self.params.insert('', 'end', iid=p['id'], values=(p['id'], p['role'], p['value']))
        self.param_choice['values'] = [p['id'] + '：' + p['role'] for p in self.project['parameters']]
        if self.project['parameters']: self.param_choice.current(0)
        for child in self.samples.winfo_children(): child.destroy()
        # All values remain editable in the parameter table; keep preview compact.
        for i, p in enumerate(self.project['parameters'][:5]):
            ttk.Label(self.samples, text=p['id'] + '  ' + p['role']).grid(row=i, column=0, sticky='w', pady=2)
            entry = ttk.Entry(self.samples, width=12); entry.insert(0, str(p['value'])); entry.grid(row=i, column=1, padx=10, pady=2)
            ttk.Label(self.samples, text='mm', style='Muted.TLabel').grid(row=i, column=2)
            entry.bind('<Return>', lambda event, pid=p['id']: self.change_value(pid, event.widget.get()))
            entry.bind('<FocusOut>', lambda event, pid=p['id']: self.change_value(pid, event.widget.get()))
        self.busy = False
        self.refresh_editor(); self.refresh_outputs(); self.draw()

    def refresh_editor(self):
        self.busy = True
        e = self.element(); self.attrs.delete(*self.attrs.get_children())
        if not e:
            self.title_text.configure(text='要素を追加してください'); self.element_name.set(''); self.expr.set('')
            self.expr_entry.configure(state='disabled'); self.name_entry.configure(state='disabled')
            self.result.configure(text=''); self.number_expr.configure(text=''); self.busy = False
            return
        self.expr_entry.configure(state='normal'); self.name_entry.configure(state='normal')
        self.title_text.configure(text=model.SCHEMAS[e['type']][0]); self.element_name.set(e['name'])
        if self.field not in model.SCHEMAS[e['type']][1]: self.field = model.SCHEMAS[e['type']][1][0]
        for k in model.SCHEMAS[e['type']][1]:
            refs = ', '.join(model.references(e['attrs'][k], self.project['parameters'])) or '固定値'
            self.attrs.insert('', 'end', iid=k, values=(k, e['attrs'][k], refs))
        self.attrs.selection_set(self.field)
        self.load_field()
        self.busy = False

    def load_field(self):
        e = self.element()
        if not e: return
        self.field_label.configure(text=self.field + ('の選択' if self.field == '方向' else 'の式'))
        if self.field == '方向':
            self.expr_entry.pack_forget(); self.insertbar.pack_forget(); self.direction.pack(fill='x', before=self.result)
            self.direction.set(e['attrs'][self.field]); self.result.configure(text='方向は概略図に反映します。')
            self.number_expr.configure(text='')
        else:
            self.direction.pack_forget(); self.expr_entry.pack(fill='x', before=self.result)
            self.insertbar.pack(fill='x', pady=10, before=self.result)
            self.expr.set(e['attrs'][self.field]); self.calc_result()

    def select_element(self, _=None):
        if self.busy: return
        selection = self.tree.selection()
        if selection and any(e['id'] == selection[0] for e in self.project['elements']):
            self.selected = selection[0]; self.refresh_editor(); self.draw()

    def select_field(self, _=None):
        if self.busy: return
        selection = self.attrs.selection()
        if selection and selection[0] != self.field:
            self.field = selection[0]; self.busy = True; self.load_field(); self.busy = False

    def expression_changed(self, *_):
        if self.busy or not self.element() or self.field == '方向': return
        self.element()['attrs'][self.field] = self.expr.get()
        self.attrs.item(self.field, values=(self.field, self.expr.get(), ', '.join(model.references(self.expr.get(), self.project['parameters'])) or '固定値'))
        self.mark(); self.calc_result(); self.refresh_outputs(); self.draw()

    def calc_result(self):
        try:
            value = model.evaluate(self.expr.get(), self.project['parameters'])
            self.result.configure(text=f'計算結果：{value:,.3f}'.rstrip('0').rstrip('.') + ' mm', foreground='#178268')
        except ValueError as exc: self.result.configure(text=str(exc), foreground='#bf4e48')
        number = re.sub(r'[^\s+*/()\-]+', lambda m: next((p['id'] for p in self.project['parameters'] if p['role'] == m[0]), m[0]), self.expr.get())
        self.number_expr.configure(text='番号での式：' + number)

    def direction_changed(self, _=None):
        if self.element(): self.element()['attrs']['方向'] = self.direction.get(); self.mark(); self.refresh_editor(); self.refresh_outputs(); self.draw()

    def insert_parameter(self):
        if not self.element() or self.field == '方向' or not self.project['parameters']: return
        choice = self.param_choice.current()
        if choice < 0: return
        name = self.project['parameters'][choice]['role']
        try: start, end = self.expr_entry.index('sel.first'), self.expr_entry.index('sel.last')
        except tk.TclError: start = end = self.expr_entry.index('insert')
        text = self.expr.get(); self.expr.set(text[:start] + name + text[end:])
        self.expr_entry.focus_set(); self.expr_entry.icursor(start + len(name))

    def half(self):
        if self.element() and self.field != '方向': self.expr.set('(' + self.expr.get() + ') / 2')

    def rename_project(self, _=None):
        name = self.project_name.get().strip()
        if name and name != self.project['name']: self.project['name'] = name; self.mark(); self.refresh_outputs()

    def rename_element(self, _=None):
        e = self.element()
        if e and e['name'] != self.element_name.get():
            e['name'] = self.element_name.get(); self.tree.item(e['id'], text=e['name']); self.mark(); self.refresh_outputs(); self.draw()

    def add_dialog(self):
        window = tk.Toplevel(self); window.title('要素を追加'); window.transient(self); window.grab_set()
        ttk.Label(window, text='追加する形状・ポイントを選択', style='Heading.TLabel', padding=16).pack()
        for kind, (label, _) in model.SCHEMAS.items():
            ttk.Button(window, text=label, command=lambda k=kind: (self.add(k), window.destroy())).pack(fill='x', padx=18, pady=6)
        ttk.Label(window, text='要素型と属性は仮の代表例です。', style='Muted.TLabel', padding=16).pack()

    def add(self, kind):
        try: self.selected = model.add_element(self.project, kind)['id']
        except ValueError as exc: messagebox.showerror('追加できません', str(exc), parent=self); return
        self.mark(); self.refresh()

    def duplicate(self):
        if self.element():
            try: self.selected = model.duplicate_element(self.project, self.element())['id']
            except ValueError as exc: messagebox.showerror('複製できません', str(exc), parent=self); return
            self.mark(); self.refresh()

    def delete(self):
        if self.element() and messagebox.askyesno('要素を削除', '選択中の要素を削除しますか？', parent=self):
            self.project['elements'] = [e for e in self.project['elements'] if e['id'] != self.selected]
            self.selected = next((e['id'] for e in self.project['elements']), None); self.mark(); self.refresh()

    def change_value(self, pid, text):
        if self.busy: return
        try:
            value = float(text)
            if not math.isfinite(value): raise ValueError()
        except ValueError:
            self.status.configure(text='サンプル寸法は有限の数値で入力してください。'); return
        p = next(p for p in self.project['parameters'] if p['id'] == pid)
        if p['value'] == value: return
        p['value'] = value; self.mark(); self.refresh()

    def add_parameter(self):
        if len(self.project['parameters']) >= 100:
            messagebox.showerror('追加できません', 'パラメータ数は最大 100 です。', parent=self); return
        n = max([int(p['id'][1:]) for p in self.project['parameters']] + [0]) + 1
        role = f'寸法{n}'
        while any(p['role'] == role for p in self.project['parameters']): role += '新'
        self.project['parameters'].append({'id': f'P{n}', 'role': role, 'value': 10})
        self.mark(); self.refresh(); self.params.selection_set(f'P{n}'); self.edit_parameter()

    def edit_parameter(self):
        selected = self.params.selection()
        if not selected: return
        p = next(p for p in self.project['parameters'] if p['id'] == selected[0])
        window = tk.Toplevel(self); window.title('パラメータ編集：' + p['id']); window.transient(self); window.grab_set()
        frame = ttk.Frame(window, padding=20); frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=p['id'] + ' の役割', style='Heading.TLabel').pack(anchor='w')
        role = ttk.Entry(frame, width=35); role.insert(0, p['role']); role.pack(fill='x', pady=8)
        ttk.Label(frame, text='サンプル値 [mm]').pack(anchor='w')
        value = ttk.Entry(frame); value.insert(0, str(p['value'])); value.pack(fill='x', pady=8)
        error = ttk.Label(frame, foreground='#bf4e48', wraplength=300); error.pack()
        def apply():
            try:
                number = float(value.get())
                if not math.isfinite(number): raise ValueError('有限の数値を入力してください。')
                model.rename_parameter(self.project, p['id'], role.get().strip())
            except ValueError as exc: error.configure(text=str(exc)); return
            p['value'] = number; self.mark(); self.refresh(); window.destroy()
        ttk.Button(frame, text='適用', command=apply, style='Primary.TButton').pack(anchor='e', pady=8)

    def remove_parameter(self):
        selected = self.params.selection()
        if not selected: return
        pid = selected[0]
        if any(pid in model.references(v, self.project['parameters']) for e in self.project['elements'] for v in e['attrs'].values()):
            messagebox.showinfo('削除できません', '使用中のパラメータです。', parent=self); return
        if not messagebox.askyesno('削除', pid + ' を削除しますか？', parent=self): return
        self.project['parameters'] = [p for p in self.project['parameters'] if p['id'] != pid]; self.mark(); self.refresh()

    @staticmethod
    def set_text(widget, text):
        widget.configure(state='normal'); widget.delete('1.0', 'end'); widget.insert('1.0', text); widget.configure(state='disabled')

    def refresh_outputs(self):
        problems = model.issues(self.project)
        self.set_text(self.check_text, '\n'.join('! ' + p for p in problems) if problems else '✓ 式・寸法・名前の基本チェックに問題はありません。')
        self.check_text.configure(state='normal'); self.check_text.insert('end', '\n○ E3D 属性・接続規則・実行マクロの検証は未対応です。'); self.check_text.configure(state='disabled')
        self.notebook.tab(1, text='確認事項' + (f' ({len(problems)})' if problems else ''))
        self.set_text(self.macro, model.macro_text(self.project))

    def rotate(self, event):
        if self.drag: self.view.set(max(-60, min(60, self.drag[1] + (event.x - self.drag[0]) / 3))); self.draw()

    def draw(self):
        if not hasattr(self, 'canvas'): return
        c = self.canvas; c.delete('all'); w, h = max(c.winfo_width(), 350), max(c.winfo_height(), 240)
        angle = math.radians(self.view.get()); scale = min(w / 420, h / 280)
        def project(v):
            x, y, z = v
            return (w * .37 + scale * (z * math.cos(angle) + x * .45), h * .5 + scale * (z * math.sin(angle) * .55 - y + x * .18))
        for t in range(-240, 300, 30):
            c.create_line(*project((t, -70, -160)), *project((t, -70, 260)), fill='#e1e9f3')
            c.create_line(*project((-240, -70, t)), *project((300, -70, t)), fill='#e1e9f3')
        def value(e, k, fallback=0):
            try: return max(-250, min(250, model.evaluate(e['attrs'].get(k, str(fallback)), self.project['parameters'])))
            except ValueError: return fallback
        def orient(v, direction):
            x, y, z = v; sign = -1 if direction.startswith('-') else 1
            axis = direction[-1:]
            if axis == 'X': return (z * sign, y, x)
            if axis == 'Y': return (x, z * sign, y)
            return (x, y, z * sign)
        def pt(e, x, y, z): return project(orient((x, y, z), e['attrs'].get('方向', 'Z')))
        shapes = [e for e in self.project['elements'] if e['type'] != 'point']
        for e in shapes[:12]:
            selected = e['id'] == self.selected; fill = '#b6cfee' if selected else '#d0dae6'; stroke = BLUE if selected else '#8c9fb5'
            pos = value(e, '位置'); length = max(1, value(e, '長さ', value(e, '幅', 100)))
            if e['type'] == 'box':
                a, b, d = value(e, '幅', 50) / 2, value(e, '高さ', 30) / 2, value(e, '奥行き', 40) / 2
                verts = [pt(e, x, y, z + pos) for x, y, z in [(-a,-b,-d),(a,-b,-d),(a,b,-d),(-a,b,-d),(-a,-b,d),(a,-b,d),(a,b,d),(-a,b,d)]]
                for face in [(0,1,2,3),(1,5,6,2),(3,2,6,7)]:
                    c.create_polygon(*[n for i in face for n in verts[i]], fill=fill, outline=stroke, width=2 if selected else 1)
            else:
                r1 = max(1, value(e, '大径', value(e, '直径', 50)) / 2)
                r2 = max(1, value(e, '小径', 50) / 2) if e['type'] == 'cone' else r1
                rings = []
                for radius, z in [(r1, pos - length / 2), (r2, pos + length / 2)]:
                    rings.append([pt(e, radius * math.cos(t * math.pi / 12), radius * math.sin(t * math.pi / 12), z) for t in range(24)])
                for i in range(24):
                    j = (i + 1) % 24
                    c.create_polygon(*rings[0][i], *rings[0][j], *rings[1][j], *rings[1][i], fill=fill, outline=fill)
                for ring in rings:
                    c.create_line(*[n for p in ring + ring[:1] for n in p], fill=stroke, width=2)
        if self.points.get():
            for e in self.project['elements']:
                if e['type'] != 'point': continue
                # Point location is a global Z offset for this prototype; direction indicates its arrow.
                x, y = project((0, 0, value(e, '位置')))
                vector = orient((0, 0, 24), e['attrs'].get('方向', 'Z'))
                end = project((vector[0], vector[1], value(e, '位置') + vector[2]))
                c.create_line(x, y, *end, fill=BLUE, width=2, arrow='last')
                r = 6 if e['id'] == self.selected else 4
                c.create_oval(x-r, y-r, x+r, y+r, fill=BLUE if e['id'] == self.selected else 'white', outline=BLUE, width=2)
                c.create_text(x+8, y-18, text=e['name'], anchor='w', fill=BLUE, font=(self.ui_font, 9))
        c.create_text(12, h-12, text='仮の軸・原点 / 概略表示', anchor='w', fill=MUTED, font=(self.ui_font, 9))
        if not shapes: c.create_text(w/2, h/2, text='形状を追加すると表示されます', fill=MUTED)

    def guard(self):
        if not self.dirty: return True
        answer = messagebox.askyesnocancel('未保存の変更', '変更を保存しますか？', parent=self)
        if answer is None: return False
        return self.save_project() if answer else True

    def save_project(self):
        self.rename_project(); self.rename_element()
        path = self.path or filedialog.asksaveasfilename(parent=self, title='プロジェクトを保存', defaultextension='.json', initialfile='catalog-project.json', filetypes=[('プロジェクト JSON', '*.json')])
        if not path: return False
        try: model.save(self.project, path)
        except (OSError, ValueError) as exc: messagebox.showerror('保存できません', str(exc), parent=self); return False
        self.path = path; self.dirty = False; self.title('Catalog Studio — ' + self.project['name'])
        self.status.configure(text='保存済み：' + str(path)); return True

    def open_project(self):
        if not self.guard(): return
        path = filedialog.askopenfilename(parent=self, title='モックアップの JSON を読み込み（E3D 出力は未対応）', filetypes=[('プロジェクト JSON', '*.json')])
        if not path: return
        try: data = model.load(path)
        except (OSError, ValueError, RecursionError) as exc: messagebox.showerror('読み込みできません', str(exc), parent=self); return
        self.project = data; self.path = path; self.dirty = False
        self.selected = next((e['id'] for e in data['elements']), None); self.refresh()
        self.title('Catalog Studio — ' + self.project['name']); self.status.configure(text='読み込み済み：' + path)

    def new_project(self):
        if not self.guard(): return
        self.project = model.sample(); self.project['name'] = '新規部品'; self.project['elements'] = []
        self.path = None; self.selected = None; self.mark(); self.refresh()

    def export(self):
        window = tk.Toplevel(self); window.title('構成確認用ファイルの出力'); window.transient(self); window.grab_set()
        ttk.Label(window, text='コメントのみのファイルです。E3D に部品を登録する実行マクロではありません。', padding=14, wraplength=600).pack()
        text = tk.Text(window, width=75, height=20, font=('Consolas', 10)); text.pack(padx=14); self.set_text(text, model.macro_text(self.project))
        def download():
            path = filedialog.asksaveasfilename(parent=window, defaultextension='.mac', initialfile='catalog-mockup-review.mac')
            if not path: return
            try: Path(path).write_text(model.macro_text(self.project), encoding='utf-8')
            except OSError as exc: messagebox.showerror('出力できません', str(exc), parent=window); return
            self.status.configure(text='構成確認用ファイルを出力：' + path); window.destroy()
        ttk.Button(window, text='確認用ファイルを保存', command=download, style='Primary.TButton').pack(pady=14)

    def close(self):
        if self.guard(): self.destroy()


def main():
    try:
        app = Studio()
    except tk.TclError as exc:
        print('GUI を起動できません。デスクトップ環境で python main.py を実行してください。\n' + str(exc), file=sys.stderr)
        return 1
    app.mainloop()
    return 0
