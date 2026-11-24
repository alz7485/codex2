"""Pack the Blender field photographs without cropping their emitter pivots."""
import sys
from pathlib import Path
from PIL import Image

out = Path(__file__).resolve().parents[2] / "飛行アニメ/ファンネル/フィンファンネル.バリア.png"
sheet = Image.new("RGBA", (4*192,5*192))
for station in range(5):
    for pose in range(4):
        with Image.open(Path(sys.argv[1])/f"{station}-{pose}.png") as image:
            assert image.size == (192,192)
            sheet.paste(image,(pose*192,station*192))
sheet.save(out)
