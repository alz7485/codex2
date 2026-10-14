"""Attribute rows with a smaller meaning line and a separate value column."""
import tkinter as tk
from tkinter import font, ttk


class AttributeTable(ttk.Frame):
    def __init__(self,parent,family):
        super().__init__(parent)
        self.rows={};self.order=[];self.selected=();self.bounds={};self.pending=None;self.ensure_visible=None;self.scheduler=self.winfo_toplevel()
        self.name_font=font.Font(self,family=family,size=11,weight='bold')
        self.meaning_font=font.Font(self,family=family,size=9)
        self.value_font=font.Font(self,family=family,size=10)
        self.heading_font=font.Font(self,family=family,size=10,weight='bold')
        self.columnconfigure(0,weight=1);self.rowconfigure(1,weight=1)
        self.header=tk.Canvas(self,height=32,bg='#edf3fa',highlightthickness=0)
        self.header.grid(row=0,column=0,sticky='ew')
        self.canvas=tk.Canvas(self,bg='white',width=300,height=320,highlightthickness=0,takefocus=True,yscrollincrement=1)
        self.canvas.grid(row=1,column=0,sticky='nsew')
        scrollbar=ttk.Scrollbar(self,command=self.scroll);scrollbar.grid(row=1,column=1,sticky='ns')
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind('<Configure>',lambda _:self.schedule())
        self.canvas.bind('<Button-1>',self.click)
        self.canvas.bind('<MouseWheel>',self.wheel)
        self.canvas.bind('<Button-4>',lambda _:self.scroll('scroll',-2,'units'))
        self.canvas.bind('<Button-5>',lambda _:self.scroll('scroll',2,'units'))
        for key,direction in (('<Up>',-1),('<Down>',1)):
            self.canvas.bind(key,lambda _,step=direction:self.navigate(step))
        self.canvas.bind('<Home>',lambda _:self.navigate(first=True))
        self.canvas.bind('<End>',lambda _:self.navigate(last=True))
        super().bind('<Destroy>',self.cleanup,add='+')

    def bind(self,sequence=None,func=None,add=None):
        if sequence in ('<Double-1>','<Return>'):return self.canvas.bind(sequence,func,add)
        return super().bind(sequence,func,add)

    def cleanup(self,event):
        if event.widget is self and self.pending:
            self.scheduler.after_cancel(self.pending);self.pending=None

    def schedule(self):
        if self.pending is None:self.pending=self.scheduler.after_idle(self.redraw)

    def insert(self,parent,index,iid,values):
        if parent:raise ValueError('Attribute rows have no children.')
        if iid in self.rows:raise ValueError('Duplicate attribute: '+iid)
        self.rows[iid]=tuple(str(v) for v in values)
        self.order.insert(len(self.order) if index=='end' else int(index),iid)
        self.schedule();return iid

    def delete(self,*items):
        for iid in items:
            if iid in self.rows:del self.rows[iid];self.order.remove(iid)
        self.selected=tuple(i for i in self.selected if i in self.rows);self.schedule()

    def get_children(self,parent=''):return tuple(self.order) if not parent else ()
    def exists(self,iid):return iid in self.rows
    def item(self,iid,option=None,**kwargs):
        if 'values' in kwargs:self.rows[iid]=tuple(str(v) for v in kwargs['values']);self.schedule()
        values=self.rows[iid]
        return values if option=='values' else {'values':values}
    def selection(self):return self.selected
    def selection_set(self,items):
        selection=(items,) if isinstance(items,str) else tuple(items)
        selection=tuple(i for i in selection if i in self.rows)[:1]
        if selection!=self.selected:
            self.selected=selection;self.ensure_visible=selection[0] if selection else None;self.schedule()
            self.event_generate('<<TreeviewSelect>>',when='tail')

    def click(self,event):
        self.canvas.focus_set();y=self.canvas.canvasy(event.y)
        for iid,(top,bottom) in self.bounds.items():
            if top<=y<bottom:self.selection_set(iid);break

    def navigate(self,step=0,first=False,last=False):
        if self.order:
            index=self.order.index(self.selected[0]) if self.selected else (-1 if step>0 else 0)
            index=0 if first else len(self.order)-1 if last else max(0,min(len(self.order)-1,index+step))
            self.selection_set(self.order[index])
        return 'break'

    def wheel(self,event):
        units=-max(1,abs(event.delta)//120) if event.delta>0 else max(1,abs(event.delta)//120)
        self.scroll('scroll',units,'units');return 'break'

    def scroll(self,*args):
        if len(args)==3 and args[0]=='scroll' and args[2]=='units':self.canvas.yview_scroll(int(args[1])*24,'units')
        else:self.canvas.yview(*args)

    def see(self,iid):
        if iid not in self.bounds:return
        top,bottom=self.bounds[iid];visible_top=self.canvas.canvasy(0);height=self.canvas.winfo_height()
        total=max(height,max((b for a,b in self.bounds.values()),default=height))
        if top<visible_top:self.canvas.yview_moveto(top/total)
        elif bottom>visible_top+height:self.canvas.yview_moveto((bottom-height)/total)

    def short_meaning(self,text,width):
        text=str(text).replace('\n',' ')
        if self.meaning_font.measure(text)<=width:return text
        while text and self.meaning_font.measure(text+'…')>width:text=text[:-1]
        return text+'…'

    def redraw(self):
        self.pending=None
        if not self.winfo_exists():return
        c=self.canvas;c.delete('all');self.header.delete('all');self.bounds={}
        width=max(220,c.winfo_width());divider=max(105,int(width*.39));value_width=max(80,width-divider-20)
        for x,text in ((10,'属性 / 意味'),(divider+10,'値・式')):
            self.header.create_text(x,16,text=text,anchor='w',font=self.heading_font,fill='#243448')
        self.header.create_line(divider,0,divider,32,fill='#dce5ef')
        top=0;name_height=self.name_font.metrics('linespace');meaning_height=self.meaning_font.metrics('linespace')
        minimum=name_height+meaning_height+18
        for iid in self.order:
            attr,meaning,value=self.rows[iid];chosen=iid in self.selected
            color='#2269de' if chosen else '#243448'
            background=c.create_rectangle(0,top,width,top+minimum,fill='#e5efff' if chosen else 'white',outline='')
            item=c.create_text(divider+10,top+8,text=value,anchor='nw',width=value_width,font=self.value_font,fill=color,tags=('value:'+iid,))
            bbox=c.bbox(item);height=max(minimum,(bbox[3]-bbox[1]+16) if bbox else minimum)
            c.coords(background,0,top,width,top+height)
            c.create_text(10,top+8,text=attr,anchor='nw',font=self.name_font,fill=color,tags=('name:'+iid,))
            c.create_text(10,top+8+name_height,text=self.short_meaning(meaning,divider-20),anchor='nw',font=self.meaning_font,fill='#597fa5' if chosen else '#738499',tags=('meaning:'+iid,))
            self.bounds[iid]=(top,top+height);top+=height
            c.create_line(0,top,width,top,fill='#e7edf4')
        c.create_line(divider,0,divider,top,fill='#e7edf4')
        c.configure(scrollregion=(0,0,width,max(top,c.winfo_height())))
        if self.ensure_visible:self.see(self.ensure_visible);self.ensure_visible=None
