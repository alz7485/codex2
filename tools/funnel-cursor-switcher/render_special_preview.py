"""Render real special effects to reviewable GIFs without a Windows desktop."""

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cursor_art import APPEARANCES, load_sprite
from effect_engine import CENTER, ClickEvent, EffectEngine
from effect_settings import FIELDS, NAMES, SPECIAL, resolve
from equipment_catalog import is_frozen


ROOT = Path(__file__).resolve().parent
FPS = 50  # GIF delays are multiples of 10 ms; 20 ms preserves engine timing.


def caption_font():
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "C:/Windows/Fonts/meiryo.ttc"):
        if Path(path).is_file():
            return ImageFont.truetype(path, 11)
    return None


def preview_candidates(group, include_frozen=False):
    return sorted(key for key in SPECIAL[group] if include_frozen or not is_frozen(key))


def render(destination=None, all_actions=False, group=None, show_pointer=True, include_frozen=False):
    requested_group = group
    groups = ([group] if group else [g for g in SPECIAL if preview_candidates(g, include_frozen)]
              if all_actions else ["spiral", "barrier"])
    for selected in groups:
        if not preview_candidates(selected, include_frozen):
            raise ValueError("この演出の装備は凍結中です。保管確認には --include-frozen を指定してください。")
    columns, rows = (1, 1) if group else (3, 2) if all_actions else (2, 1)
    page_size = columns * rows
    frames = []
    font = caption_font()
    for page in range(0, len(groups), page_size):
        engines = []
        for group in groups[page:page + page_size]:
            candidates = preview_candidates(group, include_frozen)
            key = next((k for k in candidates if "サザビー" in k), candidates[0])
            if group == "barrier":
                key = next((k for k in candidates if k.endswith("/フィンファンネル.cur")), key)
            path = ROOT / "カーソル" / key
            config, _ = resolve(path.parent.name, {}, {})
            for name in FIELDS:
                config[name]["enabled"] = name == group
            engine = EffectEngine(load_sprite(path), APPEARANCES[path.stem], config, path, seed=73)
            engines.append((group, path, engine))
        frame_count = max(125, math.ceil(max(max(layer.lifetime for layer in e.layers) for g, p, e in engines) * FPS) + 20)
        for i in range(frame_count):
            now = i / FPS
            canvas = Image.new("RGB", (256 * columns, 296 * rows), "#16202c")
            labels = ImageDraw.Draw(canvas)
            for index, (group, path, engine) in enumerate(engines):
                x, y = (index % columns) * 256, (index // columns) * 296
                events = [ClickEvent("left", (0, 0), now, 3)] if i == 0 else []
                effect = engine.step((0, 0), now, events)
                tile = Image.new("RGBA", (256, 256), "#16202c")
                if effect is not None:
                    tile.alpha_composite(effect)
                if show_pointer:
                    engine.stamp(tile, engine.sprite, (CENTER - engine.hot[0], CENTER - engine.hot[1]), 1)
                if requested_group == "shield" and i == round(engine.config["shield"]["duration"] * engine.layers[0].JOIN_AT * FPS):
                    tile.convert("RGB").resize((768, 768), Image.Resampling.LANCZOS).save(ROOT / "shield-assembly.png")
                canvas.paste(tile.convert("RGB"), (x, y + 24))
                name = path.stem.replace("ロングレンジ・フィン・ファンネル（RX-93ff）", "RX-93ff")
                title = (name + ("（演出のみ）" if not show_pointer else "")) if font else group
                detail = NAMES[group] if font else group
                if font and group == "volley" and path.stem == "サザビー":
                    action = engine.layers[0]
                    p = action.launch_progress(now)
                    detail = ("6基とも羽を閉じて上へ射出" if p < action.OPEN_AT else
                              "羽を開いて方向を変える" if p < action.TURN_AT + 0.08 else
                              "黄色い軌跡を残して6方向へ" if p < action.DEPART_AT else
                              "残光が薄れて消える" if now < action.launch_end else
                              "全機フレームアウト・一拍" if now < action.entry_at else
                              "外側から奥へ向いて再登場" if now < action.fire_at else
                              "奥の狭い範囲へ一斉射撃" if now < action.fire_end else
                              "ビームの余韻" if now < action.after_end else
                              "射撃位置で静止・消灯" if now < action.lifetime else "")
                if font and group == "cannon":
                    action = engine.layers[0]
                    p = action.progress_at(now)
                    detail = ("先端を上にして待機" if p < action.HOLD_END else
                              "閉じたまま上へ加速" if p < action.EXIT_END else
                              "フレームアウト・一拍" if p < action.ENTRY_AT else
                              "閉じたまま右から進入" if p < action.ENTRY_END else
                              "射撃位置で停止" if p < action.OPEN_AT else
                              "先端を開放" if p < action.OPEN_END else
                              "根元で光を溜める" if p < action.FIRE_AT else
                              "ビーム発射" if p < action.FIRE_END else
                              "先端を閉じて終了" if p < 1 else "")
                if font and group == "barrier" and engine.layers[0].has_rack:
                    action = engine.layers[0]
                    phase = action.field_progress(now)
                    opened_at = action.RACK_END + action.c["duration"] * action.OPEN_END
                    detail = ("6基の収納配置" if now < action.RACK_HOLD else
                              "右から1基ずつ上方へ射出" if now < action.RACK_EXIT_END else
                              "全機フレームアウト・一拍" if now < action.RACK_END else
                              "上方から三角形の頂点へ" if phase < 0.28 else
                              "内側へ向きヒンジ展開" if phase < action.OPEN_END else
                              "ヒンジ全開・一拍" if now < opened_at + action.HINGE_BEAT else
                              "Δ型Iフィールド" if phase < 1 else "")
                if font and group == "dragoon" and engine.layers[0].is_super:
                    action = engine.layers[0]
                    p = action.progress_at(now)
                    detail = ("左右4基の放射配置" if p < action.HOLD_END else
                              "外側へ射出" if p < action.EXIT_END else
                              "全機フレームアウト・2拍" if p < action.FIRE_AT else
                              "様々な角度から一斉射撃" if p < action.FIRE_END else
                              "ビームの余韻" if p < action.AFTERGLOW_END else "")
                labels.text((x + 8, y + 2), title, fill="white", font=font)
                labels.text((x + 8, y + 280), detail, fill="white", font=font)
            if not requested_group:
                labels.text((canvas.width - 110, 2), f"{page // page_size + 1} / {(len(groups) + page_size - 1) // page_size}   {now:.2f}s", fill="white")
            frames.append(canvas)
    destination = destination or ROOT / (f"{requested_group}-preview.gif" if requested_group else
                                        "archive-actions-preview.gif" if all_actions and include_frozen else
                                        "active-actions-preview.gif" if all_actions else "special-preview.gif")
    frames[0].save(destination, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Preview the current equipment actions")
    parser.add_argument("--include-frozen", action="store_true", help="Explicitly include archived equipment")
    parser.add_argument("--group", choices=tuple(SPECIAL), help="Preview a single special action")
    parser.add_argument("--effects-only", action="store_true", help="Omit the normal mouse pointer from the preview")
    args = parser.parse_args()
    render(all_actions=args.all, group=args.group, show_pointer=not args.effects_only, include_frozen=args.include_frozen)
