"""Persistent destination field beside each set editor's export button."""
import tkinter as tk
from tkinter import ttk
from . import macro_destinations as destinations


def build_field(editor, parent, *, horizontal=False):
    editor.destination_label=label=ttk.Label(parent,text='登録先',style='Muted.TLabel')
    label.pack(side='left',padx=(0,8)) if horizontal else label.pack(anchor='w')
    editor.destination_var = tk.StringVar(value=destinations.get(editor.data, editor.kind))
    editor.destination_entry = ttk.Entry(parent, textvariable=editor.destination_var, width=16)
    if horizontal:
        editor.destination_entry.pack(side='left')
    else:editor.destination_entry.pack(fill='x',pady=(3,8))

    def changed(*_):
        values = editor.data.setdefault(destinations.KEY, {})
        value = editor.destination_var.get()
        if values.get(editor.kind, '') != value:
            values[editor.kind] = value
            editor.host.mark()

    def commit(_=None):
        value = destinations.normalize(editor.destination_var.get(), strict=False)
        if value != editor.destination_var.get():
            editor.destination_var.set(value)

    editor.destination_var.trace_add('write', changed)
    editor.normalize_destination = commit
    editor.destination_entry.bind('<FocusOut>', commit)
    editor.destination_entry.bind('<Return>', commit)
