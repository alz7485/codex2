"""Project file actions for the right end of the category navigation row."""
import tkinter as tk
from . import theme


def icon(master,kind,*,color='#edf3ff'):
    image=tk.PhotoImage(master=master,width=24,height=24)
    def line(a,b):
        x,y=a;u,v=b;n=max(abs(u-x),abs(v-y),1)
        for i in range(n+1):image.put(color,(round(x+(u-x)*i/n),round(y+(v-y)*i/n)))
    def path(points):
        for a,b in zip(points,points[1:]):line(a,b)
    if kind=='new':
        path([(4,21),(4,2),(13,2),(18,7),(18,11)])
        path([(13,2),(13,7),(18,7)]);line((4,21),(11,21))
        line((17,13),(17,21));line((13,17),(21,17))
    elif kind=='open':
        path([(2,18),(2,5),(9,5),(11,8),(20,8),(20,11)])
        path([(2,20),(6,11),(22,11),(18,20),(2,20)])
    elif kind=='folder_add':
        path([(2,20),(2,5),(9,5),(11,8),(21,8),(21,12)])
        line((2,20),(12,20));line((17,14),(17,22));line((13,18),(21,18))
    elif kind=='search':
        path([(4,4),(7,2),(11,2),(14,4),(16,7),(16,11),(14,14),(11,16),(7,16),(4,14),(2,11),(2,7),(4,4)])
        line((14,14),(22,22));line((15,14),(22,21))
    else:
        path([(3,3),(18,3),(21,6),(21,21),(3,21),(3,3)])
        path([(7,3),(7,10),(17,10),(17,3)])
        path([(7,21),(7,14),(17,14),(17,21)])
        line((14,5),(14,8))
    return image


class Hint:
    def __init__(self,button,text):
        self.button=button;self.text=text;self.window=None
        for event in ('<Enter>','<FocusIn>'):button.bind(event,self.show,add='+')
        for event in ('<Leave>','<FocusOut>','<ButtonPress>','<Escape>'):button.bind(event,self.hide,add='+')

    def show(self,event=None):
        if self.window:return
        button=self.button;self.window=tk.Toplevel(button)
        self.window.overrideredirect(True)
        tk.Label(self.window,text=self.text,padx=8,pady=5,bg=theme.SUBTLE,fg=theme.INK,relief='solid',borderwidth=1).pack()
        self.window.update_idletasks()
        x=min(button.winfo_rootx(),button.winfo_screenwidth()-self.window.winfo_reqwidth()-8)
        self.window.geometry(f'+{max(0,x)}+{button.winfo_rooty()+button.winfo_height()+4}')

    def hide(self,event=None):
        if self.window:self.window.destroy();self.window=None


def build(host,parent):
    host.project_actions=tk.Frame(parent,bg=theme.NAV)
    host.project_actions.pack(side='right',padx=(12,0))
    host.project_buttons={};host.project_action_images={};host.project_action_hints={}
    for kind,label,shortcut,command in (
        ('new','新規プロジェクト','Ctrl+N',host.new_project),
        ('open','プロジェクトを開く','Ctrl+O',host.open_project),
        ('save','保存','Ctrl+S',host.save_project),
    ):
        picture=icon(host,kind);host.project_action_images[kind]=picture
        button=tk.Button(host.project_actions,text=label,image=picture,compound='none',command=command,
            width=30,height=28,padx=4,pady=4,bg=theme.ACCENT if kind=='save' else theme.NAV,
            activebackground=theme.ACCENT_HOVER if kind=='save' else '#2b4160',
            relief='flat',borderwidth=0,highlightthickness=1,highlightbackground='#536881',highlightcolor='#a8c8ff',cursor='hand2',takefocus=True)
        button.pack(side='left',padx=(5,0));button.bind('<Return>',lambda event,b=button:(b.invoke(),'break')[1])
        host.project_buttons[kind]=button
        host.project_action_hints[kind]=Hint(button,label+' ('+shortcut+')')
