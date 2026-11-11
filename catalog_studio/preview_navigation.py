"""Middle-button orbit and click recenter; left button stays for editing."""
import tkinter as tk

def attach(view):
    c=view.canvas
    state={'start':None,'moved':False}
    def press(event):
        if not view.editor.commit_inline():return
        c.focus_set();state.update(start=(event.x,event.y),moved=False)
        view.orbit_start(event)
    def move(event):
        if state['start'] is None:return
        x,y=state['start']
        if abs(event.x-x)+abs(event.y-y)>3:state['moved']=True
        if state['moved']:view.orbit_move(event)
    def release(event):
        if state['start'] is not None and not state['moved']:
            x,y=state['start'];px,py=getattr(view.camera,'pan',(0,0))
            view.camera.pan=(px+c.winfo_width()/2-x,py+c.winfo_height()/2-y)
        state['start']=None;view.orbit=None;view.redraw()
    c.bind('<Button-2>',press);c.bind('<B2-Motion>',move);c.bind('<ButtonRelease-2>',release)
    def wire(event=None):
        target=view if hasattr(view,'render_mode') else None
        if target:
            target.render_mode.set('ソリッド' if target.render_mode.get()=='ワイヤー' else 'ワイヤー')
            target.display_changed(immediate=True)
        return 'break'
    c.bind('<F11>',wire)
    root=view._root()
    if not getattr(root,'_preview_f11',False):
        root._preview_f11=True
        def dispatch(event):
            # Visible page preview, including standalone SPEC windows.
            try:focus=root.focus_get()
            except (KeyError, tk.TclError):focus=None
            candidates=[v for v in getattr(root,'_preview_views',()) if v.winfo_exists() and v.winfo_ismapped() and hasattr(v,'render_mode')]
            for item in candidates:
                if focus and str(focus).startswith(str(item.winfo_toplevel())) and item.winfo_toplevel()!=root:
                    item.render_mode.set('ソリッド' if item.render_mode.get()=='ワイヤー' else 'ワイヤー');item.display_changed(immediate=True);return 'break'
            for item in candidates:
                if item.winfo_toplevel()==root:
                    item.render_mode.set('ソリッド' if item.render_mode.get()=='ワイヤー' else 'ワイヤー');item.display_changed(immediate=True);return 'break'
        root.bind('<F11>',dispatch,add='+')
