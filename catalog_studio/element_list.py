"""Numbered element rows with an editable name and a smaller type line."""
import tkinter as tk
from tkinter import font,ttk


class ElementList(tk.Canvas):
    def __init__(self,parent,family,edit_context):
        super().__init__(parent,bg='white',highlightthickness=1,highlightbackground='#b6c2ce',width=210,takefocus=True,yscrollincrement=1)
        self.rows={};self.node_children={'':[]};self.selected=();self.bounds={};self.pending=None;self.editing=None
        self.edit_context=edit_context;self.scheduler=self.winfo_toplevel();self.tag_styles={}
        self.name_font=font.Font(self,family=family,size=11)
        self.type_font=font.Font(self,family=family,size=9)
        self.heading_font=font.Font(self,family=family,size=10,weight='bold')
        self.row_height=self.name_font.metrics('linespace')+self.type_font.metrics('linespace')+18
        self.bind('<Configure>',lambda _:self.schedule())
        self.bind('<Button-1>',self.click)
        self.bind('<Double-1>',self.edit_clicked)
        self.bind('<Return>',lambda _:self.begin_edit(self.selected[0]) if self.selected else None)
        self.bind('<MouseWheel>',lambda event:self.wheel(event))
        self.bind('<Button-4>',lambda _:self.yview_scroll(-1,'units'))
        self.bind('<Button-5>',lambda _:self.yview_scroll(1,'units'))
        self.bind('<Up>',lambda _:self.navigate(-1));self.bind('<Down>',lambda _:self.navigate(1))
        self.bind('<Home>',lambda _:self.navigate(first=True));self.bind('<End>',lambda _:self.navigate(last=True))
        self.bind('<Destroy>',self.cleanup,add='+')

    def __getitem__(self,key):
        if key=='columns':return ('number','name')
        return super().__getitem__(key)

    def cleanup(self,event):
        if event.widget is self:
            self.cancel_edit()
            if self.pending:self.scheduler.after_cancel(self.pending);self.pending=None

    def schedule(self):
        if self.pending is None:self.pending=self.scheduler.after_idle(self.redraw)

    def insert(self,parent,index,iid,text='',values=(),open=True):
        if iid in self.rows or parent and parent not in self.rows:raise ValueError('Invalid element row.')
        self.rows[iid]={'parent':parent,'text':text,'values':tuple(values),'open':open,'tags':()};self.node_children[iid]=[]
        siblings=self.node_children[parent];siblings.insert(len(siblings) if index=='end' else int(index),iid);self.schedule();return iid

    def delete(self,*items):
        def remove(iid):
            if iid not in self.rows:return
            for child in tuple(self.node_children[iid]):remove(child)
            if self.editing and self.editing['iid']==iid:self.cancel_edit()
            self.node_children[self.rows[iid]['parent']].remove(iid);del self.node_children[iid];del self.rows[iid]
        for iid in items:remove(iid)
        self.selected=tuple(i for i in self.selected if i in self.rows);self.schedule()

    def get_children(self,parent=''):return tuple(self.node_children.get(parent,()))
    def exists(self,iid):return iid in self.rows
    def parent(self,iid):return self.rows[iid]['parent']
    def item(self,iid,option=None,**kwargs):
        if kwargs:
            if 'values' in kwargs:kwargs['values']=tuple(kwargs['values'])
            self.rows[iid].update(kwargs);self.schedule()
        return self.rows[iid].get(option) if option else self.rows[iid].copy()
    def selection(self):return self.selected
    def selection_set(self,items):
        selected=(items,) if isinstance(items,str) else tuple(items)
        selected=tuple(i for i in selected if i in self.rows)[:1]
        if selected!=self.selected:
            if not self.finish_edit():return
            self.selected=selected;self.schedule();self.event_generate('<<TreeviewSelect>>',when='tail')

    def visible(self,parent=''):
        for iid in self.node_children.get(parent,()):
            yield iid
            if self.rows[iid]['open']:yield from self.visible(iid)

    def depth(self,iid):
        depth=0
        while self.rows[iid]['parent']:depth+=1;iid=self.rows[iid]['parent']
        return depth

    def identify_row(self,y):
        if y<32:return ''
        value=self.canvasy(y)
        return next((iid for iid,(top,bottom) in self.bounds.items() if top<=value<bottom),'')
    def bbox(self,iid,column=None):
        if iid not in self.bounds:return ()
        top,bottom=self.bounds[iid];y=top-self.canvasy(0)
        return () if bottom-self.canvasy(0)<=32 or y>=self.winfo_height() else (0,round(y),self.winfo_width(),bottom-top)
    def tag_configure(self,name,**kwargs):self.tag_styles[name]=kwargs;self.schedule()

    def click(self,event):
        if not self.finish_edit():return
        self.focus_set();iid=self.identify_row(event.y)
        if iid:self.selection_set(iid)

    def edit_clicked(self,event):
        iid=self.identify_row(event.y)
        if iid and event.x>=45:self.begin_edit(iid)
        return 'break'

    def navigate(self,step=0,first=False,last=False):
        items=list(self.visible())
        if items:
            index=items.index(self.selected[0]) if self.selected else (-1 if step>0 else 0)
            index=0 if first else len(items)-1 if last else max(0,min(len(items)-1,index+step))
            self.selection_set(items[index]);self.see(items[index])
        return 'break'

    def yview(self,*args):
        if len(args)==3 and args[0]=='scroll' and args[2]=='units':args=(args[0],int(args[1])*self.row_height,args[2])
        result=super().yview(*args)
        if args:self.draw_header()
        return result
    def yview_scroll(self,number,what):return self.yview('scroll',number,what)
    def yview_moveto(self,fraction):return self.yview('moveto',fraction)
    def wheel(self,event):
        self.yview_scroll(-max(1,abs(event.delta)//120) if event.delta>0 else max(1,abs(event.delta)//120),'units');return 'break'
    def see(self,iid):
        if iid not in self.bounds:return
        top,bottom=self.bounds[iid];offset=self.canvasy(0);height=self.winfo_height()
        total=max(height,max((b for a,b in self.bounds.values()),default=height))
        if top<offset+32:self.yview_moveto(max(0,top-32)/total)
        elif bottom>offset+height:self.yview_moveto((bottom-height)/total)

    def shorten(self,text,width,face):
        if face.measure(text)<=width:return text
        while text and face.measure(text+'…')>width:text=text[:-1]
        return text+'…'

    def begin_edit(self,iid):
        if iid not in self.rows or not self.finish_edit():return False
        context=self.edit_context(iid)
        if context is None:return False
        self.selection_set(iid);self.see(iid);variable=tk.StringVar(value=context['value'])
        entry=ttk.Entry(self,textvariable=variable,font=self.name_font)
        self.editing={'iid':iid,'variable':variable,'entry':entry,'context':context}
        entry.bind('<Return>',lambda _:self.finish_edit());entry.bind('<Escape>',lambda _:self.cancel_edit())
        entry.bind('<FocusOut>',lambda _:self.finish_edit())
        self.draw_editor();entry.focus_set();entry.selection_range(0,'end');entry.icursor('end');return True

    def finish_edit(self):
        if not self.editing:return True
        editing=self.editing;self.editing=None
        try:editing['context']['commit'](editing['variable'].get())
        except ValueError as exc:
            self.editing=editing;editing['context']['report'](str(exc));return False
        editing['entry'].destroy();self.schedule();return True
    def cancel_edit(self):
        if self.editing:
            editing=self.editing;self.editing=None;editing['entry'].destroy();self.schedule()
        return 'break'
    def draw_editor(self):
        if self.editing and self.editing['iid'] in self.bounds:
            iid=self.editing['iid'];x=51+self.depth(iid)*12;top=self.bounds[iid][0]
            self.create_window(x,top+5,anchor='nw',window=self.editing['entry'],width=max(55,self.winfo_width()-x-7),tags=('editor',))

    def draw_header(self):
        super().delete('header');top=self.canvasy(0);width=max(120,self.winfo_width())
        self.create_rectangle(0,top,width,top+32,fill='#edf3fa',outline='#aebccb',tags=('header',))
        for x,label in ((8,'番号'),(53,'要素名 / 種類')):self.create_text(x,top+16,text=label,anchor='w',font=self.heading_font,fill='#243448',tags=('header',))
        self.create_line(45,top,45,top+32,fill='#aebccb',tags=('header',))

    def redraw(self):
        self.pending=None
        if not self.winfo_exists():return
        super().delete('all');self.bounds={};width=max(120,self.winfo_width());top=32
        for iid in self.visible():
            row=self.rows[iid];number,name,kind=row['values'];chosen=iid in self.selected
            color='#2269de' if chosen else '#243448';background='#e5efff' if chosen else 'white'
            for tag in row['tags']:background=self.tag_styles.get(tag,{}).get('background',background)
            self.create_rectangle(0,top,width,top+self.row_height,fill=background,outline='')
            x=53+self.depth(iid)*12;available=max(25,width-x-8)
            self.create_text(8,top+9,text=number,anchor='nw',font=self.name_font,fill=color,tags=('number:'+iid,))
            self.create_text(x,top+8,text=self.shorten(row['text'],available,self.name_font),anchor='nw',font=self.name_font,fill=color,tags=('name:'+iid,))
            self.create_text(x,top+9+self.name_font.metrics('linespace'),text=self.shorten(kind,available,self.type_font),anchor='nw',font=self.type_font,fill='#597fa5' if chosen else '#738499',tags=('type:'+iid,))
            self.bounds[iid]=(top,top+self.row_height);top+=self.row_height
        for _,bottom in self.bounds.values():self.create_line(0,bottom,width,bottom,fill='#aebccb')
        self.create_line(45,32,45,max(top,self.winfo_height()),fill='#aebccb')
        self.configure(scrollregion=(0,0,width,max(top,self.winfo_height())))
        self.draw_header();self.draw_editor()
