"""Edit PARAM preset contents independently of catalogue creation."""
import copy
import re
import tkinter as tk
from tkinter import messagebox, ttk
from . import presets, project, theme, parameter_catalog as catalog


class PresetEditor(ttk.Frame):
    def __init__(self,host):
        super().__init__(host.content);self.host=host;self.loading=True;self.cell=None
        host.heading('PARAM プリセット','番号・意味・STEXT（意味の英語名）を編集します。')
        self.pack(fill='both',expand=True)
        self.list=host.registered_browser.tree
        style=ttk.Style(self)
        if not hasattr(host,'parameter_grid_image'):
            host.parameter_grid_image=tk.PhotoImage(master=host,width=2,height=2)
            host.parameter_grid_image.put(theme.RULE,to=(0,1,2,2));host.parameter_grid_image.put(theme.RULE,to=(1,0,2,2))
            style.element_create('ParameterCellRule','image',host.parameter_grid_image,border=(0,0,1,1),sticky='nswe')
            style.layout('Parameter.Treeview.Cell',[('ParameterCellRule',{'sticky':'nswe','children':[('Treeitem.padding',{'sticky':'nswe','children':[('Treeitem.text',{'sticky':'nswe'})]})]})])
        toolbar=ttk.Frame(self);toolbar.pack(fill='x',pady=(0,8))
        ttk.Label(toolbar,text='プリセット名').pack(side='left',padx=(0,8))
        self.name_var=tk.StringVar();self.name_entry=ttk.Entry(toolbar,textvariable=self.name_var,width=24);self.name_entry.pack(side='left',fill='x',expand=True)
        self.state_label=ttk.Label(toolbar,text='',style='Muted.TLabel');self.state_label.pack(side='left',padx=8)
        self.save_button=ttk.Button(toolbar,text='プリセットを保存',command=self.save,style='Primary.TButton');self.save_button.pack(side='right')
        ttk.Button(toolbar,text='複製',command=self.duplicate,style='Compact.TButton').pack(side='right',padx=6)
        ttk.Button(toolbar,text='適用範囲',command=self.toggle_details,style='Compact.TButton').pack(side='right')
        self.details=ttk.Frame(self);self.metadata={'name':self.name_var};self.metadata_widgets={'name':self.name_entry}
        for key,label in (('period','登録時期'),('component','コンポーネント'),('description','補足')):
            row=ttk.Frame(self.details);row.pack(fill='x',pady=2);ttk.Label(row,text=label,width=18).pack(side='left')
            var=tk.StringVar();self.metadata[key]=var;entry=ttk.Entry(row,textvariable=var);entry.pack(side='left',fill='x',expand=True);self.metadata_widgets[key]=entry
        self.body=ttk.Frame(self);self.body.pack(fill='both',expand=True)
        tools=ttk.Frame(self.body);tools.pack(fill='x',pady=(0,5))
        ttk.Label(tools,text='PARAM 一覧',style='Heading.TLabel').pack(side='left')
        self.add_row_button=ttk.Button(tools,text='＋ 行追加',command=self.add_row,style='Compact.Primary.TButton');self.add_row_button.pack(side='right')
        self.add_row_button.configure(width=8)
        self.message=ttk.Label(self.body,text='',foreground='#a15b38',wraplength=650)
        self.message.pack(side='bottom',fill='x',pady=(7,0))
        self.message.bind('<Configure>',lambda e:self.message.configure(wraplength=max(120,e.width-8)))
        self.table=host.table(self.body,[('number','番号',60),('meaning','意味',240),('english','STEXT',300),('description','補足',1)],height=8)
        self.table.configure(displaycolumns=('number','meaning','english'),style='Parameter.Treeview')
        for key,width in (('number',60),('meaning',240),('english',300)):
            self.table.column(key,width=width,minwidth=60 if key=='number' else 120,stretch=False)
        self.table.tag_configure('missing',foreground='#a15b38')
        self.table.bind('<Double-1>',self.edit_at);self.table.bind('<Return>',lambda _:self.begin_cell(self.selected_id(),'meaning'))
        self.table.bind('<Button-3>',self.context)
        self.menu=tk.Menu(self,tearoff=False)
        for label,fn in (('行を複製',self.duplicate_row),('行を削除',self.remove_parameter),('詳細設定（補足・単位・値型）',self.edit_parameter)):
            self.menu.add_command(label=label,command=fn)
        self.menu.add_separator();self.menu.add_command(label='参照種類別の役割',command=self.reference_roles)
        self.menu.add_command(label='プリセットを削除',command=self.delete)
        for var in self.metadata.values():var.trace_add('write',self.metadata_changed)
        self.load(presets.selected_id(host.data))

    def record(self):return presets.get(self.host.data,self.ident)
    def parameters(self):return self.draft['parameters']
    def selected_id(self):return next(iter(self.table.selection()),None)
    def load(self,ident):
        self.loading=True;self.ident=ident
        record=presets.get(self.host.data,ident)
        self.draft=copy.deepcopy(record if record else {'id':'','name':'既存規則（従来データ）','period':'','component':'','description':'','parameters':self.host.data['parameters'],'reference_roles':self.host.data.get('reference_roles',{})})
        self.baseline=copy.deepcopy(self.draft)
        for key,var in self.metadata.items():var.set(self.draft.get(key,''))
        for entry in self.metadata_widgets.values():entry.configure(state='normal' if record else 'readonly')
        self.loading=False;self.refresh_rows();self.changed()

    def metadata_changed(self,*_):
        if self.loading:return
        for key,var in self.metadata.items():self.draft[key]=var.get()
        self.changed()

    def has_changes(self):return self.draft!=self.baseline or bool(self.cell and self.cell['var'].get()!=self.cell['original'])
    def changed(self):
        self.state_label.configure(text='未保存の編集' if self.has_changes() else '保存済み')
        self.message.configure(text='')

    def refresh_rows(self):
        selected=self.selected_id();self.table.delete(*self.table.get_children())
        for p in catalog.ordered(self.parameters()):
            self.table.insert('','end',iid=p['id'],values=(int(p['id'][1:]),presets.meaning(p),p.get('english_name',''),p.get('description','')),tags=('missing',) if not p.get('english_name','').strip() else ())
        if selected and self.table.exists(selected):self.table.selection_set(selected)

    def edit_at(self,event):
        pid=self.table.identify_row(event.y);column=self.table.identify_column(event.x)
        key={'#1':'number','#2':'meaning','#3':'english_name'}.get(column)
        if pid and key:self.begin_cell(pid,key)
        return 'break'

    def begin_cell(self,pid,key):
        if not pid or not self.finish_cell():return
        column={'number':'number','meaning':'meaning','english_name':'english'}.get(key)
        if not column:return
        self.table.selection_set(pid);self.table.see(pid);self.update_idletasks()
        bbox=self.table.bbox(pid,column)
        if not bbox:return
        p=next(p for p in self.parameters() if p['id']==pid)
        value=str(int(pid[1:])) if key=='number' else (presets.meaning(p) if key=='meaning' else p.get(key,''))
        var=tk.StringVar(value=value);entry=ttk.Entry(self.table,textvariable=var)
        self.cell={'pid':pid,'key':key,'var':var,'entry':entry,'original':value}
        x,y,w,h=bbox;entry.place(x=x,y=y,width=w,height=h);entry.focus_set();entry.selection_range(0,'end')
        entry.bind('<Return>',lambda _:self.finish_cell());entry.bind('<Escape>',lambda _:self.cancel_cell())
        entry.bind('<Tab>',lambda _:self.next_cell());entry.bind('<FocusOut>',lambda _:self.finish_cell())
        var.trace_add('write',lambda *_:self.state_label.configure(text='未保存の編集'))

    def next_cell(self):
        if not self.cell:return 'break'
        pid,key=self.cell['pid'],self.cell['key']
        if self.finish_cell():self.begin_cell(pid,'english_name' if key=='meaning' else 'meaning')
        return 'break'

    def edit_value(self,pid,key,value):
        p=next(p for p in self.parameters() if p['id']==pid);value=str(value).strip()
        if key=='number':
            raw=value[1:] if value.upper().startswith('P') else value
            if not re.fullmatch(r'[1-9]\d{0,5}',raw):raise ValueError('番号は1〜999999の整数です。')
            new='P'+raw
            if new!=pid:
                if any(q['id']==new for q in self.parameters()):raise ValueError('PARAM 番号が重複しています。')
                if catalog.in_use(self.host.data,self.ident,pid):raise ValueError(pid+' は使用中のため再採番できません。')
                p['id']=new
                if not any(q['id']==new for q in self.baseline['parameters']):p['role']=self.new_alias(new)
        else:
            if key not in ('meaning','english_name','description','unit','value_type'):raise ValueError('編集できない項目です。')
            if len(value)>2000 or '\x00' in value:raise ValueError('2000文字以内で入力してください。')
            if key=='english_name' and ('\n' in value or '\r' in value):raise ValueError('英語名は1行で入力してください。')
            if (presets.meaning(p) if key=='meaning' else p.get(key,''))==value:return
            p[key]=value
        self.refresh_rows();self.changed()

    def finish_cell(self):
        cell=self.cell
        if not cell:return True
        try:self.edit_value(cell['pid'],cell['key'],cell['var'].get())
        except ValueError as exc:self.message.configure(text=str(exc));cell['entry'].focus_set();return False
        self.cell=None;cell['entry'].destroy();self.changed();return True

    def cancel_cell(self):
        if self.cell:cell=self.cell;self.cell=None;cell['entry'].destroy();self.changed()

    def new_alias(self,pid):
        alias='PARAM_'+pid[1:]
        while any(p['role']==alias for p in self.parameters()):alias+='N'
        return alias

    def add_row(self):
        if not self.finish_cell():return
        if len(self.parameters())>=100:self.message.configure(text='PARAM は最大100件です。');return
        pid='P'+str(max((int(p['id'][1:]) for p in self.parameters()),default=0)+1)
        self.parameters().append({'id':pid,'role':self.new_alias(pid),'meaning':'','english_name':'','unit':'mm','value_type':'number'})
        self.refresh_rows();self.changed();self.begin_cell(pid,'meaning')

    def context(self,event):
        if not self.finish_cell():return
        pid=self.table.identify_row(event.y)
        if pid:self.table.selection_set(pid)
        self.menu.post(event.x_root,event.y_root)

    def duplicate_row(self):
        if not self.finish_cell() or not self.selected_id():return
        original=copy.deepcopy(next(p for p in self.parameters() if p['id']==self.selected_id()))
        if len(self.parameters())>=100:self.message.configure(text='PARAM は最大100件です。');return
        pid='P'+str(max(int(p['id'][1:]) for p in self.parameters())+1)
        original.update(id=pid,role=self.new_alias(pid));self.parameters().append(original)
        self.refresh_rows();self.table.selection_set(pid);self.changed()

    def remove_parameter(self):
        if not self.finish_cell():return
        pid=self.selected_id()
        if not pid:return
        if catalog.in_use(self.host.data,self.ident,pid):self.message.configure(text=pid+' は式・SCOM・要素プリセットで使用中です。');return
        self.draft['parameters']=[p for p in self.parameters() if p['id']!=pid];self.refresh_rows();self.changed()

    def save(self):
        if not self.finish_cell():return False
        original=self.record()
        live=original if original is not None else dict(self.baseline,parameters=self.host.data['parameters'],reference_roles=self.host.data.get('reference_roles',{}))
        if live!=self.baseline:self.message.configure(text='保存先の規則が変更されています。再読込して編集してください。');return False
        try:catalog.save_preset(self.host.data,self.ident,self.draft)
        except ValueError as exc:self.message.configure(text=str(exc));return False
        self.load(self.ident);self.host.mark('PARAM プリセットを保存しました。');return True

    def can_leave(self):
        if not self.finish_cell():return False
        if not self.has_changes():return True
        answer=messagebox.askyesnocancel('プリセットの未保存編集','プリセットの編集を保存しますか？',parent=self.host)
        if answer is None:return False
        if answer:return self.save()
        self.load(self.ident);return True

    def select_preset(self,ident):
        if ident==self.ident:return
        if not self.can_leave():self.host.registered_browser.refresh();return
        self.host.data['active_parameter_preset_id']=ident;self.load(ident);self.host.mark()

    def select(self,_=None):
        selected=self.list.selection()
        if selected:self.select_preset('' if selected[0].endswith(':legacy') else selected[0].split(':',1)[1])

    def toggle_details(self):
        if self.details.winfo_manager():self.details.pack_forget()
        else:self.details.pack(fill='x',before=self.body,pady=(0,8))

    def create(self,duplicate=False):
        if not self.can_leave():return
        win=tk.Toplevel(self.host);win.title('プリセットを複製' if duplicate else '新しい PARAM プリセット');win.geometry('440x200');win.transient(self.host);win.grab_set()
        body=ttk.Frame(win,padding=16);body.pack(fill='both',expand=True)
        ttk.Label(body,text='プリセット名').pack(anchor='w')
        var=tk.StringVar(value=self.draft['name']+' の複製' if duplicate else '新規プリセット');entry=ttk.Entry(body,textvariable=var);entry.pack(fill='x',pady=8);entry.focus_set();entry.selection_range(0,'end')
        error=ttk.Label(body,text='',foreground='#a15b38');error.pack(fill='x')
        def apply():
            try:record=presets.add(self.host.data,var.get().strip(),self.ident,empty=not duplicate)
            except ValueError as exc:error.configure(text=str(exc));return
            self.host.data['active_parameter_preset_id']=record['id'];self.load(record['id']);self.host.mark();win.destroy()
        row=ttk.Frame(body);row.pack(side='bottom',fill='x');ttk.Button(row,text='作成',command=apply,style='Primary.TButton').pack(side='right');ttk.Button(row,text='キャンセル',command=win.destroy).pack(side='right',padx=6)
        win.submit=apply;win.name_var=var;entry.bind('<Return>',lambda _:apply());return win

    def add(self):return self.create()
    def duplicate(self):return self.create(True)
    def edit(self):self.toggle_details()
    def edit_parameter(self):
        pid=self.selected_id()
        if pid:self.parameter_form(next(p for p in self.parameters() if p['id']==pid))
    def parameter_form(self,param=None):
        if param is None:self.add_row();return
        if not self.finish_cell():return
        param=next(p for p in self.parameters() if p['id']==param['id'])
        win=tk.Toplevel(self.host);win.title(param['id']+' の詳細設定');win.geometry('440x430');win.transient(self.host);win.grab_set()
        body=ttk.Frame(win,padding=16);body.pack(fill='both',expand=True);variables={}
        for key,label in (('description','補足説明'),('unit','単位'),('value_type','値型')):
            ttk.Label(body,text=label).pack(anchor='w',pady=(5,3));var=tk.StringVar(value=param.get(key,'number' if key=='value_type' else ''));variables[key]=var
            widget=ttk.Combobox(body,textvariable=var,values=('number','word'),state='readonly') if key=='value_type' else ttk.Entry(body,textvariable=var)
            widget.pack(fill='x')
        def apply():
            param.update({k:v.get().strip() for k,v in variables.items()});self.refresh_rows();self.changed();win.destroy()
        ttk.Label(body,text='式用の既存別名は保持します：'+param['role'],style='Muted.TLabel',wraplength=390).pack(fill='x',pady=12)
        ttk.Button(body,text='編集を反映',command=apply).pack(side='bottom',fill='x');return win

    def delete(self):
        record=self.record()
        if not record or not self.can_leave():return
        try:
            if presets.users(self.host.data,self.ident):raise ValueError('SCOM または定義で使用中です。')
            if not messagebox.askyesno('削除',record['name']+' を削除しますか？',parent=self.host):return
            presets.remove(self.host.data,self.ident)
        except ValueError as exc:self.message.configure(text=str(exc));return
        self.load('');self.host.mark()

    def reference_roles(self):
        if not self.can_leave():return
        from .companion_ui import json_dialog
        owner=self.record() if self.record() is not None else self.host.data
        def apply(value):project.validate_reference_roles(value);owner['reference_roles']=value
        json_dialog(self.host,'このプリセットの参照種類別の役割',owner.get('reference_roles',{}),apply)
