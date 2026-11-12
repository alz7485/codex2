"""Non-editing hover diagram of the three NAPP target roles."""
import tkinter as tk
from . import theme


def draw_sample(canvas,value,family):
    mask=int(value)
    canvas.create_text(12,15,text='NAPP '+str(mask)+'：負形状の適用先',anchor='w',fill=theme.INK,font=(family,10,'bold'))
    for index,(bit,label) in enumerate(((1,'取付先 / Attached'),(2,'所有元 / Owner'),(4,'自身 / Self'))):
        x=14+index*118;y=57;active=bool(mask&bit)
        fill='#dbe9fb' if active else '#f1f3f6';edge=theme.ACCENT if active else '#a0acba'
        if active:
            # Extruded L profile: the upper-right corner is physically missing.
            canvas.create_polygon(x,y+12,x+21,y,x+65,y,x+44,y+12,fill=fill,outline=edge)
            canvas.create_polygon(x+44,y+12,x+65,y,x+65,y+28,x+44,y+40,fill='#e8b6a9',outline='#ba514d')
            canvas.create_polygon(x+44,y+40,x+65,y+28,x+101,y+28,x+80,y+40,fill='#f6d4cb',outline='#ba514d')
            canvas.create_polygon(x+80,y+40,x+101,y+28,x+101,y+62,x+80,y+74,fill=fill,outline=edge)
            canvas.create_polygon(x,y+12,x+44,y+12,x+44,y+40,x+80,y+40,x+80,y+74,x,y+74,fill=fill,outline=edge,width=2)
        else:
            canvas.create_polygon(x,y+12,x+21,y,x+101,y,x+80,y+12,fill=fill,outline=edge)
            canvas.create_polygon(x+80,y+12,x+101,y,x+101,y+62,x+80,y+74,fill=fill,outline=edge)
            canvas.create_rectangle(x,y+12,x+80,y+74,fill=fill,outline=edge)
        canvas.create_text(x+48,y+92,text=label,fill=theme.INK,font=(family,9))
        canvas.create_text(x+48,y+112,text=('Design側のみ' if bit==1 else '適用') if active else '適用しない',fill=edge,font=(family,9,'bold'))
    canvas.create_text(12,204,text='Attachedは別のDesign部品。ツール内はOwner / Selfに適用。',anchor='w',fill=theme.MUTED,font=(family,8))


class NappHint:
    def __init__(self,table):
        self.table=table;self.pending=None;self.window=None;self.choice=None
        c=table.canvas
        c.bind('<Motion>',self.motion,add='+');c.bind('<Leave>',lambda e:self.hide(),add='+')
        for event in ('<ButtonPress>','<MouseWheel>','<Button-4>','<Button-5>','<Configure>'):
            c.bind(event,lambda e:self.hide(),add='+')
    def motion(self,event):
        t=self.table;y=t.canvas.canvasy(event.y)
        choice=next((value for (row,value),(a,b,c,d) in t.toggle_bounds.items() if row=='NAPP' and a<=event.x<=c and b<=y<=d),None)
        if choice==self.choice:return
        self.hide();self.choice=choice
        if choice is not None:
            self.pending=t.after(400,lambda:self.show(choice,event.x_root,event.y_root))
    def show(self,choice,x,y):
        self.pending=None
        if not self.table.winfo_exists() or self.choice!=choice:return
        win=self.window=tk.Toplevel(self.table);win.withdraw();win.overrideredirect(True)
        c=tk.Canvas(win,width=370,height=220,bg='white',highlightthickness=1,highlightbackground=theme.BORDER)
        c.pack();draw_sample(c,choice,self.table.meaning_font.actual('family'))
        win.geometry(f'+{max(0,min(x+14,win.winfo_screenwidth()-374))}+{max(0,min(y+18,win.winfo_screenheight()-224))}')
        win.deiconify()
    def hide(self):
        if self.pending:self.table.after_cancel(self.pending);self.pending=None
        if self.window:self.window.destroy();self.window=None
        self.choice=None
