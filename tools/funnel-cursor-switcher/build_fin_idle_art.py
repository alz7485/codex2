"""Assemble the app's Windows cursor and sprites from Blender's RGBA renders."""
import argparse
import struct
from pathlib import Path

from PIL import Image

from build_qubeley_art import dib, visible_bounds
from idle_motion import CELL, STEPS

ROOT = Path(__file__).resolve().parent
NAME = 'フィンファンネル'
ART = ROOT / '飛行アニメ' / 'ファンネル'
CUR = ROOT / 'カーソル' / 'ファンネル' / (NAME + '.cur')

def square_bounds(image):
    x0, y0, x1, y1 = visible_bounds(image)
    edge = max(x1-x0, y1-y0) + 4
    left, top = (x0+x1-edge)//2, (y0+y1-edge)//2
    return left, top, left+edge, top+edge

def build(folder):
    def photo(name):
        with Image.open(folder / (name+'.png')) as im:
            return im.convert('RGBA')

    resting = photo('roll-00')
    box = square_bounds(resting)
    body = resting.crop(box)
    # The click point follows the exposed leading tip at each native resolution.
    directory = bytearray()
    payloads = bytearray()
    old = CUR.read_bytes()
    count = struct.unpack_from('<H',old,4)[0]
    for index in range(count):
        w, h = struct.unpack_from('BB',old,6+16*index)
        side = w or 256
        icon = body.resize((side,side), Image.Resampling.LANCZOS)
        alpha = icon.getchannel('A')
        hx,hy = min(((x,y) for y in range(side) for x in range(side)
                     if alpha.getpixel((x,y)) >= 175), key=lambda xy: (sum(xy),xy[1]))
        payload = dib(icon)
        directory.extend(struct.pack('<BBBBHHII',w,h,0,0,hx,hy,len(payload),6+16*count+len(payloads)))
        payloads.extend(payload)
        if side == 32:
            icon.save(CUR.with_suffix('.png'))
    CUR.write_bytes(old[:6]+directory+payloads)

    idle = Image.new('RGBA',(CELL*STEPS,CELL))
    # Fixed film gate for all angles, with 8px of ANI padding at native scale.
    margin=(box[2]-box[0])/4
    gate=(box[0]-margin,box[1]-margin,box[2]+margin,box[3]+margin)
    for i in range(STEPS):
        image=photo(f'roll-{i:02d}').transform((CELL,CELL),Image.Transform.EXTENT,gate,Image.Resampling.BICUBIC)
        idle.alpha_composite(image,(i*CELL,0))
    idle.save(ART / (NAME+'.待機回転.png'))

    for prefix,suffix in [('flight',''),('open','.展開')]:
        strip=Image.new('RGBA',(384,96))
        for i in range(4):
            strip.alpha_composite(photo(f'{prefix}-{i}').resize((96,96),Image.Resampling.LANCZOS),(96*i,0))
        strip.save(ART / (NAME+suffix+'.png'))

    for label,suffix in [('rack','.3D収納正面'),('rack-fold','.3D収納中央')]:
        unit=photo(label)
        unit=unit.crop(visible_bounds(unit))
        pair=Image.new('RGBA',(unit.width*2,unit.height))
        pair.alpha_composite(unit,(0,0))
        pair.alpha_composite(unit,(unit.width,0))
        pair.save(ART / (NAME+suffix+'.png'))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('renders',type=Path)
    build(parser.parse_args().renders)
