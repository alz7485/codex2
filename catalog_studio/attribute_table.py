"""Attribute rows with a smaller meaning line and a separate value column."""
import tkinter as tk
from tkinter import font, ttk
from . import theme


class AttributeTable(ttk.Frame):
    def __init__(self,parent,family,value_caption=None,edit_context=None,missing_value=None,editor_factory=None):
        super().__init__(parent)
        self.rows={};self.order=[];self.selected=();self.bounds={};self.pending=None;self.ensure_visible=None;self.scheduler=self.winfo_toplevel()
        self.value_caption=value_caption or (lambda key,value:'')
        self.edit_context=edit_context;self.editing=None
        self.missing_value=missing_value or (lambda key:False)
        self.editor_factory=editor_factory
        self.name_font=font.Font(self,family=family,size=11,weight='bold')
        self.meaning_font=font.Font(self,family=family,size=9)
        self.value_font=font.Font(self,family=family,size=10)
        self.heading_font=font.Font(self,family=family,size=10,weight='bold')
        self.columnconfigure(0,weight=1);self.rowconfigure(1,weight=1)
        self.header=tk.Canvas(self,height=32,bg=theme.SUBTLE,highlightthickness=0)
        self.header.grid(row=0,column=0,sticky='ew')
        self.canvas=tk.Canvas(self,bg='white',width=300,height=320,highlightthickness=1,highlightbackground=theme.RULE,highlightcolor=theme.ACCENT,takefocus=True,yscrollincrement=1)
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
        if event.widget is self:
            self.cancel_edit()
            if self.pending:self.scheduler.after_cancel(self.pending);self.pending=None

    def schedule(self):
        if self.pending is None:self.pending=self.scheduler.after_idle(self.redraw)

    def insert(self,parent,index,iid,values):
        if parent:raise ValueError('Attribute rows have no children.')
        if iid in self.rows:raise ValueError('Duplicate attribute: '+iid)
        self.rows[iid]=tuple(str(v) for v in values)
        self.order.insert(len(self.order) if index=='end' else int(index),iid)
        self.schedule();return iid

    def delete(self,*items):
        if self.editing and self.editing['iid'] in items:self.cancel_edit()
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
            if not self.finish_edit():return
            self.selected=selection;self.ensure_visible=selection[0] if selection else None;self.schedule()
            self.event_generate('<<TreeviewSelect>>',when='tail')

    def click(self,event):
        if not self.finish_edit():return
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

    def begin_edit(self,iid):
        if self.editing and self.editing['iid']==iid and 'dialog' in self.editing:
            self.editing['dialog'].lift();self.editing['entry'].focus_set();return True
        if not self.edit_context or iid not in self.rows or not self.finish_edit():return False
        context=self.edit_context(iid)
        if context is None:return False
        if self.editor_factory:
            self.selection_set(iid);self.see(iid)
            self.editing=self.editor_factory(self,iid,context);return True
        self.selection_set(iid);variable=tk.StringVar(value=context['value'])
        choices=context.get('choices',())
        entry=ttk.Combobox(self.canvas,textvariable=variable,values=choices,state='normal') if choices else ttk.Entry(self.canvas,textvariable=variable)
        self.editing={'iid':iid,'variable':variable,'entry':entry,'context':context}
        entry.bind('<Return>',lambda _:self.finish_edit())
        entry.bind('<Escape>',lambda _:self.cancel_edit())
        entry.bind('<FocusOut>',self.edit_blur)
        if choices:entry.bind('<<ComboboxSelected>>',lambda _:self.finish_edit())
        self.see(iid);self.draw_editor();entry.focus_set();entry.selection_range(0,'end');entry.icursor('end')
        return True

    def edit_blur(self,event):
        if self.editing and isinstance(self.editing['entry'],ttk.Combobox):
            entry=self.editing['entry']
            popup=entry.tk.call('ttk::combobox::PopdownWindow',str(entry))
            if entry.tk.call('winfo','ismapped',popup):return
        self.finish_edit()

    def finish_edit(self):
        if not self.editing:return True
        editing=self.editing;self.editing=None
        try:editing['context']['commit'](editing['variable'].get())
        except ValueError as exc:
            self.editing=editing;editing['context']['report'](str(exc))
            if 'dialog' in editing:editing['dialog'].report(str(exc))
            return False
        if 'dialog' in editing:editing['dialog'].dispose()
        else:editing['entry'].destroy()
        self.schedule();return True

    def cancel_edit(self):
        if self.editing:
            editing=self.editing;self.editing=None
            if 'dialog' in editing:editing['dialog'].dispose()
            else:editing['entry'].destroy()
            self.schedule()
        return 'break'

    def draw_editor(self):
        if self.editing and 'dialog' not in self.editing and self.editing['iid'] in self.bounds:
            width=max(220,self.canvas.winfo_width());divider=max(105,int(width*.39));top=self.bounds[self.editing['iid']][0]
            self.canvas.create_window(divider+6,top+3,anchor='nw',window=self.editing['entry'],width=max(80,width-divider-12),tags=('editor',))

    def redraw(self):
        self.pending=None
        if not self.winfo_exists():return
        c=self.canvas;c.delete('all');self.header.delete('all');self.bounds={}
        width=max(220,c.winfo_width());divider=max(105,int(width*.39));value_width=max(80,width-divider-20)
        for x,text in ((10,'属性 / 意味'),(divider+10,'値・式')):
            self.header.create_text(x,16,text=text,anchor='w',font=self.heading_font,fill=theme.INK)
        self.header.create_line(divider,0,divider,32,fill=theme.RULE)
        self.header.create_line(0,31,width,31,fill=theme.RULE)
        top=0;name_height=self.name_font.metrics('linespace');meaning_height=self.meaning_font.metrics('linespace')
        minimum=name_height+meaning_height+10
        for iid in self.order:
            attr,meaning,value=self.rows[iid];chosen=iid in self.selected
            color=theme.ACCENT if chosen else theme.INK
            background=c.create_rectangle(0,top,width,top+minimum,fill=theme.SELECT if chosen else 'white',outline='')
            item=c.create_text(divider+10,top+5,text=value,anchor='nw',width=value_width,font=self.value_font,fill=color,tags=('value:'+iid,))
            bbox=c.bbox(item);value_height=(bbox[3]-bbox[1]) if bbox else self.value_font.metrics('linespace')
            caption=self.value_caption(attr,value);caption_height=0
            if caption:
                caption_item=c.create_text(divider+10,top+7+value_height,text=self.short_meaning(caption,value_width-2),anchor='nw',font=self.meaning_font,fill='#597fa5' if chosen else theme.MUTED,tags=('caption:'+iid,))
                caption_bbox=c.bbox(caption_item);caption_height=caption_bbox[3]-caption_bbox[1]+2
            height=max(minimum,value_height+caption_height+10)
            c.coords(background,0,top,width,top+height)
            if self.missing_value(iid):
                c.create_rectangle(divider+3,top+3,width-4,top+height-3,outline='#d94343',width=2,tags=('required:'+iid,))
                c.itemconfigure(item,text='入力してください',fill='#bc3434')
            c.create_text(10,top+5,text=attr,anchor='nw',font=self.name_font,fill=color,tags=('name:'+iid,))
            c.create_text(10,top+5+name_height,text=self.short_meaning(meaning,divider-20),anchor='nw',font=self.meaning_font,fill='#597fa5' if chosen else theme.MUTED,tags=('meaning:'+iid,))
            self.bounds[iid]=(top,top+height);top+=height
        for iid in self.selected:
            if iid in self.bounds:
                a,b=self.bounds[iid];c.create_rectangle(1,a,4,b,fill=theme.ACCENT,outline='')
        for _,bottom in self.bounds.values():c.create_line(0,bottom,width,bottom,fill=theme.RULE)
        c.create_line(divider,0,divider,max(top,c.winfo_height()),fill=theme.RULE)
        c.configure(scrollregion=(0,0,width,max(top,c.winfo_height())))
        if self.ensure_visible:self.see(self.ensure_visible);self.ensure_visible=None
        self.draw_editor()
