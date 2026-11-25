from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from runpy import run_path
from zipfile import ZipFile
from io import BytesIO
import base64
import time
import tkinter as tk
from PIL import ImageGrab

root_path = Path(__file__).parent
data = b"".join(base64.b64decode(p.read_text()) for p in sorted((root_path/"assets190").glob("*.b64")))
with ZipFile(BytesIO(data)) as z:
    z.extractall(root_path)
with ZipFile(root_path/"hinu122/model-assets.zip") as z:
    z.extractall(root_path/"hinu122")
app = run_path(str(root_path/"FunnelCursorSwitcher.pyw"))
app["enable_monitor_dpi"]()
out = root_path/"ui-screenshots"
out.mkdir(exist_ok=True)
with TemporaryDirectory() as profile:
    system = Mock(store=Path(profile))
    window = tk.Tk()
    from effect_editor import Editor
    ui = Editor(window,app["discover_cursors"](root_path/"カーソル"),system,app["APP_NAME"])
    ui.effect = Mock()
    ui.preview.mode.set("停止")
    window.geometry("+50+50")
    names = [("01-fin","フィンファンネル"),("02-qubeley","キュベレイ"),("03-sazabi","サザビー"),("04-hinu","Hi-νガンダム"),("05-hinu-hws","Hi-νガンダムHWS")]
    names.append(("06-dragoon","ストライクフリーダム"))
    for filename,name in names:
        category="ドラグーン" if filename=="06-dragoon" else "ファンネル"
        ui.equipment_buttons[root_path/"カーソル"/category/(name+".cur")].invoke()
        ui.update_preview()
        window.lift()
        window.update()
        for i in range(8):
            window.update()
            time.sleep(.08)
        x,y=window.winfo_rootx(),window.winfo_rooty()
        ImageGrab.grab(bbox=(x,y,x+window.winfo_width(),y+window.winfo_height())).save(out/(filename+".png"))
        print(filename,window.winfo_width(),window.winfo_height(),flush=True)
    ui.close()
