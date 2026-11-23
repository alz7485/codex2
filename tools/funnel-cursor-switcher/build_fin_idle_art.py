"""Render a rigid C-shaped fin funnel using the approved launch textures."""
import math
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / '飛行アニメ' / 'ファンネル'
NAME = 'フィンファンネル.待機回転'
STEPS = 48

@lru_cache(maxsize=1)
def textures():
    with Image.open(FOLDER / 'フィンファンネル.収納正面.png') as image:
        image = image.convert('RGBA')
    bounds = image.getchannel('A').point(lambda a: 255 if a >= 144 else 0).getbbox()
    image = image.crop((bounds[0], bounds[1], (bounds[0] + bounds[2]) // 2, bounds[3]))
    # Existing-pixel boundaries of the two gold bands, not repainted artwork.
    return (image.crop((0, 0, image.width, 956)),
            image.crop((0, 1180, image.width, image.height)),
            image.crop((0, 956, image.width, 1180)))

def model():
    upper, lower, hinge = textures()
    length, width, gap, thick = 950.0, 154.0, 224.0, 12.0
    left, right = -length / 2, length / 2
    faces = []
    def face(points, normal, color=None, texture=None, uv=None):
        faces.append((points, normal, color, texture, uv))
    for center, outer, texture in ((-gap / 2, -1, upper), (gap / 2, 1, lower)):
        top, bottom = center - thick / 2, center + thick / 2
        for y, normal in ((top, (0, -1, 0)), (bottom, (0, 1, 0))):
            points = [(left, y, -width / 2), (right, y, -width / 2),
                      (right, y, width / 2), (left, y, width / 2)]
            if normal[1] == outer:
                uv = ([points[0], points[3], points[2], points[1]] if outer < 0 else
                      [points[1], points[2], points[3], points[0]])
                face(points, normal, texture=texture, uv=uv)
            else:
                face(points, normal, color=(48, 52, 65))
        for z, normal in ((-width / 2, (0, 0, -1)), (width / 2, (0, 0, 1))):
            face([(left, top, z), (right, top, z), (right, bottom, z), (left, bottom, z)],
                 normal, color=(202, 201, 209))
    top, bottom = -gap / 2 - thick / 2, gap / 2 + thick / 2
    for z, normal in ((-width / 2, (0, 0, -1)), (width / 2, (0, 0, 1))):
        points = [(right, top, z), (right + width, top, z),
                  (right + width, bottom, z), (right, bottom, z)]
        face(points, normal, texture=hinge, uv=points)
    for y, normal in ((top, (0, -1, 0)), (bottom, (0, 1, 0))):
        points = [(right, y, -width / 2), (right + width, y, -width / 2),
                  (right + width, y, width / 2), (right, y, width / 2)]
        face(points, normal, texture=hinge.crop((0, 41, hinge.width, hinge.height - 42)), uv=points)
        # Small gold end trims around a navy core, not a solid gold block.
        for edge in (right, right + width - 16):
            face([(edge, y, -width / 2), (edge + 16, y, -width / 2),
                  (edge + 16, y, width / 2), (edge, y, width / 2)], normal, color=(222, 168, 39))
    return faces, length + width, width / 2

def paint_texture(canvas, texture, corners, brightness):
    p, q, _, r = corners
    a, d = (q[0] - p[0]) / texture.width, (q[1] - p[1]) / texture.width
    b, e = (r[0] - p[0]) / texture.height, (r[1] - p[1]) / texture.height
    determinant = a * e - b * d
    if abs(determinant) < 1e-8:
        return
    inverse = (e / determinant, -b / determinant, (b * p[1] - e * p[0]) / determinant,
               -d / determinant, a / determinant, (d * p[0] - a * p[1]) / determinant)
    texture = ImageEnhance.Brightness(texture).enhance(brightness)
    projected = texture.transform(canvas.size, Image.Transform.AFFINE, inverse,
                                  Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0))
    canvas.alpha_composite(projected)

def render(step, side=96):
    supersample = 3
    target = side * supersample
    canvas = Image.new('RGBA', (target, target))
    faces, span, center_x = model()
    angle = step / STEPS * math.tau
    cosine, sine = math.cos(angle), math.sin(angle)
    scale = target * 0.92 / span
    def rotate(point):
        x, y, z = point
        return x, y * cosine - z * sine, y * sine + z * cosine
    def project(point):
        x, y, _ = rotate(point)
        return target / 2 + (x - center_x) * scale, target / 2 + y * scale
    visible = []
    for points, normal, color, texture, uv in faces:
        direction = rotate(normal)
        if direction[2] >= -1e-7:
            continue
        depth = sum(rotate(p)[2] for p in points) / len(points)
        visible.append((depth, points, direction, color, texture, uv))
    # Opaque surfaces occlude the far rail. No pose crossfade or deformation.
    for _, points, normal, color, texture, uv in sorted(visible, key=lambda item: item[0], reverse=True):
        shade = 0.78 + 0.22 * -normal[2]
        if texture is not None:
            paint_texture(canvas, texture, [project(p) for p in uv], shade)
        else:
            ImageDraw.Draw(canvas).polygon([project(p) for p in points],
                fill=tuple(round(c * shade) for c in color) + (255,))
    return canvas.resize((side, side), Image.Resampling.LANCZOS)

def build():
    sheet = Image.new('RGBA', (96 * STEPS, 96))
    for step in range(STEPS):
        sheet.alpha_composite(render(step), (step * 96, 0))
    path = FOLDER / (NAME + '.png')
    sheet.save(path)
    print(path)

if __name__ == '__main__':
    build()
