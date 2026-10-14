"""Focused two-column layout for point and geometry authoring."""
import tkinter as tk
from tkinter import ttk
from . import element_schema as schema


def build_simple(editor):
    e = editor
    e.simple_layout = True
    point = e.kind == 'PTSET'
    e.canvas = None
    e.creating = e.settings_open = e.references_open = False

    top = ttk.Frame(e)
    top.pack(fill='x', pady=(0, 16))
    ttk.Label(top, text=e.kind, style='Heading.TLabel').pack(side='left')
    ttk.Label(top, text='ポイントを作成' if point else '形状を作成', style='Muted.TLabel').pack(side='left', padx=12)

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
    if not point:
        ttk.Button(row, text='構成プレビュー', command=e.open_preview).pack(side='left', padx=6)
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
    left = ttk.Frame(e.main_split, padding=(0, 0, 16, 0))
    right = ttk.Frame(e.main_split, padding=(16, 0, 0, 0))
    e.main_split.add(left, weight=1)
    e.main_split.add(right, weight=3)
    e.host.balance(e.main_split, (.30,))
    e.def_choice = tk.StringVar()
    ttk.Label(left, textvariable=e.def_name, style='Heading.TLabel', wraplength=290).pack(anchor='w', pady=(0, 4))
    ttk.Label(left, text='PARAM プリセット', style='Muted.TLabel').pack(anchor='w', pady=(8, 0))
    e.preset_choice = ttk.Combobox(left, state='readonly')
    e.preset_choice.pack(fill='x', pady=(6, 16))
    e.preset_choice.bind('<<ComboboxSelected>>', e.assign_preset)
    row = ttk.Frame(left)
    row.pack(fill='x', pady=(0, 8))
    ttk.Label(row, text='ポイント' if point else '形状の構成', style='Heading.TLabel').pack(side='left')
    e.add_button = ttk.Button(row, text='＋ 追加', command=e.toggle_create, style='Primary.TButton')
    e.add_button.pack(side='right')
    if point:ttk.Button(row,text='3D',command=e.open_point_canvas,width=4).pack(side='right',padx=5)

    e.creation_frame = ttk.LabelFrame(left, text='種類を選んで作成', padding=10)
    e.negative = tk.BooleanVar(value=False)
    if not point:
        ttk.Checkbutton(e.creation_frame, text='ネガティブ形状', variable=e.negative, command=e.populate_library).pack(anchor='w', pady=(0, 6))
    holder = ttk.Frame(e.creation_frame)
    holder.pack(fill='x')
    e.library = tk.Listbox(holder, height=4, exportselection=False, font=(e.host.ui_font, 10), relief='flat', selectbackground='#e4efff', selectforeground='#2269de')
    e.library.pack(side='left', fill='x', expand=True)
    scroll = ttk.Scrollbar(holder, command=e.library.yview)
    scroll.pack(side='right', fill='y')
    e.library.configure(yscrollcommand=scroll.set)
    e.type_help = ttk.Label(e.creation_frame, text='', wraplength=270, justify='left', style='Muted.TLabel')
    e.type_help.pack(fill='x', pady=10)
    e.creation_frame.bind('<Configure>', lambda event: e.type_help.configure(wraplength=max(140, event.width - 24)))
    e.library.bind('<<ListboxSelect>>', e.describe_selected_type)
    e.create_element_button = ttk.Button(e.creation_frame, text='作成', command=e.add_element, style='Primary.TButton')
    e.create_element_button.pack(fill='x')
    e.populate_library()

    e.tree_holder = ttk.Frame(left)
    e.tree_holder.pack(fill='both', expand=True)
    e.elements = ttk.Treeview(e.tree_holder, columns=('number', 'type') if point else ('type',), show='tree headings', selectmode='browse')
    e.elements.heading('#0', text='要素名')
    e.elements.column('#0', width=150, minwidth=70)
    e.elements.heading('type', text='種類')
    e.elements.column('type', width=70, minwidth=55)
    if point:
        e.elements.heading('number', text='番号')
        e.elements.column('number', width=45, minwidth=35)
    e.elements.grid(row=0, column=0, sticky='nsew')
    scroll = ttk.Scrollbar(e.tree_holder, command=e.elements.yview)
    scroll.grid(row=0, column=1, sticky='ns')
    e.elements.configure(yscrollcommand=scroll.set)
    e.tree_holder.rowconfigure(0, weight=1)
    e.tree_holder.columnconfigure(0, weight=1)
    e.elements.bind('<<TreeviewSelect>>', e.select_element)
    row = ttk.Frame(left)
    row.pack(side='bottom', fill='x', pady=(8, 0), before=e.tree_holder)
    more = ttk.Menubutton(row, text='操作 ▾')
    menu = tk.Menu(more, tearoff=False)
    for label, command in [('複製', e.duplicate_element), ('削除', e.delete_element), ('上へ移動', lambda: e.move_element(-1)), ('下へ移動', lambda: e.move_element(1))]:
        menu.add_command(label=label, command=command)
    menu.add_separator()
    menu.add_command(label='セットの設定・確認',command=e.toggle_settings)
    e.operations_menu=menu
    e.settings_menu_index=menu.index('end')
    more.configure(menu=menu)
    more.pack(side='left')
    e.child_button = ttk.Button(row, text='子要素を追加', command=e.add_child)
    if point:
        ttk.Label(row, text='P0：自動生成', style='Muted.TLabel').pack(side='right')

    ttk.Label(right, text='属性', style='Heading.TLabel').pack(anchor='w', pady=(0, 4))
    e.element_name = tk.StringVar()
    e.type_choice = tk.StringVar()
    e.element_note = ttk.Label(right, text='', style='Muted.TLabel', wraplength=740)
    e.element_note.pack(anchor='w', pady=(0, 12))

    e.tabs = ttk.Notebook(right)
    e.tabs.pack(fill='both', expand=True)
    sections = [('main', '基本属性' if point else '形状・位置')]
    sections += [('detail', '詳細属性')] if point else [('common', '共通属性'), ('negative', 'ネガティブ属性')]
    sections += [('extra', '保持した追加属性')]
    e.tables = {}
    e.tab_frames = {}
    e.section_order = [key for key, label in sections]
    for key, label in sections:
        frame = ttk.Frame(e.tabs, padding=8)
        e.tab_frames[key] = frame
        e.tabs.add(frame, text=label)
        table = e.host.table(frame, [('attr', '属性', 90), ('meaning', '意味', 230), ('value', '値・式', 350)], height=8)
        table.bind('<<TreeviewSelect>>', lambda event, section=key: e.select_field(section))
        table.bind('<Double-1>', lambda _: e.focus_value_input())
        e.tables[key] = table
    e.tabs.bind('<<NotebookTabChanged>>', e.tab_changed)

    box = ttk.Frame(right, padding=(0, 14, 0, 0))
    box.pack(side='bottom', fill='x', before=e.tabs)
    row = ttk.Frame(box)
    row.pack(fill='x', pady=(0, 8))
    e.field_label = ttk.Label(row, text='', style='Heading.TLabel')
    e.field_label.pack(side='left')
    e.reference_button = ttk.Button(row, text='PARAM を選ぶ…', command=e.toggle_references)
    e.reference_button.pack(side='right')
    e.expression = tk.StringVar()
    e.expression.trace_add('write', e.edit_expression)
    e.expression_entry = ttk.Entry(box, textvariable=e.expression, font=(e.host.ui_font, 13))
    e.expression_entry.pack(fill='x')
    e.choice_entry = ttk.Combobox(box, textvariable=e.expression, state='normal')
    e.reference_frame = ttk.Frame(box)
    e.reference_frame.pack(fill='x', pady=(6, 0))
    e.expression_caption = ttk.Label(e.reference_frame, text='', style='Muted.TLabel', wraplength=710)
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
    for label, command in [('挿入', e.insert_reference), ('÷ 2', e.half), ('式を整理', e.normalize_expression)]:
        ttk.Button(row, text=label, command=command).pack(side='left', padx=3)
    e.role_label = ttk.Label(e.reference_controls, text='', style='Muted.TLabel', wraplength=710)
    e.role_label.pack(anchor='w', fill='x', pady=(6, 0))
    e.role_label.bind('<Configure>', lambda event: e.role_label.configure(wraplength=max(160, event.width - 8)))
    e.context_helpers = ttk.Frame(box)
    e.context_helpers.pack(fill='x')
    e.helper_buttons = [(ttk.Button(e.context_helpers, text=label, command=command), match) for label, command, match in [('NAPP 適用先', e.edit_napp, 'negative'), ('直径／半径', e.edit_sizes, 'LSNO'), ('LINE の点列', e.edit_points, 'LINE')]]
    e.validation_note = ttk.Label(box, text='', foreground='#bb6440', wraplength=710)
    e.validation_note.pack(anchor='w', pady=(4, 0))
