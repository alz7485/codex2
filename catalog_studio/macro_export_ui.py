"""Preview and save the current set as a NEW-format .mac file."""
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import macro_export


def open_export(editor):
    host = editor.host
    grabbed = host.grab_current()
    if grabbed:
        grabbed.lift(); grabbed.focus_set(); return
    if not editor.commit_inline():
        return
    definition = editor.definition()
    if not definition:
        host.status.configure(text='出力するセットを選んでください。'); return
    requested_name = editor.def_name.get().strip()
    editor.commit_name()
    if requested_name != definition['name']:
        return
    try:
        source = macro_export.creation_text([definition])
    except ValueError as exc:
        messagebox.showerror('作成マクロを出力できません', str(exc), parent=host); return
    window = tk.Toplevel(host)
    window.title(definition['kind'] + '：MAC出力')
    window.geometry('820x650'); window.minsize(560, 400)
    window.transient(host); window.grab_set()
    ttk.Label(window, text=definition['name'] + '\nこのセットのみを出力します。式・属性を保持し、仮値やSCOMは含めません。\nE3D 4.0 実機での実行は未確認です。', padding=12, wraplength=520).pack(fill='x')
    footer = ttk.Frame(window, padding=12); footer.pack(side='bottom', fill='x')
    window.source = tk.Text(window, wrap='none', font=('Consolas', 10))
    horizontal = ttk.Scrollbar(window, orient='horizontal', command=window.source.xview)
    horizontal.pack(side='bottom', fill='x', padx=12)
    scroll = ttk.Scrollbar(window, orient='vertical', command=window.source.yview)
    scroll.pack(side='right', fill='y')
    window.source.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
    window.source.pack(fill='both', expand=True, padx=(12, 0))
    window.source.insert('1.0', source); window.source.configure(state='disabled')

    def save():
        filename = re.sub(r'[^\w.-]+', '-', definition['name'].lstrip('/')) or definition['kind']
        path = filedialog.asksaveasfilename(parent=window, title='作成マクロを保存',
                                          defaultextension='.mac', initialfile=filename + '.mac',
                                          filetypes=[('E3D / PDMS macro', '*.mac'), ('Text', '*.txt')])
        if not path:
            return
        try:
            macro_export.save(path, source)
        except (OSError, ValueError) as exc:
            messagebox.showerror('MAC保存エラー', str(exc), parent=window); return
        host.status.configure(text='作成マクロを保存しました：' + path)
        window.destroy()

    window.save_button = ttk.Button(footer, text='.mac を保存', command=save, style='Primary.TButton')
    window.save_button.pack(side='right')
    ttk.Button(footer, text='取消', command=window.destroy).pack(side='right', padx=8)
    return window
