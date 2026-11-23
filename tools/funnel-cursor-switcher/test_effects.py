import unittest
from copy import deepcopy
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory

from cursor_art import APPEARANCES, load_sprite
from effect_engine import (
    CENTER,
    ClickEvent,
    ClickTracker,
    EffectEngine,
    Followers,
    Particles,
    Rare,
)
from effect_settings import (
    BUTTONS,
    MODIFIERS,
    SPECIAL,
    FIELDS,
    SAMPLES,
    Settings,
    atomic_write,
    difference,
    encode,
    patch,
    read_preset,
    resolve,
)

ROOT = Path(__file__).resolve().parent
CURSOR = ROOT / "カーソル" / "ファンネル" / "キュベレイ.cur"
SPRITE = load_sprite(CURSOR)


def engine(groups=(), edits=None, cursor=CURSOR):
    config, _ = resolve("ファンネル", {}, edits or {})
    for g in FIELDS:
        config[g]["enabled"] = g in groups
    return EffectEngine(
        SPRITE if cursor == CURSOR else load_sprite(cursor), APPEARANCES[cursor.stem], config, cursor, seed=73
    )


class Rendering(unittest.TestCase):
    def test_independent_and_combined(self):
        for special, name in (("spiral", "キュベレイ"), ("barrier", "フィンファンネル")):
            available = [g for g in FIELDS if g not in SPECIAL or g == special]
            for flags in product((False, True), repeat=len(available)):
                groups = [g for g, on in zip(available, flags) if on]
                self.check_combination(groups, CURSOR.with_name(name + ".cur"))

    def check_combination(self, groups, cursor):
        with self.subTest(groups=groups):
            e = engine(groups, {"idle": {"delay": 0.1}, "rare": {"cooldown": 3, "frequency": 12}}, cursor)
            self.assertEqual(len(e.layers), len(groups))
            seen = False
            for i in range(25):
                pos = (-125 + i * 3, -97) if i < 10 else (-98, -97)
                event = [ClickEvent("left", pos, i / 60, 3)] if i == 9 else []
                frame = e.step(pos, i / 60, event)
                if groups == ["rare"] and i == 10:
                    e.layers[0].next = 0.21
                if frame is not None:
                    seen |= bool(frame.getbbox())
                    self.assertEqual(frame.getpixel((CENTER, CENTER))[3], 0)
            self.assertEqual(seen, bool(groups))
            self.assertIsNone(e.step(None, 1))
            self.assertFalse(e.has_moved)

    def test_spiral_launch_anchor_and_lifetime(self):
        e = engine(["spiral"])
        origin = (-100, 20)
        self.assertIsNone(e.step(origin, 0, [ClickEvent("right", origin, 0)]))
        e.step(origin, 0.1, [ClickEvent("left", origin, 0.1, 3)])
        fixed = e.step(origin, 0.5)
        shifted = e.step((-90, 20), 0.5, [ClickEvent("double", origin, 0.5)])
        self.assertEqual(
            shifted.getbbox(), tuple(n - 10 if i % 2 == 0 else n for i, n in enumerate(fixed.getbbox()))
        )
        self.assertEqual(e.layers[0].last_launch, 0.1)
        self.assertIsNone(e.step(origin, 1.3))

    def test_special_command_and_cooldown(self):
        pos = (10, 20)
        for group, name in (("spiral", "キュベレイ"), ("barrier", "フィンファンネル")):
            path = CURSOR.with_name(name + ".cur")
            for keys, mask in MODIFIERS.items():
                for label, button in BUTTONS.items():
                    e = engine([group], {group: {"modifiers": keys, "button": label}}, path)
                    self.assertIsNone(e.step(pos, 0, [ClickEvent(button, pos, 0)]))
                    self.assertIsNone(e.step(pos, 0.05, [ClickEvent(button, pos, 0.05, mask ^ 1)]))
                    other = "right" if button == "left" else "left"
                    self.assertIsNone(e.step(pos, 0.1, [ClickEvent(other, pos, 0.1, mask)]))
                    e.step(pos, 0.2, [ClickEvent(button, pos, 0.2, mask)])
                    self.assertTrue(e.step(pos, 0.5).getbbox())
                    e.step(pos, 1.2, [ClickEvent(button, pos, 1.2, mask)])
                    self.assertEqual(e.layers[0].last_launch, 0.2)
                    self.assertIsNone(e.step(pos, 2.2))
                    e.step(pos, 3.3, [ClickEvent(button, pos, 3.3, mask)])
                    self.assertEqual(e.layers[0].last_launch, 3.3)
        self.assertIsNone(engine(["barrier"]).step(pos, 0, [ClickEvent("left", pos, 0, 3)]))

    def test_velocity_transitions(self):
        e = engine(["boost", "trail"])
        self.assertIsNone(e.step((0, 0), 0))
        self.assertIsNotNone(e.step((4, 0), 0.02))
        self.assertAlmostEqual(e.speed, 200)
        self.assertTrue(e.started)
        e.step((4, 0), 0.10)
        e.step((4, 0), 0.18)
        self.assertTrue(e.stopped)
        self.assertIsNone(e.step((4, 0), 0.8))
        self.assertIsNone(e.step((-3800, -1600), 0.82))
        self.assertFalse(e.has_moved)

    def test_click_precedence(self):
        tracker = ClickTracker()
        e = engine(["click"])
        events = [tracker.press("left", (4, 4), 0.1), tracker.press("left", (5, 4), 0.21)]
        self.assertEqual([event.kind for event in events], ["left", "double"])
        e.step((5, 4), 0.22, events)
        self.assertEqual([event.kind for event in e.layers[0].events], ["double"])
        self.assertEqual(tracker.press("left", (5, 4), 0.26).kind, "left")
        self.assertEqual(tracker.press("left", (18, 4), 0.3).kind, "left")
        self.assertEqual(tracker.press("right", (18, 4), 0.32).kind, "right")
        self.assertIsNone(e.step((5, 4), 1.0))

    def test_burst_and_rare_interrupt(self):
        e = engine(FIELDS, {"particles": {"maximum": 11}, "followers": {"count": 3}})
        pos = (20, 20)
        e.step(pos, 0)
        rare = next(l for l in e.layers if isinstance(l, Rare))
        rare.next = 0.1
        e.step(pos, 0.11)
        self.assertLess(rare.phase, 1)
        for i in range(1, 100):
            pos = (20 + i, 20)
            now = 0.11 + i / 60
            e.step(pos, now, [ClickEvent("left", pos, now)] * 25)
        self.assertEqual(rare.phase, 1)
        for layer in e.layers:
            if isinstance(layer, Particles):
                self.assertLessEqual(len(layer.items), 11)
            if isinstance(layer, Followers):
                self.assertEqual(len(layer.positions), 3)

    def test_visual_styles(self):
        for g, fields in FIELDS.items():
            for k, f in fields.items():
                if g in SPECIAL or len(f.choices) < 2:
                    continue
                results = set()
                for v in f.choices:
                    e = engine([g], {g: {k: v}})
                    frames = []
                    for i in range(27):
                        pos = (i * 3, min(i, 9)) if i < 16 else (45, 9)
                        kind = k if k in ("left", "right", "double") else "left"
                        frame = e.step(pos, i / 60, [ClickEvent(kind, pos, i / 60)] if i == 9 else [])
                        if frame:
                            frames.append(hash(frame.tobytes()))
                    results.add(tuple(frames))
                self.assertGreater(len(results), 1, (g, k))


class Persistence(unittest.TestCase):
    def test_spiral_defaults_and_existing_bindings(self):
        with TemporaryDirectory() as temp:
            store = Settings(Path(temp) / "effects.json")
            for path in CURSOR.parent.glob("キュベレイ*.cur"):
                key = f"ファンネル/{path.name}"
                self.assertTrue(store.binding(key)["overrides"]["spiral"]["enabled"])
            key = "ファンネル/キュベレイ.cur"
            store.cursors[key] = {"preset": "標準", "overrides": {}}
            store.write()
            self.assertEqual(Settings(store.path).binding(key)["overrides"], {})
            self.assertEqual(store.binding("ファンネル/サザビー.cur")["overrides"], {})

    def test_priority_and_diff(self):
        p = {"trail": {"style": "残像", "width": 4}}
        base, _ = resolve("インコム", p, {})
        full, source = resolve("インコム", p, {"trail": {"width": 5}})
        self.assertEqual(full["trail"]["style"], "残像")
        self.assertEqual(source["trail"]["style"], "プリセット")
        self.assertEqual(full["trail"]["width"], 5)
        self.assertEqual(difference(full, base), {"trail": {"width": 5}})
        self.assertEqual(resolve("インコム", {}, {})[1]["trail"]["style"], "分類")

    def test_roundtrip_and_concurrent_write(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "設定.json"
            s = Settings(path)
            old = Settings(path)
            key = "自作/兵装.ani"
            s.presets["私の設定"] = {"boost": {"width": 1.6}}
            s.cursors[key] = {"preset": "私の設定", "overrides": {"click": {"enabled": True}}}
            s.active = key
            s.write()
            with self.assertRaises(ValueError):
                old.write()
            again = Settings(path)
            self.assertEqual(again.binding(key), s.binding(key))
            self.assertEqual(again.active, key)
            draft = again.binding(key)
            draft["preset"] = "控えめ"
            self.assertEqual(again.binding(key)["preset"], "私の設定")
            file = Path(temp) / "交換.json"
            atomic_write(file, encode(dict(schema_version=1, name="私の設定", effects=s.presets["私の設定"])))
            self.assertEqual(read_preset(file), ("私の設定", s.presets["私の設定"]))

    def test_corruption_validation_and_unknown_fields(self):
        for original in (b"{", b'{"schema_version":0}', b"[]", b'{"schema_version":1,"presets":3}'):
            with TemporaryDirectory() as temp:
                path = Path(temp) / "effects.json"
                path.write_bytes(original)
                s = Settings(path)
                self.assertTrue(s.warning)
                s.write()
                self.assertEqual(path.with_suffix(".bak").read_bytes(), original)
                self.assertFalse(Settings(path).warning)
        self.assertEqual(patch({"other": 3, "particles": {"rate": False, "life": float("nan")}}), {})
        with self.assertRaises(ValueError):
            patch({"boost": {"color": "broken"}}, strict=True)
        before = deepcopy(SAMPLES)
        resolve("ビット", SAMPLES["戦闘モード"], {})
        self.assertEqual(SAMPLES, before)


if __name__ == "__main__":
    unittest.main()
