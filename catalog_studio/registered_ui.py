"""Persistent browser for named catalogue data, independent of page navigation."""
import tkinter as tk
from tkinter import ttk


class RegisteredBrowser(ttk.Frame):
    def __init__(self, host, parent):
        super().__init__(parent, padding=(12, 14, 8, 12), width=250)
        self.host = host
        self.signature = None
        self.items = {}
        self.pack(side='left', fill='y')
        self.pack_propagate(False)
        ttk.Label(self, text='登録データ', style='Heading.TLabel').pack(anchor='w')
        self.search = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self.search)
        entry.pack(fill='x', pady=(10, 4))
        ttk.Label(self, text='名前・種類で検索', style='Muted.TLabel').pack(anchor='w', pady=(0, 10))
        holder = ttk.Frame(self)
        holder.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(holder, show='tree', selectmode='browse')
        self.tree.column('#0', width=240, minwidth=160)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(holder, command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(holder, orient='horizontal', command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.search.trace_add('write', lambda *_: self.refresh())
        self.refresh()

    def refresh(self):
        host = self.host
        data = host.data
        query = self.search.get().strip().casefold()
        signature = (query, tuple((collection, r['id'], r['name'], r.get('kind', '')) for collection in ('definitions', 'scoms', 'specs') for r in data[collection]))
        if signature != self.signature:
            opened = {key: self.tree.item(key, 'open') for key in self.tree.get_children()}
            self.tree.delete(*self.tree.get_children())
            self.items = {}
            groups = [('PTSET', 'PTSET', 'definitions'), ('GMSET', 'GMSET', 'definitions'), ('SCOM', 'SCOM', 'scoms'), ('SPEC', 'スペック', 'specs'), ('structural', '構造材・NGMSET', 'definitions')]
            for kind, label, collection in groups:
                records = [r for r in data[collection] if collection != 'definitions' or (r['kind'] not in ('PTSET', 'GMSET') if kind == 'structural' else r['kind'] == kind)]
                visible = [r for r in records if query in (r['name'] + ' ' + r.get('kind', kind) + ' ' + label).casefold()]
                if query and not visible:
                    continue
                group = 'group:' + kind
                self.tree.insert('', 'end', iid=group, text=label + ' (' + str(len(visible)) + ')', open=opened.get(group, True))
                for record in visible:
                    key = collection + ':' + record['id']
                    text = record['name'] + (' [' + record['kind'] + ']' if kind == 'structural' else '')
                    self.tree.insert(group, 'end', iid=key, text=text)
                    self.items[key] = (collection, record)
            self.signature = signature
        target = None
        if host.page in ('ptset', 'gmset', 'structural'):
            target = 'definitions:' + str(host.definition_id)
        elif host.page == 'catalog':
            target = 'scoms:' + str(host.scom_id)
        elif host.page == 'specs':
            target = 'specs:' + str(host.spec_id)
        if target and self.tree.exists(target):
            if self.tree.selection() != (target,):
                self.tree.selection_set(target)
                self.tree.see(target)

    def select(self, _=None):
        if self.host.busy:
            return
        selected = self.tree.selection()
        if not selected or selected[0] not in self.items:
            return
        collection, record = self.items[selected[0]]
        host = self.host
        if collection == 'definitions':
            page = {'PTSET': 'ptset', 'GMSET': 'gmset'}.get(record['kind'], 'structural')
            if host.page == page and host.definition_id == record['id']:
                return
            host.commit_definition_name()
            host.definition_id = record['id']
            if page == 'structural':
                host.structural_kind = record['kind']
        elif collection == 'scoms':
            page = 'catalog'
            if host.page == page and host.scom_id == record['id']:
                return
            host.scom_id = record['id']
        else:
            page = 'specs'
            if host.page == page and host.spec_id == record['id']:
                return
            host.spec_id = record['id']
        host.switch(page)
