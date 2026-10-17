"""Preview/select catalogue creation text before appending independent definitions."""
import tkinter as tk
from tkinter import filedialog, ttk

from . import element_schema as schema, macro_import


class MacroImportDialog(tk.Toplevel):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.parsed = None
        self.analyzed_text = None
        self.title('PTSET・GMSET の作成マクロを読み込む')
        self.geometry('920x760'); self.minsize(680, 640)
        self.transient(host); self.grab_set()
        body = ttk.Frame(self, padding=16); body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        for row, weight in ((3,3), (5,2), (6,2)): body.rowconfigure(row, weight=weight, minsize=60)
        ttk.Label(body, text='PTSET・GMSET を読み込む', style='Heading.TLabel').grid(row=0, column=0, sticky='w')
        description = ttk.Label(body, text='ファイルを開くか、NEW PTSET /名前・NEW GMSET /名前 から始まる作成マクロを貼り付けて解析します。', wraplength=820)
        description.grid(row=1, column=0, sticky='ew', pady=(6,8))
        top = ttk.Frame(body); top.grid(row=2, column=0, sticky='ew', pady=(0,8))
        self.file_button = ttk.Button(top, text='ファイルを開く (.mac / .txt)', command=self.open_file)
        self.file_button.pack(side='left')
        ttk.Button(top, text='テキストを解析', command=self.analyze, style='Primary.TButton').pack(side='left', padx=8)
        self.source_label = ttk.Label(top, text='貼り付け入力', style='Muted.TLabel', wraplength=220); self.source_label.pack(side='left')
        source_frame = ttk.Frame(body); source_frame.grid(row=3, column=0, sticky='nsew')
        self.source = tk.Text(source_frame, width=40, height=8, wrap='none', undo=True, font=('Consolas', 10))
        self.source.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(source_frame, command=self.source.yview); scrollbar.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(source_frame, orient='horizontal', command=self.source.xview); horizontal.grid(row=1, column=0, sticky='ew')
        self.source.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        source_frame.rowconfigure(0, weight=1); source_frame.columnconfigure(0, weight=1)
        self.source.bind('<<Modified>>', self.invalidate)
        ttk.Label(body, text='取り込むセットを選択（Ctrl / Shift で複数選択）', style='Heading.TLabel').grid(row=4, column=0, sticky='w', pady=(12,5))
        selection_frame = ttk.Frame(body); selection_frame.grid(row=5, column=0, sticky='nsew')
        self.records = ttk.Treeview(selection_frame, columns=('kind', 'name', 'count'), show='headings', selectmode='extended', height=4)
        for key, label, width in [('kind','種類',90), ('name','定義名',480), ('count','要素数（子を含む）',130)]:
            self.records.heading(key, text=label); self.records.column(key, width=width, minwidth=70)
        self.records.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(selection_frame, command=self.records.yview); scrollbar.grid(row=0, column=1, sticky='ns')
        self.records.configure(yscrollcommand=scrollbar.set)
        selection_frame.rowconfigure(0, weight=1); selection_frame.columnconfigure(0, weight=1)
        self.records.bind('<<TreeviewSelect>>', self.select)
        detail_frame = ttk.Frame(body); detail_frame.grid(row=6, column=0, sticky='nsew', pady=(8,5))
        self.details = tk.Text(detail_frame, width=40, height=4, wrap='word', state='disabled', font=(host.ui_font, 10))
        self.details.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(detail_frame, command=self.details.yview); scrollbar.pack(side='right', fill='y')
        self.details.configure(yscrollcommand=scrollbar.set)
        hint = ttk.Label(body, text='既存定義は上書きしません。同名は別名で追加します。PARAM の意味・単位・値型は読込後に設定してください。', wraplength=820, style='Muted.TLabel')
        hint.grid(row=7, column=0, sticky='ew', pady=4)
        self.notice = ttk.Label(body, text='テキストを解析すると取り込む定義を選べます。', wraplength=820)
        self.notice.grid(row=8, column=0, sticky='ew', pady=6)
        buttons = ttk.Frame(body); buttons.grid(row=9, column=0, sticky='ew')
        ttk.Button(buttons, text='取消', command=self.destroy).pack(side='right')
        self.apply_button = ttk.Button(buttons, text='選択した定義を追加', command=self.apply, style='Primary.TButton', state='disabled')
        self.apply_button.pack(side='right', padx=8)
        body.bind('<Configure>', lambda event: [label.configure(wraplength=max(300, event.width-8)) for label in (description, hint, self.notice)] if event.widget is body else None)
        self.source.focus_set()

    def text(self): return self.source.get('1.0', 'end-1c')

    def invalidate(self, _=None):
        if not self.source.edit_modified(): return
        self.source.edit_modified(False)
        if self.text() == self.analyzed_text: return
        self.parsed = None
        self.records.delete(*self.records.get_children())
        self.apply_button.configure(state='disabled')
        self.notice.configure(text='テキストを変更しました。「テキストを解析」を押してください。')
        self.show_details('')

    def show_details(self, text):
        self.details.configure(state='normal'); self.details.delete('1.0', 'end')
        self.details.insert('1.0', text); self.details.configure(state='disabled')

    def open_file(self):
        path = filedialog.askopenfilename(parent=self, title='作成マクロを開く',
                                          filetypes=[('作成マクロ・テキスト','*.mac *.txt'), ('すべてのファイル','*.*')])
        if not path: return
        try: text, encoding = macro_import.read_text(path)
        except (OSError, ValueError) as exc:
            self.notice.configure(text='ファイルを開けません：' + str(exc)); return
        self.source.delete('1.0', 'end'); self.source.insert('1.0', text)
        self.source.edit_modified(False)
        self.source_label.configure(text=path.rsplit('/', 1)[-1].rsplit('\\', 1)[-1] + ' / ' + encoding)
        self.analyze()

    def analyze(self):
        self.parsed = None; self.apply_button.configure(state='disabled')
        self.records.delete(*self.records.get_children())
        text = self.text()
        try: parsed = macro_import.parse(text)
        except (ValueError, RecursionError) as exc:
            self.notice.configure(text='解析できません：' + str(exc)); self.show_details('取り込みは行っていません。該当行を確認してください。'); return
        self.parsed, self.analyzed_text = parsed, text
        for record in parsed.definitions:
            self.records.insert('', 'end', iid=record['id'], values=(record['kind'], record['name'], sum(1 for _ in schema.walk(record['elements']))))
        self.records.selection_set(*self.records.get_children())
        self.notice.configure(text=f'{len(parsed.definitions)}件の定義を解析しました。マクロは実行していません。')
        self.select()

    def select(self, _=None):
        selection = set(self.records.selection())
        self.apply_button.configure(state='normal' if self.parsed and selection else 'disabled')
        if not self.parsed: return
        lines = [f'選択：{len(selection)}件 / {len(self.parsed.definitions)}件',
                 '選択した定義には専用の空のPARAMプリセットを作成します。既存の規則・SCOM実値は変更しません。']
        for record in self.parsed.definitions:
            if record['id'] not in selection: continue
            lines.append('\n' + record['kind'] + ' ' + record['name'])
            for element in schema.walk(record['elements']):
                lines.append('  ' + element['type'] + ' ' + element['name'])
                lines.extend('    ' + key + ' ' + value for key, value in element['attrs'].items())
        if self.parsed.warnings:
            lines.append('\n読込時の注意（ファイル全体）：')
            lines.extend(self.parsed.warnings)
        self.show_details('\n'.join(lines))

    def apply(self):
        if not self.parsed or self.text() != self.analyzed_text:
            self.notice.configure(text='テキストを再解析してください。'); return
        selected = self.records.selection()
        if not selected:
            self.notice.configure(text='取り込む定義を選択してください。'); return
        host = self.host
        if host.page == 'rules' and not host.preset_editor.can_leave(): return
        if host.commit_definition_name() is False: return
        try: candidate, added, renamed = macro_import.prepare_import(host.data, self.parsed, selected)
        except (ValueError, RecursionError) as exc:
            self.notice.configure(text='取り込めません：' + str(exc)); return
        preferred = next((record for record in added if record['kind'].lower() == host.page), added[0])
        host.data = candidate
        host.definition_id = preferred['id']; host.element_id = None; host.field = None
        host.page = {'PTSET':'ptset', 'GMSET':'gmset'}.get(preferred['kind'], 'structural')
        if host.page == 'structural': host.structural_kind = preferred['kind']
        host.registered_browser.search.set('')
        self.destroy()
        host.render_page()
        message = f'作成マクロから{len(added)}件追加しました。PARAM規則を確認し、Ctrl+Sで保存してください。'
        if renamed: message += f' 同名の{len(renamed)}件は -IMPORT- 番号を付けて追加しました。'
        host.mark(message)
