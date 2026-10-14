"""Registered records for the currently selected category."""
import tkinter as tk
from tkinter import ttk


class RegisteredBrowser(ttk.Frame):
    def __init__(self, host, parent):
        super().__init__(parent, padding=(12, 14, 8, 12), width=220)
        self.host = host
        self.signature = None
        self.items = {}
        self.category = None
        self.refreshing = False
        self.pack(side='left', fill='y')
        self.pack_propagate(False)
        toolbar=ttk.Frame(self);toolbar.pack(fill='x')
        self.heading=ttk.Label(toolbar, text='登録データ', style='PaneTitle.TLabel')
        self.heading.pack(side='left')
        self.add_button=ttk.Button(toolbar,text='＋ 追加',command=self.add_definition,style='Primary.TButton')
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
        if self.refreshing:return
        self.refreshing=True
        try:self._refresh()
        finally:self.refreshing=False

    def _refresh(self):
        host = self.host
        data = host.data
        if self.category!=host.page:
            self.category=host.page
            self.search.set('')
        categories={'ptset':('PTSET','definitions'), 'gmset':('GMSET','definitions'), 'catalog':('SCOM','scoms'), 'specs':('スペック','specs'), 'structural':('構造材・NGMSET','definitions'), 'texts':('説明・材質','texts'), 'tables':('共通テーブル','tables'), 'books':('カタログ本','books'), 'rules':('PARAM プリセット','parameter_presets')}
        label,collection=categories.get(host.page,('確認・マクロ',None))
        if host.page in ('ptset','gmset'):self.add_button.pack(side='right')
        else:self.add_button.pack_forget()
        records=[r for r in data.get(collection,[]) if isinstance(r,dict) and 'id' in r] if collection else []
        if host.page in ('ptset','gmset'):records=[r for r in records if r['kind']==host.page.upper()]
        elif host.page=='structural':records=[r for r in records if r['kind'] not in ('PTSET','GMSET')]
        elif host.page=='rules':records=[{'id':'legacy','name':'既存規則（従来データ）'}]+records
        query = self.search.get().strip().casefold()
        visible=[r for r in records if query in (r.get('name',r.get('title',''))+' '+r.get('kind',r.get('type',''))+' '+label).casefold()]
        self.heading.configure(text=label+' ('+str(len(visible))+')')
        signature = (host.page, query, tuple((r['id'], r.get('name',r.get('title','')), r.get('kind',r.get('type',''))) for r in visible))
        if signature != self.signature:
            self.tree.delete(*self.tree.get_children())
            self.items = {}
            for record in visible:
                key = collection + ':' + record['id']
                text = record.get('name',record.get('title','')) + (' [' + record['kind'] + ']' if host.page == 'structural' else '')
                self.tree.insert('', 'end', iid=key, text=text)
                self.items[key] = (collection, record)
            self.signature = signature
        target = None
        if host.page in ('ptset', 'gmset', 'structural'):
            target = 'definitions:' + str(host.definition_id)
        elif host.page == 'catalog':
            target = 'scoms:' + str(host.scom_id)
        elif host.page == 'specs':
            target = 'specs:' + str(host.spec_id)
        elif host.page=='rules':target='parameter_presets:'+str(data.get('active_parameter_preset_id') or 'legacy')
        elif host.page=='books':target='books:'+str(host.selected_book)
        elif host.page in ('texts','tables') and hasattr(host,'companion_editor'):target=host.page+':'+str(host.companion_editor.selected)
        if target and self.tree.exists(target):
            if self.tree.selection() != (target,):
                self.tree.selection_set(target)
                self.tree.see(target)

    def add_definition(self):
        if self.host.page not in ('ptset','gmset'):return
        if self.host.commit_definition_name() is False:return
        self.host.definition_form(self.host.page.upper())

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
            if host.commit_definition_name() is False:self.refresh();return
            host.definition_id = record['id']
            if page == 'structural':
                host.structural_kind = record['kind']
        elif collection == 'scoms':
            page = 'catalog'
            if host.page == page and host.scom_id == record['id']:
                return
            host.scom_id = record['id']
        elif collection=='specs':
            page = 'specs'
            if host.page == page and host.spec_id == record['id']:
                return
            host.spec_id = record['id']
        elif collection=='parameter_presets':
            ident='' if record['id']=='legacy' else record['id']
            if host.data.get('active_parameter_preset_id','')==ident:return
            host.data['active_parameter_preset_id']=ident;host.mark();host.render_page();return
        elif collection=='books':
            host.selected_book=record['id'];host.books_table.selection_set(record['id']);host.update_book_info();return
        elif collection in ('texts','tables'):
            host.companion_editor.table.selection_set(record['id']);host.companion_editor.select();return
        else:return
        host.switch(page)
