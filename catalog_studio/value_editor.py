"""Compact transactional attribute editor with preset-aware expression helpers."""
import re
import tkinter as tk
from tkinter import ttk
from . import element_schema as schema, expressions, presets, theme

LITERALS={'NUMB','DESC','PURP','PSKEY','GTYP','SKEY','PKEY','LEVEL','OBST','NAPP','CLFLA','TUFLA','TVISI','BVISI'}


class ValueEditor(tk.Toplevel):
    def __init__(self,editor,table,key,context):
        super().__init__(editor.winfo_toplevel())
        self.withdraw();self.editor=editor;self.table=table;self.key=key;self.context=context
        self.previous_grab=self.grab_current();self.title(key+' を編集');self.transient(editor.winfo_toplevel())
        self.resizable(True,False);self.configure(bg=theme.SURFACE)
        self.data=editor.data;self.definition=editor.definition();self.element=editor.element()
        self.variable=tk.StringVar(value=context['value']);self.family=tk.StringVar(value='PARAM');self.number=tk.StringVar()
        self.uses_parameters=key not in LITERALS;self.role_options={}
        body=ttk.Frame(self,padding=14);body.pack(fill='both',expand=True);body.columnconfigure(0,weight=1)
        header=ttk.Frame(body);header.grid(row=0,column=0,sticky='ew')
        ttk.Label(header,text=key,style='Heading.TLabel').pack(side='left')
        ttk.Label(header,text=schema.meaning(self.element['type'],key),style='Muted.TLabel').pack(side='left',padx=10)
        ttk.Label(body,text=self.element['name'],style='Muted.TLabel',wraplength=410).grid(row=1,column=0,sticky='w',pady=(3,8))
        choices=context.get('choices',())
        self.entry=ttk.Combobox(body,textvariable=self.variable,values=choices,state='normal',exportselection=False,font=(editor.host.ui_font,12)) if choices else ttk.Entry(body,textvariable=self.variable,exportselection=False,font=(editor.host.ui_font,12))
        self.entry.grid(row=2,column=0,sticky='ew')
        self.caption=ttk.Label(body,text='',style='AttributeMeaning.TLabel',wraplength=410)
        self.caption.grid(row=3,column=0,sticky='w',pady=(4,8))
        if self.uses_parameters:
            references=ttk.LabelFrame(body,text='PARAM を挿入',padding=8);references.grid(row=4,column=0,sticky='ew');references.columnconfigure(1,weight=1)
            self.family_choice=ttk.Combobox(references,textvariable=self.family,values=schema.REFERENCE_TYPES,state='readonly',width=13)
            self.family_choice.grid(row=0,column=0,sticky='ew',padx=(0,6))
            self.number_choice=ttk.Combobox(references,textvariable=self.number,width=18)
            self.number_choice.grid(row=0,column=1,sticky='ew')
            self.insert_button=ttk.Button(references,text='挿入',width=5,command=self.insert_reference,style='Compact.TButton')
            self.insert_button.grid(row=0,column=2,padx=(6,0))
            self.role_label=ttk.Label(references,text='',style='AttributeMeaning.TLabel',wraplength=390)
            self.role_label.grid(row=1,column=0,columnspan=3,sticky='w',pady=(5,0))
            tools=ttk.Frame(body);tools.grid(row=5,column=0,sticky='ew',pady=(8,0))
            self.operator_buttons={}
            for label,text in (('+',' + '),('−',' - '),('×',' * '),('÷',' / '),('( )','( )')):
                button=ttk.Button(tools,text=label,width=3,command=lambda value=text:self.insert_text(value),style='Compact.TButton')
                button.pack(side='left',padx=(0,3));self.operator_buttons[label]=button
            self.half_button=ttk.Button(tools,text='÷2',width=4,command=self.half,style='Compact.TButton');self.half_button.pack(side='left',padx=(0,3))
            self.normalize_button=ttk.Button(tools,text='式を整理',width=8,command=self.normalize,style='Compact.TButton');self.normalize_button.pack(side='right')
            self.family.trace_add('write',lambda *_:self.refresh_references());self.number.trace_add('write',lambda *_:self.update_role())
            self.refresh_references()
        self.error=ttk.Label(body,text='',foreground='#bc3434',wraplength=410)
        self.error.grid(row=6,column=0,sticky='ew',pady=(6,0))
        footer=ttk.Frame(body);footer.grid(row=7,column=0,sticky='ew',pady=(10,0))
        self.confirm_button=ttk.Button(footer,text='確定',width=7,command=self.apply,style='Primary.TButton');self.confirm_button.pack(side='right')
        self.cancel_button=ttk.Button(footer,text='取消',width=7,command=self.cancel);self.cancel_button.pack(side='right',padx=(0,6))
        self.variable.trace_add('write',lambda *_:self.update_caption());self.update_caption()
        self.bind('<Escape>',lambda _:self.cancel());self.bind('<Return>',lambda _:self.apply())
        # Combobox popdowns must keep their own Enter / Escape behavior.
        self.entry.bind('<Return>',lambda _:self.apply());self.entry.bind('<Escape>',lambda _:self.cancel())
        self.protocol('WM_DELETE_WINDOW',self.cancel)
        self.update_idletasks();width=460;height=self.winfo_reqheight()
        parent=editor.winfo_toplevel();x=parent.winfo_rootx()+(parent.winfo_width()-width)//2;y=parent.winfo_rooty()+(parent.winfo_height()-height)//2
        x=max(self.winfo_vrootx(),min(x,self.winfo_vrootx()+self.winfo_vrootwidth()-width))
        y=max(self.winfo_vrooty(),min(y,self.winfo_vrooty()+self.winfo_vrootheight()-height))
        self.geometry(f'{width}x{height}+{x}+{y}');self.minsize(400,height)
        self.deiconify();self.grab_set();self.entry.focus_set();self.entry.selection_range(0,'end');self.entry.icursor('end')

    def as_editing(self):
        return {'iid':self.key,'variable':self.variable,'entry':self.entry,'context':self.context,'dialog':self}

    def update_caption(self):
        self.caption.configure(text=presets.expression_names(self.data,self.definition,self.variable.get()) if self.uses_parameters else '')

    def roles(self):
        if self.family.get()=='PARAM':return {p['id']:presets.caption(p) for p in presets.rules(self.data,self.definition)}
        return presets.reference_roles(self.data,self.definition).get(self.family.get(),{})

    def refresh_references(self):
        old=self.role_options.get(self.number.get(),'1');roles=self.roles()
        self.role_options={pid[1:]+'：'+name:pid[1:] for pid,name in roles.items()}
        self.number_choice['values']=tuple(self.role_options)
        self.number.set(next((label for label,number in self.role_options.items() if number==old),next(iter(self.role_options),'1')))
        self.update_role()

    def selected_number(self):
        value=self.role_options.get(self.number.get(),self.number.get().strip())
        match=re.fullmatch(r'(?:P)?([1-9]\d*)',value,re.IGNORECASE)
        if not match:raise ValueError('参照番号は正の整数で指定してください。')
        return match[1]

    def update_role(self):
        try:
            number=self.selected_number();name=self.roles().get('P'+number,'設定名未登録')
            self.role_label.configure(text=self.family.get()+' '+number+'  '+name)
        except ValueError:self.role_label.configure(text='番号または登録済みの設定名を選択してください。')

    def insert_text(self,text):
        try:a,b=self.entry.index('sel.first'),self.entry.index('sel.last')
        except tk.TclError:a=b=self.entry.index('insert')
        current=self.variable.get();self.variable.set(current[:a]+text+current[b:])
        self.entry.selection_clear();self.entry.focus_set();self.entry.icursor(a+len(text))

    def insert_reference(self):
        try:self.insert_text(self.family.get()+'['+self.selected_number()+']');self.error.configure(text='')
        except ValueError as exc:self.report(str(exc))

    def half(self):
        self.variable.set('('+self.variable.get()+') / 2');self.entry.selection_clear();self.entry.icursor('end');self.entry.focus_set()

    def normalize(self):
        try:self.variable.set(expressions.normalized(self.variable.get(),presets.rules(self.data,self.definition)));self.error.configure(text='')
        except ValueError as exc:self.report(str(exc))

    def report(self,text):self.error.configure(text=text)
    def apply(self):self.table.finish_edit();return 'break'
    def cancel(self):self.table.cancel_edit();return 'break'

    def dispose(self):
        previous=self.previous_grab
        try:self.grab_release()
        except tk.TclError:pass
        self.destroy()
        try:
            if previous is not None and previous.winfo_exists():previous.grab_set()
        except tk.TclError:pass


def open_editor(editor,table,key,context):
    return ValueEditor(editor,table,key,context).as_editing()
