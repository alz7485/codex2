"""Unitless point layout, independent of E3D distances and SCOM values."""
import copy
import tkinter as tk
from tkinter import ttk
from . import element_schema as schema, presets
from .point_geometry import Camera, PLANES, LAYOUT_KEY, axis_vector, schematic_position, schematic_placement


class PointCanvas(ttk.Frame):
    def __init__(self,editor,parent):
        super().__init__(parent);self.editor=editor
        style=ttk.Style(self)
        style.configure('Preview.Toolbutton',padding=(5,3),background='#edf3fa',foreground='#34495e')
        style.map('Preview.Toolbutton',background=[('selected','#2269de'),('active','#dce9fa')],foreground=[('selected','white')])
        self.camera=Camera();self.pending=None;self.hits={};self.positions={};self.dragging=None;self.orbit=None
        self.settings_open=False;self.error_message=''
        self.mode=tk.StringVar(value='選択・移動');self.plane=tk.StringVar(value='XY');self.view=tk.StringVar(value='立体');self.kind=tk.StringVar(value='PTCAR')
        self.show_grid=tk.BooleanVar(value=True);self.show_axes=tk.BooleanVar(value=True);self.show_labels=tk.BooleanVar(value=True)
        self.show_relations=tk.BooleanVar(value=True);self.settings_visible=tk.BooleanVar(value=False)
        self.columnconfigure(0,weight=1);self.rowconfigure(5,weight=1)
        ttk.Label(self,text='3D プレビュー · 仮配置',style='Heading.TLabel').grid(row=0,column=0,sticky='w',pady=(0,8))
        toolbar=ttk.Frame(self);toolbar.grid(row=1,column=0,sticky='ew',pady=(0,6))
        self.mode_buttons=self.toggles(toolbar,self.mode,('選択・移動','点を追加'),self.mode_changed)
        self.settings_button=ttk.Checkbutton(toolbar,text='表示設定',variable=self.settings_visible,command=self.toggle_settings,style='Preview.Toolbutton');self.settings_button.pack(side='right')
        viewbar=ttk.Frame(self);viewbar.grid(row=2,column=0,sticky='ew',pady=(0,6))
        ttk.Label(viewbar,text='配置面',style='Muted.TLabel').pack(side='left',padx=(0,4))
        self.plane_buttons=self.toggles(viewbar,self.plane,tuple(PLANES),self.plane_changed)
        camera_bar=ttk.Frame(self);camera_bar.grid(row=3,column=0,sticky='ew',pady=(0,8))
        ttk.Label(camera_bar,text='視点',style='Muted.TLabel').pack(side='left',padx=(0,16))
        self.view_buttons=self.toggles(camera_bar,self.view,('立体','正面'),self.view_changed)
        self.option_holder=ttk.Frame(self);self.option_holder.grid(row=4,column=0,sticky='ew')
        self.settings_frame=ttk.Frame(self.option_holder);self.display_buttons={}
        for index,(label,var) in enumerate((('グリッド',self.show_grid),('座標軸',self.show_axes),('点番号',self.show_labels),('原点との関係',self.show_relations))):
            button=ttk.Checkbutton(self.settings_frame,text=label,variable=var,command=self.redraw,style='Preview.Toolbutton')
            button.grid(row=index//2,column=index%2,sticky='ew',padx=(0,4),pady=(0,4));self.display_buttons[label]=button
        self.settings_frame.columnconfigure((0,1),weight=1)
        self.add_options=ttk.LabelFrame(self.option_holder,text='追加する点',padding=6);self.kind_buttons={}
        for index,kind in enumerate(schema.PT_TYPES):
            button=ttk.Radiobutton(self.add_options,text=kind,variable=self.kind,value=kind,command=self.new_kind_changed,style='Preview.Toolbutton')
            button.grid(row=0,column=index,sticky='ew');self.kind_buttons[kind]=button
        self.guide=ttk.Label(self.add_options,text='',wraplength=280,style='Muted.TLabel');self.guide.grid(row=1,column=0,columnspan=4,sticky='ew',pady=(4,0))
        self.guide.bind('<Configure>',lambda ev:self.guide.configure(wraplength=max(140,ev.width-4)))
        self.mode.trace_add('write',lambda *_:self.mode_changed())
        self.canvas=tk.Canvas(self,bg='#f3f7fc',highlightthickness=0,width=320,height=260);self.canvas.grid(row=5,column=0,sticky='nsew')
        self.canvas.bind('<Configure>',lambda _:self.redraw());self.canvas.bind('<Button-1>',self.press);self.canvas.bind('<B1-Motion>',self.move);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Button-3>',self.orbit_start);self.canvas.bind('<B3-Motion>',self.orbit_move)
        self.canvas.bind('<MouseWheel>',lambda ev:self.zoom(1.12 if ev.delta>0 else 1/1.12));self.canvas.bind('<Button-4>',lambda _:self.zoom(1.12));self.canvas.bind('<Button-5>',lambda _:self.zoom(1/1.12))
        self.proposal_frame=ttk.LabelFrame(self,text='仮配置の反映内容',padding=8);self.proposal_frame.columnconfigure(0,weight=1)
        self.proposal_label=ttk.Label(self.proposal_frame,text='',wraplength=280);self.proposal_label.grid(row=0,column=0,sticky='ew')
        self.proposal_label.bind('<Configure>',lambda ev:self.proposal_label.configure(wraplength=max(140,ev.width-4)))
        actions=ttk.Frame(self.proposal_frame);actions.grid(row=1,column=0,sticky='ew',pady=(6,0))
        self.apply_button=ttk.Button(actions,text='配置を反映',command=self.apply,style='Primary.TButton',state='disabled');self.apply_button.pack(side='left')
        ttk.Button(actions,text='取消',command=self.cancel).pack(side='left',padx=6)
        self.note=ttk.Label(self,text='',wraplength=280,foreground='#738499');self.note.grid(row=7,column=0,sticky='ew',pady=(6,0))
        self.note.bind('<Configure>',lambda ev:self.note.configure(wraplength=max(140,ev.width-4)))
        hint=ttk.Label(self,text='グリッドに距離・単位はありません。\n左：仮配置 / 右：回転 / ホイール：ズーム\n距離・PARAM式は右の赤枠へ入力します。',wraplength=280,style='Muted.TLabel');hint.grid(row=8,column=0,sticky='ew',pady=(6,0))
        hint.bind('<Configure>',lambda ev:hint.configure(wraplength=max(140,ev.width-4)))
        self.update_guide();self.redraw()

    @staticmethod
    def toggles(parent,variable,values,command):
        buttons={}
        for value in values:
            button=ttk.Radiobutton(parent,text=value,variable=variable,value=value,command=command,style='Preview.Toolbutton')
            button.pack(side='left',padx=(0,2));buttons[value]=button
        return buttons

    def toggle_settings(self):
        self.settings_open=not self.settings_open;self.settings_visible.set(self.settings_open)
        self.settings_frame.pack_forget();self.add_options.pack_forget()
        if self.settings_open:self.settings_frame.pack(fill='x',pady=(0,8))
        elif self.mode.get()=='点を追加':self.add_options.pack(fill='x',pady=(0,8))

    def mode_changed(self):
        self.cancel()
        if self.mode.get()=='点を追加' and not self.settings_open:self.add_options.pack(fill='x',pady=(0,8))
        else:self.add_options.pack_forget()

    def new_kind_changed(self):self.update_guide();self.cancel()
    def update_guide(self):
        guide=schema.PT_GUIDES[self.kind.get()]
        self.guide.configure(text=guide['name']+'\n'+guide['position'])

    def close(self):
        if getattr(self.editor,'point_canvas',None) is self:self.editor.point_canvas=None
        self.destroy()

    def refresh_options(self):self.redraw()

    def redraw(self):
        if not self.winfo_exists():return
        c=self.canvas;c.delete('all');w,h=c.winfo_width(),c.winfo_height();self.hits={};self.positions={}
        def xy(point):return self.camera.project(point,w,h)
        a,b=PLANES[self.plane.get()]
        if self.show_grid.get():
            for i in range(-8,9):
                for first,second in ((a,b),(b,a)):
                    p=[0,0,0];p[first]=i*.25;p[second]=-2;q=p.copy();q[second]=2
                    c.create_line(*xy(p),*xy(q),fill='#dee7f0',tags=('grid',))
        origin=xy((0,0,0));c.create_oval(origin[0]-4,origin[1]-4,origin[0]+4,origin[1]+4,fill='#34495e',outline='')
        c.create_text(origin[0]+8,origin[1]+10,text='P0 · 原点',anchor='w',fill='#56677a')
        if self.show_axes.get():
            for index,color in enumerate(('#df6258','#42a47d','#3877d7')):
                for sign in (-1,1):
                    p=[0,0,0];p[index]=sign*1.8;end=xy(p)
                    c.create_line(*origin,*end,fill=color,width=2 if sign>0 else 1,arrow='last',tags=('axes',))
                    c.create_text(end[0]+8,end[1],text=('+' if sign>0 else '−')+'XYZ'[index],fill=color,tags=('axes',))
        definition=self.editor.definition()
        for index,element in enumerate((definition or {}).get('elements',[])):
            if element['type'] not in schema.PT_TYPES:continue
            point=schematic_position(element,index);self.positions[element['id']]=point;x,y=xy(point);self.hits[element['id']]=(x,y)
            selected=element['id']==self.editor.element_id;color='#2269de' if selected else '#657c94';r=7 if selected else 5
            if self.show_relations.get():c.create_line(*origin,x,y,fill='#b3c4d8',dash=(3,4),tags=('relations',))
            c.create_oval(x-r,y-r,x+r,y+r,fill=color,outline='white',width=2)
            if self.show_labels.get():c.create_text(x+11,y-10,text='P'+str(element['attrs'].get('NUMB','?')),anchor='w',fill=color,tags=('labels',))
            try:
                vector=axis_vector(schema.value(element,'PAXI' if element['type'] in ('PTAXI','PTMIX') else 'PTCDIR'))
                c.create_line(x,y,*xy(tuple(point[i]+.25*vector[i] for i in range(3))),fill=color,arrow='last')
            except ValueError:pass
        message='模式表示：配置は距離・寸法比を表しません。'
        if not definition:message='左の PTSET 一覧からセットを選ぶか追加してください。'
        self.note.configure(text=self.error_message or message,foreground='#ad6536' if self.error_message else '#738499')
        if self.pending:
            x,y=xy(self.pending['point']);c.create_oval(x-9,y-9,x+9,y+9,outline='#dc9431',width=3)
            c.create_text(x+13,y+10,text='候補',anchor='w',fill='#b27324')
            c.create_window(8,h-8,window=self.proposal_frame,anchor='sw',width=max(160,w-16))

    def plane_changed(self):
        if self.view.get()=='正面':self.camera.face(self.plane.get())
        self.cancel()
    def view_changed(self):
        self.camera=Camera()
        if self.view.get()=='正面':self.camera.face(self.plane.get())
        self.redraw()
    def face(self):self.view.set('正面');self.view_changed()
    def reset_view(self):self.view.set('立体');self.view_changed()
    def zoom(self,factor):self.camera.zoom=max(25,min(600,self.camera.zoom*factor));self.redraw()
    def orbit_start(self,event):self.orbit=(event.x,event.y,self.camera.yaw,self.camera.pitch)
    def orbit_move(self,event):
        if self.orbit:
            self.view.set('立体');x,y,yaw,pitch=self.orbit;self.camera.yaw=yaw+(event.x-x)*.5;self.camera.pitch=max(-85,min(85,pitch+(event.y-y)*.5));self.redraw()

    def pick(self,x,y):return next((ident for ident,point in sorted(self.hits.items(),key=lambda item:(item[1][0]-x)**2+(item[1][1]-y)**2) if (point[0]-x)**2+(point[1]-y)**2<=144),None)
    def press(self,event):
        self.dragging=None
        if self.mode.get()=='点を追加':self.propose(event.x,event.y);return
        ident=self.pick(event.x,event.y)
        if ident:
            if not self.editor.commit_inline():return
            self.cancel();self.editor.elements.selection_set(ident);self.editor.select_element();self.dragging=ident;self.redraw()
    def move(self,event):
        if self.dragging:self.propose(event.x,event.y,self.dragging)
    def release(self,event):self.dragging=None

    def propose(self,x,y,ident=None):
        e=self.editor;self.error_message=''
        try:
            if not e.definition():raise ValueError('先に PTSET を作成してください。')
            if not e.commit_inline():return
            plane=self.plane.get();perpendicular=next(i for i in range(3) if i not in PLANES[plane])
            element=next((r for r in e.definition()['elements'] if r['id']==ident),None)
            if ident and not element:raise ValueError('要素が変更されています。選択し直してください。')
            fixed=self.positions[ident][perpendicular] if element else 0
            point=self.camera.unproject(x,y,self.canvas.winfo_width(),self.canvas.winfo_height(),plane,fixed)
            kind=element['type'] if element else self.kind.get()
            point,attrs=schematic_placement(kind,point,element['attrs'] if element else None,plane if element else None)
            base=copy.deepcopy(element['attrs']) if element else None
            layout=copy.deepcopy(element.get(LAYOUT_KEY)) if element else None
            if self.pending and self.pending['id']==ident and ident:base=self.pending['base'];layout=self.pending['layout']
            self.pending={'id':ident,'base':base,'layout':layout,'attrs':attrs,'point':point,'kind':kind,'preset':presets.selected_id(e.data,e.definition()),'definition':e.definition_id}
            combined={**(base or schema.default_attrs(kind)),**attrs};missing=schema.missing_fields({'type':kind,'attrs':combined})
            changes=' / '.join(k+' '+v for k,v in attrs.items() if v)
            relation='・'.join(('+' if v>0 else '−')+'XYZ'[i] for i,v in enumerate(point) if v) or '原点'
            text=('移動：'+element['name'] if element else '新規：'+kind)+' · '+relation
            if changes:text+='\n反映：'+changes
            if missing:text+='\n右で入力：'+'・'.join(missing)
            text+='\n距離は算出しません。距離式は右で指定します。'
            self.proposal_label.configure(text=text);self.apply_button.configure(state='normal');self.redraw()
        except (ValueError,KeyError) as exc:self.error_message=str(exc);self.pending=None;self.apply_button.configure(state='disabled');self.redraw()

    def cancel(self):
        self.error_message='';self.pending=None;self.dragging=None;self.apply_button.configure(state='disabled');self.proposal_label.configure(text='');self.redraw()
    def apply(self):
        if not self.pending:return
        p=self.pending;e=self.editor
        try:
            if not e.commit_inline():return
            if p['definition']!=e.definition_id or p['preset']!=presets.selected_id(e.data,e.definition()):raise ValueError('セット・プリセットが変更されています。候補を作り直してください。')
            if p['id']:
                element=next((r for r in e.definition()['elements'] if r['id']==p['id']),None)
                if not element or element['attrs']!=p['base'] or element.get(LAYOUT_KEY)!=p['layout']:raise ValueError('属性・配置が変更されています。候補を作り直してください。')
            else:element=schema.add_element(e.definition(),p['kind'])
            element['attrs'].update(p['attrs']);element[LAYOUT_KEY]=list(p['point'])
            e.element_id=element['id'];e.field=None;e.select_first_section();e.host.mark();self.pending=None;e.refresh();self.cancel()
            missing=schema.missing_fields(element)
            if missing:e.tables['main'].selection_set(missing[0]);e.tables['main'].see(missing[0])
        except ValueError as exc:self.error_message=str(exc);self.redraw()
