"""Editable SCOM table with staged row additions and Excel imports."""
import copy
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import project,presets,scom_sheet as model

class ScomSheet(tk.Toplevel):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.data=host.data;self.snapshot=copy.deepcopy(host.data);self.cate_id=host.cate_id;self.seed_id=host.scom_id
        self.seed=project.get(host.data,'scoms',self.seed_id);self.editing=None
        self.preset_id=presets.selected_id(host.data,self.seed);self.working,self.labels=model.text_columns(host.data,self.cate_id,self.preset_id)
        self.title('SCOM表登録');self.geometry('1100x650');self.transient(host);self.grab_set()
        self.columns=list(self.labels)
        self.rows=[model.row(host.data,s) for s in host.data['scoms'] if s['cate_id']==self.cate_id]
        bar=ttk.Frame(self,padding=12);bar.pack(fill='x')
        ttk.Label(bar,text='PARAMプリセット').pack(side='left')
        self.preset_options=presets.choices(host.data)
        self.preset_choice=ttk.Combobox(bar,values=list(self.preset_options),state='readonly',width=28)
        self.preset_choice.set(next((n for n,i in self.preset_options.items() if i==self.preset_id),''));self.preset_choice.pack(side='left',padx=8)
        self.preset_choice.bind('<<ComboboxSelected>>',self.choose_preset)
        self.add_button=ttk.Button(bar,text='＋ 行追加',style='AttributeTool.TButton',command=self.add);self.add_button.pack(side='left',padx=3)
        self.excel_button=ttk.Button(bar,text='▦ Excel読込',style='AttributeTool.TButton',command=self.load_excel);self.excel_button.pack(side='left',padx=3)
        ttk.Label(self,text='セルをダブルクリックして編集。新しい行は選択中SCOMの参照・PARAMを引き継ぎます。列見出しはTEXTのSTEXTです。Excelには名前とSTEXT、またはP1等のPARAM番号を指定できます。',padding=(12,0),wraplength=1040).pack(anchor='w')
        area=ttk.Frame(self,padding=12);area.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(area,columns=self.columns,show='headings',selectmode='browse')
        for col in self.columns:self.tree.heading(col,text=self.labels[col]);self.tree.column(col,width=210,minwidth=90)
        self.tree.grid(row=0,column=0,sticky='nsew')
        v=ttk.Scrollbar(area,command=lambda *args:(self.finish(),self.tree.yview(*args)));v.grid(row=0,column=1,sticky='ns')
        h=ttk.Scrollbar(area,orient='horizontal',command=lambda *args:(self.finish(),self.tree.xview(*args)));h.grid(row=1,column=0,sticky='ew')
        self.tree.configure(yscrollcommand=v.set,xscrollcommand=h.set);area.rowconfigure(0,weight=1);area.columnconfigure(0,weight=1)
        self.tree.bind('<Double-1>',self.edit)
        self.tree.bind('<Configure>',lambda _:self.finish())
        for event in ('<MouseWheel>','<Button-4>','<Button-5>'):self.tree.bind(event,lambda _:self.finish(),add='+')
        self.error=ttk.Label(self,text='',foreground='#bb4949',padding=12);self.error.pack(fill='x')
        footer=ttk.Frame(self,padding=12);footer.pack(fill='x')
        self.save_button=ttk.Button(footer,text='表を登録',style='Primary.TButton',command=self.save);self.save_button.pack(side='right')
        ttk.Button(footer,text='取消',command=self.destroy).pack(side='right',padx=8)
        self.refresh()
    def choose_preset(self,_=None):
        self.finish();ident=self.preset_options.get(self.preset_choice.get(),self.preset_id)
        create=messagebox.askyesno('TEXT作成確認','選択したPARAMプリセットに対応するTEXTをCATE内に作成しますか？\n既存の対応TEXTはそのまま使用します。\n表の登録時にまとめて確定します。',parent=self)
        try:working,labels=model.text_columns(self.working,self.cate_id,ident,create)
        except ValueError as exc:
            self.error.configure(text=str(exc));self.preset_choice.set(next(n for n,i in self.preset_options.items() if i==self.preset_id));return
        self.working=working;self.labels=labels;self.preset_id=ident;self.columns=list(labels)
        self.tree.configure(columns=self.columns)
        for col in self.columns:self.tree.heading(col,text=labels[col]);self.tree.column(col,width=210,minwidth=90)
        self.error.configure(text='TEXTとSCOMの変更は「表を登録」で確定します。');self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i,row in enumerate(self.rows):self.tree.insert('','end',iid=str(i),values=[row.get(c,'') for c in self.columns])
    def template(self):
        row=model.row(self.data,self.seed) if self.seed else {c:'' for c in self.columns}
        row.pop('id',None);return row
    def add(self):
        self.finish();row=self.template();i=1;names={r['NAME'].casefold() for r in self.rows}|{s['name'].casefold() for s in self.data['scoms']}
        while '/NEW-SCOM-'+str(i) in {n.upper() for n in names}:i+=1
        row['NAME']='/NEW-SCOM-'+str(i);self.rows.append(row);self.refresh();self.tree.selection_set(str(len(self.rows)-1));self.tree.see(str(len(self.rows)-1))
    def edit(self,event):
        self.finish();iid=self.tree.identify_row(event.y);col=self.tree.identify_column(event.x)
        if not iid or not col:return
        key=self.columns[int(col[1:])-1];box=self.tree.bbox(iid,col)
        if not box:return
        var=tk.StringVar(value=str(self.rows[int(iid)].get(key,'')));entry=ttk.Entry(self.tree,textvariable=var)
        entry.place(x=box[0],y=box[1],width=box[2],height=box[3]);entry.focus_set();entry.selection_range(0,'end')
        self.editing=(entry,var,int(iid),key)
        entry.bind('<Return>',lambda _:self.finish());entry.bind('<FocusOut>',lambda _:self.finish());entry.bind('<Escape>',lambda _:self.cancel_edit())
    def cancel_edit(self):
        if self.editing:entry=self.editing[0];self.editing=None;entry.destroy()
    def finish(self):
        if self.editing:
            entry,var,i,key=self.editing;self.rows[i][key]=var.get();self.cancel_edit();self.tree.item(str(i),values=[self.rows[i].get(c,'') for c in self.columns])
    def stage_excel(self,rows):
        staged=copy.deepcopy(self.rows);seen=set()
        for raw in rows:
            name=str(raw.get('NAME','')).strip();name=name if name.startswith('/') else '/'+name
            if name.casefold() in seen:raise ValueError('ExcelのSCOM名が重複しています。')
            seen.add(name.casefold())
            target=next((r for r in staged if r.get('NAME','').casefold()==name.casefold()),None)
            if target is None:target=self.template();staged.append(target)
            target.update(raw);target['NAME']=name
        model.apply(self.working,self.cate_id,staged,self.seed_id,self.preset_id)
        self.rows=staged;self.refresh()
    def load_excel(self):
        self.finish();path=filedialog.askopenfilename(parent=self,filetypes=[('Excel','*.xlsx *.xlsm')])
        if not path:return
        try:
            sheets=model.sheet_names(path)
            rows=model.read_excel(path,aliases={v:k for k,v in self.labels.items()})[0] if len(sheets)==1 else None
        except (ValueError,OSError,ImportError,KeyError) as exc:self.error.configure(text=str(exc));return
        if len(sheets)==1:
            try:self.stage_excel(rows);self.error.configure(text='Excelを表へ読み込みました。「表を登録」で確定します。')
            except ValueError as exc:self.error.configure(text=str(exc))
            return
        win=tk.Toplevel(self);win.title('Excelシートを選択');win.transient(self);win.grab_set()
        choice=ttk.Combobox(win,values=sheets,state='readonly');choice.pack(padx=16,pady=16);choice.current(0)
        def apply():
            try:rows,_=model.read_excel(path,choice.get(),aliases={v:k for k,v in self.labels.items()});self.stage_excel(rows)
            except (ValueError,OSError,KeyError) as exc:self.error.configure(text=str(exc));return
            win.destroy();self.grab_set()
        ttk.Button(win,text='読込',command=apply).pack(pady=12)
        win.protocol('WM_DELETE_WINDOW',lambda:(win.destroy(),self.grab_set()))
    def save(self):
        self.finish()
        try:
            if self.host.data is not self.data or self.host.data!=self.snapshot:raise ValueError('プロジェクトが変更されています。表を開き直してください。')
            candidate,ids=model.apply(self.working,self.cate_id,self.rows,self.seed_id,self.preset_id)
        except ValueError as exc:self.error.configure(text=str(exc));return
        self.host.data=candidate;self.host.scom_id=ids[0] if ids else None;self.host.catalog_tab='scom';self.destroy();self.host.mark('SCOM表を登録しました。');self.host.render_page()

def open_sheet(host):
    if host.commit_definition_name() is False:return
    if not project.get(host.data,'cates',host.cate_id):host.status.configure(text='CATEを選択してください。');return
    return ScomSheet(host)
