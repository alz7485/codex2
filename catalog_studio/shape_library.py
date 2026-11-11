"""Aligned icon / type / meaning rows with the Listbox selection interface."""
import tkinter as tk
from . import theme,shape_icons

class ShapeLibrary(tk.Canvas):
    def __init__(self,parent,family):
        super().__init__(parent,background='white',highlightthickness=0,width=320,height=440)
        self.items=[];self.chosen=();self.family=family
        self.bind('<Configure>',lambda e:self.draw())
        self.bind('<Button-1>',self.click)
    def size(self):return len(self.items)
    def insert(self,index,text):self.items.append(text);self.draw()
    def delete(self,first,last=None):self.items=[];self.chosen=();self.draw()
    def get(self,index,last=None):return tuple(self.items[int(index):]) if last is not None else self.items[int(index)]
    def curselection(self):return self.chosen
    def selection_set(self,index,last=None):self.chosen=(int(index),);self.draw()
    def selection_clear(self,*args):self.chosen=();self.draw()
    def activate(self,index):pass
    def see(self,index):pass
    def bbox(self,index):return (0,int(index)*24,self.winfo_width(),24)
    def click(self,event):
        index=int(self.canvasy(event.y)//24)
        if 0<=index<len(self.items):self.selection_set(index);self.event_generate('<<ListboxSelect>>')
    def draw(self):
        super().delete('all')
        for i,item in enumerate(self.items):
            kind,_,label=item.partition(' ');label=label.strip();y=i*24
            chosen=i in self.chosen
            if chosen:self.create_rectangle(0,y,self.winfo_width(),y+24,fill=theme.SELECT,outline='')
            color=theme.ACCENT if chosen else theme.INK
            shape_icons.draw(self,kind,2,y+1,color,theme.SELECT if chosen else 'white')
            self.create_text(37,y+12,text=kind,anchor='w',font=(self.family,10),fill=color)
            self.create_text(104,y+12,text=label,anchor='w',font=(self.family,10),fill=color)
        self.configure(scrollregion=(0,0,self.winfo_width(),len(self.items)*24))
