"""Registered records for the currently selected category."""
import tkinter as tk
from tkinter import ttk, messagebox
from . import theme, browser_folders as folders


class RegisteredBrowser(ttk.Frame):
    def __init__(self, host, parent):
        super().__init__(parent, padding=(12, 14, 10, 0), width=220,style='Sidebar.TFrame')
        self.host = host
        self.signature = None
        self.items = {}
        self.category = None
        self.refreshing = False
        self.renaming=None
        self.open_states={}
        self.pack(side='left', fill='y')
        self.pack_propagate(False)
        toolbar=ttk.Frame(self,style='Sidebar.TFrame');toolbar.pack(fill='x')
        self.heading=ttk.Label(toolbar, text='登録データ', style='SidebarTitle.TLabel')
        self.heading.pack(side='left')
        from .project_actions import icon,Hint
        self.action_icons={k:icon(self,k,color=theme.ACCENT) for k in ('new','folder_add','search','macro','sdte_add','text_add','scom_add')}
        organize=ttk.Frame(self,style='Sidebar.TFrame');organize.pack(fill='x',pady=(8,6))
        self.add_button=ttk.Button(organize,text='アイテムを追加',image=self.action_icons['new'],compound='none',command=self.add_definition,style='AttributeTool.TButton')
        self.folder_button=ttk.Button(organize,text='フォルダを追加',image=self.action_icons['folder_add'],compound='none',command=self.add_folder,style='AttributeTool.TButton');self.folder_button.pack(side='left')
        self.action_hints=(Hint(self.add_button,'アイテムを追加'),Hint(self.folder_button,'フォルダを追加'))
        self.catalog_buttons={};self.catalog_hints=[]
        for kind in ('SDTE','TEXT','SCOM'):
            button=ttk.Button(organize,text=kind+'追加',image=self.action_icons[kind.lower()+'_add'],compound='none',command=lambda k=kind:self.add_catalog_record(k),style='AttributeTool.TButton')
            self.catalog_buttons[kind]=button
            self.catalog_hints.append(Hint(button,kind+'を追加'))
        self.macro_button=ttk.Menubutton(organize,text='マクロ ▾',image=self.action_icons['macro'],compound='left',style='AttributeTool.TButton')
        self.macro_menu=tk.Menu(self.macro_button,tearoff=False)
        self.macro_button.configure(menu=self.macro_menu)
        self.macro_menu.add_command(label='読込',command=host.import_creation_macro)
        from .macro_export_ui import open_export
        from .macro_destinations_ui import edit_destinations
        self.macro_menu.add_command(label='出力',command=lambda:open_export(host.geometry_editor))
        self.macro_menu.add_separator()
        self.macro_menu.add_command(label='登録先編集',command=lambda:edit_destinations(host.geometry_editor))
        self.search = tk.StringVar()
        self.search_row=ttk.Frame(self,style='Sidebar.TFrame');self.search_row.pack(fill='x',pady=(0,8))
        ttk.Label(self.search_row,image=self.action_icons['search'],style='Sidebar.TLabel').pack(side='left',padx=(0,4))
        self.search_entry=ttk.Entry(self.search_row,textvariable=self.search)
        self.search_entry.pack(side='left',fill='x',expand=True)
        self.clipboard=None
        holder = ttk.Frame(self)
        holder.pack(fill='both', expand=True)
        style=ttk.Style(self)
        style.configure('Ruled.Treeview',rowheight=30)
        self.rule_image=tk.PhotoImage(master=self,width=512,height=64)
        self.rule_image.put(theme.RULE,to=(0,63,512,64))
        style.element_create('RegisteredRowRule','image',self.rule_image,border=(0,0,0,1),width=0,height=0,sticky='nswe')
        style.layout('Ruled.Treeview.Item',[('RegisteredRowRule',{'sticky':'nswe','children':style.layout('Treeview.Item')})])
        self.folder_image=tk.PhotoImage(master=self,width=16,height=16)
        self.folder_image.put('#bf8b2a',to=(1,3,8,6));self.folder_image.put('#e6b64d',to=(1,5,15,14))
        self.folder_image.put('#f7d477',to=(2,6,14,8))
        from .preview_icons import create as preview_icon
        self.record_image=preview_icon(self)
        self.tree = ttk.Treeview(holder, show='tree', selectmode='browse',style='Ruled.Treeview')
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
        self.tree.bind('<F2>',lambda _:self.rename_item())
        self.tree.bind('<Double-1>',self.rename_at)
        self.context_menu=tk.Menu(self.tree,tearoff=False)
        for label,command,shortcut in (
            ('切り取り',lambda:self.copy_item(cut=True),'Ctrl+X'),('コピー',self.copy_item,'Ctrl+C'),('貼り付け',self.paste_item,'Ctrl+V'),
            ('移動先を選択…',self.move_item,''),('名前を変更',self.rename_item,''),('削除',self.delete_item,'')):
            self.context_menu.add_command(label=label,command=command,accelerator=shortcut)
        self.tree.bind('<Button-3>',self.popup)
        for sequence,command in (('<Control-x>',lambda:self.copy_item(cut=True)),('<Control-c>',self.copy_item),('<Control-v>',self.paste_item)):
            self.tree.bind(sequence,lambda event,fn=command:(fn(),'break')[1])
        ttk.Label(self,text='右クリック：移動・コピー・貼り付け',style='Sidebar.TLabel',wraplength=190).pack(anchor='w',pady=6)
        self.search.trace_add('write', lambda *_: self.refresh())
        self.refresh()

    def refresh(self):
        if self.renaming:self.cancel_rename()
        if self.refreshing:return
        self.refreshing=True
        try:self._refresh()
        finally:self.refreshing=False

    def rows(self):
        host=self.host;data=host.data;page=host.page
        categories={'ptset':('PTSET','definitions'),'gmset':('GMSET','definitions'),'catalog':('カタログ','cates'),'specs':('スペック','specs'),'structural':('構造材・NGMSET','definitions'),'texts':('説明・材質','texts'),'tables':('共通テーブル','tables'),'books':('カタログ本','books'),'rules':('PARAM プリセット','parameter_presets')}
        label,collection=categories.get(page,('確認・マクロ',None))
        rows=[];places=data.get('browser_placements',{})
        for f in data.get('browser_folders',[]):
            if f['page']==page:rows.append(('folder:'+f['id'],'folder:'+f['parent_id'] if f['parent_id'] else '',f['name'],None,f))
        records=list(data.get(collection,[])) if collection else []
        if page in ('ptset','gmset'):records=[r for r in records if r['kind']==page.upper()]
        elif page=='structural':records=[r for r in records if r['kind'] not in ('PTSET','GMSET')]
        elif page=='rules':records=[{'id':'legacy','name':'既存規則（従来データ）'}]+records
        def append(col,r,parent=None,kind=''):
            key=col+':'+r['id'];folder=places.get(page+'|'+key,'')
            owner=('folder:'+folder if folder else '') if parent is None else parent
            name=r.get('name',r.get('title',''))
            text=(kind+' ' if kind else '')+name
            rows.append((key,owner,text,col,r))
        for r in records:
            append(collection,r,kind='CATE' if page=='catalog' else r['kind'] if page=='structural' else '')
        if page=='catalog':
            owners={r['id'] for r in records}
            for col,kind in (('scoms','SCOM'),('texts',''),('catalog_details','DETAIL'),('catalog_props','PROP')):
                for r in data.get(col,[]):
                    owner=r.get('parent_id') if col=='texts' else r.get('cate_id')
                    if owner not in owners or col=='texts' and r['type'] not in ('SDTE','TEXT'):continue
                    parent='cates:'+owner
                    if col in ('catalog_details','catalog_props'):
                        parent='related:'+owner
                        if not any(row[0]==parent for row in rows):rows.append((parent,'cates:'+owner,'SPEC用の関連データ',None,{}))
                    append(col,r,parent,kind or r.get('type',''))
        rank={k:i for i,k in enumerate(data.get('browser_order',{}).get(page,[]))}
        rows.sort(key=lambda row:rank.get(row[0],len(rank)))
        return label,rows

    def _refresh(self):
        host=self.host;data=host.data;page=host.page
        previous=self.tree.selection();same_page=self.category==page
        if self.category!=page:
            if self.category:self.open_states[self.category]={key:bool(self.tree.item(key,'open')) for key in self.all_keys if self.tree.exists(key)}
            self.category=page;self.search.set('');previous=()
        self.configure(width=320 if page=='catalog' else 300)
        self.tree.column('#0',width=460 if page=='catalog' else 320 if page=='specs' else 240)
        label,rows=self.rows();self.all_keys=[row[0] for row in rows]
        self.items={k:(col,r) for k,_,_,col,r in rows if col}
        self.folder_nodes={k:r for k,_,_,col,r in rows if k.startswith('folder:')}
        query=self.search.get().strip().casefold();lookup={row[0]:row for row in rows}
        visible={key for key,parent,text,col,r in rows if not query or query in (text+' '+r.get('kind',r.get('type',''))+' '+label).casefold()}
        if query:
            matches=set(visible)
            for key in lookup:
                parent=lookup[key][1]
                while parent:
                    if parent in matches:visible.add(key);break
                    parent=lookup[parent][1]
            for key in list(visible):
                parent=lookup[key][1]
                while parent:visible.add(parent);parent=lookup[parent][1]
        rows=[row for row in rows if row[0] in visible]
        self.items={k:v for k,v in self.items.items() if k in visible}
        self.heading.configure(text=label+' ('+str(len(self.items))+')')
        if page in ('ptset','gmset','rules'):self.add_button.pack(side='left',before=self.folder_button,padx=(0,4))
        else:self.add_button.pack_forget()
        self.add_button.configure(text='PARAM プリセットを追加' if page=='rules' else 'アイテムを追加',width=0)
        state='normal' if page in folders.PAGES else 'disabled'
        self.folder_button.configure(state=state)
        from . import project
        cate=project.get(data,'cates',host.cate_id) if page=='catalog' else None
        for button in self.catalog_buttons.values():
            if page=='catalog':button.pack(side='left',padx=(4,0))
            else:button.pack_forget()
            button.configure(state='normal' if cate else 'disabled')
        if page in ('ptset','gmset'):self.macro_button.pack(side='left',padx=(4,0))
        else:self.macro_button.pack_forget()
        signature=(page,query,tuple((k,parent,text) for k,parent,text,_,_ in rows))
        if signature!=self.signature:
            states=dict(self.open_states.get(page,{}))
            if same_page and (not self.signature or not self.signature[1]):states.update({k:bool(self.tree.item(k,'open')) for k in self.all_keys if self.tree.exists(k)})
            if query and (not self.signature or not self.signature[1]):self.open_states[page]=dict(states)
            self.tree.delete(*self.tree.get_children())
            pending=list(rows)
            while pending:
                ready=[r for r in pending if not r[1] or self.tree.exists(r[1])]
                if not ready:break
                for key,parent,text,col,r in ready:
                    options={'image':self.folder_image} if key.startswith('folder:') else {'image':self.record_image} if col=='definitions' else {}
                    self.tree.insert(parent,'end',iid=key,text=text,open=True if query else states.get(key,True),**options)
                emitted={r[0] for r in ready}
                pending=[r for r in pending if r[0] not in emitted]
            self.signature=signature
        target=None
        if page in ('ptset','gmset','structural'):target='definitions:'+str(host.definition_id)
        elif page=='catalog':
            if getattr(host,'catalog_tab','scom')=='members' and getattr(host,'catalog_member_key',None):target=host.catalog_member_key
            else:target='scoms:'+str(host.scom_id) if host.scom_id else 'cates:'+str(host.cate_id)
            if getattr(self,'catalog_target',None)=='cates:'+str(host.cate_id):target=self.catalog_target
        elif page=='specs':target='specs:'+str(host.spec_id)
        elif page=='rules':target='parameter_presets:'+str(data.get('active_parameter_preset_id') or 'legacy')
        elif page=='books':target='books:'+str(host.selected_book)
        elif page in ('texts','tables') and hasattr(host,'companion_editor'):target=page+':'+str(host.companion_editor.selected)
        changed=target!=getattr(self,'last_record_target',None);self.last_record_target=target
        if not changed and previous and previous[0].startswith('folder:') and self.tree.exists(previous[0]):target=previous[0]
        if target and self.tree.exists(target) and self.tree.selection()!=(target,):
            self.tree.selection_set(target)
            if previous!=(target,):self.tree.see(target)

    def ready(self):
        if not self.finish_rename():return False
        if self.host.page=='rules' and not self.host.preset_editor.can_leave():return False
        return self.host.commit_definition_name() is not False

    def popup(self,event):
        key=self.tree.identify_row(event.y)
        if key:self.tree.selection_set(key);self.select()
        else:self.tree.selection_remove(*self.tree.selection())
        self.tree.focus_set()
        folder=key in self.folder_nodes
        movable=folder or key in self.items and folders.movable(self.host.page,key)
        for i,enabled in enumerate((movable,movable and self.host.page in ('ptset','gmset'),bool(self.clipboard and self.clipboard.data is self.host.data and self.clipboard.page==self.host.page),movable,folder or key in self.items and self.host.page in ('ptset','gmset'),folder or key in self.items and self.host.page in ('ptset','gmset'))):
            self.context_menu.entryconfigure(i,state='normal' if enabled else 'disabled')
        try:self.context_menu.tk_popup(event.x_root,event.y_root)
        finally:self.context_menu.grab_release()

    def copy_item(self,cut=False):
        if not self.ready():return
        selected=self.tree.selection()
        if not selected:return
        from .browser_clipboard import Clipboard
        try:self.clipboard=Clipboard(self.host.data,self.host.page,selected[0],cut=cut)
        except ValueError as exc:self.host.status.configure(text=str(exc));return
        self.host.status.configure(text='切り取りました。貼り付け先のフォルダか余白を右クリックしてください。' if cut else 'コピーしました。貼り付け先のフォルダか余白を右クリックしてください。')

    def paste_item(self):
        if not self.clipboard or not self.ready():return
        selected=self.tree.selection();key=selected[0] if selected else ''
        parent=key if key in self.folder_nodes else self.tree.parent(key) if key and self.tree.exists(key) else ''
        folder=parent.split(':',1)[1] if parent.startswith('folder:') else ''
        try:target=self.clipboard.paste(self.host.data,self.host.page,folder)
        except ValueError as exc:self.host.status.configure(text=str(exc));return
        if self.clipboard.cut:self.clipboard=None
        self.search.set('');self.signature=None
        if target.startswith('definitions:'):
            self.host.definition_id=target.split(':',1)[1];self.host.render_page()
        self.host.mark('貼り付けました。Ctrl+Sでプロジェクトを保存できます。')
        self.tree.selection_set(target);self.tree.see(target)

    def rename_at(self,event):
        key=self.tree.identify_row(event.y)
        editable=key in self.folder_nodes or self.host.page in ('ptset','gmset') and key in self.items
        if editable and self.tree.identify_element(event.x,event.y)!='Treeitem.indicator':
            self.tree.selection_set(key);self.rename_item();return 'break'

    def cancel_rename(self):
        if self.renaming:
            state=self.renaming;self.renaming=None;state['entry'].destroy()
        return 'break'

    def finish_rename(self):
        state=self.renaming
        if not state:return True
        data=state['data'];record=state['record'];name=state['variable'].get().strip()
        try:
            if self.host.data is not data or self.host.page!=state['page']:raise ValueError('プロジェクト・画面が変更されています。')
            if state['folder']:
                folders.update(data,record['id'],name=name)
            else:
                if not any(r is record for r in data['definitions']):raise ValueError('項目が削除されています。')
                if not name or any(r is not record and r['name'].casefold()==name.casefold() for r in data['definitions']):raise ValueError('名前が空か重複しています。')
                record['name']=name
        except ValueError as exc:self.host.status.configure(text=str(exc));return False
        self.cancel_rename()
        if not state['folder']:self.host.geometry_editor.refresh()
        self.host.mark('名前を変更しました。');return True

    def rename_item(self):
        if not self.finish_rename() or not self.ready():return
        selected=self.tree.selection();key=selected[0] if selected else ''
        folder=key in self.folder_nodes
        if not folder and (self.host.page not in ('ptset','gmset') or key not in self.items):return
        record=self.folder_nodes[key] if folder else self.items[key][1]
        self.tree.see(key);self.tree.update_idletasks();box=self.tree.bbox(key,'#0')
        if not box:return
        x,y,w,h=box
        variable=tk.StringVar(value=record['name']);entry=ttk.Entry(self.tree,textvariable=variable)
        entry.place(x=x+22,y=y,width=max(80,min(w-22,self.tree.winfo_width()-x-22)),height=h)
        self.renaming=dict(entry=entry,variable=variable,record=record,folder=folder,data=self.host.data,page=self.host.page)
        entry.bind('<Return>',lambda _:(self.finish_rename(),'break')[1])
        entry.bind('<Escape>',lambda _:self.cancel_rename())
        entry.bind('<FocusOut>',lambda _:self.finish_rename())
        entry.focus_set();entry.selection_range(0,'end')
        return 'break'

    def delete_item(self):
        selected=self.tree.selection();key=selected[0] if selected else ''
        if key in self.folder_nodes:self.delete_folder();return
        if self.host.page in ('ptset','gmset') and key in self.items and self.ready():self.host.delete_definition()

    def folder_form(self,mode):
        if not self.ready():return
        page=self.host.page;data=self.host.data;selected=self.tree.selection()
        key=selected[0] if selected else '';folder=self.folder_nodes.get(key)
        if mode=='rename' and not folder:return
        if mode=='move' and not folder and (key not in self.items or not folders.movable(page,key)):
            text='カタログの中身はCATEを選択してまとめて移動してください。' if page=='catalog' else '移動する登録データを選択してください。従来データの既存規則は移動できません。'
            messagebox.showinfo('フォルダで整理',text,parent=self.host);return
        options=folders.choices(data,page);fields=[]
        nearby=mode=='add' and page in ('ptset','gmset')
        if mode in ('add','rename'):fields.append(('name','フォルダ名',folder['name'] if mode=='rename' else '',None))
        if mode!='rename' and not nearby:fields.append(('parent','配置先',next((n for n,i in options.items() if i==(folder['id'] if mode=='add' and folder else '')),'（最上位）'),list(options)))
        def apply(values):
            if self.host.data is not data:raise ValueError('プロジェクトが変更されています。')
            if nearby:
                ident=folders.add(data,page,values['name'],selected=key);self.search.set('')
            elif mode=='add':ident=folders.add(data,page,values['name'],options[values['parent']])
            elif mode=='rename':folders.update(data,folder['id'],name=values['name']);ident=folder['id']
            elif folder:folders.update(data,folder['id'],parent=options[values['parent']]);ident=folder['id']
            else:folders.move(data,page,key,options[values['parent']]);ident=None
            self.signature=None
            target='folder:'+ident if ident else key
            def reveal():
                if self.host.data is data and self.tree.exists(target):self.tree.selection_set(target);self.tree.see(target)
            self.host.after_idle(reveal)
        self.host.form({'add':'フォルダを追加','rename':'フォルダ名を変更','move':'フォルダへ移動'}[mode],fields,apply)

    def add_folder(self):
        if self.host.page not in ('ptset','gmset'):return self.folder_form('add')
        if not self.ready():return
        selected=self.tree.selection();key=selected[0] if selected else ''
        names={f['name'] for f in self.host.data.get('browser_folders',[]) if f['page']==self.host.page}
        name=self.fresh_name('新しいフォルダ',names)
        try:ident=folders.add(self.host.data,self.host.page,name,selected=key)
        except ValueError as exc:self.host.status.configure(text=str(exc));return
        self.reveal_created('folder:'+ident)

    @staticmethod
    def fresh_name(base,names):
        number=1
        while f'{base}({number})' in names:number+=1
        return f'{base}({number})'

    def reveal_created(self,key):
        self.search.set('');self.signature=None;self.host.mark()
        self.tree.selection_set(key);self.tree.see(key);self.tree.focus(key)

    def rename_folder(self):self.folder_form('rename')
    def move_item(self):self.folder_form('move')
    def delete_folder(self):
        selected=self.tree.selection();folder=self.folder_nodes.get(selected[0]) if selected else None
        if not folder or not self.ready():return
        try:folders.remove(self.host.data,folder['id'])
        except ValueError as exc:messagebox.showinfo('フォルダを削除できません',str(exc),parent=self.host);return
        self.host.mark('空の整理フォルダを削除しました。')

    def add_catalog_record(self,kind):
        if self.host.page!='catalog' or not self.ready():return
        from . import project
        if not project.get(self.host.data,'cates',self.host.cate_id):return
        if kind=='SCOM':return self.host.scom_form()
        if kind in ('SDTE','TEXT'):return self.host.catalog_members.create(kind)

    def add_definition(self):
        if self.host.page=='rules':self.host.preset_editor.add();return
        if self.host.page not in ('ptset','gmset') or not self.ready():return
        from . import project,presets
        import uuid
        data=self.host.data
        if len(data['definitions'])>=project.LIMITS['definitions']:
            self.host.status.configure(text='定義数の上限です。');return
        selected=self.tree.selection();anchor=selected[0] if selected else ''
        name=self.fresh_name('新しいアイテム',{r['name'] for r in data['definitions']})
        record=dict(id=uuid.uuid4().hex,name=name,kind=self.host.page.upper(),revision='01',elements=[],parameter_preset_id=presets.selected_id(data))
        key='definitions:'+record['id']
        try:folders.place_created(data,self.host.page,key,anchor)
        except ValueError as exc:self.host.status.configure(text=str(exc));return
        data['definitions'].append(record);self.host.definition_id=record['id']
        if record['kind']=='PTSET':data['creation_draft']={'ptset_id':record['id']}
        self.host.render_page();self.reveal_created(key)

    def select(self, _=None):
        if self.host.busy:
            return
        selected = self.tree.selection()
        if not selected or selected[0] not in self.items:
            return
        collection, record = self.items[selected[0]]
        host = self.host
        if host.page=='catalog' and collection in ('cates','scoms','texts','catalog_details','catalog_props'):
            self.catalog_target=selected[0]
            if collection=='cates':
                host.cate_id=record['id'];host.scom_id=next((r['id'] for r in host.data['scoms'] if r['cate_id']==record['id']),None)
                host.catalog_tab='scom'
            elif collection=='scoms':
                host.cate_id=record['cate_id'];host.scom_id=record['id'];host.catalog_tab='scom'
            else:
                host.cate_id=record.get('parent_id') if collection=='texts' else record['cate_id']
                host.scom_id=next((r['id'] for r in host.data['scoms'] if r['cate_id']==host.cate_id),None)
                host.catalog_member_key=selected[0];host.catalog_tab='members'
            current=(host.cate_id,host.scom_id,host.catalog_tab,getattr(host,'catalog_member_key',None))
            if getattr(self,'catalog_context',None)==current:return
            self.catalog_context=current;host.switch('catalog');return
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
            host.catalog_tab='scom'
        elif collection=='specs':
            page = 'specs'
            if host.page == page and host.spec_id == record['id']:
                return
            host.spec_id = record['id']
        elif collection=='parameter_presets':
            ident='' if record['id']=='legacy' else record['id']
            if host.data.get('active_parameter_preset_id','')==ident:return
            host.preset_editor.select_preset(ident);return
        elif collection=='books':
            host.selected_book=record['id'];host.books_table.selection_set(record['id']);host.update_book_info();return
        elif collection in ('texts','tables'):
            host.companion_editor.table.selection_set(record['id']);host.companion_editor.select();return
        else:return
        host.switch(page)
