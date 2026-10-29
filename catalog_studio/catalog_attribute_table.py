"""Catalogue cell editing facade over the shared two-line attribute table."""
from types import SimpleNamespace
from .attribute_table import AttributeTable


class CatalogAttributeTable(AttributeTable):
    def __init__(self,parent,family):
        super().__init__(parent,family);self.serial=0

    def bind(self,sequence=None,func=None,add=None):
        if sequence=='<ButtonRelease-1>' and func:
            self.canvas.bind(sequence,lambda e:func(SimpleNamespace(x=e.x+self.canvas.winfo_x(),y=e.y+self.canvas.winfo_y())),add)
        return super().bind(sequence,func,add)

    def insert(self,parent,index,iid=None,values=(),tags=(),meaning=''):
        self.serial+=1;iid=iid or 'catalog-field-'+str(self.serial)
        return super().insert(parent,index,iid,(values[0],meaning,values[1]))

    def item(self,iid,option=None,**kwargs):
        if 'values' in kwargs:
            values=kwargs['values'];kwargs['values']=(values[0],self.rows[iid][1],values[1])
        result=super().item(iid,option,**kwargs)
        if option=='values':return result[0],result[2]
        return {'values':(result['values'][0],result['values'][2])}

    def scroll(self,*args):
        commit=getattr(self,'before_scroll',None)
        if commit and not commit():return
        return super().scroll(*args)

    def focus(self):return self.selected[0] if self.selected else ''
    def identify_column(self,x):return '#2' if x>=max(105,int(max(220,self.canvas.winfo_width())*.39)) else '#1'
    def identify_row(self,y):
        y=self.canvas.canvasy(y-self.canvas.winfo_y())
        return next((iid for iid,(a,b) in self.bounds.items() if a<=y<b),'')

    def bbox(self,iid,column='value'):
        if iid not in self.bounds:return ()
        top,bottom=self.bounds[iid];width=max(220,self.canvas.winfo_width());divider=max(105,int(width*.39))
        return (self.canvas.winfo_x()+divider+4,int(top-self.canvas.canvasy(0))+self.canvas.winfo_y()+3,max(80,width-divider-10),min(30,int(bottom-top-6)))
