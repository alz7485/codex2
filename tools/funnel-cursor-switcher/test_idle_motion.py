import json
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from cursor_art import APPEARANCES, load_sprite
from effect_engine import ClickEvent, EffectEngine
from effect_settings import FIELDS, Settings, resolve
from idle_motion import NativeIdleCursor, PADDING, STEPS, animation_bytes, idle_sheet, read_turntable, turn_frame


ROOT = Path(__file__).resolve().parent
CURSOR = ROOT / "カーソル" / "ファンネル" / "フィンファンネル.cur"


def idle_engine(period=2.4, direction="順回転", path=CURSOR, enabled=True):
    config, _ = resolve(path.parent.name, {}, {"idle": {
        "motion": "横回転", "turn_period": period, "turn_direction": direction}})
    for group in FIELDS:
        config[group]["enabled"] = group == "idle" and enabled
    return EffectEngine(load_sprite(path), APPEARANCES[path.stem], config, path)


def advance(engine, time, pos=(0, 0), events=()):
    previous = engine.last_time
    if previous is not None:
        while time - previous > 0.5:
            previous += 0.5
            engine.step(pos, previous)
    return engine.step(pos, time, events)


class IdleMotion(unittest.TestCase):
    def test_rigid_c_turntable_front_edge_back_and_loop(self):
        sheet = idle_sheet(CURSOR)
        frames = read_turntable(sheet)
        self.assertEqual(len(frames), STEPS)
        # Enter from the actual upper-left pointer, including its original
        # placement relative to the click hotspot. Padding never scales it.
        original = load_sprite(CURSOR)
        first = turn_frame(sheet, 0)
        self.assertEqual(first.crop((PADDING, PADDING, PADDING+32, PADDING+32)).tobytes(), original.tobytes())
        # A roll about the beam keeps the long direction upper-left. Turning
        # about screen X would reverse the slope during the second half.
        for frame in frames:
            alpha = frame.getchannel('A')
            box = alpha.point(lambda a: 255 if a > 144 else 0).getbbox()
            self.assertTrue(0 < box[0] < box[2] < frame.width)
            self.assertTrue(0 < box[1] < box[3] < frame.height)
            points = [(x, y) for y in range(frame.height) for x in range(frame.width)
                      if alpha.getpixel((x, y)) > 144]
            mean_x = sum(p[0] for p in points) / len(points)
            mean_y = sum(p[1] for p in points) / len(points)
            covariance = sum((x-mean_x)*(y-mean_y) for x,y in points)
            self.assertGreater(covariance, 0)
        self.assertNotEqual(frames[0].tobytes(), frames[STEPS // 4].tobytes())
        self.assertEqual(turn_frame(sheet, 0).tobytes(), turn_frame(sheet, STEPS).tobytes())
        self.assertIsNone(idle_sheet(CURSOR.with_name("νガンダムHWS.cur")))

    def test_delay_speed_direction_and_movement_click_cancel(self):
        e = idle_engine()
        advance(e, 0)
        advance(e, 0.8)
        self.assertIsNone(e.idle_turn_step)
        advance(e, 1.5)
        self.assertEqual(e.idle_turn_step, 12)
        self.assertNotEqual(e.pointer_image.tobytes(), e.sprite.tobytes())
        for period, direction, expected in ((1.2, "順回転", 24), (2.4, "逆回転", 36)):
            other = idle_engine(period, direction)
            advance(other, 0)
            advance(other, 1.5)
            self.assertEqual(other.idle_turn_step, expected)
        advance(e, 1.52, (1, 0))
        self.assertIsNone(e.idle_turn_step)
        self.assertEqual(e.pointer_image.tobytes(), e.sprite.tobytes())
        advance(e, 2.6, (1, 0))
        self.assertIsNotNone(e.idle_turn_step)
        advance(e, 2.62, (1, 0), [ClickEvent("left", (1, 0), 2.62)])
        self.assertIsNone(e.idle_turn_step)
        e.step(None, 2.64)
        self.assertIsNone(e.idle_turn_step)

    def test_other_equipment_and_disabled_mode_keep_original_pointer(self):
        for path, enabled in ((CURSOR, False), (CURSOR.with_name("キュベレイ.cur"), True)):
            e = idle_engine(path=path, enabled=enabled)
            advance(e, 0)
            advance(e, 1.8)
            self.assertIsNone(e.idle_turn_step)
            self.assertEqual(e.pointer_image.tobytes(), e.sprite.tobytes())

    def test_settings_roundtrip_per_cursor(self):
        with TemporaryDirectory() as folder:
            p = Path(folder) / "effects.json"
            store = Settings(p)
            key = "ファンネル/フィンファンネル.cur"
            binding = store.binding(key)
            binding["overrides"]["idle"] = {"enabled": True, "motion": "横回転", "delay": 1.5,
                                               "turn_period": 3.2, "turn_direction": "逆回転"}
            store.cursors[key] = binding
            store.write()
            saved = Settings(p)
            self.assertEqual(saved.binding(key), binding)
            self.assertNotIn("idle", saved.binding("ファンネル/キュベレイ.cur")["overrides"])

    def test_native_animation_timing_hotspot_and_restore_once(self):
        e = idle_engine()
        data = animation_bytes(e.idle_sheet, 2.4, "順回転", e.hot)
        self.assertEqual(data[:4], b"RIFF")
        self.assertEqual(data[8:12], b"ACON")
        offset = data.index(b"rate")
        rates = struct.unpack_from("<" + "I" * STEPS, data, offset + 8)
        self.assertEqual(sum(rates), 144)
        self.assertGreaterEqual(min(rates), 1)
        at = data.index(b"icon") + 8
        self.assertEqual(struct.unpack_from("<HHH", data, at), (0, 2, 1))
        self.assertEqual(struct.unpack_from("<HH", data, at + 10), tuple(v+PADDING for v in e.hot))
        with TemporaryDirectory() as folder:
            api = Mock()
            native = NativeIdleCursor(e.idle_sheet, e.config["idle"], e.hot, folder, api)
            native.update(True)
            native.update(True)
            api.install.assert_called_once()
            native.update(False)
            native.close()
            api.restore.assert_called_once()
            self.assertEqual(native.path.read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
