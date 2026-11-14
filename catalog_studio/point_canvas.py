"""Point direction rotation and attribute-driven unitless PARAM preview."""
import copy
import math
import tkinter as tk
from tkinter import ttk
from . import element_schema as schema, presets, expressions
from .point_geometry import Camera, PLANES, LAYOUT_KEY, DIMENSIONS_KEY, schematic_position, schematic_placement
from .point_preview import PointPreview, empty, remember
from . import theme, preview_controls, preview_colors


class PointCanvas(ttk.Frame):
    def __init__(self,editor,parent):
        super().__init__(parent);self.editor=editor
        self.camera=Camera();self.pending=None;self.hits={};self.positions={};self.direction_hits={};self.dragging=None;self.orbit=None
        self.error_message='';self.menu_context=None;self.press_position=None;self.rotation_start=None;self.rotation_step=90;self.last_rotation_pixel=None;self.control_down=False;self.drag_mode=None;self.move_state=None
        self.plane=tk.StringVar(value='XY');self.view=tk.StringVar(value='立体')
        self.show_grid=tk.BooleanVar(value=True);self.show_axes=tk.BooleanVar(value=True)
        self.show_labels=tk.BooleanVar(value=True);self.show_relations=tk.BooleanVar(value=True)
        self.columnconfigure(0,weight=1);self.rowconfigure(3,weight=1)
        preview_controls.build(self,0)
        self.display_buttons={}
        for label,var in (('グリッド',self.show_grid),('座標軸',self.show_axes),('点番号',self.show_labels),('関係線',self.show_relations)):
            button=ttk.Checkbutton(self.settings_content,text=label,variable=var,command=self.redraw,style='Preview.Toolbutton')
            button.pack(anchor='w',fill='x',pady=2);self.display_buttons[label]=button
        self.selection_label=ttk.Label(self,text='選択：なし',style='Muted.TLabel');self.selection_label.grid(row=4,column=0,sticky='w',pady=(6,0))
        self.plane_overlay=plane_row=ttk.Frame(self.body,padding=4)
        plane_row.grid(row=0,column=0,sticky='nw',padx=8,pady=8)
        ttk.Label(plane_row,text='作図面 (F5)',style='Muted.TLabel').pack(side='left',padx=(0,6))
        self.plane_buttons={}
        for plane in PLANES:
            button=ttk.Radiobutton(plane_row,text=plane,image=self.preview_icons[plane],compound='left',variable=self.plane,value=plane,command=self.plane_changed,style='Preview.Toolbutton')
            button.pack(side='left',padx=(0,2));self.plane_buttons[plane]=button
        self.unit_label=ttk.Label(self.body,text='仮配置・単位なし',style='Muted.TLabel')
        self.unit_label.grid(row=0,column=0,sticky='sw',padx=10,pady=10)
        self.context_menu=tk.Menu(self,tearoff=False)
        self.create_menu=tk.Menu(self.context_menu,tearoff=False)
        for kind in schema.PT_TYPES:
            self.create_menu.add_command(label=kind+'：'+schema.PT_GUIDES[kind]['name'],command=lambda selected=kind:self.create_at_menu(selected))
        self.context_menu.add_cascade(label='点を作成',menu=self.create_menu)
        self.context_menu.add_separator();self.context_menu.add_command(label='閉じる',command=self.dismiss_menu)
        self.canvas=tk.Canvas(self.body,bg=theme.SUBTLE,highlightthickness=1,highlightbackground=theme.BORDER,highlightcolor=theme.ACCENT,width=320,height=260);self.canvas.grid(row=0,column=0,sticky='nsew')
        plane_row.lift();self.unit_label.lift()
        preview_controls.zoom_buttons(self)
        self.canvas.bind('<Configure>',lambda _:self.redraw());self.canvas.bind('<Button-1>',self.press);self.canvas.bind('<B1-Motion>',self.move);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Button-3>',self.create_press)
        self.canvas.bind('<MouseWheel>',lambda ev:self.zoom(1.12 if ev.delta>0 else 1/1.12));self.canvas.bind('<Button-4>',lambda _:self.zoom(1.12));self.canvas.bind('<Button-5>',lambda _:self.zoom(1/1.12))
        self.note=ttk.Label(self,text='',wraplength=280,foreground='#738499');self.note.grid(row=5,column=0,sticky='ew',pady=(6,0))
        self.note.bind('<Configure>',lambda ev:self.note.configure(wraplength=max(140,ev.width-4)))
        hint=ttk.Label(self,text='ホイールドラッグ：回転 / ホイールクリック：パン ｜ 点ドラッグ：90° / Alt中5° / Ctrl中は移動 ｜ 右クリック：点作成 ｜ ホイール：ズーム',wraplength=280,style='Muted.TLabel');hint.grid(row=6,column=0,sticky='ew',pady=(6,0))
        hint.bind('<Configure>',lambda ev:hint.configure(wraplength=max(140,ev.width-4)))
        for key in ('Alt_L','Alt_R'):
            self.canvas.bind('<KeyPress-'+key+'>',lambda e:self.alt_rotation(True))
            self.canvas.bind('<KeyRelease-'+key+'>',lambda e:self.alt_rotation(False))
        for key in ('Control_L','Control_R'):
            self.canvas.bind('<KeyPress-'+key+'>',lambda e:self.control_move(True))
            self.canvas.bind('<KeyRelease-'+key+'>',lambda e:self.control_move(False))
        self.canvas.bind('<Escape>',lambda _:self.cancel());self.redraw()
        from .preview_navigation import attach as navigation
        navigation(self)
        from .preview_preferences import attach
        attach(self)
        self.plane_binding=self.editor.host.bind('<F5>',self.cycle_plane,add='+')
        self.bind('<Destroy>',self.release_plane_binding,add='+')

    def open_details(self):preview_controls.open_panel(self)
    def close_details(self):preview_controls.close_panel(self)
    def fit_all(self):
        self.cancel();self.redraw()
        right,up=self.camera.basis();points=list(self.positions.values())+[(0,0,0)]
        xmax=max((abs(sum(a*b for a,b in zip(right,p))) for p in points),default=1)
        ymax=max((abs(sum(a*b for a,b in zip(up,p))) for p in points),default=1)
        vertical_margin=max(50,self.plane_overlay.winfo_reqheight()+30)
        self.camera.zoom=max(.001,min((self.canvas.winfo_width()-100)/max(2*xmax,.01),(self.canvas.winfo_height()-2*vertical_margin)/max(2*ymax,.01)))
        self.redraw()

    def dismiss_menu(self):
        self.context_menu.unpost();self.create_menu.unpost();self.menu_context=None

    def create_at_menu(self,kind):
        context=self.menu_context;self.dismiss_menu()
        if not context:return
        if (context['data'] is not self.editor.data or context['definition']!=self.editor.definition_id or context['plane']!=self.plane.get()):
            self.error_message='セット・基準面が変更されています。配置位置を選び直してください。';self.redraw();return
        self.propose(*context['pixels'],kind=kind)
        if self.pending:self.apply()

    def close(self):
        self.dismiss_menu()
        if getattr(self.editor,'point_canvas',None) is self:self.editor.point_canvas=None
        self.destroy()

    def refresh_options(self):self.redraw()

    def redraw(self):
        if not self.winfo_exists():return
        c=self.canvas;c.configure(background=preview_colors.get(self,'background'));c.delete('all');w,h=c.winfo_width(),c.winfo_height();self.hits={};self.positions={};self.direction_hits={}
        def xy(point):return self.camera.project(point,w,h)
        a,b=PLANES[self.plane.get()]
        if self.show_grid.get():
            for i in range(-8,9):
                for first,second in ((a,b),(b,a)):
                    p=[0,0,0];p[first]=i*.25;p[second]=-2;q=p.copy();q[second]=2
                    c.create_line(*xy(p),*xy(q),fill=preview_colors.get(self,'grid'),tags=('grid',))
        origin=xy((0,0,0));c.create_oval(origin[0]-4,origin[1]-4,origin[0]+4,origin[1]+4,fill='#34495e',outline='')
        c.create_text(origin[0]+8,origin[1]+10,text='P0 · 原点',anchor='w',fill='#56677a')
        if self.show_axes.get():
            for index,color in enumerate(('#df6258','#42a47d','#3877d7')):
                for sign in (-1,1):
                    p=[0,0,0];p[index]=sign*1.8;end=xy(p)
                    c.create_line(*origin,*end,fill=color,width=2 if sign>0 else 1,arrow='last',tags=('axes',))
                    c.create_text(end[0]+8,end[1],text=('+' if sign>0 else '−')+'XYZ'[index],fill=color,tags=('axes',))
        definition=self.editor.definition()
        selected=self.editor.element()
        self.selection_label.configure(text='選択：'+(selected['name'] if selected else 'なし'))
        model=(self.pending or {}).get('preview') or (PointPreview(self.editor.data,definition) if definition else None)
        self.preview_model=model
        elements=enumerate((definition or {}).get('elements',[]))
        for index,element in sorted(elements,key=lambda pair:pair[1]['id']==self.editor.element_id):
            if element['type'] not in schema.PT_TYPES:continue
            try:point,vector=model.point(model.number_for(element['id']))
            except ValueError:point,vector=schematic_position(element,index),(0,0,0)
            self.positions[element['id']]=point;x,y=xy(point);self.hits[element['id']]=(x,y)
            selected=element['id'] in self.editor.elements.selection();color=preview_colors.get(self,'selected' if selected else 'points');r=11 if selected else 8
            if self.show_relations.get():c.create_line(*origin,x,y,fill='#b3c4d8',dash=(3,4),tags=('relations',))
            if selected:c.create_oval(x-r-5,y-r-5,x+r+5,y+r+5,outline=preview_colors.get(self,'selected'),width=2,tags=('selected-point-halo',))
            c.create_oval(x-r,y-r,x+r,y+r,fill=color,outline='white',width=2,tags=('point','selected-point' if selected else 'other-point'))
            if self.show_labels.get():c.create_text(x+r+6,y-r-4,text='P'+str(element['attrs'].get('NUMB','?')),anchor='w',fill=color,font=(self.editor.host.ui_font,11 if selected else 10,'bold' if selected else 'normal'),tags=('labels',))
            if not any(vector):
                vector=tuple(1 if i==a else 0 for i in range(3))
            if any(vector):
                self.direction_hits[element['id']]=xy(tuple(point[i]+.3*vector[i] for i in range(3)))
                c.create_line(x,y,*xy(tuple(point[i]+.3*vector[i] for i in range(3))),fill=color,width=3 if selected else 1.5,arrow='last')
        message='ドラッグ：90°刻み（Alt中5°）。位置は属性値で変更（PARAMは仮値で表示）。'
        if not definition:message='左の PTSET 一覧からセットを選ぶか追加してください。'
        elif self.editor.element_id:
            try:
                sources=model.sources(self.editor.element_id)
                if sources:message+=' / '+'、'.join(f'{family} {pid[1:]}' for family,pid,_ in sources)
                number=model.number_for(self.editor.element_id)
                if number in model.problems:message+=' / '+model.problems[number]
            except ValueError:pass
        self.note.configure(text=self.error_message or message,foreground='#ad6536' if self.error_message else '#738499')
        if self.pending:
            x,y=xy(self.pending['point']);c.create_oval(x-18,y-18,x+18,y+18,outline='#dc9431',width=3)
            c.create_text(x+13,y+10,text='候補',anchor='w',fill='#b27324')
            if self.pending.get('angle_label'):
                label=c.create_text(w-14,55,text=self.pending['angle_label'],anchor='ne',font=(self.editor.host.ui_font,11,'bold'),fill='#174b8c',tags=('rotation-angle',))
                bounds=c.bbox(label)
                panel=c.create_rectangle(bounds[0]-8,bounds[1]-5,bounds[2]+8,bounds[3]+5,fill='#e8f0ff',outline='#9ebbe9',tags=('rotation-angle',))
                c.tag_lower(panel,label)


    def cycle_plane(self,event=None):
        host=self.editor.host
        if not self.winfo_exists() or not self.winfo_ismapped():return
        grab=host.grab_current()
        if grab is not None and grab is not host:return
        planes=tuple(PLANES);self.plane.set(planes[(planes.index(self.plane.get())+1)%len(planes)])
        self.plane_changed()
        return 'break'

    def release_plane_binding(self,event):
        if event.widget is self and getattr(self,'plane_binding',None):
            self.editor.host.unbind('<F5>',self.plane_binding);self.plane_binding=None

    def plane_changed(self):
        self.cancel()
    def view_changed(self):
        self.cancel();self.camera=Camera()
        if self.view.get() in PLANES:self.plane.set(self.view.get())
        elif self.view.get()=='立体':self.plane.set('XY')
        if self.view.get()!='立体':self.camera.face(self.plane.get() if self.view.get()=='正面' else self.view.get())
        self.redraw()
    def face(self):self.view.set('正面');self.view_changed()
    def reset_view(self):self.view.set('立体');self.view_changed()
    def zoom(self,factor):self.dismiss_menu();self.camera.zoom=max(25,min(600,self.camera.zoom*factor));self.redraw()
    def orbit_start(self,event):self.cancel();self.orbit=(event.x,event.y,self.camera.yaw,self.camera.pitch)
    def orbit_move(self,event):
        if self.orbit:
            self.view.set('立体');x,y,yaw,pitch=self.orbit;self.camera.yaw=yaw+(event.x-x)*.5;self.camera.pitch=max(-85,min(85,pitch+(event.y-y)*.5));self.redraw()

    def pick(self,x,y):return next((ident for ident,point in sorted(self.hits.items(),key=lambda item:((item[1][0]-x)**2+(item[1][1]-y)**2,item[0]!=self.editor.element_id)) if (point[0]-x)**2+(point[1]-y)**2<=(20 if ident==self.editor.element_id else 15)**2),None)
    def press(self,event):
        if not self.editor.commit_inline():return
        self.cancel();self.canvas.focus_set();
        if len(self.editor.elements.selection())>1:return
        ident=self.pick(event.x,event.y) or next((ident for ident,p in self.direction_hits.items() if (p[0]-event.x)**2+(p[1]-event.y)**2<=225),None)
        if ident:
            self.editor.elements.selection_set(ident);self.editor.select_element()
            self.dragging=ident;self.press_position=(event.x,event.y);self.rotation_start=None;self.last_rotation_pixel=None;self.rotation_step=5 if getattr(event,'state',0)&(0x8|0x20000) else 90;self.control_down=bool(getattr(event,'state',0)&4);self.redraw()
        else:self.orbit=None

    def create_press(self,event):
        if not self.editor.commit_inline():return
        self.cancel();self.canvas.focus_set()
        self.menu_context={'pixels':(event.x,event.y),'data':self.editor.data,'definition':self.editor.definition_id,'plane':self.plane.get()}
        self.context_menu.entryconfigure(0,state='normal' if self.editor.definition() else 'disabled')
        try:self.context_menu.tk_popup(self.canvas.winfo_rootx()+event.x,self.canvas.winfo_rooty()+event.y)
        finally:self.context_menu.grab_release()

    def alt_rotation(self,pressed):
        self.rotation_step=5 if pressed else 90
        if self.dragging and self.last_rotation_pixel:
            self.route_drag()
        return 'break'

    def control_move(self,pressed):
        self.control_down=pressed
        if self.dragging and self.last_rotation_pixel:self.route_drag()
        return 'break'

    def route_drag(self):
        mode='move' if self.control_down else 'rotate'
        if mode!=self.drag_mode:
            self.pending=None;self.rotation_start=None;self.move_state=None;self.drag_mode=mode
        if self.control_down:self.propose_move(*self.last_rotation_pixel,self.dragging)
        else:self.propose_rotation(*self.last_rotation_pixel,self.dragging)

    def move(self,event):
        if not self.dragging:self.orbit_move(event);return
        if self.dragging and self.press_position and max(abs(event.x-self.press_position[0]),abs(event.y-self.press_position[1]))>=4:
            self.rotation_step=5 if getattr(event,'state',0)&(0x8|0x20000) else 90
            self.last_rotation_pixel=(event.x,event.y)
            self.control_down=bool(getattr(event,'state',0)&4)
            self.route_drag()

    def release(self,event):
        self.orbit=None
        if self.dragging and self.pending:self.apply()
        self.dragging=None;self.press_position=None;self.rotation_start=None
        if self.pending and self.pending.get('rotation_only'):
            self.pending.pop('angle_label',None);self.redraw()

    def propose_move(self,x,y,ident):
        e=self.editor;self.error_message=''
        try:
            if len(e.elements.selection())>1:return
            if not e.commit_inline():return
            definition=e.definition();node=next(n for n in definition['elements'] if n['id']==ident)
            model=PointPreview(e.data,definition);plane=self.plane.get();a,b=PLANES[plane]
            normal=next(i for i in range(3) if i not in (a,b))
            if self.move_state is None:
                axis=node['attrs'].get('PAXI','') if node['type']=='PTAXI' else None
                self.move_state=dict(snapshot=copy.deepcopy(definition['elements']),dimensions=copy.deepcopy(definition.get(DIMENSIONS_KEY)),axis=axis,ready=False,plane=plane)
                if node['type']=='PTAXI':
                    origin,vector=model.axis(axis) if not empty(axis) else ((0,0,0),(1,0,0))
                    current=model.location(ident)
                    self.move_state['ready']=empty(axis) or math.dist(self.camera.project(current,self.canvas.winfo_width(),self.canvas.winfo_height()),self.camera.project(origin,self.canvas.winfo_width(),self.canvas.winfo_height()))<=14
            state=self.move_state
            if state['snapshot']!=definition['elements'] or state['dimensions']!=definition.get(DIMENSIONS_KEY) or state['plane']!=plane:raise ValueError('属性・配置が変更されています。ドラッグをやり直してください。')
            point=self.camera.unproject(x,y,self.canvas.winfo_width(),self.canvas.winfo_height(),plane,model.location(ident)[normal]);attrs={}
            if node['type']=='PTAXI':
                axis=state['axis'];origin,vector=model.axis(axis) if not empty(axis) else ((0,0,0),(1,0,0))
                origin_pixel=self.camera.project(origin,self.canvas.winfo_width(),self.canvas.winfo_height())
                if math.dist((x,y),origin_pixel)<=14:
                    point=origin;state['ready']=True
                elif state['ready'] and not any(abs(v)>1e-8 for v in origin):
                    index=max((a,b),key=lambda i:abs(point[i]));axis=('-' if point[index]<0 else '')+'XYZ'[index]
                    state['axis']=axis;state['ready']=False
                    point=tuple(point[index] if i==index else 0. for i in range(3))
                else:point=self.camera.unproject_axis(x,y,self.canvas.winfo_width(),self.canvas.winfo_height(),origin,vector)
                if not empty(axis):attrs['PAXI']=axis
            if node['type'] in ('PTAXI','PTCAR','PTMIX'):
                for key,text in model.fields(node).items():
                    try:root=expressions.parse(text,model.parameters)
                    except ValueError:continue
                    if root[0] not in ('number','quantity'):continue
                    if key=='PDIS':
                        origin,vector=model.axis(attrs.get('PAXI',node['attrs'].get('PAXI','')))
                        distance=sum((point[i]-origin[i])*vector[i] for i in range(3))/model.scale
                    else:distance=point['XYZ'.index(key[-1])]/model.scale
                    attrs[key]=f'{distance:.12g}'
            working=copy.deepcopy(definition);target=next(n for n in working['elements'] if n['id']==ident)
            target['attrs'].update(attrs);target[LAYOUT_KEY]=list(point)
            preview=model.moved(working,ident,plane)
            self.pending=dict(id=ident,attrs=attrs,point=preview.location(ident),preview=preview,move_only=True,
                              snapshot=state['snapshot'],dimensions=state['dimensions'],definition=e.definition_id,preset=presets.selected_id(e.data,definition))
            self.redraw()
        except (ValueError,KeyError,StopIteration) as exc:self.error_message=str(exc);self.pending=None;self.redraw()

    def propose_rotation(self,x,y,ident):
        e=self.editor;self.error_message=''
        try:
            if len(e.elements.selection())>1:return
            if not e.commit_inline():return
            node=next(n for n in e.definition()['elements'] if n['id']==ident)
            key='PAXI' if node['type'] in ('PTAXI','PTMIX') else 'PTCDIR'
            model=PointPreview(e.data,e.definition());a,b=PLANES[self.plane.get()]
            normal=next(i for i in range(3) if i not in (a,b))
            if self.rotation_start is None:
                text=schema.value(node,key)
                origin,vector=model.axis(text) if not empty(text) else ((0,0,0),tuple(1. if i==a else 0. for i in range(3)))
                if any(abs(v)>1e-8 for v in origin):raise ValueError('参照点を原点とする方向は属性欄で変更してください。')
                if math.hypot(vector[a],vector[b])<1e-8:raise ValueError('方向が作図面に垂直です。別の作図面を選択してください。')
                pivot=model.location(ident)
                sx,sy=self.press_position or (x,y)
                start=self.camera.unproject(sx,sy,self.canvas.winfo_width(),self.canvas.winfo_height(),self.plane.get(),pivot[normal])
                offset=(start[a]-pivot[a],start[b]-pivot[b])
                angle=math.atan2(*reversed(offset)) if math.hypot(*offset)>0.04 else math.atan2(vector[b],vector[a])
                self.rotation_start=(ident,pivot,vector,angle,self.plane.get(),copy.deepcopy(e.definition()['elements']),copy.deepcopy(e.definition().get(DIMENSIONS_KEY)))
            saved_id,pivot,vector,start_angle,plane,start_elements,start_dimensions=self.rotation_start
            if e.definition()['elements']!=start_elements or e.definition().get(DIMENSIONS_KEY)!=start_dimensions:
                raise ValueError('属性・配置が変更されています。ドラッグをやり直してください。')
            if saved_id!=ident or plane!=self.plane.get():raise ValueError('選択・作図面が変更されています。')
            end=self.camera.unproject(x,y,self.canvas.winfo_width(),self.canvas.winfo_height(),plane,pivot[normal])
            if math.hypot(end[a]-pivot[a],end[b]-pivot[b])<1e-8:return
            delta=math.atan2(end[b]-pivot[b],end[a]-pivot[a])-start_angle
            degrees=round(math.degrees(delta)/self.rotation_step)*self.rotation_step
            theta=math.radians(degrees);rotated=list(vector)
            rotated[a]=vector[a]*math.cos(theta)-vector[b]*math.sin(theta)
            rotated[b]=vector[a]*math.sin(theta)+vector[b]*math.cos(theta)
            axis=None
            for i in range(3):
                if abs(abs(rotated[i])-1)<1e-8:axis=('-' if rotated[i]<0 else '')+'XYZ'[i];break
            if axis is None:
                if abs(rotated[normal])<1e-8:
                    axis=f'{"XYZ"[a]}{math.degrees(math.atan2(rotated[b],rotated[a])):.10g}{"XYZ"[b]}'
                else:axis=f'X{math.degrees(math.atan2(rotated[1],rotated[0])):.10g}Y{math.degrees(math.asin(max(-1,min(1,rotated[2])))):.10g}Z'
            working=copy.deepcopy(e.definition());target=next(n for n in working['elements'] if n['id']==ident)
            target['attrs'][key]=axis
            rotation_layout=None
            if node['type']=='PTAXI':
                distance=sum(pivot[i]*vector[i] for i in range(3))
                rotation_layout=[distance*v for v in rotated]
                target[LAYOUT_KEY]=rotation_layout
            preview=PointPreview(e.data,working)
            self.pending=dict(id=ident,attrs={key:axis},point=preview.location(ident),preview=preview,
                              snapshot=copy.deepcopy(e.definition()['elements']),dimensions=copy.deepcopy(e.definition().get(DIMENSIONS_KEY)),
                              definition=e.definition_id,preset=presets.selected_id(e.data,e.definition()),rotation_only=True,rotation_layout=rotation_layout,angle_label=f'{key} / {plane}  {math.degrees(math.atan2(rotated[b],rotated[a]))%360:.0f}°  (回転 {degrees:+d}° / {self.rotation_step}°刻み)')
            self.redraw()
        except (ValueError,KeyError,StopIteration) as exc:
            self.error_message=str(exc);self.pending=None;self.redraw()

    def propose(self,x,y,ident=None,kind=None):
        if ident:return self.propose_rotation(x,y,ident)
        e=self.editor;self.error_message=''
        try:
            if not e.definition():raise ValueError('先に PTSET を作成してください。')
            if not e.commit_inline():return
            plane=self.plane.get()
            point=self.camera.unproject(x,y,self.canvas.winfo_width(),self.canvas.winfo_height(),plane,0)
            point,attrs=schematic_placement(kind,point)
            working=copy.deepcopy(e.definition());target=schema.add_element(working,kind)
            target['attrs'].update(attrs);target[LAYOUT_KEY]=list(point)
            preview=PointPreview(e.data,working)
            self.pending=dict(id=None,attrs=attrs,point=preview.location(target['id']),kind=kind,
                              preset=presets.selected_id(e.data,e.definition()),definition=e.definition_id,
                              preview=preview,snapshot=copy.deepcopy(e.definition()['elements']),
                              dimensions=copy.deepcopy(e.definition().get(DIMENSIONS_KEY)))
            self.redraw()
        except (ValueError,KeyError) as exc:self.error_message=str(exc);self.pending=None;self.redraw()

    def cancel(self):
        self.dismiss_menu();self.error_message='';self.pending=None;self.dragging=None;self.press_position=None;self.rotation_start=None;self.move_state=None;self.drag_mode=None;self.last_rotation_pixel=None;self.orbit=None;self.redraw()
    def apply(self):
        if not self.pending:return
        p=self.pending;e=self.editor
        try:
            if not e.commit_inline():return
            if p['definition']!=e.definition_id or p['preset']!=presets.selected_id(e.data,e.definition()):raise ValueError('セット・プリセットが変更されています。候補を作り直してください。')
            if e.definition()['elements']!=p['snapshot']:raise ValueError('属性・配置が変更されています。候補を作り直してください。')
            if e.definition().get(DIMENSIONS_KEY)!=p['dimensions']:raise ValueError('共有仮寸法が変更されています。候補を作り直してください。')
            if p.get('move_only'):
                element=next(n for n in e.definition()['elements'] if n['id']==p['id'])
                element['attrs'].update(p['attrs'])
                for node,index in p['preview'].nodes.values():
                    original=next(n for n in e.definition()['elements'] if n['id']==node['id'])
                    original[LAYOUT_KEY]=list(p['preview'].location(node['id']))
                e.definition()[DIMENSIONS_KEY]=p['preview'].snapshot()
                e.host.mark();self.pending=None;e.refresh();self.cancel();return
            if p.get('rotation_only'):
                element=next(r for r in e.definition()['elements'] if r['id']==p['id'])
                element['attrs'].update(p['attrs'])
                if p.get('rotation_layout') is not None:element[LAYOUT_KEY]=p['rotation_layout']
                e.host.mark();self.pending=None;e.refresh();self.cancel();return
            element=schema.add_element(e.definition(),p['kind'])
            element['attrs'].update(p['attrs']);element[LAYOUT_KEY]=list(p['point'])
            e.definition()[DIMENSIONS_KEY]=p['preview'].snapshot();remember(e.data,e.definition())
            e.element_id=element['id'];e.field=None;e.select_first_section();e.host.mark();self.pending=None;e.refresh();self.cancel()
            missing=schema.missing_fields(element)
            if missing:e.tables['main'].selection_set(missing[0]);e.tables['main'].see(missing[0])
        except ValueError as exc:self.error_message=str(exc);self.redraw()
