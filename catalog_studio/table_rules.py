"""Thin cell rules aligned with a native headed Treeview."""
import tkinter as tk
from tkinter import ttk


class TableRules:
    def __init__(self, tree):
        self.root=tree._root();self.tree=tree;self.lines=[];self.pending=None;self.closed=False
        for event in ('<Configure>','<ButtonRelease-1>','<<TreeviewSelect>>'):
            tree.bind(event,lambda e:self.schedule(),add='+')
        tree.bind('<Destroy>',self.close,add='+')
        self.schedule()

    def schedule(self):
        if not self.closed and self.pending is None and self.tree.winfo_exists():
            self.pending=self.root.after_idle(self.draw)

    def close(self,event):
        if event.widget is self.tree:
            self.closed=True
            if self.pending is not None:
                self.root.after_cancel(self.pending);self.pending=None

    def draw(self):
        self.pending=None
        tree=self.tree
        if not tree.winfo_exists():return
        for item in self.lines:item.destroy()
        self.lines=[]
        width,height=tree.winfo_width(),tree.winfo_height()
        # Identify the heading bottom even when the table has no rows.
        top=next((y for y in range(min(height,100))
                  if tree.identify_region(5,y) in ('cell','tree')),None)
        boxes=[tree.bbox(row) for row in tree.get_children()]
        boxes=[box for box in boxes if box]
        if boxes:top=min(box[1] for box in boxes)
        if top is None:
            top=next((y for y in range(min(height,100))
                      if tree.identify_region(5,y)=='heading'),1)
            while top<height and tree.identify_region(5,top) in ('heading','separator'):top+=1
        rowheight=boxes[0][3] if boxes else int(ttk.Style(tree).lookup(tree.cget('style') or 'Treeview','rowheight') or 30)
        def line(x,y,w,h):
            item=tk.Frame(tree,background='#c7d4e5',borderwidth=0,takefocus=False)
            item.place(x=x,y=y,width=w,height=h);self.lines.append(item)
            for sequence in ('<Button-1>','<ButtonRelease-1>','<Double-1>','<Button-3>'):
                item.bind(sequence,lambda e,s=sequence:tree.event_generate(s,
                    x=e.x+e.widget.winfo_x(),y=e.y+e.widget.winfo_y(),state=e.state))
            item.bind('<MouseWheel>',lambda e:tree.event_generate('<MouseWheel>',delta=e.delta))
            for sequence in ('<Button-4>','<Button-5>'):
                item.bind(sequence,lambda e,s=sequence:tree.event_generate(s))
        columns=tree['displaycolumns']
        if columns==('#all',):columns=tree['columns']
        widths=[tree.column(col,'width') for col in columns]
        x=1-tree.xview()[0]*sum(widths)
        for size in widths:
            if 0<=round(x)<width:line(round(x),top,1,max(0,height-top))
            x+=size
        if 0<=round(x)<width:line(round(x),top,1,max(0,height-top))
        for y in range(top,height,max(1,rowheight)):line(0,y,width,1)

        for item in tree.winfo_children():
            if isinstance(item,(ttk.Entry,ttk.Combobox)):item.lift()
