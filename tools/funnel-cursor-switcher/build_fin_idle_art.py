"""Rotate the normal upper-left fin cursor as two rigid parallel panels."""
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

@lru_cache(maxsize=1)
def normal_cursor():
    import struct
    data = (ROOT / 'カーソル/ファンネル/フィンファンネル.cur').read_bytes()
    count = struct.unpack_from('<H', data, 4)[0]
    entries = [struct.unpack_from('<BBBBHHII', data, 6 + i * 16) for i in range(count)]
    entry = max(entries, key=lambda e: e[0] or 256)
    width, height, offset = entry[0] or 256, entry[1] or 256, entry[-1]
    return Image.frombytes('RGBA', (width, height),
        data[offset + 40:offset + 40 + width * height * 4], 'raw', 'BGRA', 0, -1)


def add(*vectors):
    return tuple(sum(parts) for parts in zip(*vectors))


def mul(vector, factor):
    return tuple(value * factor for value in vector)


def material_from_cursor(points, shift=(0, 0), size=(96, 512)):
    # Project the existing artwork onto a real planar surface in its initial
    # pose. Its markings and shading are not replaced by a new side drawing.
    p, q, _, r = points
    coefficients = ((q[0] - p[0]) / size[0], (r[0] - p[0]) / size[1], p[0] + shift[0],
                    (q[1] - p[1]) / size[0], (r[1] - p[1]) / size[1], p[1] + shift[1])
    return normal_cursor().transform(size, Image.Transform.AFFINE, coefficients,
                                     Image.Resampling.BICUBIC)


@lru_cache(maxsize=1)
def model():
    # The two parallel panels are fitted to the NORMAL upper-left cursor.
    # All three basis vectors are perpendicular in 3D. This reproduces its
    # initial diagonal projection without rotating the sprite into a side pose.
    length = (178.0, 218.0, 124.2367592743977)
    separation = (52.0, 0.0, -74.5029083677332)
    width = (-14.0, 17.0, -9.7716654177742)
    normal = mul(separation, 1 / math.sqrt(sum(c*c for c in separation)))
    origin = (15.0, 8.0, -36.0)
    faces = []
    def face(points, outward, texture=None, color=None):
        faces.append((points, outward, color, texture, points))
    panels = []
    for index in range(2):
        tip = add(origin, mul(separation, index))
        points = [tip, add(tip, width), add(tip, width, length), add(tip, length)]
        panels.append(points)
        # At the starting angle the left inner face is navy; the right
        # outer face is white. The supplied photograph shows this distinction.
        for direction in (-1, 1):
            surface = [add(p, mul(normal, direction * 5.0)) for p in points]
            outside = direction == (-1 if index == 0 else 1)
            if direction == 1:
                texture = material_from_cursor(surface)
            elif outside:
                texture = textures()[0]
            else:
                texture = material_from_cursor(surface, shift=(-52, 0))
            face(surface, mul(normal, direction), texture=texture)
        # Thin panel edges, rather than a solid white box.
        for edge in range(4):
            a, b = points[edge], points[(edge + 1) % 4]
            edge_vector = tuple(b[i] - a[i] for i in range(3))
            outward = (edge_vector[1] * normal[2] - edge_vector[2] * normal[1],
                       edge_vector[2] * normal[0] - edge_vector[0] * normal[2],
                       edge_vector[0] * normal[1] - edge_vector[1] * normal[0])
            norm = math.sqrt(sum(c*c for c in outward))
            outward = mul(outward, 1 / norm)
            quad = [add(a, mul(normal, -5.0)), add(a, mul(normal, 5.0)),
                    add(b, mul(normal, 5.0)), add(b, mul(normal, -5.0))]
            face(quad, outward, color=(196, 196, 206) if edge in (1, 3) else (42, 45, 57))
    # A short connecting hinge at the lower-right of the unchanged initial pose.
    a = add(origin, mul(length, .95))
    bridge_length = mul(length, .075)
    box = [a, add(a, separation), add(a, separation, width), add(a, width)]
    end = [add(p, bridge_length) for p in box]
    for quad in (box, list(reversed(end)),
                 *[[box[i], end[i], end[(i+1)%4], box[(i+1)%4]] for i in range(4)]):
        u = tuple(quad[1][i]-quad[0][i] for i in range(3))
        v = tuple(quad[3][i]-quad[0][i] for i in range(3))
        n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        magnitude = math.sqrt(sum(c*c for c in n))
        n = mul(n, 1/magnitude)
        if n[2] < 0:
            texture = material_from_cursor(quad)
        else:
            texture = Image.new('RGBA', (128, 64), (37, 42, 52, 255))
            draw = ImageDraw.Draw(texture)
            draw.rectangle((0, 0, 10, 63), fill=(218, 166, 39))
            draw.rectangle((117, 0, 127, 63), fill=(218, 166, 39))
            draw.rectangle((40, 13, 87, 51), fill=(23, 29, 37), outline=(72, 80, 92), width=3)
            for y in (23, 32, 41):
                draw.line((48, y, 79, y), fill=(91, 98, 109), width=2)
        face(quad, n, texture=texture, color=(48, 49, 57))
    return faces

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
    if step % STEPS == 0:
        if side == 32:
            with Image.open(ROOT / 'カーソル/ファンネル/フィンファンネル.png') as image:
                return image.convert('RGBA')
        return normal_cursor().resize((side, side), Image.Resampling.LANCZOS)
    target = side * 3
    canvas = Image.new('RGBA', (target, target))
    angle = step / STEPS * math.tau
    cosine, sine = math.cos(angle), math.sin(angle)
    def rotate(point, is_normal=False):
        x, y, z = point
        if not is_normal:
            y -= 128
        return x, y * cosine - z * sine, y * sine + z * cosine
    def project(point):
        x, y, _ = rotate(point)
        return x / 256 * target, (128 + y) / 256 * target
    visible = []
    for points, normal, color, texture, uv in model():
        direction = rotate(normal, True)
        if direction[2] >= -1e-7:
            continue
        depth = sum(rotate(p)[2] for p in points) / len(points)
        visible.append((depth, points, direction, color, texture, uv))
    for _, points, normal, color, texture, uv in sorted(visible, key=lambda item: item[0], reverse=True):
        shade = 0.86 + 0.14 * -normal[2]
        if texture is not None:
            paint_texture(canvas, texture, [project(p) for p in uv], min(shade, 1))
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
