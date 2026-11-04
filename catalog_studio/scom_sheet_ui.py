"""Editable SCOM table with staged row additions and Excel imports."""
import copy
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,font
from . import project,presets,scom_sheet as model

class ScomSheet(tk.Toplevel):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.data=host.data;self.snapshot=copy.deepcopy(host.data);self.cate_id=host.cate_id;self.seed_id=host.scom_id
        self.seed=project.get(host.data,'scoms',self.seed_id);self.editing=None
        self.preset_id=presets.selected_id(host.data,self.seed);self.working,self.labels=model.text_columns(host.data,self.cate_id,self.preset_id)
        self.title('SCOM表登録');self.geometry(str(min(1440,self.winfo_screenwidth()-80))+'x'+str(min(820,self.winfo_screenheight()-100)));self.minsize(1000,600);self.transient(host);self.grab_set()
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
        self.header=tk.Canvas(area,height=48,highlightthickness=0,background='#f5f8fc')
        self.header.grid(row=0,column=0,sticky='ew');self.header.bind('<Configure>',lambda _:self.draw_headers())
        self.tree=ttk.Treeview(area,columns=self.columns,show='',selectmode='browse')
        self.configure_headers()
        self.header_hint=HeaderHint(self)
        self.tree.grid(row=1,column=0,sticky='nsew')
        v=ttk.Scrollbar(area,command=lambda *args:(self.finish(),self.tree.yview(*args)));v.grid(row=1,column=1,sticky='ns')
        h=ttk.Scrollbar(area,orient='horizontal',command=lambda *args:(self.finish(),self.tree.xview(*args),self.draw_headers()));h.grid(row=2,column=0,sticky='ew')
        self.horizontal=h
        self.tree.configure(yscrollcommand=lambda a,b:(v.set(a,b),self.schedule_rules()),xscrollcommand=self.sync_header);area.rowconfigure(1,weight=1);area.columnconfigure(0,weight=1)
        self.tree.bind('<Double-1>',self.edit)
        self.tree.bind('<Configure>',lambda _:self.finish())
        for event in ('<MouseWheel>','<Button-4>','<Button-5>'):self.tree.bind(event,lambda _:self.finish(),add='+')
        self.error=ttk.Label(self,text='',foreground='#bb4949',padding=12);self.error.pack(fill='x')
        footer=ttk.Frame(self,padding=12);footer.pack(fill='x')
        self.save_button=ttk.Button(footer,text='表を登録',style='Primary.TButton',command=self.save);self.save_button.pack(side='right')
        ttk.Button(footer,text='取消',command=self.destroy).pack(side='right',padx=8)
        self.rules=SheetRules(self)
        self.refresh()
    def schedule_rules(self):
        if hasattr(self,'rules'):self.rules.schedule()

    def configure_headers(self):
        self.header_font=font.Font(self,family=self.host.ui_font,size=9,weight='bold')
        for col in self.columns:
            if col=='NAME':title='名前';width=170
            else:
                label=' '.join(self.labels[col].split());width=108;short=label
                while short and self.header_font.measure(short+('…' if short!=label else ''))>width-18:short=short[:-1]
                title='PA'+col[1:]+'\n'+short+('…' if short!=label else '')
            self.tree.heading(col,text=title);self.tree.column(col,width=width,minwidth=90,stretch=False)
        if hasattr(self,'header_hint'):self.header_hint.hide()
        self.draw_headers()

    def sync_header(self,first,last):
        self.horizontal.set(first,last);self.draw_headers();self.schedule_rules()

    def header_cells(self):
        widths=[int(self.tree.column(c,'width')) for c in self.columns]
        x=-self.tree.xview()[0]*sum(widths)
        for col,width in zip(self.columns,widths):
            yield col,x,width
            x+=width

    def draw_headers(self):
        if not hasattr(self,'header') or not hasattr(self,'tree'):return
        self.header.delete('all')
        for col,x,width in self.header_cells():
            title=self.tree.heading(col,'text');lines=title.split('\n',1)
            self.header.create_rectangle(x,0,x+width,48,fill='#f5f8fc',outline='#d3ddec')
            self.header.create_text(x+width/2,13 if len(lines)>1 else 24,text=lines[0],font=(self.host.ui_font,9,'bold'),fill='#40556d')
            if len(lines)>1:self.header.create_text(x+width/2,34,text=lines[1],font=(self.host.ui_font,9),fill='#637993')

    def choose_preset(self,_=None):
        self.finish();ident=self.preset_options.get(self.preset_choice.get(),self.preset_id)
        create=messagebox.askyesno('TEXT作成確認','選択したPARAMプリセットに対応するTEXTをCATE内に作成しますか？\n既存の対応TEXTはそのまま使用します。\n表の登録時にまとめて確定します。',parent=self)
        try:working,labels=model.text_columns(self.working,self.cate_id,ident,create)
        except ValueError as exc:
            self.error.configure(text=str(exc));self.preset_choice.set(next(n for n,i in self.preset_options.items() if i==self.preset_id));return
        self.working=working;self.labels=labels;self.preset_id=ident;self.columns=list(labels)
        self.tree.configure(columns=self.columns)
        self.configure_headers()
        self.error.configure(text='TEXTとSCOMの変更は「表を登録」で確定します。');self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i,row in enumerate(self.rows):self.tree.insert('','end',iid=str(i),values=[row.get(c,'') for c in self.columns])
        self.schedule_rules()
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


class HeaderHint:
    def __init__(self,editor):
        self.editor=editor;self.tree=editor.tree;self.key=None;self.pending=None;self.window=None
        self.editor.header.bind('<Motion>',self.motion,add='+')
        for event in ('<Leave>','<ButtonPress>','<Destroy>','<MouseWheel>'):
            self.tree.bind(event,lambda _:self.hide(),add='+')
            self.editor.header.bind(event,lambda _:self.hide(),add='+')
    def motion(self,event):
        key=next((col for col,x,width in self.editor.header_cells() if x<=event.x<x+width),None)
        if key is None:self.hide();return
        if key==self.key:return
        self.hide();self.key=key;self.position=(event.x_root+12,event.y_root+20)
        self.pending=self.tree.after(450,self.show)
    def show(self):
        self.pending=None
        if not self.key or not self.tree.winfo_exists():return
        label=self.editor.labels[self.key]
        self.window=tk.Toplevel(self.tree);self.window.overrideredirect(True)
        text=label if self.key=='NAME' else 'PA'+self.key[1:]+'\n'+label
        ttk.Label(self.window,text=text,wraplength=480,justify='left',padding=8,relief='solid',borderwidth=1).pack()
        self.window.update_idletasks();x,y=self.position
        x=max(0,min(x,self.tree.winfo_screenwidth()-self.window.winfo_reqwidth()-8))
        y=max(0,min(y,self.tree.winfo_screenheight()-self.window.winfo_reqheight()-8))
        self.window.geometry('+'+str(x)+'+'+str(y))
    def hide(self):
        if self.pending is not None:
            self.tree.after_cancel(self.pending);self.pending=None
        if self.window is not None:
            self.window.destroy();self.window=None
        self.key=None


class SheetRules:
    """One-pixel grid overlays, aligned with native cell geometry and scrolling."""
    def __init__(self,editor):
        self.editor=editor;self.tree=editor.tree;self.lines=[];self.pending=None
        self.tree.bind('<Configure>',lambda _:self.schedule(),add='+')
        self.tree.bind('<Destroy>',self.close,add='+')
    def schedule(self):
        if self.pending is None:self.pending=self.tree.after_idle(self.draw)
    def close(self,event):
        if event.widget is self.tree and self.pending is not None:
            self.tree.after_cancel(self.pending);self.pending=None
    def draw(self):
        self.pending=None
        if not self.tree.winfo_exists():return
        for line in self.lines:line.destroy()
        self.lines=[];w=self.tree.winfo_width();h=self.tree.winfo_height()
        def line(x,y,width,height):
            item=tk.Frame(self.tree,background='#c7d4e5',borderwidth=0,takefocus=False)
            item.place(x=x,y=y,width=width,height=height);self.lines.append(item)
            item.bind('<Button-1>',lambda e:self.tree.event_generate('<Button-1>',x=e.x+e.widget.winfo_x(),y=e.y+e.widget.winfo_y()))
            from types import SimpleNamespace
            item.bind('<Double-1>',lambda e:self.editor.edit(SimpleNamespace(x=e.x+e.widget.winfo_x(),y=e.y+e.widget.winfo_y())))
            item.bind('<MouseWheel>',lambda e:self.tree.event_generate('<MouseWheel>',delta=e.delta))
            for sequence in ('<Button-4>','<Button-5>'):item.bind(sequence,lambda e,s=sequence:self.tree.event_generate(s))
        for col,x,width in self.editor.header_cells():
            for edge in (round(x),round(x+width)):
                if 0<=edge<w:line(edge,0,1,h)
        first=self.tree.identify_row(1);box=self.tree.bbox(first) if first else ()
        height=box[3] if box else int(ttk.Style(self.tree).lookup('Treeview','rowheight') or 30)
        offset=box[1]%height if box else 0
        for y in range(offset,h,max(1,height)):line(0,y,w,1)
        if self.editor.editing:self.editor.editing[0].lift()
