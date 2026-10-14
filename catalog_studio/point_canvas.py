"""Interactive 3D point canvas with explicit parameter-expression proposals."""
import copy
import math
import tkinter as tk
from fractions import Fraction
from tkinter import ttk
from . import element_schema as schema, expressions, presets, project
from .point_geometry import Camera, PLANES, axis_vector, formula, placement, position


class PointCanvas(tk.Toplevel):
    def __init__(self,editor):
        super().__init__(editor.host);self.editor=editor;self.title('PTSET · 3D キャンバス');self.geometry('1120x820');self.minsize(940,760);self.transient(editor.host)
        self.camera=Camera();self.pending=None;self.hits={};self.positions={};self.dragging=None;self.orbit=None;self.source_options={};self.parameter_options={}
        self.mode=tk.StringVar(value='選択・移動');self.plane=tk.StringVar(value='XY');self.step=tk.StringVar(value='1/2');self.level=tk.StringVar(value='0');self.kind=tk.StringVar(value='PTCAR');self.axis=tk.StringVar(value='X')
        toolbar=ttk.Frame(self,padding=12);toolbar.pack(fill='x')
        for label in ('選択・移動','点を追加'):ttk.Radiobutton(toolbar,text=label,variable=self.mode,value=label,command=self.cancel).pack(side='left',padx=5)
        ttk.Label(toolbar,text='配置面').pack(side='left',padx=(20,5));plane=ttk.Combobox(toolbar,textvariable=self.plane,values=list(PLANES),state='readonly',width=5);plane.pack(side='left');plane.bind('<<ComboboxSelected>>',lambda _:self.cancel())
        ttk.Button(toolbar,text='面を正面',command=self.face).pack(side='left',padx=8)
        ttk.Button(toolbar,text='標準視点',command=self.reset_view).pack(side='left')
        ttk.Label(toolbar,text='右ドラッグ：回転 / ホイール：ズーム',style='Muted.TLabel').pack(side='right')
        body=ttk.Frame(self,padding=(12,0,12,12));body.pack(fill='both',expand=True)
        side=ttk.Frame(body,width=275,padding=(14,0,0,0));side.pack(side='right',fill='y');side.pack_propagate(False)
        self.canvas=tk.Canvas(body,bg='#f3f7fc',highlightthickness=0);self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda _:self.redraw());self.canvas.bind('<Button-1>',self.press);self.canvas.bind('<B1-Motion>',self.move);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Button-3>',self.orbit_start);self.canvas.bind('<B3-Motion>',self.orbit_move);self.canvas.bind('<MouseWheel>',lambda ev:self.zoom(1.12 if ev.delta>0 else 1/1.12));self.canvas.bind('<Button-4>',lambda _:self.zoom(1.12));self.canvas.bind('<Button-5>',lambda _:self.zoom(1/1.12))
        self.parameter_choice=self.choice(side,'基準 PARAM（長さ）',[],None)
        self.parameter_choice.bind('<<ComboboxSelected>>',lambda _:self.cancel())
        self.source_choice=self.choice(side,'確認用 SCOM',[],None)
        self.source_choice.bind('<<ComboboxSelected>>',self.source_changed)
        self.choice(side,'グリッド間隔（基準 PARAM の倍率）',['1/4','1/2','1','1/10'],self.step)
        self.choice(side,'追加する面の位置（倍率）',['0','1/2','1','-1/2','-1'],self.level)
        self.choice(side,'新規ポイントの種類',['PTAXI','PTCAR','PTMIX'],self.kind)
        self.choice(side,'新規ポイントの方向',['X','-X','Y','-Y','Z','-Z'],self.axis)
        self.guide=ttk.Label(side,text='',wraplength=245,style='Muted.TLabel');self.guide.pack(fill='x',pady=8)
        self.kind.trace_add('write',lambda *_:self.update_guide())
        ttk.Label(side,text='位置の式候補',style='Heading.TLabel').pack(anchor='w',pady=(10,4))
        self.proposal_label=ttk.Label(side,text='キャンバスで点を選択・移動してください。',wraplength=245);self.proposal_label.pack(fill='x')
        actions=ttk.Frame(side);actions.pack(fill='x',pady=10)
        self.apply_button=ttk.Button(actions,text='式を適用',command=self.apply,style='Primary.TButton',state='disabled');self.apply_button.pack(side='left')
        ttk.Button(actions,text='取消',command=self.cancel).pack(side='left',padx=6)
        self.note=ttk.Label(side,text='',wraplength=245,foreground='#ad6536');self.note.pack(fill='x',pady=6)
        ttk.Label(side,text='P0 は原点・編集不可。\n未解釈の点は推測して配置しません。\nマウス操作だけでは保存値を変更せず、「式を適用」で反映します。',wraplength=245,style='Muted.TLabel').pack(fill='x',side='bottom')
        self.refresh_options();self.update_guide();self.protocol('WM_DELETE_WINDOW',self.close)

    def choice(self,parent,label,values,variable):
        ttk.Label(parent,text=label).pack(anchor='w',pady=(4,3))
        widget=ttk.Combobox(parent,values=values,state='readonly',textvariable=variable,width=27);widget.pack(fill='x');widget.bind('<<ComboboxSelected>>',lambda _:self.cancel());return widget

    def close(self):
        if getattr(self.editor,'point_canvas',None) is self:self.editor.point_canvas=None
        self.destroy()

    def refresh_options(self):
        e=self.editor;old=self.parameter_options.get(self.parameter_choice.get());self.parameter_options={'PARAM '+p['id'][1:]+'（'+p['role']+'）':p['id'] for p in presets.rules(e.data,e.definition()) if p.get('value_type','number')=='number' and p.get('unit','').lower() not in ('deg','degree','度')}
        self.parameter_choice['values']=list(self.parameter_options)
        key=next((k for k,v in self.parameter_options.items() if v==old),next((k for k,v in self.parameter_options.items() if v=='P3'),next(iter(self.parameter_options),'')));self.parameter_choice.set(key)
        self.source_options={'PARAM 基準の表示（値=1）':None,**{s['name']:s['id'] for s in e.data['scoms'] if presets.selected_id(e.data,s)==presets.selected_id(e.data,e.definition())}}
        self.source_choice['values']=list(self.source_options);self.source_choice.set(next((k for k,v in self.source_options.items() if v==e.preview_scom_id),next(iter(self.source_options))))
        self.redraw()

    def source_changed(self,_=None):
        self.editor.preview_scom_id=self.source_options.get(self.source_choice.get());self.editor.scom_choice.set(self.source_choice.get() if self.editor.preview_scom_id else '');self.editor.refresh_values();self.editor.update_validation();self.cancel()

    def context(self):
        e=self.editor;pid=self.parameter_options.get(self.parameter_choice.get())
        if not pid:raise ValueError('長さの基準 PARAM をプリセットに登録してください。')
        s=project.get(e.data,'scoms',self.source_options.get(self.source_choice.get()))
        if s:
            presets.require_compatible(e.data,s,e.definition());contexts=expressions.contexts_for(s);attributes=s.get('component_attrs',{})
            scale=expressions.evaluate('PARAM '+pid[1:],contexts,attributes,presets.rules(e.data,e.definition()))
        else:contexts={'PARAM':{pid:1}};attributes={};scale=1
        if type(scale) not in (int,float) or not math.isfinite(scale) or scale<=0:raise ValueError('基準 PARAM の確認値は正の数が必要です。')
        return pid,contexts,attributes,scale

    def update_guide(self):
        guide=schema.PT_GUIDES[self.kind.get()];self.guide.configure(text=guide['position']+'\n'+guide['direction'])

    def redraw(self):
        if not self.winfo_exists():return
        c=self.canvas;c.delete('all');w,h=c.winfo_width(),c.winfo_height();self.hits={};self.positions={};bad=[]
        def xy(point):return self.camera.project(point,w,h)
        plane=self.plane.get();a,b=PLANES[plane];fixed=Fraction(self.level.get())
        spacing=float(Fraction(self.step.get()));count=min(30,math.ceil(2/spacing))
        for i in range(-count,count+1):
            for first,second in ((a,b),(b,a)):
                p=[float(fixed)]*3;p[first]=i*spacing;p[second]=-2;q=p.copy();q[second]=2
                c.create_line(*xy(p),*xy(q),fill='#dee7f0')
        origin=xy((0,0,0));c.create_oval(origin[0]-4,origin[1]-4,origin[0]+4,origin[1]+4,fill='#34495e',outline='');c.create_text(origin[0]+8,origin[1]+10,text='P0',anchor='w',fill='#56677a')
        for index,color in enumerate(('#df6258','#42a47d','#3877d7')):
            p=[0,0,0];p[index]=1.8;end=xy(p);c.create_line(*origin,*end,fill=color,width=2,arrow='last');c.create_text(end[0]+8,end[1],text='XYZ'[index],fill=color)
        try:
            pid,contexts,attributes,scale=self.context()
            for element in (self.editor.definition() or {}).get('elements',[]):
                try:point=position(element,contexts,attributes,presets.rules(self.editor.data,self.editor.definition()));normalized=tuple(v/scale for v in point)
                except (ValueError,TypeError) as exc:bad.append(element['name']+'：'+str(exc));continue
                self.positions[element['id']]=normalized;x,y=xy(normalized);self.hits[element['id']]=(x,y)
                selected=element['id']==self.editor.element_id;color='#2269de' if selected else '#657c94';r=7 if selected else 5
                c.create_oval(x-r,y-r,x+r,y+r,fill=color,outline='white',width=2);c.create_text(x+11,y-10,text='P'+str(element['attrs'].get('NUMB','?')),anchor='w',fill=color)
                try:vector=axis_vector(element['attrs'].get('PAXI',element['attrs'].get('PTCDIR','')));end=tuple(normalized[i]+.25*vector[i] for i in range(3));c.create_line(x,y,*xy(end),fill=color,arrow='last')
                except ValueError:pass
            if self.pending:
                x,y=xy(self.pending['point']);c.create_oval(x-9,y-9,x+9,y+9,outline='#dc9431',width=3);c.create_text(x+13,y+10,text='候補',anchor='w',fill='#b27324')
            self.note.configure(text=('未表示 '+str(len(bad))+' 点\n'+'\n'.join(bad[:2])) if bad else ('確認用 SCOM の値で表示' if self.source_options.get(self.source_choice.get()) else '表示用に基準 PARAM=1 を使用。数値は定義に保存しません。'))
        except ValueError as exc:self.note.configure(text=str(exc))

    def face(self):self.camera.face(self.plane.get());self.redraw()
    def reset_view(self):self.camera=Camera();self.redraw()
    def zoom(self,factor):self.camera.zoom=max(25,min(600,self.camera.zoom*factor));self.redraw()
    def orbit_start(self,event):self.orbit=(event.x,event.y,self.camera.yaw,self.camera.pitch)
    def orbit_move(self,event):
        if self.orbit:
            x,y,yaw,pitch=self.orbit;self.camera.yaw=yaw+(event.x-x)*.5;self.camera.pitch=max(-85,min(85,pitch+(event.y-y)*.5));self.redraw()

    def pick(self,x,y):return next((ident for ident,point in sorted(self.hits.items(),key=lambda item:(item[1][0]-x)**2+(item[1][1]-y)**2) if (point[0]-x)**2+(point[1]-y)**2<=144),None)
    def press(self,event):
        self.dragging=None
        if self.mode.get()=='点を追加':self.propose(event.x,event.y);return
        ident=self.pick(event.x,event.y)
        if ident:
            self.cancel();self.editor.elements.selection_set(ident);self.editor.select_element();self.dragging=ident;self.redraw()
    def move(self,event):
        if self.dragging or self.mode.get()=='点を追加':self.propose(event.x,event.y,self.dragging)
    def release(self,event):self.dragging=None

    def propose(self,x,y,ident=None):
        e=self.editor
        try:
            pid,contexts,attributes,scale=self.context();plane=self.plane.get();perpendicular=next(i for i in range(3) if i not in PLANES[plane]);element=next((r for r in e.definition()['elements'] if r['id']==ident),None)
            fixed=self.positions[ident][perpendicular] if element else float(Fraction(self.level.get()))
            point=self.camera.unproject(x,y,self.canvas.winfo_width(),self.canvas.winfo_height(),plane,fixed);step=Fraction(self.step.get());coefficients=[Fraction(round(v/float(step)))*step for v in point]
            kind=element['type'] if element else self.kind.get();axis=element['attrs'].get('PAXI','X') if element else self.axis.get()
            attrs=placement(kind,coefficients,pid,axis,plane if element else None)
            if kind=='PTAXI':
                vector=axis_vector(axis);index=next(i for i,v in enumerate(vector) if v);point=[0,0,0];point[index]=float(coefficients[index])
            else:
                point=[float(v) for v in coefficients]
                if element:point[perpendicular]=fixed
            base=copy.deepcopy(element['attrs']) if element else None
            if self.pending and self.pending['id']==ident and ident:base=self.pending['base']
            self.pending={'id':ident,'base':base,'attrs':attrs,'point':point,'kind':kind,'axis':axis,'preset':presets.selected_id(e.data,e.definition()),'definition':e.definition_id}
            self.proposal_label.configure(text=('移動：'+element['name'] if element else '新規：'+kind)+'\n\n'+'\n'.join(k+' = '+presets.display_expression(e.data,e.definition(),v) for k,v in attrs.items()));self.apply_button.configure(state='normal');self.redraw()
        except (ValueError,KeyError) as exc:self.note.configure(text=str(exc));self.pending=None;self.apply_button.configure(state='disabled')

    def cancel(self):
        self.pending=None;self.dragging=None;self.apply_button.configure(state='disabled');self.proposal_label.configure(text='キャンバスで点を選択・移動してください。');self.redraw()
    def apply(self):
        if not self.pending:return
        p=self.pending;e=self.editor
        try:
            if p['definition']!=e.definition_id or p['preset']!=presets.selected_id(e.data,e.definition()):raise ValueError('セット・プリセットが変更されています。候補を作り直してください。')
            if p['id']:
                element=next((r for r in e.definition()['elements'] if r['id']==p['id']),None)
                if not element or element['attrs']!=p['base']:raise ValueError('属性が変更されています。候補を作り直してください。')
            else:
                element=schema.add_element(e.definition(),p['kind']);element['attrs']['PAXI' if p['kind'] in ('PTAXI','PTMIX') else 'PTCDIR']=p['axis']
            element['attrs'].update(p['attrs']);e.element_id=element['id'];e.field=None;e.section='main';e.tabs.select(0);e.host.mark();self.pending=None;e.refresh();self.cancel()
        except ValueError as exc:self.note.configure(text=str(exc))
