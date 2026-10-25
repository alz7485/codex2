"""Unitless point layout with PARAM dimensions editable from any shared point."""
import copy
import tkinter as tk
from tkinter import ttk
from . import element_schema as schema, presets, expressions
from .point_geometry import Camera, PLANES, LAYOUT_KEY, DIMENSIONS_KEY, schematic_position, schematic_placement
from .point_preview import PointPreview, empty, remember
from . import theme, preview_controls


class PointCanvas(ttk.Frame):
    def __init__(self,editor,parent):
        super().__init__(parent);self.editor=editor
        self.camera=Camera();self.pending=None;self.hits={};self.positions={};self.dragging=None;self.orbit=None
        self.error_message='';self.menu_context=None;self.press_position=None
        self.plane=tk.StringVar(value='XY');self.view=tk.StringVar(value='立体')
        self.show_grid=tk.BooleanVar(value=True);self.show_axes=tk.BooleanVar(value=True)
        self.show_labels=tk.BooleanVar(value=True);self.show_relations=tk.BooleanVar(value=True)
        self.columnconfigure(0,weight=1);self.rowconfigure(3,weight=1)
        ttk.Label(self,text='3D プレビュー　 ·　仮配置・単位なし',style='Heading.TLabel').grid(row=0,column=0,sticky='w',pady=(0,8))
        preview_controls.build(self,1)
        self.display_buttons={}
        for label,var in (('グリッド',self.show_grid),('座標軸',self.show_axes),('点番号',self.show_labels),('関係線',self.show_relations)):
            button=ttk.Checkbutton(self.settings_content,text=label,variable=var,command=self.redraw,style='Preview.Toolbutton')
            button.pack(anchor='w',fill='x',pady=2);self.display_buttons[label]=button
        context=ttk.Frame(self);context.grid(row=2,column=0,sticky='ew',pady=(0,6))
        self.selection_label=ttk.Label(context,text='選択：なし',style='Muted.TLabel');self.selection_label.pack(side='left')
        ttk.Label(context,text='作図面',style='Muted.TLabel').pack(side='left',padx=(14,4))
        self.plane_choice=ttk.Combobox(context,textvariable=self.plane,values=tuple(PLANES),state='readonly',width=4)
        self.plane_choice.pack(side='left');self.plane_choice.bind('<<ComboboxSelected>>',lambda _:self.plane_changed())
        self.context_menu=tk.Menu(self,tearoff=False)
        self.create_menu=tk.Menu(self.context_menu,tearoff=False)
        for kind in schema.PT_TYPES:
            self.create_menu.add_command(label=kind+'：'+schema.PT_GUIDES[kind]['name'],command=lambda selected=kind:self.create_at_menu(selected))
        self.context_menu.add_cascade(label='点を作成',menu=self.create_menu)
        self.context_menu.add_separator();self.context_menu.add_command(label='閉じる',command=self.dismiss_menu)
        self.canvas=tk.Canvas(self.body,bg=theme.SUBTLE,highlightthickness=1,highlightbackground=theme.BORDER,highlightcolor=theme.ACCENT,width=320,height=260);self.canvas.grid(row=0,column=0,sticky='nsew')
        preview_controls.zoom_buttons(self)
        self.canvas.bind('<Configure>',lambda _:self.redraw());self.canvas.bind('<Button-1>',self.press);self.canvas.bind('<B1-Motion>',self.move);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Button-3>',self.orbit_start);self.canvas.bind('<B3-Motion>',self.orbit_move)
        self.canvas.bind('<MouseWheel>',lambda ev:self.zoom(1.12 if ev.delta>0 else 1/1.12));self.canvas.bind('<Button-4>',lambda _:self.zoom(1.12));self.canvas.bind('<Button-5>',lambda _:self.zoom(1/1.12))
        self.note=ttk.Label(self,text='',wraplength=280,foreground='#738499');self.note.grid(row=4,column=0,sticky='ew',pady=(6,0))
        self.note.bind('<Configure>',lambda ev:self.note.configure(wraplength=max(140,ev.width-4)))
        hint=ttk.Label(self,text='空白：点を作成 ｜ ドラッグ：移動 ｜ 右：回転 ｜ ホイール：ズーム',wraplength=280,style='Muted.TLabel');hint.grid(row=5,column=0,sticky='ew',pady=(6,0))
        hint.bind('<Configure>',lambda ev:hint.configure(wraplength=max(140,ev.width-4)))
        self.canvas.bind('<Escape>',lambda _:self.cancel());self.redraw()

    def open_details(self):preview_controls.open_panel(self)
    def close_details(self):preview_controls.close_panel(self)
    def fit_all(self):
        self.cancel();self.redraw()
        right,up=self.camera.basis();points=list(self.positions.values())+[(0,0,0)]
        xmax=max((abs(sum(a*b for a,b in zip(right,p))) for p in points),default=1)
        ymax=max((abs(sum(a*b for a,b in zip(up,p))) for p in points),default=1)
        self.camera.zoom=max(.001,min((self.canvas.winfo_width()-100)/max(2*xmax,.01),(self.canvas.winfo_height()-100)/max(2*ymax,.01)))
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
            selected=element['id']==self.editor.element_id;color=theme.ACCENT if selected else '#657c94';r=11 if selected else 8
            if self.show_relations.get():c.create_line(*origin,x,y,fill='#b3c4d8',dash=(3,4),tags=('relations',))
            if selected:c.create_oval(x-r-5,y-r-5,x+r+5,y+r+5,outline=theme.ACCENT,width=2,tags=('selected-point-halo',))
            c.create_oval(x-r,y-r,x+r,y+r,fill=color,outline='white',width=2,tags=('point','selected-point' if selected else 'other-point'))
            if self.show_labels.get():c.create_text(x+r+6,y-r-4,text='P'+str(element['attrs'].get('NUMB','?')),anchor='w',fill=color,font=(self.editor.host.ui_font,11 if selected else 10,'bold' if selected else 'normal'),tags=('labels',))
            if any(vector):
                c.create_line(x,y,*xy(tuple(point[i]+.3*vector[i] for i in range(3))),fill=color,width=3 if selected else 1.5,arrow='last')
        message='共有仮寸法：どの点を動かしても同じ PARAM の点が追従します。'
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


    def plane_changed(self):
        self.cancel()
    def view_changed(self):
        self.cancel();self.camera=Camera()
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
        self.cancel();self.canvas.focus_set();ident=self.pick(event.x,event.y)
        if ident:
            self.editor.elements.selection_set(ident);self.editor.select_element()
            self.dragging=ident;self.press_position=(event.x,event.y);self.redraw()
        else:
            self.menu_context={'pixels':(event.x,event.y),'data':self.editor.data,'definition':self.editor.definition_id,'plane':self.plane.get()}
            self.context_menu.entryconfigure(0,state='normal' if self.editor.definition() else 'disabled')
            try:self.context_menu.tk_popup(self.canvas.winfo_rootx()+event.x,self.canvas.winfo_rooty()+event.y)
            finally:self.context_menu.grab_release()

    def move(self,event):
        if self.dragging and self.press_position and max(abs(event.x-self.press_position[0]),abs(event.y-self.press_position[1]))>=4:
            self.propose(event.x,event.y,self.dragging)

    def release(self,event):
        if self.dragging and self.pending:self.apply()
        self.dragging=None;self.press_position=None

    def propose(self,x,y,ident=None,kind=None):
        e=self.editor;self.error_message=''
        try:
            if not e.definition():raise ValueError('先に PTSET を作成してください。')
            if not e.commit_inline():return
            plane=self.plane.get();perpendicular=next(i for i in range(3) if i not in PLANES[plane])
            element=next((r for r in e.definition()['elements'] if r['id']==ident),None)
            if ident and not element:raise ValueError('要素が変更されています。選択し直してください。')
            model=PointPreview(e.data,e.definition())
            if element:
                if element['type']!='PTPOS' or not empty(element['attrs'].get('PTCPOS','')):
                    for text in model.fields(element).values():
                        if not empty(text):expressions.parse(text,model.parameters)
                direction_key='PAXI' if element['type'] in ('PTAXI','PTMIX') else 'PTCDIR'
                direction=schema.value(element,direction_key)
                if not empty(direction):model.axis(direction)
            if element and element['type']=='PTAXI' and not empty(element['attrs'].get('PAXI','')):
                origin,vector=model.axis(element['attrs']['PAXI'])
                point=self.camera.unproject_axis(x,y,self.canvas.winfo_width(),self.canvas.winfo_height(),origin,vector)
                # Keep the axis expression and let the shared dimensions decide
                # which distance is editable, including reference-point axes.
                attrs={}
            else:
                fixed=self.positions[ident][perpendicular] if element else 0
                point=self.camera.unproject(x,y,self.canvas.winfo_width(),self.canvas.winfo_height(),plane,fixed)
                attrs=None
            kind=element['type'] if element else kind
            if attrs is None:point,attrs=schematic_placement(kind,point,element['attrs'] if element else None,plane if element else None)
            working=copy.deepcopy(e.definition())
            target=next(r for r in working['elements'] if r['id']==ident) if element else schema.add_element(working,kind)
            target['attrs'].update(attrs);target[LAYOUT_KEY]=list(point)
            proposed=model.moved(working,target['id'],plane) if element else PointPreview(e.data,working)
            point=proposed.location(target['id'])
            base=copy.deepcopy(element['attrs']) if element else None
            layout=copy.deepcopy(element.get(LAYOUT_KEY)) if element else None
            if self.pending and self.pending['id']==ident and ident:base=self.pending['base'];layout=self.pending['layout']
            self.pending={'id':ident,'base':base,'layout':layout,'attrs':attrs,'point':point,'kind':kind,'preset':presets.selected_id(e.data,e.definition()),'definition':e.definition_id,'preview':proposed,'snapshot':copy.deepcopy(e.definition()['elements']),'dimensions':copy.deepcopy(e.definition().get(DIMENSIONS_KEY))}
            self.redraw()
        except (ValueError,KeyError) as exc:self.error_message=str(exc);self.pending=None;self.redraw()

    def cancel(self):
        self.dismiss_menu();self.error_message='';self.pending=None;self.dragging=None;self.press_position=None;self.redraw()
    def apply(self):
        if not self.pending:return
        p=self.pending;e=self.editor
        try:
            if not e.commit_inline():return
            if p['definition']!=e.definition_id or p['preset']!=presets.selected_id(e.data,e.definition()):raise ValueError('セット・プリセットが変更されています。候補を作り直してください。')
            if e.definition()['elements']!=p['snapshot']:raise ValueError('属性・配置が変更されています。候補を作り直してください。')
            if e.definition().get(DIMENSIONS_KEY)!=p['dimensions']:raise ValueError('共有仮寸法が変更されています。候補を作り直してください。')
            if p['id']:
                element=next((r for r in e.definition()['elements'] if r['id']==p['id']),None)
                if not element or element['attrs']!=p['base'] or element.get(LAYOUT_KEY)!=p['layout']:raise ValueError('属性・配置が変更されています。候補を作り直してください。')
                current=PointPreview(e.data,e.definition()).location(element['id'])
                if all(element['attrs'].get(k)==v for k,v in p['attrs'].items()) and max(abs(a-b) for a,b in zip(current,p['point']))<1e-9:
                    self.cancel();return
            else:element=schema.add_element(e.definition(),p['kind'])
            element['attrs'].update(p['attrs']);element[LAYOUT_KEY]=list(p['point'])
            e.definition()[DIMENSIONS_KEY]=p['preview'].snapshot();remember(e.data,e.definition())
            e.element_id=element['id'];e.field=None;e.select_first_section();e.host.mark();self.pending=None;e.refresh();self.cancel()
            missing=schema.missing_fields(element)
            if missing:e.tables['main'].selection_set(missing[0]);e.tables['main'].see(missing[0])
        except ValueError as exc:self.error_message=str(exc);self.redraw()
