"""List context actions and drag ordering for catalogue elements."""
import tkinter as tk
from . import element_library


def context_menu(editor):
    e=editor;menu=tk.Menu(e.elements,tearoff=False)
    menu.add_command(label='複製',command=e.duplicate_element)
    menu.add_command(label='削除',command=e.delete_element)
    library=tk.Menu(menu,tearoff=False)
    from . import element_presets_ui
    library.add_command(label='現在を登録',command=lambda:element_presets_ui.register_current(e))
    library.add_command(label='呼び出し',command=lambda:element_presets_ui.choose(e,'recall'))
    library.add_command(label='登録したプリセットを編集',command=lambda:element_presets_ui.choose(e,'edit'))
    menu.add_separator();menu.add_cascade(label='要素プリセット',menu=library)
    menu.add_separator();menu.add_command(label='セットの設定・確認',command=e.toggle_settings)
    e.context_menu=e.operations_menu=menu;e.element_preset_menu=library;e.settings_menu_index=menu.index('end')
    from . import model_settings, element_schema as schema
    menu.add_command(label='確認用設計値（DDANGLE 等）',command=lambda:model_settings.edit(e))
    negatives=tk.Menu(menu,tearoff=False)
    for kind in schema.NEGATIVE_BASE:
        negatives.add_command(label=kind,command=lambda k=kind:e.add_negative_child(k))
    menu.add_cascade(label='負形状を子として追加',menu=negatives)
    negative_index=menu.index('end')
    def popup(event):
        ident=e.elements.identify_row(event.y)
        if ident:e.elements.selection_set(ident);e.select_element()
        for index in (0,1):menu.entryconfigure(index,state='normal' if ident else 'disabled')
        node=e.element();menu.entryconfigure(negative_index,state='normal' if node and any(k in schema.NEGATIVE_BASE for k in schema.allowed_children(node['type'])) else 'disabled')
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:menu.grab_release()
    e.elements.bind('<Button-3>',popup)


def enable_drag(editor):
    e=editor;e.drag_source=None;e.drag_active=False;e.drop_target=None
    e.elements.tag_configure('drop_target',background='#dcece6')
    def clear():
        if e.drop_target and e.elements.exists(e.drop_target):e.elements.item(e.drop_target,tags=())
        e.drop_target=None
    def press(event):
        e.drag_source=e.elements.identify_row(event.y);e.drag_start=event.y;e.drag_active=False
    def move(event):
        if not e.drag_source or abs(event.y-e.drag_start)<5:return
        e.drag_active=True;clear();target=e.elements.identify_row(event.y)
        if target and target!=e.drag_source and e.elements.parent(target)==e.elements.parent(e.drag_source):
            e.drop_target=target;e.elements.item(target,tags=('drop_target',))
        if event.y<35:e.elements.yview_scroll(-1,'units')
        elif event.y>e.elements.winfo_height()-20:e.elements.yview_scroll(1,'units')
        return 'break'
    def release(event):
        source=e.drag_source;target=e.elements.identify_row(event.y);active=e.drag_active
        e.drag_source=None;e.drag_active=False;clear()
        if not active:return
        if not target or target==source or e.elements.parent(target)!=e.elements.parent(source):return 'break'
        siblings=list(e.elements.get_children(e.elements.parent(source)));siblings.remove(source)
        index=siblings.index(target);box=e.elements.bbox(target)
        if box and event.y>box[1]+box[3]/2:index+=1
        try:
            if not e.commit_inline():return 'break'
            if element_library.reorder(e.data,e.definition(),source,index):
                e.element_id=source
                if e.point_canvas:e.point_canvas.cancel()
                e.host.mark();e.refresh();e.elements.see(source)
        except ValueError as exc:e.host.status.configure(text=str(exc))
        return 'break'
    e.elements.bind('<ButtonPress-1>',press,add='+')
    e.elements.bind('<B1-Motion>',move)
    e.elements.bind('<ButtonRelease-1>',release)
