"""Catalogue view using the same GeometryCanvas as the GMSET editor."""
import tkinter as tk
from tkinter import ttk
from . import project,catalog_dimensions
from .geometry_canvas import GeometryCanvas


class CatalogueEditor:
    def __init__(self,host):
        self.host=host;self.preview_scom_id=host.scom_id;self.element_id=None
        self.scom_choice=tk.StringVar(master=host)
    @property
    def data(self):return self.host.data
    @property
    def definition_id(self):return (self.definition() or {}).get('id')
    def definition(self):
        scom=project.get(self.data,'scoms',self.preview_scom_id)
        return project.get(self.data,'definitions',(scom or {}).get('gmset_id'))
    def element(self):return None
    def commit_inline(self):
        inspector=getattr(self.host,'catalog_inspector',None)
        return inspector.finish() if inspector and inspector.winfo_exists() else True
    def refresh_values(self):pass
    def update_validation(self):pass
    def draw(self):self.view.redraw()
    def redraw_points(self):self.view.redraw()


class CatalogGeometryPreview(GeometryCanvas):
    def __init__(self,host,parent):
        self.dimension_drag=None;self.dimension_items={};self.dimension_measurements=[]
        self.geometry_click=None;self.geometry_moved=False
        self.dimension_lines=tk.BooleanVar(master=host,value=True)
        self.dimension_stext=tk.BooleanVar(master=host,value=False)
        editor=CatalogueEditor(host);editor.view=self
        editor.reference_bar=ttk.Frame(parent)
        super().__init__(editor,parent)
        editor.reference_bar.pack_forget()
        self.dimension_buttons={}
        for key,text,var in (('visible','↔ 寸法',self.dimension_lines),('stext','文 STEXT',self.dimension_stext)):
            button=ttk.Checkbutton(self.mode_overlay,text=text,variable=var,command=self.dimensions_changed,style='Preview.Toolbutton')
            button.pack(side='left',padx=2)
            self.dimension_buttons[key]=button
        self.selection_label.master.grid_remove()
        self.note.grid_remove()
        from . import model_settings
        ttk.Button(self.settings_content,text='設計値を編集',command=lambda:model_settings.edit(editor),style='AttributeTool.TButton').pack(fill='x',pady=(8,0))
        ttk.Checkbutton(self.settings_content,text='寸法線（登録寸法のみ）',variable=self.dimension_lines,command=self.dimensions_changed).pack(anchor='w',pady=(8,0))
        self.pack(fill='both',expand=True)
        self.focus_override=self.toggle_focus
        # Selection is controlled by the catalogue list; keep its SCOM context.
        self.scom_choice.configure(state='disabled')
    def redraw(self):
        if getattr(self,'refreshing',False):return
        from .element_schema import walk
        if self.editor.element_id and not any(n['id']==self.editor.element_id for n in walk((self.editor.definition() or {}).get('elements',[]))):self.editor.element_id=None
        self.fit_padding=100 if self.actual and self.dimension_lines.get() else 55
        super().redraw()
        catalog_dimensions.draw(self)
        if hasattr(self,'issue_label') and self.winfo_exists():
            if self.issue_label.cget('text'):self.issue_label.grid()
            else:self.issue_label.grid_remove()

    def refresh_options(self):
        super().refresh_options();self.scom_choice.configure(state='disabled')
    def load(self,data,scom,selected=None):
        ident=(scom or {}).get('id');changed=ident!=self.editor.preview_scom_id
        self.cancel(redraw=False)
        if changed or getattr(self,'selection_data',None) is not data:self.editor.element_id=None
        self.selection_data=data;self.editor.preview_scom_id=ident
        if changed or not getattr(self,'loaded',False):self.mode.set('SCOM 実寸' if scom and scom.get('values') else '仮サイズ')
        self.loaded=True
        self.redraw()
    def press(self,event):
        self.canvas.focus_set()
        if not self.editor.commit_inline():return
        key=catalog_dimensions.hit(self,event.x,event.y)
        if key:catalog_dimensions.start(self,key,event)
        else:
            self.geometry_click=(event.x,event.y);self.geometry_moved=False
            self.orbit_start(event)
    def move(self,event):
        if self.dimension_drag:catalog_dimensions.move(self,event)
        else:
            if self.geometry_click and ((event.x-self.geometry_click[0])**2+(event.y-self.geometry_click[1])**2)>16:self.geometry_moved=True
            if self.geometry_moved:super().move(event)
    def release(self,event=None):
        if self.dimension_drag:catalog_dimensions.release(self)
        else:
            click=self.geometry_click;self.geometry_click=None
            super().release(event)
            if click and not self.geometry_moved and event is not None:
                self.editor.element_id=self.pick_element(event.x,event.y)
                self.redraw()
    def cancel(self,redraw=True):
        self.dimension_drag=None;self.geometry_click=None
        return super().cancel(redraw)
    def pick_element(self,x,y):
        from .surface_render import inside_polygon
        # In solid mode the frontmost projected face wins, including transparent surfaces.
        if self.render_mode.get()!='ワイヤー':
            for points,ident in reversed(self.pick_faces):
                if inside_polygon(x,y,points):return ident
        for item in reversed(self.canvas.find_overlapping(x-3,y-3,x+3,y+3)):
            ident=next((t[8:] for t in self.canvas.gettags(item) if t.startswith('element:')),None)
            if ident:return ident
        return None

    def dimensions_changed(self):
        self.dimension_drag=None;self.redraw()

    def toggle_focus(self):
        host=self.editor.host;split=host.catalog_panes;attribute=host.catalog_inspector.master
        if getattr(self,'focused',False):
            split.add(attribute,weight=2);split.update_idletasks();split.sashpos(0,self.catalog_sash)
            self.focused=False;self.focus_button.configure(text='拡大')
        else:
            self.catalog_sash=split.sashpos(0);split.forget(attribute)
            self.focused=True;self.focus_button.configure(text='戻す')
