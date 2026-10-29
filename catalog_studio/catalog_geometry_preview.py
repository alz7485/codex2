"""Catalogue view using the same GeometryCanvas as the GMSET editor."""
import tkinter as tk
from tkinter import ttk
from . import project
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
        editor=CatalogueEditor(host);editor.view=self
        editor.reference_bar=ttk.Frame(parent)
        super().__init__(editor,parent)
        editor.reference_bar.pack_forget()
        self.selection_label.master.grid_remove()
        self.note.grid_remove()
        from . import model_settings
        ttk.Button(self.settings_content,text='設計値を編集',command=lambda:model_settings.edit(editor),style='AttributeTool.TButton').pack(fill='x',pady=(8,0))
        self.pack(fill='both',expand=True)
        self.focus_override=self.toggle_focus
        # Selection is controlled by the catalogue list; keep its SCOM context.
        self.scom_choice.configure(state='disabled')
    def redraw(self):
        super().redraw()
        if hasattr(self,'issue_label') and self.winfo_exists():
            if self.issue_label.cget('text'):self.issue_label.grid()
            else:self.issue_label.grid_remove()

    def refresh_options(self):
        super().refresh_options();self.scom_choice.configure(state='disabled')
    def load(self,data,scom,selected=None):
        ident=(scom or {}).get('id');changed=ident!=self.editor.preview_scom_id
        self.cancel(redraw=False);self.editor.preview_scom_id=ident
        if changed or not getattr(self,'loaded',False):self.mode.set('SCOM 実寸' if scom and scom.get('values') else '仮サイズ')
        self.loaded=True
        self.redraw()
    def press(self,event):
        self.canvas.focus_set()
        if self.editor.commit_inline():self.orbit_start(event)
    def toggle_focus(self):
        host=self.editor.host;split=host.catalog_panes;attribute=host.catalog_inspector.master
        if getattr(self,'focused',False):
            split.add(attribute,weight=2);split.update_idletasks();split.sashpos(0,self.catalog_sash)
            self.focused=False;self.focus_button.configure(text='拡大')
        else:
            self.catalog_sash=split.sashpos(0);split.forget(attribute)
            self.focused=True;self.focus_button.configure(text='戻す')
