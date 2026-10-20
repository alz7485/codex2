"""Elements, permanent preview, and attributes beside the registered browser."""
import tkinter as tk
from tkinter import ttk
from . import element_schema as schema
from .attribute_table import AttributeTable
from .element_list import ElementList
from . import theme


def build_simple(editor):
    e = editor
    e.simple_layout = True
    e.unified_attributes = True
    e.attribute_sections = {}
    e.configure(style='Workspace.TFrame')
    point = e.kind == 'PTSET'
    e.canvas = None
    e.creating = e.settings_open = e.references_open = False

    e.settings_frame = ttk.LabelFrame(e, text='セットの設定・確認', padding=12)
    row = ttk.Frame(e.settings_frame)
    row.pack(fill='x')
    ttk.Label(row, text=e.kind + ' 名').pack(side='left')
    e.def_name = tk.StringVar()
    e.name_entry = ttk.Entry(row, textvariable=e.def_name, width=28)
    e.name_entry.pack(side='left', padx=8)
    e.name_entry.bind('<FocusOut>', lambda _: e.commit_name())
    e.name_entry.bind('<Return>', lambda _: e.commit_name())
    ttk.Button(row, text='PARAM プリセットを管理', command=lambda: e.host.switch('rules')).pack(side='left', padx=8)
    row = ttk.Frame(e.settings_frame)
    row.pack(fill='x', pady=(10, 0))
    if schema.PARENT_FIELDS[e.kind]:
        ttk.Button(row, text='親属性', command=e.edit_parent).pack(side='left')
    ttk.Button(row, text='セットを複製', command=e.duplicate_definition).pack(side='left', padx=6)
    ttk.Button(row, text='出力を確認', command=e.review).pack(side='left')
    e.usage_label = ttk.Label(row, text='', style='Muted.TLabel')
    e.usage_label.pack(side='right')
    row = ttk.Frame(e.settings_frame)
    row.pack(fill='x', pady=(10, 0))
    ttk.Label(row, text='確認用 SCOM').pack(side='left')
    e.scom_choice = ttk.Combobox(row, state='readonly', width=28)
    e.scom_choice.pack(side='left', padx=8)
    e.scom_choice.bind('<<ComboboxSelected>>', e.select_scom)
    ttk.Button(row, text='値・ANGL を開く', command=e.open_scom).pack(side='left')
    e.values_label = ttk.Label(row, text='', style='Muted.TLabel', wraplength=370)
    e.values_label.pack(side='left', padx=12)
    e.element_details = ttk.Label(e.settings_frame, text='', style='Muted.TLabel', wraplength=1000)
    e.element_details.pack(anchor='w', fill='x', pady=(8, 0))
    e.element_details.bind('<Configure>', lambda event: e.element_details.configure(wraplength=max(160, event.width - 8)))

    e.main_split = ttk.Panedwindow(e, orient='horizontal')
    e.main_split.pack(fill='both', expand=True)
    left = ttk.Frame(e.main_split, padding=(10,10),style='Card.TFrame')
    center = ttk.Frame(e.main_split, padding=(12,10),style='Card.TFrame')
    right = ttk.Frame(e.main_split, padding=(10,10),width=330,style='Card.TFrame')
    right.pack_propagate(False)
    e.element_pane,e.preview_pane,e.attribute_pane=left,center,right
    e.main_split.add(left, weight=1)
    e.main_split.add(center, weight=4)
    e.main_split.add(right, weight=0)
    e.panes_initialized=False
    def initialize_panes(event):
        if e.panes_initialized or event.width<600:return
        e.panes_initialized=True
        e.main_split.sashpos(0,max(160,min(230,int(event.width*.19))))
        e.main_split.sashpos(1,event.width-336)
    e.main_split.bind('<Configure>',initialize_panes)
    e.def_choice = tk.StringVar()
    name=ttk.Label(left, textvariable=e.def_name, style='Heading.TLabel', wraplength=210)
    name.pack(anchor='w',fill='x',pady=(0,4))
    name.bind('<Configure>',lambda event:name.configure(wraplength=max(110,event.width-4)))
    if not getattr(e.host,'is_preset_editor',False):
        e.import_macro_button=ttk.Button(left,text='作成マクロを読み込む',command=e.host.import_creation_macro)
        e.import_macro_button.pack(fill='x',pady=(0,8))
        from .macro_destinations_ui import build_field
        build_field(e, left)
        from .macro_export_ui import open_export
        e.export_macro_button=ttk.Button(left,text='作成マクロを出力 (.mac)',command=lambda:open_export(e))
        e.export_macro_button.pack(fill='x',pady=(0,8))
    row = ttk.Frame(left)
    row.pack(fill='x', pady=(0, 8))
    ttk.Label(row, text='要素', style='Heading.TLabel').pack(side='left')
    e.add_button = ttk.Button(row, text='＋ 追加', command=e.toggle_create, style='Compact.Primary.TButton')
    e.add_button.pack(side='right')

    if point and not getattr(e.host,'is_preset_editor',False):
        from .element_presets_ui import select_ptset_preset
        preset_bar=ttk.Frame(left)
        preset_bar.pack(fill='x',pady=(0,8))
        ttk.Label(preset_bar,text='PTSET プリセット',style='Muted.TLabel').pack(anchor='w',pady=(0,3))
        e.element_preset_choice=ttk.Combobox(preset_bar,state='readonly',width=12)
        e.element_preset_choice.pack(fill='x')
        e.element_preset_choice.bind('<<ComboboxSelected>>',lambda _:select_ptset_preset(e))

    e.creation_frame=tk.Toplevel(e)
    e.creation_frame.withdraw();e.creation_frame.title('ポイントを追加' if point else '形状を追加')
    e.creation_frame.geometry('420x360' if point else '440x420');e.creation_frame.minsize(400,350 if point else 400)
    e.creation_frame.transient(e.winfo_toplevel())
    e.creation_frame.protocol('WM_DELETE_WINDOW',lambda:e.toggle_create() if e.creating else e.creation_frame.withdraw())
    creation=ttk.Frame(e.creation_frame,padding=16);creation.pack(fill='both',expand=True)
    ttk.Label(creation,text='種類を選んで作成',style='Heading.TLabel').pack(anchor='w',pady=(0,12))
    e.negative = tk.BooleanVar(value=False)
    if not point:
        ttk.Checkbutton(creation, text='ネガティブ形状', variable=e.negative, command=e.populate_library).pack(anchor='w', pady=(0, 6))
    holder = ttk.Frame(creation)
    holder.pack(fill='both',expand=True)
    e.library = tk.Listbox(holder, height=4 if point else 8, exportselection=False, font=(e.host.ui_font, 10), relief='flat',borderwidth=0,activestyle='none',selectbackground=theme.SELECT,selectforeground=theme.ACCENT)
    e.library.pack(side='left', fill='both', expand=True)
    scroll = ttk.Scrollbar(holder, command=e.library.yview)
    scroll.pack(side='right', fill='y')
    e.library.configure(yscrollcommand=scroll.set)
    e.type_help = ttk.Label(creation, text='', wraplength=440, justify='left', style='Muted.TLabel')
    e.type_help.pack(fill='x', pady=10)
    e.creation_frame.bind('<Configure>', lambda event: e.type_help.configure(wraplength=max(140,event.width-32)) if event.widget is e.creation_frame else None)
    e.library.bind('<<ListboxSelect>>', e.describe_selected_type)
    actions=ttk.Frame(creation);actions.pack(fill='x',pady=(6,0))
    e.create_element_button = ttk.Button(actions, text='作成', command=e.add_element, style='Primary.TButton',width=12)
    e.create_element_button.pack(side='right')
    e.cancel_creation_button=ttk.Button(actions,text='キャンセル',width=9,command=lambda:e.toggle_create() if e.creating else None)
    e.cancel_creation_button.pack(side='right',padx=(0,6))
    e.populate_library()

    e.tree_holder = ttk.Frame(left)
    e.tree_holder.pack(fill='both', expand=True)
    e.elements = ElementList(e.tree_holder,e.host.ui_font,e.element_name_context)
    e.elements.grid(row=0, column=0, sticky='nsew')
    scroll = ttk.Scrollbar(e.tree_holder, command=e.elements.yview)
    scroll.grid(row=0, column=1, sticky='ns')
    e.elements.configure(yscrollcommand=scroll.set)
    e.tree_holder.rowconfigure(0, weight=1)
    e.tree_holder.columnconfigure(0, weight=1)
    e.elements.bind('<<TreeviewSelect>>', e.select_element)
    row = ttk.Frame(left)
    row.pack(side='bottom', fill='x', pady=(8, 0), before=e.tree_holder)
    from .construction_actions import context_menu,enable_drag
    context_menu(e);enable_drag(e)
    e.child_button = ttk.Button(row, text='子要素を追加', command=e.add_child)
    if point:
        ttk.Label(row, text='P0：自動生成', style='Muted.TLabel').pack(side='right')

    ttk.Label(right, text='PARAM プリセット', style='Muted.TLabel').pack(anchor='w',pady=(0,4))
    e.preset_choice = ttk.Combobox(right, state='readonly')
    e.preset_choice.pack(fill='x', pady=(0,12))
    e.preset_choice.bind('<<ComboboxSelected>>', e.assign_preset)
    ttk.Label(right, text='属性値', style='Heading.TLabel').pack(anchor='w', pady=(0, 4))
    e.element_name = tk.StringVar()
    e.type_choice = tk.StringVar()
    e.element_note = ttk.Label(right, text='', style='Muted.TLabel', wraplength=740)
    e.element_note.pack(anchor='w', pady=(0, 12))
    e.element_note.bind('<Configure>',lambda event:e.element_note.configure(wraplength=max(160,event.width-4)))

    e.tabs = ttk.Frame(right)
    e.tabs.pack(fill='both', expand=True)
    e.tables = {}
    e.tab_frames = {}
    e.section_order = ['main']
    table = AttributeTable(e.tabs,e.host.ui_font,lambda attr,value:e.parameter_caption(attr,value) if e.attribute_section(attr)!='extra' else '',lambda attr:e.inline_context(attr,e.attribute_section(attr)),lambda attr:attr in schema.missing_fields(e.element()))
    from .value_editor import open_editor
    table.editor_factory=lambda table,key,context:open_editor(e,table,key,context)
    table.pack(fill='both',expand=True)
    table.bind('<<TreeviewSelect>>',lambda event:e.select_field('main'))
    table.bind('<Double-1>',lambda _:e.focus_value_input())
    table.bind('<Return>',lambda _:e.focus_value_input())
    e.tables['main'] = table

    box = ttk.Frame(right, padding=(0, 14, 0, 0))
    # Legacy controller variables remain available, while input lives in a dialog.
    row = ttk.Frame(box)
    row.pack(fill='x', pady=(0, 8))
    caption=ttk.Frame(row)
    e.field_label = ttk.Label(caption, text='', style='Heading.TLabel')
    e.field_label.pack(anchor='w')
    e.field_meaning=ttk.Label(caption,text='',style='AttributeMeaning.TLabel')
    e.field_meaning.pack(anchor='w',fill='x')
    e.reference_button = ttk.Button(row, text='PARAM を選ぶ…', command=e.toggle_references)
    e.reference_button.pack(side='right')
    def wrap_caption(event):
        width=max(100,event.width-e.reference_button.winfo_reqwidth()-12)
        e.field_label.configure(wraplength=width);e.field_meaning.configure(wraplength=width)
    row.bind('<Configure>',wrap_caption)
    e.expression = tk.StringVar()
    e.expression.trace_add('write', e.edit_expression)
    e.expression_entry = ttk.Entry(box, textvariable=e.expression, font=(e.host.ui_font, 13))
    e.choice_entry = ttk.Combobox(box, textvariable=e.expression, state='normal')
    e.reference_frame = ttk.Frame(box)
    e.reference_frame.pack(fill='x', pady=(6, 0))
    e.expression_caption = ttk.Label(e.reference_frame, text='', style='AttributeMeaning.TLabel', wraplength=710)
    e.expression_caption.bind('<Configure>', lambda event: e.expression_caption.configure(wraplength=max(160, event.width - 8)))
    e.reference_controls = ttk.Frame(e.reference_frame)
    row = ttk.Frame(e.reference_controls)
    row.pack(fill='x')
    e.ref_kind = ttk.Combobox(row, values=schema.REFERENCE_TYPES, state='readonly', width=14)
    e.ref_kind.set('PARAM')
    e.ref_kind.pack(side='left')
    e.ref_kind.bind('<<ComboboxSelected>>', lambda _: e.update_role())
    e.ref_number = tk.StringVar(value='1')
    e.number_entry = ttk.Spinbox(row, from_=1, to=999, width=5, textvariable=e.ref_number)
    e.number_entry.pack(side='left', padx=6)
    e.ref_number.trace_add('write', lambda *_: e.update_role())
    ttk.Button(row,text='挿入',command=e.insert_reference,style='Compact.TButton').pack(side='left',padx=3)
    row=ttk.Frame(e.reference_controls);row.pack(fill='x',pady=(4,0))
    for label, command in [('÷ 2', e.half), ('式を整理', e.normalize_expression)]:
        ttk.Button(row, text=label, command=command,style='Compact.TButton').pack(side='left', padx=3)
    e.role_label = ttk.Label(e.reference_controls, text='', style='Muted.TLabel', wraplength=710)
    e.role_label.pack(anchor='w', fill='x', pady=(6, 0))
    e.role_label.bind('<Configure>', lambda event: e.role_label.configure(wraplength=max(160, event.width - 8)))
    footer=ttk.Frame(right);footer.pack(side='bottom',fill='x',before=e.tabs,pady=(6,0))
    e.context_helpers = ttk.Frame(footer)
    e.context_helpers.pack(fill='x')
    e.helper_buttons = [(ttk.Button(e.context_helpers, text=label, command=command), match) for label, command, match in [('NAPP 適用先', e.edit_napp, 'negative'), ('直径／半径', e.edit_sizes, 'LSNO'), ('LINE の点列', e.edit_points, 'LINE')]]
    e.validation_note = ttk.Label(footer, text='', foreground='#bb6440', wraplength=710)
    e.validation_note.pack(anchor='w', pady=(4, 0))
    e.validation_note.bind('<Configure>',lambda event:e.validation_note.configure(wraplength=max(160,event.width-4)))

    if point:
        from .point_canvas import PointCanvas
        e.point_canvas=PointCanvas(e,center)
        e.point_canvas.pack(fill='both',expand=True)
    else:
        ttk.Label(center,text='3D プレビュー · GMSET + PTSET',style='Heading.TLabel').pack(anchor='w',pady=(0,6))
        if not getattr(e.host,'is_preset_editor',False):
            pair_row=ttk.Frame(center);pair_row.pack(fill='x',pady=(0,6))
            ttk.Label(pair_row,text='適用する PTSET',style='Muted.TLabel').pack(side='left',padx=(0,8))
            e.ptset_choice=ttk.Combobox(pair_row,state='readonly');e.ptset_choice.pack(side='left',fill='x',expand=True)
            e.ptset_choice.bind('<<ComboboxSelected>>',e.assign_ptset)
            e.pairing_note=ttk.Label(center,text='',style='AttributeMeaning.TLabel',wraplength=500)
            e.pairing_note.pack(anchor='w',fill='x',pady=(0,6))
            e.pairing_note.bind('<Configure>',lambda event:e.pairing_note.configure(wraplength=max(160,event.width-4)))
        from .geometry_canvas import GeometryCanvas
        e.geometry_view=GeometryCanvas(e,center)
        e.geometry_view.pack(fill='both',expand=True)
        e.canvas=e.geometry_view.canvas
