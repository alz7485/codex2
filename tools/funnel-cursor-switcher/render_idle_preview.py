"""Preview the normal upper-left cursor rolling around its beam axis."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from idle_motion import STEPS, idle_sheet, turn_frame

ROOT = Path(__file__).resolve().parent

def font(size):
    for path in ('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 'C:/Windows/Fonts/meiryo.ttc'):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def render():
    sheet = idle_sheet(ROOT / 'カーソル' / 'ファンネル' / 'フィンファンネル.cur')
    title, small = font(17), font(13)
    frames = []
    for step in range(STEPS):
        canvas = Image.new('RGBA', (600, 320), '#19232e')
        draw = ImageDraw.Draw(canvas)
        draw.text((18, 12), '左上向きのまま、射線の方向を軸に回転', font=title, fill='white')
        draw.text((164, 62), '拡大', font=small, fill='#d7e3ee')
        draw.text((448, 62), '実際のサイズ', font=small, fill='#d7e3ee')
        canvas.alpha_composite(turn_frame(sheet, step, 192), (68, 28))
        canvas.alpha_composite(turn_frame(sheet, step, 32), (480, 139))
        draw.text((20, 286), '開始コマは通常カーソルと同じ絵・同じ位置です', font=small, fill='white')
        frames.append(canvas.convert('RGB'))
    path = ROOT / 'fin-idle-preview.gif'
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=50, loop=0)
    print(path)

if __name__ == '__main__':
    render()
