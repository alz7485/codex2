"""Combined GMSET / PTSET preview with draft-only resize handles."""
import copy
import math
import tkinter as tk
from tkinter import ttk
from PIL import ImageTk
from . import geometry_scene as geometry, project, theme
from .surface_render import alpha_surface, inside_polygon, feature_edges
from . import geometry_preview, representation, model_settings, element_schema as schema


class GeometryCanvas(ttk.Frame):
    def __init__(self,editor,parent):
        super().__init__(parent);self.editor=editor;self.camera=geometry.FitCamera();self.scene=geometry.Scene()
        self.mode=tk.StringVar(value='仮サイズ');self.view=tk.StringVar(value='立体')
        self.plane=tk.StringVar(value='XY');self.view_mode=tk.StringVar(value='立体')
        self.show_grid=tk.BooleanVar(value=True);self.show_axes=tk.BooleanVar(value=True)
        self.show_labels=tk.BooleanVar(value=True)
        self.show_points=tk.BooleanVar(value=True);self.show_negative=tk.BooleanVar(value=True)
        settings=getattr(editor.host,'gmset_display_settings',{})
        rep=getattr(editor.host,'gmset_representation',{})
        self.representation_mode=tk.StringVar(value=rep.get('mode','全形状'))
        self.rep_options=dict(tube=rep.get('tube',True),cl=rep.get('cl',False),obst=rep.get('obst',False),level=rep.get('level',0),obst_bypass=rep.get('obst_bypass',False))
        self.render_mode=tk.StringVar(value=settings.get('mode','ソリッド'))
        self.transparency=tk.DoubleVar(value=settings.get('transparency',0))
        self.render_job=None;self.surface_image=None;self.surface_bitmap=None;self.pick_faces=[]
        self.drag=None;self.orbit=None;self.handles={};self.screen_points={};self.refreshing=False;self.resize_issue=''
        self.columnconfigure(0,weight=1);self.rowconfigure(3,weight=1)
        controls=ttk.Frame(self);controls.grid(row=0,column=0,sticky='ew',pady=(0,4));controls.columnconfigure(0,weight=1)
        self.control_viewport=tk.Canvas(controls,width=1,height=1,highlightthickness=0,bg=theme.SURFACE)
        self.control_viewport.grid(row=0,column=0,sticky='ew')
        self.control_scroll=ttk.Scrollbar(controls,orient='horizontal',command=self.control_viewport.xview)
        self.control_viewport.configure(xscrollcommand=self.control_scroll.set)
        self.control_row=ttk.Frame(self.control_viewport)
        self.control_window=self.control_viewport.create_window(0,0,anchor='nw',window=self.control_row)
        self.control_groups={}
        for title in ('基準面','視点','表示'):
            group=ttk.LabelFrame(self.control_row,text=title,padding=(4,3))
            group.pack(side='left',fill='y',padx=(0,6));self.control_groups[title]=group
        self.plane_buttons=self.toggles(self.control_groups['基準面'],self.plane,('XY','XZ','YZ'),self.plane_changed)
        self.view_buttons=self.toggles(self.control_groups['視点'],self.view_mode,('立体','正面'),self.choose_view)
        self.overlay_buttons={}
        for label,var in (('グリッド',self.show_grid),('座標軸',self.show_axes),('点番号',self.show_labels)):
            button=ttk.Checkbutton(self.control_groups['表示'],text=label,variable=var,command=self.redraw,style='Preview.Toolbutton')
            button.pack(side='left',padx=(0,2));self.overlay_buttons[label]=button
        self.control_row.bind('<Configure>',self.fit_controls);self.control_viewport.bind('<Configure>',self.fit_controls)
        row=ttk.Frame(self);row.grid(row=1,column=0,sticky='ew',pady=(0,3))
        mode_row=ttk.Frame(row);mode_row.pack(fill='x')
        self.mode_buttons=self.toggles(mode_row,self.mode,('仮サイズ','SCOM 実寸'),self.mode_changed)
        for key,label in (('仮サイズ','仮配置で確認'),('SCOM 実寸','登録寸法で確認')):
            self.mode_buttons[key].configure(text=label)
        scom_row=ttk.Frame(row);scom_row.pack(fill='x',pady=(2,0))
        ttk.Label(scom_row,text='参照SCOM',style='Muted.TLabel').pack(side='left',padx=(0,6))
        self.scom_choice=ttk.Combobox(scom_row,state='readonly',width=10);self.scom_choice.pack(side='left',fill='x',expand=True)
        self.scom_choice.bind('<<ComboboxSelected>>',self.select_scom)
        display=ttk.Frame(self);display.grid(row=2,column=0,sticky='ew',pady=(0,3))
        self.display_buttons={}
        for label in ('ソリッド','ワイヤー','面＋線'):
            button=ttk.Radiobutton(display,text=label,variable=self.render_mode,value=label,command=lambda:self.display_changed(immediate=True),style='Preview.Toolbutton')
            button.pack(side='left',padx=(0,3));self.display_buttons[label]=button
        self.details_button=ttk.Button(display,text='詳細表示…',command=self.open_details,style='Compact.TButton')
        self.details_button.pack(side='left',padx=(4,0))
        self.details=tk.Toplevel(self);self.details.withdraw();self.details.title('プレビューの詳細表示')
        self.details.transient(editor.host);self.details.resizable(False,False)
        self.details.protocol('WM_DELETE_WINDOW',self.details.withdraw)
        details=ttk.Frame(self.details,padding=16);details.pack(fill='both',expand=True)
        ttk.Label(details,text='プレビューの詳細表示',style='Heading.TLabel').grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,10))
        overlays=ttk.Frame(details);overlays.grid(row=1,column=0,columnspan=3,sticky='w',pady=(0,10))
        for label,var in (('接続点・方向矢印',self.show_points),('負形状',self.show_negative)):
            ttk.Checkbutton(overlays,text=label,variable=var,command=self.redraw,style='Preview.Toolbutton').pack(side='left',padx=(0,6))
        ttk.Label(details,text='透過率').grid(row=2,column=0,sticky='w')
        self.transparency_scale=ttk.Scale(details,from_=0,to=100,variable=self.transparency,length=180)
        self.transparency_scale.grid(row=2,column=1,sticky='ew',padx=8)
        self.transparency_label=ttk.Label(details,text='0%',width=5,style='Muted.TLabel');self.transparency_label.grid(row=2,column=2)
        ttk.Label(details,text='描画対象').grid(row=3,column=0,sticky='w',pady=10)
        self.representation_choice=ttk.Combobox(details,state='readonly',width=12,textvariable=self.representation_mode,values=('全形状','属性確認'))
        self.representation_choice.grid(row=3,column=1,sticky='w',padx=8)
        self.representation_choice.bind('<<ComboboxSelected>>',lambda _:self.representation_changed())
        actions=ttk.Frame(details);actions.grid(row=4,column=0,columnspan=3,sticky='ew')
        ttk.Button(actions,text='表示条件',command=lambda:representation.edit(self),style='Compact.TButton').pack(side='left')
        ttk.Button(actions,text='設計値',command=lambda:model_settings.edit(editor),style='Compact.TButton').pack(side='left',padx=6)
        ttk.Button(actions,text='閉じる',command=self.details.withdraw,style='Compact.TButton').pack(side='right')
        self.transparency.trace_add('write',self.display_changed)
        self.canvas=tk.Canvas(self,bg=theme.SUBTLE,highlightthickness=1,highlightbackground=theme.BORDER,width=1,height=1)
        self.canvas.grid(row=3,column=0,sticky='nsew')
        self.note=ttk.Label(self,text='',style='Muted.TLabel',wraplength=360);self.note.grid(row=4,column=0,sticky='ew',pady=(6,0))
        self.note.bind('<Configure>',lambda e:self.note.configure(wraplength=max(120,e.width-4)))
        self.issue_label=ttk.Label(self,text='',foreground='#a15c24',wraplength=360);self.issue_label.grid(row=5,column=0,sticky='ew',pady=(4,0))
        self.issue_label.bind('<Configure>',lambda e:self.issue_label.configure(wraplength=max(120,e.width-4)))
        self.canvas.bind('<Configure>',lambda _:self.redraw())
        self.canvas.bind('<Button-1>',self.press);self.canvas.bind('<B1-Motion>',self.move);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Button-3>',self.orbit_start);self.canvas.bind('<B3-Motion>',self.orbit_move)
        self.canvas.bind('<ButtonRelease-3>',lambda _:setattr(self,'orbit',None));self.canvas.bind('<Escape>',lambda _:self.cancel())
        self.bind('<Destroy>',lambda e:self.dispose() if e.widget is self else None)

    @staticmethod
    def toggles(parent,variable,values,command):
        buttons={}
        for value in values:
            button=ttk.Radiobutton(parent,text=value,variable=variable,value=value,command=command,style='Preview.Toolbutton')
            button.pack(side='left',padx=(0,2));buttons[value]=button
        return buttons

    def fit_controls(self,_=None):
        width,height=self.control_row.winfo_reqwidth(),self.control_row.winfo_reqheight()
        visible=self.control_viewport.winfo_width()
        self.control_viewport.configure(height=height,scrollregion=(0,0,max(width,visible),height))
        self.control_viewport.itemconfigure(self.control_window,width=max(width,visible))
        if width>visible:self.control_scroll.grid(row=1,column=0,sticky='ew')
        else:self.control_scroll.grid_remove();self.control_viewport.xview_moveto(0)

    def choose_view(self):
        self.view.set('立体' if self.view_mode.get()=='立体' else self.plane.get())
        self.view_changed()

    def plane_changed(self):
        self.view_mode.set('正面');self.choose_view()

    def open_details(self):
        self.details.deiconify();self.details.lift()

    def sync_display_controls(self):
        self.transparency_label.configure(text=f'{round(self.transparency.get())}%')
        self.transparency_scale.configure(state='disabled' if self.render_mode.get()=='ワイヤー' else 'normal')

    def representation_settings(self):return dict(self.rep_options,mode=self.representation_mode.get())

    def representation_changed(self):
        self.cancel(redraw=False)
        self.editor.host.gmset_representation=self.representation_settings();self.redraw()

    def display_changed(self,*_,immediate=False):
        self.sync_display_controls()
        self.editor.host.gmset_display_settings={'mode':self.render_mode.get(),'transparency':self.transparency.get()}
        if self.render_job:self.after_cancel(self.render_job);self.render_job=None
        if immediate:self.redraw()
        else:self.render_job=self.after(35,self.redraw)

    def dispose(self):
        if self.render_job:self.after_cancel(self.render_job);self.render_job=None
        self.cancel(redraw=False);self.surface_image=None;self.surface_bitmap=None

    @property
    def actual(self):return self.mode.get()=='SCOM 実寸'

    def refresh_options(self):
        definition=self.editor.definition();ident=(definition or {}).get('id')
        self.scom_options={'SCOM を選択':''}
        for scom in self.editor.data['scoms']:
            if scom.get('gmset_id')==ident:self.scom_options[scom['name']]=scom['id']
        self.scom_choice['values']=list(self.scom_options)
        current=self.editor.preview_scom_id
        self.scom_choice.set(next((name for name,ident in self.scom_options.items() if ident==current),'SCOM を選択'))
        self.scom_choice.configure(state='readonly' if len(self.scom_options)>1 else 'disabled')

    def select_scom(self,_=None):
        self.cancel(redraw=False)
        self.editor.preview_scom_id=self.scom_options.get(self.scom_choice.get()) or None
        self.mode.set('SCOM 実寸' if self.editor.preview_scom_id else '仮サイズ')
        self.editor.scom_choice.set(self.scom_choice.get() if self.editor.preview_scom_id else '')
        self.editor.refresh_values();self.editor.update_validation();self.redraw()

    def mode_changed(self):self.cancel(redraw=False);self.redraw()

    def view_changed(self):
        self.cancel(redraw=False)
        self.view_mode.set('立体' if self.view.get()=='立体' else '正面')
        if self.view.get()!='立体':self.plane.set(self.view.get())
        if self.view.get()=='立体':self.camera.yaw,self.camera.pitch=40,30
        else:self.camera.face(self.view.get())
        self.redraw()

    def redraw(self):
        if self.render_job:self.after_cancel(self.render_job);self.render_job=None
        if not self.winfo_exists() or self.refreshing:return
        self.refreshing=True
        try:self._redraw()
        finally:self.refreshing=False

    def _redraw(self):
        e=self.editor;c=self.canvas;c.delete('all');self.handles={};self.screen_points={};self.refresh_options();self.sync_display_controls()
        self.surface_image=None;self.surface_bitmap=None;self.pick_faces=[]
        scom=project.get(e.data,'scoms',e.preview_scom_id)
        definition=e.definition()
        if self.drag and self.drag['context']!=geometry_preview.context(e.data,definition):
            self.drag=None;self.resize_issue='属性・PTSET・共有仮値が変更されています。ハンドルを選び直してください。'
        if self.drag and self.drag.get('candidate'):
            definition=copy.deepcopy(definition)
            node=next((n for n in schema.walk(definition['elements']) if n['id']==self.drag['node']['id']),None)
            if node:node[geometry.SCALE_KEY]=self.drag['candidate']
        self.scene=geometry.build_scene(e.data,definition,scom,self.actual,preview_state=self.drag.get('candidate_state') if self.drag else None,representation_settings=self.representation_settings())
        meshes=[m for m in self.scene.meshes if not m.negative or self.show_negative.get()]
        width,height=max(c.winfo_width(),100),max(c.winfo_height(),100)
        vertices=[p for m in meshes for p in m.vertices]+([p[0] for p in self.scene.points.values()] if self.show_points.get() else [])
        if not self.drag:self.camera.fit(vertices,width,height,padding=55)
        def xy(point):return self.camera.project(point,width,height)
        # A fixed screen grid provides depth cues without claiming a distance scale.
        if self.show_grid.get():
            for x in range(20,width,32):c.create_line(x,0,x,height,fill='#e9eef6',tags='grid')
            for y in range(20,height,32):c.create_line(0,y,width,y,fill='#e9eef6',tags='grid')
        right,up=self.camera.basis()
        if self.show_axes.get():
            for i,color in enumerate(('#d85d59','#34986a','#387bd4')):
                x,y=42+28*right[i],height-42-28*up[i]
                c.create_line(42,height-42,x,y,fill=color,arrow='last',width=2,tags='orientation')
                c.create_text(x+7,y,text='XYZ'[i],fill=color,tags='orientation')
        faces=[];negative=[]
        for mesh in meshes:
            selected=mesh.ident==e.element_id or self.parent_selected(mesh.ident)
            outline=theme.ACCENT if selected else '#58799b';fill='#a9caef' if selected else '#cfdeed'
            for face in mesh.faces:
                if len(face)<3:continue
                points=[mesh.vertices[i] for i in face]
                normal=geometry.cross(geometry.sub(points[1],points[0]),geometry.sub(points[2],points[0]))
                length=math.hypot(*normal);light=abs(geometry.dot(geometry.mul(normal,1/length),(0.3,-.4,.86))) if length else .5
                shade=min(1,.68+.3*light)
                rgb=tuple(int(fill[i:i+2],16) for i in (1,3,5));color='#' + ''.join(f'{int(v*shade):02x}' for v in rgb)
                faces.append((sum(self.camera.depth(p) for p in points)/len(points),mesh,face,color,outline))
            if mesh.negative:negative.append(mesh)
        ordered=sorted(faces,key=lambda f:f[0]);mode=self.render_mode.get();opacity=1-max(0,min(100,self.transparency.get()))/100
        polygons=[]
        for _,mesh,face,fill,outline in ordered:
            if mesh.negative:continue
            points=[xy(mesh.vertices[i]) for i in face]
            self.pick_faces.append((points,mesh.ident))
            if mesh.ident in self.scene.soft:continue
            if mode=='ワイヤー':continue
            polygons.append((points,fill))
            if opacity==1:c.create_polygon(*(v for p in points for v in p),fill=fill,outline='',width=1,tags=('mesh','element:'+mesh.ident,'surface'))
            else:c.create_polygon(*(v for p in points for v in p),fill='',outline='',tags=('mesh','element:'+mesh.ident,'surface-hit'))
        if mode!='ワイヤー' and 0<opacity<1 and polygons:
            self.surface_bitmap=alpha_surface((width,height),polygons,opacity)
            self.surface_image=ImageTk.PhotoImage(self.surface_bitmap,master=c)
            c.create_image(0,0,anchor='nw',image=self.surface_image,tags='transparent-surface')
        if mode in ('ワイヤー','面＋線') or self.scene.soft:
            for mesh in meshes:
                if mesh.negative:continue
                if mode not in ('ワイヤー','面＋線') and mesh.ident not in self.scene.soft:continue
                color=theme.ACCENT if mesh.ident==e.element_id or self.parent_selected(mesh.ident) else '#58799b'
                edges=feature_edges(mesh,geometry.cross(*self.camera.basis()),visible_only=(mode=='面＋線' and opacity==1))
                for a,b in edges:c.create_line(*xy(mesh.vertices[a]),*xy(mesh.vertices[b]),fill=color,width=1,dash=(4,3) if mesh.ident in self.scene.soft else (),tags=('mesh','wireframe','element:'+mesh.ident))
        for mesh in meshes:
            for line in mesh.lines:
                c.create_line(*(v for i in line for v in xy(mesh.vertices[i])),fill=theme.ACCENT,width=2,tags=('mesh','element:'+mesh.ident))
        # Negative volumes stay visible as orange wireframes; no Boolean cut is claimed.
        for mesh in negative:
            edges=feature_edges(mesh,geometry.cross(*self.camera.basis()))
            for a,b in edges:c.create_line(*xy(mesh.vertices[a]),*xy(mesh.vertices[b]),fill='#c7812e',dash=(4,3),tags=('negative','element:'+mesh.ident))
        if self.show_points.get():
            for number,(point,direction,name) in self.scene.points.items():
                x,y=xy(point);self.screen_points[number]=(x,y)
                end=xy(geometry.add(point,geometry.mul(direction,self.camera.span*.08)))
                # Keep arrow glyphs and labels within the viewport at fitted extremities.
                c.create_line(x,y,max(12,min(width-12,end[0])),max(12,min(height-12,end[1])),fill='#237c74',arrow='last',width=2,tags='point-direction')
                c.create_oval(x-4,y-4,x+4,y+4,fill='#167b73',outline='white',tags=('point','point:'+str(number)))
                if self.show_labels.get():c.create_text(x+8,y-10,text='P'+str(number),anchor='w',fill='#176e68',font=(e.host.ui_font,9),tags='point-label')
        chosen=next((m for m in meshes if m.ident==e.element_id),None)
        if chosen and chosen.vertices and not self.actual:self.draw_handles(chosen,xy)
        if not meshes:
            c.create_text(width/2,height/2,text='表示できる形状がありません。\n属性・PTSET・SCOM を確認してください。' if (e.definition() or {}).get('elements') else '形状を追加してください。',fill=theme.MUTED,width=max(100,width-60),tags='empty')
        dimensions=''
        if self.actual and meshes:
            points=[p for m in meshes for p in m.vertices]
            dimensions='\n外形：'+' / '.join('XYZ'[i]+' '+format(max(p[i] for p in points)-min(p[i] for p in points),'.5g') for i in range(3))+' mm（DB 単位）'
        self.note.configure(text=('登録寸法で確認：寸法比を保持して全体表示 / 右ドラッグ：回転'+dimensions if self.actual else '仮配置で確認：どの形状のハンドルからも同じ PARAM を更新\n対応する PTSET の点・他の形状も追従 / 距離・単位なし\n属性・PARAM 式は保持 / 右ドラッグ：回転')+'\n負形状は橙色の輪郭で重ねて表示します。')
        status=('登録寸法で確認 · '+(scom['name'] if scom else '参照SCOMを選択してください')) if self.actual else '仮配置で確認 · 編集用の仮値'
        c.create_text(12,12,text=status,anchor='nw',fill=theme.MUTED,width=max(100,width-24),font=(e.host.ui_font,9),tags='preview-mode')
        hidden=self.scene.hidden
        selected_reason=hidden.get(e.element_id)
        messages=([selected_reason] if selected_reason else [])+self.scene.issues+([self.resize_issue] if self.resize_issue else [])
        if hidden:messages.append('表示条件による非表示：'+str(len(hidden))+' 件。要素一覧で選ぶと理由を表示します。')
        self.issue_label.configure(text=('表示できない項目：'+str(len(messages))+' 件\n'+'\n'.join(messages[:2])+ ('\nほか '+str(len(messages)-2)+' 件' if len(messages)>2 else '')) if messages else '')

    def parent_selected(self,ident):
        definition=self.editor.definition() or {}
        node=next((n for n in definition.get('elements',[]) if n['id']==ident),None)
        if not node:return False
        from .element_schema import walk
        return any(n['id']==self.editor.element_id for n in walk(node.get('children',[])))

    def draw_handles(self,mesh,xy):
        lo=[min(p[i] for p in mesh.vertices) for i in range(3)];hi=[max(p[i] for p in mesh.vertices) for i in range(3)]
        center=[a/2+b/2 for a,b in zip(lo,hi)]
        for i,color in enumerate(('#d85d59','#34986a','#387bd4')):
            if hi[i]-lo[i]<=1e-12:continue
            end=center.copy();end[i]=hi[i];x,y=xy(end);start=xy(center)
            self.canvas.create_line(*start,x,y,fill=color,width=2,tags='resize-guide')
            self.canvas.create_rectangle(x-5,y-5,x+5,y+5,fill='white',outline=color,width=2,tags=('resize','handle:'+str(i)))
            self.canvas.create_text(x+8,y+10,text='XYZ'[i],fill=color,anchor='w',tags='resize-label')
            self.handles[i]={'screen':(x,y),'start':start,'extent':hi[i]-lo[i]}

    def press(self,event):
        self.canvas.focus_set()
        if not self.editor.commit_inline():return
        self.resize_issue=''
        if not self.actual:
            hit=next((i for i,h in self.handles.items() if math.hypot(event.x-h['screen'][0],event.y-h['screen'][1])<=10),None)
            if hit is not None:
                node=self.editor.element();handle=self.handles[hit]
                self.drag={'data':self.editor.data,'definition':self.editor.definition_id,'node':node,'axis':hit,'origin':(event.x,event.y),'screen':handle['screen'],'center':handle['start'],'extent':handle['extent'],'old':copy.deepcopy(node.get(geometry.SCALE_KEY)),'scale':list(node.get(geometry.SCALE_KEY,(1,1,1))),
                           'context':geometry_preview.context(self.editor.data,self.editor.definition()),'state':self.scene.preview.snapshot()}
                return
        hits=self.canvas.find_overlapping(event.x-3,event.y-3,event.x+3,event.y+3)
        for item in reversed(hits):
            ident=next((t[8:] for t in self.canvas.gettags(item) if t.startswith('element:')),None)
            if ident:
                self.editor.elements.selection_set(ident);self.editor.select_element();return
        if self.render_mode.get()!='ワイヤー':
            for points,ident in reversed(self.pick_faces):
                if inside_polygon(event.x,event.y,points):
                    self.editor.elements.selection_set(ident);self.editor.select_element();return

    def move(self,event):
        if not self.drag:return
        d=self.drag
        if self.actual or d['data'] is not self.editor.data or d['definition']!=self.editor.definition_id:self.cancel();return
        if d['context']!=geometry_preview.context(self.editor.data,self.editor.definition()):
            self.drag=None;self.resize_issue='属性・PTSET・共有仮値が変更されています。ハンドルを選び直してください。';self.redraw();return
        vector=(d['screen'][0]-d['center'][0],d['screen'][1]-d['center'][1]);length=math.hypot(*vector)
        if length<4:return
        delta=((event.x-d['origin'][0])*vector[0]+(event.y-d['origin'][1])*vector[1])/length
        ratio=max(.05,min(50,1+delta/length))
        try:
            preview=geometry_preview.GeometryPreview(self.editor.data,self.editor.definition(),d['state'])
            state=preview.resize(d['node']['id'],d['axis'],d['extent']*ratio)
            if state is None:
                if preview.has_dimensions(d['node']):raise ValueError('この軸の寸法には変更できる PARAM がありません。別のハンドルを選んでください。')
                scale=list(d['scale']);scale[d['axis']]=max(.02,min(50,scale[d['axis']]*ratio));d['candidate']=scale;d.pop('candidate_state',None)
            else:d['candidate_state']=state;d.pop('candidate',None)
            self.resize_issue=''
        except (ValueError,OverflowError) as exc:
            d.pop('candidate',None);d.pop('candidate_state',None);self.resize_issue=str(exc)
        self.redraw()

    def release(self,_=None):
        if not self.drag:return
        d=self.drag;self.drag=None
        if d['data'] is self.editor.data and d['definition']==self.editor.definition_id and any(n is d['node'] for n in schema.walk((self.editor.definition() or {}).get('elements',[]))):
            if d['context']!=geometry_preview.context(self.editor.data,self.editor.definition()):
                self.resize_issue='属性・PTSET・共有仮値が変更されています。ハンドルを選び直してください。'
            elif d.get('candidate_state') is not None and d['candidate_state']!=d['state']:
                geometry_preview.store(self.editor.data,self.editor.definition(),d['candidate_state'])
                self.editor.host.mark('PARAM の共有仮値を更新しました。点と形状に反映しています。')
            elif d.get('candidate') is not None and d['candidate']!=d['old']:
                d['node'][geometry.SCALE_KEY]=d['candidate']
                self.editor.host.mark('仮のサイズを変更しました。PARAM 式・SCOM の値は保持しています。')
        self.redraw()

    def cancel(self,redraw=True):
        self.drag=None;self.resize_issue=''
        if redraw and self.winfo_exists():self.redraw()

    def orbit_start(self,event):self.orbit=(event.x,event.y,self.camera.yaw,self.camera.pitch)
    def orbit_move(self,event):
        if not self.orbit:return
        x,y,yaw,pitch=self.orbit;self.camera.yaw=yaw+(event.x-x)*.5;self.camera.pitch=max(-89,min(89,pitch+(event.y-y)*.5))
        self.view.set('立体');self.view_mode.set('立体');self.redraw()
