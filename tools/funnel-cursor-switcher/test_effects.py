import math
import struct
import unittest
from copy import deepcopy
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch as mock_patch

from cursor_art import APPEARANCES, load_sprite
from flight_art import read_poses
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
    special_group,
)

ROOT = Path(__file__).resolve().parent
CURSOR = ROOT / "カーソル" / "ファンネル" / "キュベレイ.cur"
SPRITE = load_sprite(CURSOR)


def engine(groups=(), edits=None, cursor=CURSOR):
    config, _ = resolve(cursor.parent.name, {}, edits or {})
    for g in FIELDS:
        config[g]["enabled"] = g in groups
    return EffectEngine(
        SPRITE if cursor == CURSOR else load_sprite(cursor), APPEARANCES[cursor.stem], config, cursor, seed=73
    )


class Rendering(unittest.TestCase):
    def test_sazabi_art_opens_red_covers_around_short_dark_core(self):
        from verify_windows_release import verify_base_frame

        path = CURSOR.with_name("サザビー.cur")
        verify_base_frame(path)
        self.assertEqual(struct.unpack_from("<HHH", path.read_bytes()), (0, 2, 16))
        poses = read_poses(ROOT / "飛行アニメ" / "ファンネル" / "サザビー.png")
        self.assertEqual(len({pose.tobytes() for pose in poses}), 4)
        closed, opened = poses[0], poses[-1]
        self.assertGreater(opened.getbbox()[3] - opened.getbbox()[1],
                           closed.getbbox()[3] - closed.getbbox()[1])
        # Opening reveals the dark inner cylinder behind the red front head.
        # Compare the rear area, excluding the grey forward muzzle.
        def dark_core(image):
            count = 0
            for y in range(24, 73):
                for x in range(12, 64):
                    r, g, b, a = image.getpixel((x, y))
                    count += (a > 200 and max(r, g, b) < 115
                              and max(r, g, b) - min(r, g, b) < 20)
            return count
        self.assertGreater(dark_core(opened), max(40, dark_core(closed) * 2))

    def test_sazabi_attack_uses_separately_authored_rear_view(self):
        e = engine(["volley"], cursor=CURSOR.with_name("サザビー.cur"))
        rear_path = e.art.sheet.with_name("サザビー.後方.png")
        rear = read_poses(rear_path)
        self.assertEqual(len(rear), 4)
        self.assertNotEqual(rear[0].tobytes(), read_poses(e.art.sheet)[3].tobytes())
        image = e.art.rear_frame(0, 96)
        self.assertEqual(image.tobytes(), rear[0].tobytes())
        self.assertTrue(image.getbbox())

    def test_sazabi_six_closed_vertical_launches_open_and_branch(self):
        from effect_engine import SazabiLaunch, RemoteVolley

        e = engine(["volley"], cursor=CURSOR.with_name("サザビー.cur"))
        e.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
        action = e.layers[0]
        self.assertIsInstance(action, SazabiLaunch)
        with mock_patch.object(action, "beam") as beam:
            with mock_patch.object(e, "fly", wraps=e.fly) as fly:
                e.step((0, 0), 0.075)
                self.assertEqual(fly.call_count, 6)
                for call in fly.call_args_list:
                    self.assertEqual(call.args[2], -math.pi / 2)
                    self.assertEqual(call.args[3], 0)
            for i in range(6):
                start, later = action.location(i, 0), action.location(i, 0.15)
                self.assertEqual(start[0], later[0])
                self.assertLess(later[1], start[1])
                # Fast from the first frames, with a longer straight climb.
                early = action.location(i, action.TURN_AT * 0.1)
                turn = action.location(i, action.TURN_AT)
                climb = start[1] - turn[1]
                self.assertGreater(start[1] - early[1], climb * 0.08)
                old_climb = action.c["radius"] * (0.9 - (i % 3) * 0.2) + 18
                self.assertGreater(climb, old_climb + 30)
            self.assertLess(action.c["duration"] * action.TURN_AT / action.LAUNCH_SPEED, 0.2)
            self.assertLess(action.launch_end, 1.0)
            self.assertAlmostEqual(action.entry_at - action.launch_end, 0.4)
            with mock_patch.object(e, "fly", wraps=e.fly) as fly:
                frame = e.step((0, 0), 0.425)
                self.assertEqual(fly.call_count, 6)
                self.assertTrue(all(call.args[3] == 3 for call in fly.call_args_list))
            headings = [round(action.heading(i, 0.7), 2) for i in range(6)]
            self.assertEqual(len(set(headings)), 6)
            self.assertTrue(any(r > 150 and g > 150 and b < 150 and a > 50
                                for r, g, b, a in (frame.getpixel((x, y))
                                    for y in range(frame.height) for x in range(frame.width))))
            for i in range(6):
                x, y = action.location(i, 0.95)
                self.assertTrue(x < -action.SIZE or x > 256 + action.SIZE)
            self.assertIsNone(e.step((0, 0), action.launch_end + 0.05).getbbox())
            self.assertIsNone(e.step((0, 0), action.entry_at - 0.01).getbbox())
            with mock_patch.object(e.art, "rear_frame", wraps=e.art.rear_frame) as rear:
                frame = e.step((0, 0), action.fire_at + 0.08)
                self.assertEqual(rear.call_count, 6)
                self.assertTrue(frame.getbbox())
            segments = [action.shot_segment(i, action.fire_at + 0.08) for i in range(6)]
            self.assertEqual(len(set(end for start, end in segments)), 6)
            centre = (action.origin[0] + 5, action.origin[1] - 55)
            for start, end in segments:
                self.assertLess(math.dist(end, centre), 10 * action.c["radius"] / 64)
                self.assertGreater(math.dist(start, end), 30)
            for i in range(6):
                self.assertIsNone(action.shot_segment(i, action.fire_at - 0.001))
                x, y = action.attack_position(i, action.entry_at)
                self.assertTrue(x < -20 or x > 276 or y < -20 or y > 276)
            # Remain at the firing stations, at the same size and heading,
            # through the afterglow and the final fade.
            rendered = []
            for elapsed in (action.fire_end + 0.01, action.after_end + 0.08, action.lifetime - 0.01):
                with mock_patch.object(e.art, "rear_frame", wraps=e.art.rear_frame) as rear:
                    e.step((0, 0), elapsed)
                    rendered.append([call.args for call in rear.call_args_list])
                for i in range(6):
                    self.assertEqual(action.attack_position(i, elapsed), action.firing_station(i))
            self.assertEqual(rendered[0], rendered[1])
            self.assertEqual(rendered[1], rendered[2])
            self.assertIsNone(e.step((0, 0), action.lifetime + 0.01))
            beam.assert_not_called()
        archived = engine(["volley"], cursor=CURSOR.with_name("ヤクト・ドーガ.cur"))
        self.assertIs(type(archived.layers[0]), RemoteVolley)

    def test_sazabi_beams_do_not_cross_or_overlap_near_target(self):
        from itertools import combinations

        e = engine(["volley"], cursor=CURSOR.with_name("サザビー.cur"))
        e.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
        action = e.layers[0]
        def side(a, b, p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        for radius in (32, 64, 84):
            action.c["radius"] = radius
            segments = [action.shot_segment(i, action.fire_at + 0.08) for i in range(6)]
            for (a, b), (c, d) in combinations(segments, 2):
                crossed = side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0
                self.assertFalse(crossed)
                # The bright ends and their faint glow stay separated too.
                self.assertGreater(math.dist(b, d), 2 * min(1, radius / 64))

    def test_long_range_art_has_closed_flight_and_open_firing(self):
        from build_long_range_art import NAME, FOLDER
        from verify_windows_release import verify_base_frame

        path = ROOT / "カーソル" / "ファンネル" / (NAME + ".cur")
        verify_base_frame(path)
        data = path.read_bytes()
        self.assertEqual(struct.unpack_from("<HHH", data), (0, 2, 16))
        self.assertEqual(struct.unpack_from("<HH", data, 10), (2, 3))
        flight = read_poses(FOLDER / (NAME + ".png"))
        firing = read_poses(FOLDER / (NAME + ".展開.png"))
        self.assertEqual(len(flight), 4)
        self.assertEqual(len(firing), 4)
        self.assertEqual(flight[0].tobytes(), firing[0].tobytes())
        def rails(image):
            mask = [image.getpixel((80, y))[3] > 144 for y in range(96)]
            return sum(v and (y == 0 or not mask[y - 1]) for y, v in enumerate(mask))
        self.assertTrue(all(rails(image) == 1 for image in flight))
        self.assertEqual(rails(firing[3]), 2)
        pixels = [flight[0].getpixel((x, y)) for y in range(96) for x in range(96)
                  if flight[0].getpixel((x, y))[3] > 144]
        self.assertGreater(sum(r > 150 and g < 110 and b < 140 for r, g, b, a in pixels), 5)
        self.assertGreater(sum(r > 150 and g > 90 and b < 100 for r, g, b, a in pixels), 5)
        self.assertGreater(sum(b > 120 and b > r * 1.25 for r, g, b, a in pixels), 5)
        self.assertGreater(sum(min(r, g, b) > 160 for r, g, b, a in pixels), 5)

    def test_long_range_closed_launch_pause_entry_then_open_root_beam(self):
        path = CURSOR.with_name("ロングレンジ・フィン・ファンネル（RX-93ff）.cur")
        e = engine(["cannon"], cursor=path)
        e.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
        action = e.layers[0]
        def step(p):
            elapsed = action.c["duration"] * p + (action.CHARGE_TIME if p > action.OPEN_END else 0)
            return e.step((0, 0), elapsed)
        heights = [action.launch_position(action.HOLD_END + t)[1] for t in (0, 0.03, 0.06)]
        self.assertGreater(heights[1] - heights[2], heights[0] - heights[1])
        for p in (0.08, 0.14):
            with mock_patch.object(e, "fly", wraps=e.fly) as fly:
                step(p)
                self.assertEqual(fly.call_args.args[3], 0)
                self.assertFalse(fly.call_args.kwargs.get("deploying", False))
        self.assertIsNone(step(action.EXIT_END - 0.001).getbbox())
        for p in (action.EXIT_END + 0.01, action.ENTRY_AT - 0.001):
            with mock_patch.object(e, "fly") as fly:
                self.assertIsNone(step(p).getbbox())
                fly.assert_not_called()
            self.assertEqual(action.opening(p), 0)
            self.assertIsNone(action.shot_segment(p))
        positions = []
        for p in (action.ENTRY_AT + 0.01, (action.ENTRY_AT + action.ENTRY_END) / 2, action.ENTRY_END):
            with mock_patch.object(e, "fly", wraps=e.fly) as fly:
                step(p)
                positions.append(fly.call_args.args[1])
                self.assertEqual(fly.call_args.args[3], 0)
                self.assertFalse(fly.call_args.kwargs["deploying"])
        self.assertTrue(positions[0][0] > positions[1][0] > positions[2][0])
        self.assertEqual(positions[-1], action.station())
        with mock_patch.object(e, "fly", wraps=e.fly) as fly:
            step((action.OPEN_AT + action.OPEN_END) / 2)
            self.assertEqual(fly.call_args.args[1], action.station())
            self.assertTrue(fly.call_args.kwargs["deploying"])
        self.assertIsNone(action.shot_segment((action.OPEN_AT + action.OPEN_END) / 2))
        charge_start = action.c["duration"] * action.OPEN_END
        charge_frames = []
        for hold in (0.04, action.CHARGE_TIME * 0.85):
            with mock_patch.object(e, "fly", wraps=e.fly) as fly:
                charge_frames.append(e.step((0, 0), charge_start + hold))
                self.assertEqual(fly.call_args.args[3], 3)
                self.assertEqual(fly.call_args.args[1], action.station())
            self.assertIsNone(action.shot_segment(action.progress))
            self.assertEqual(charge_frames[-1].getpixel((20, round(action.station()[1])))[3], 0)
        rx, ry = (round(v) for v in action.emitter_position())
        energy = [sum(frame.getpixel((x, y))[0] * frame.getpixel((x, y))[3]
                      for y in range(ry - 8, ry + 9) for x in range(rx - 8, rx + 9))
                  for frame in charge_frames]
        self.assertGreater(energy[1], energy[0])
        with mock_patch.object(e, "fly", wraps=e.fly) as fly:
            frame = step(0.8)
            self.assertEqual(fly.call_args.args[3], 3)
            self.assertTrue(fly.call_args.kwargs["deploying"])
        start, end = action.shot_segment(0.8)
        self.assertLess(math.dist(start, action.station()), action.SIZE * 0.1)
        self.assertLess(end[0], start[0])
        self.assertEqual(end[1], start[1])
        self.assertGreaterEqual(sum(frame.getpixel((20, y))[3] > 100 for y in range(256)), 8)
        self.assertIsNone(step(1.01))

    def test_super_dragoon_detail_art_and_cursor(self):
        from build_dragoon_art import read_source
        from verify_windows_release import verify_base_frame

        path = ROOT / "カーソル" / "ドラグーン" / "ストライクフリーダム.cur"
        verify_base_frame(path)
        self.assertEqual(struct.unpack_from("<HHH", path.read_bytes()), (0, 2, 16))
        source = read_source()
        source.thumbnail((512, 512))
        pixels = [source.getpixel((x, y)) for y in range(source.height) for x in range(source.width)
                  if source.getpixel((x, y))[3] >= 144]
        self.assertGreater(sum(min(r, g, b) > 165 and max(r, g, b) - min(r, g, b) < 55
                               for r, g, b, a in pixels), 20)
        self.assertGreater(sum(r > 140 and g > 95 and b < g * 0.75 for r, g, b, a in pixels), 20)
        for pose in read_poses(engine(cursor=path).art.sheet):
            x0, y0, x1, y1 = pose.getbbox()
            self.assertGreater((x1 - x0) / (y1 - y0), 5)

    def test_super_dragoon_exits_before_synchronous_crossfire(self):
        path = ROOT / "カーソル" / "ドラグーン" / "ストライクフリーダム.cur"
        e = engine(["dragoon"], cursor=path)
        e.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
        effect = e.layers[0]
        self.assertEqual(effect.count, 8)
        duration = effect.c["duration"]
        held = e.step((0, 0), duration * 0.04)
        layout = effect.launch_layout()
        self.assertEqual(len(layout), 8)
        self.assertEqual(sum(pos[0] < CENTER for pos, heading in layout), 4)
        self.assertEqual(sum(pos[0] > CENTER for pos, heading in layout), 4)
        self.assertTrue(all(math.hypot(pos[0] - CENTER, pos[1] - CENTER)
                            < effect.c["radius"] * 0.6 for pos, heading in layout))
        self.assertLess(duration * effect.EXIT_END, 0.5)
        self.assertTrue(held.getbbox())
        # Test real clipped pixels just BEFORE the phase boundary, rather than
        # merely hiding the sprites at that boundary.
        exited = e.step((0, 0), duration * (effect.EXIT_END - 0.001))
        self.assertIsNone(exited.getbbox())
        gap = e.step((0, 0), duration * ((effect.EXIT_END + effect.FIRE_AT) / 2))
        self.assertIsNone(gap.getbbox())
        self.assertEqual(effect.shot_rays(), [])
        # Leave a visible beat after the pods exit, then cross the viewport
        # in a few frames instead of slowly extending the beam.
        self.assertGreaterEqual(duration * (effect.FIRE_AT - effect.EXIT_END), 0.9)
        waiting = e.step((0, 0), duration * effect.FIRE_AT - 0.1)
        self.assertIsNone(waiting.getbbox())
        fast_shot = e.step((0, 0), duration * effect.FIRE_AT + 0.06)
        for x in (30, 230):
            y = round(CENTER - 24 + (x - (CENTER - 180)) * 56 / 360)
            self.assertGreater(fast_shot.getpixel((x, y))[3], 50)
        with mock_patch.object(e, "fly") as fly:
            volley = e.step((0, 0), duration * (effect.FIRE_AT + 0.2))
            fly.assert_not_called()
        self.assertTrue(volley.getbbox())
        rays = effect.shot_rays()
        self.assertEqual(len(rays), 8)
        self.assertEqual(len({end for start, end in rays}), 8)
        self.assertEqual(len({start for start, end in rays}), 8)
        angles = {round(math.atan2(b[1] - a[1], b[0] - a[0]), 1) for a, b in rays}
        self.assertGreaterEqual(len(angles), 6)
        self.assertTrue(all(x < 0 or x > 256 or y < 0 or y > 256
                            for ray in rays for x, y in ray))
        crossings = []
        for i, (a, b) in enumerate(rays):
            dx, dy = b[0] - a[0], b[1] - a[1]
            for c, d in rays[i + 1:]:
                ex, ey = d[0] - c[0], d[1] - c[1]
                determinant = dx * ey - dy * ex
                if abs(determinant) < 1e-6:
                    continue
                t = ((c[0] - a[0]) * ey - (c[1] - a[1]) * ex) / determinant
                x, y = a[0] + dx * t, a[1] + dy * t
                if 0 < x < 256 and 0 < y < 256:
                    crossings.append((x, y))
        self.assertGreaterEqual(len(crossings), 8)
        self.assertGreater(max(x for x, y in crossings) - min(x for x, y in crossings), 80)
        self.assertGreater(max(y for x, y in crossings) - min(y for x, y in crossings), 80)
        self.assertEqual(effect.launch_layout(), [])
        trail_frames = [e.step((0, 0), duration * p) for p in
                        (effect.FIRE_END + 0.03, effect.AFTERGLOW_END - 0.02)]
        alpha_energy = [sum(i * n for i, n in enumerate(frame.getchannel("A").histogram()))
                        for frame in trail_frames]
        self.assertGreater(alpha_energy[0], alpha_energy[1])
        self.assertGreater(alpha_energy[1], 0)
        self.assertIsNone(e.step((0, 0), duration * (effect.AFTERGLOW_END + 0.001)).getbbox())
        self.assertEqual(effect.shot_rays(), [])

        # The other live DRAGOON retains its own ten-unit action.
        legend = engine(["dragoon"], cursor=path.with_name("レジェンドガンダム.cur"))
        legend.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
        self.assertFalse(legend.layers[0].is_super)
        with mock_patch.object(legend, "fly") as fly:
            legend.step((0, 0), 0.7)
            self.assertEqual(fly.call_count, 10)

    def test_nightingale_is_red_with_a_tapered_forward_end(self):
        from verify_windows_release import verify_base_frame

        path = CURSOR.with_name("ナイチンゲール.cur")
        verify_base_frame(path)
        for pose in read_poses(engine(cursor=path).art.sheet):
            pixels = [pose.getpixel((x, y)) for y in range(96) for x in range(96)
                      if pose.getpixel((x, y))[3] >= 144]
            self.assertGreater(sum(r for r, g, b, a in pixels), 1.5 * sum(g for r, g, b, a in pixels))
            alpha = pose.getchannel("A")
            rear = sum(alpha.getpixel((x, y)) for y in range(96) for x in range(8, 40))
            tip = sum(alpha.getpixel((x, y)) for y in range(96) for x in range(64, 92))
            self.assertGreater(rear, tip * 2)

    def test_quin_mansa_points_upper_left_and_flies_forward(self):
        path = CURSOR.with_name("クィン・マンサ.cur")
        data = path.read_bytes()
        for i in range(struct.unpack_from("<H", data, 4)[0]):
            w, h, _, _, hx, hy, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + i * 16)
            side = w or 256
            self.assertLess(hx + hy, side * 0.15)
            self.assertGreaterEqual(data[offset + 40 + ((side - 1 - hy) * side + hx) * 4 + 3], 144)
        sprite = load_sprite(path)
        alpha = sprite.getchannel("A")
        leading = sum(alpha.getpixel((x, y)) >= 144 for y in range(16) for x in range(16))
        rear = sum(alpha.getpixel((x, y)) >= 144 for y in range(16, 32) for x in range(16, 32))
        self.assertLess(leading, rear)
        # Flight cells use +X as forward: the narrow end must be on the right.
        for pose in read_poses(engine(cursor=path).art.sheet):
            alpha = pose.getchannel("A")
            left = sum(alpha.getpixel((x, y)) for y in range(96) for x in range(48))
            right = sum(alpha.getpixel((x, y)) for y in range(96) for x in range(48, 96))
            self.assertGreater(left, right)

    def test_qubeley_round_body_and_windows_cursor_frames(self):
        from verify_windows_release import verify_base_frame

        for name in ("キュベレイ", "キュベレイMk-II（プル機）", "キュベレイMk-II（プルツー機）"):
            path = CURSOR.with_name(name + ".cur")
            with self.subTest(cursor=name):
                verify_base_frame(path)
                data = path.read_bytes()
                self.assertEqual(struct.unpack_from("<HHH", data), (0, 2, 16))
                sizes = []
                for index in range(16):
                    w, h, _, _, hx, hy, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + index * 16)
                    side = w or 256
                    sizes.append(side)
                    self.assertEqual(w, h)
                    self.assertEqual(struct.unpack_from("<IiiHH", data, offset), (40, side, side * 2, 1, 32))
                    self.assertGreaterEqual(data[offset + 40 + ((side - 1 - hy) * side + hx) * 4 + 3], 144)
                    self.assertEqual(length, 40 + side * side * 4 + ((side + 31) // 32) * 4 * side)
                self.assertEqual(sizes, [32, 40, 48, 56, 64, 72, 80, 88, 96, 112, 128, 144, 160, 192, 224, 256])
                self.assertEqual(struct.unpack_from("<HH", data, 10), (0, 3))
                poses = read_poses(engine(cursor=path).art.sheet)
                # The large rear shell is closed and coloured, rather than the
                # old open cone with a blue hollow rear nozzle.
                r, g, b, a = poses[0].getpixel((20, 48))
                self.assertGreater(a, 200)
                self.assertGreater(r, g)
                self.assertGreater(b, g)

    def test_authored_flight_and_deployment_frames(self):
        for cursor in (ROOT / "カーソル").glob("*/*.cur"):
            name = f"{cursor.parent.name}/{cursor.name}"
            e = engine(cursor=cursor)
            poses = read_poses(e.art.sheet)
            with self.subTest(cursor=name):
                self.assertEqual(len({pose.tobytes() for pose in poses}), 4)
                self.assertTrue(all(pose.getbbox() for pose in poses))
                self.assertNotEqual(e.art.frame(0, 0, 24).tobytes(), e.art.frame(1.57, 0, 24).tobytes())
                if name in SPECIAL["barrier"]:
                    boxes = [e.art.frame(0, i, 96, deploying=True).getbbox() for i in range(4)]
                    proportions = [(x1 - x0) / (y1 - y0) for x0, y0, x1, y1 in boxes]
                    self.assertEqual(len(proportions), 4)
                    self.assertEqual(proportions, sorted(proportions, reverse=True))
                    self.assertGreater(proportions[0], 2)
                    # The final rails form a narrow V, rather than a straight line.
                    self.assertGreater(proportions[-1], 0.65)
                    self.assertLess(proportions[-1], 1.25)

    def test_spiral_light_precedes_equipment(self):
        for name in ("キュベレイ", "キュベレイMk-II（プル機）", "キュベレイMk-II（プルツー機）"):
            with self.subTest(cursor=name):
                e = engine(["spiral"], {"spiral": {"count": 2}}, CURSOR.with_name(name + ".cur"))
                duration = e.config["spiral"]["duration"]
                with mock_patch.object(e, "fly") as fly:
                    e.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
                    early = e.step((0, 0), duration * 0.2)
                    self.assertTrue(early.getbbox())
                    fly.assert_not_called()
                    pixels = [early.getpixel((x, y)) for y in range(early.height)
                              for x in range(early.width) if early.getpixel((x, y))[3]]
                    self.assertTrue(all(b > g > r for r, g, b, a in pixels))
                    e.step((0, 0), duration * 0.4)
                    self.assertTrue(fly.called)
                    partial = fly.call_args.args[5]
                    fly.reset_mock()
                    e.step((0, 0), duration * 0.65)
                    self.assertEqual(fly.call_count, 2)
                    self.assertGreater(fly.call_args.args[5], partial)

    def test_spiral_launch_accelerates_then_exits_straight(self):
        e = engine(["spiral"])
        effect = e.layers[0]
        radius = lambda t: math.dist((0, 0), effect.location((0, 0), 0, t))
        self.assertLess(radius(0.3) - radius(0), radius(0.6) - radius(0.3))
        for index in range(effect.c["count"]):
            points = [effect.location((CENTER, CENTER), index, t) for t in (0.65, 0.75, 0.85)]
            a, b, c = points
            self.assertAlmostEqual((b[0] - a[0]) * (c[1] - b[1]) -
                                   (b[1] - a[1]) * (c[0] - b[0]), 0)
            x, y = effect.location((CENTER, CENTER), index, 0.95)
            self.assertTrue(x < -20 or x > 276 or y < -20 or y > 276)

    def test_spiral_keeps_blue_path_until_straight_departure(self):
        e = engine(["spiral"], {"spiral": {"count": 2}})
        effect = e.layers[0]
        origin = (CENTER, CENTER)
        self.assertEqual(effect.location(origin, 0, 0), origin)
        duration = effect.c["duration"]
        e.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
        # A point far behind the moving head must remain lit, including while
        # the body fades in. Keep it until straight departure, then let the spiral disappear.
        # Stay outside the intentional 2px pointer-center mask with slow launch.
        sample = tuple(round(v) for v in effect.location(origin, 0, 0.16))
        for progress in (0.20, 0.31, 0.39, 0.50, 0.59):
            frame = e.step((0, 0), duration * progress)
            r, g, b, a = frame.getpixel(sample)
            self.assertGreater(a, 0)
            self.assertGreater(b, g)
            self.assertGreater(g, r)
        self.assertEqual(e.step((0, 0), duration * 0.76).getpixel(sample)[3], 0)

    def test_field_powers_up_after_opening(self):
        e = engine(["barrier"], cursor=CURSOR.with_name("フィンファンネル.cur"))
        pos = (0, 0)
        e.step(pos, 0, [ClickEvent("left", pos, 0, 3)])
        # This point is inside one face and well away from the three pivot points.
        point = (CENTER + 8, CENTER + 5)
        lead = e.layers[0].RACK_END
        action = e.layers[0]
        for t in (0.35, 0.6, 0.77):
            self.assertEqual(e.step(pos, lead + t).getpixel(point)[3], 0)
        opened_at = lead + action.c["duration"] * action.OPEN_END
        held = []
        for elapsed in (opened_at + 0.01, opened_at + action.HINGE_BEAT - 0.01):
            with mock_patch.object(e, "fly", wraps=e.fly) as fly:
                image = e.step(pos, elapsed)
                self.assertEqual(fly.call_count, 3)
                self.assertTrue(all(call.args[3] == 3 for call in fly.call_args_list))
                held.append([call.args[1:5] for call in fly.call_args_list])
            self.assertEqual(image.getpixel(point)[3], 0)
        self.assertEqual(held[0], held[1])
        self.assertGreater(e.step(pos, lead + action.HINGE_BEAT + 0.98).getpixel(point)[3], 0)

    def test_fin_launches_six_from_right_before_delta_field(self):
        from PIL import Image

        for name in ("フィンファンネル", "νガンダムHWS"):
            e = engine(["barrier"], cursor=CURSOR.with_name(name + ".cur"))
            stored = e.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
            # All six units form one connected bank before the first release.
            pixels = {(x, y) for y in range(256) for x in range(256)
                      if stored.getpixel((x, y))[3] > 100}
            total = len(pixels)
            pending = [pixels.pop()]
            while pending:
                x, y = pending.pop()
                for dx, dy in product((-1, 0, 1), repeat=2):
                    neighbor = (x + dx, y + dy)
                    if neighbor in pixels:
                        pixels.remove(neighbor)
                        pending.append(neighbor)
            self.assertLess(len(pixels), total * 0.01)
            action = e.layers[0]
            held = action.rack_layout(0)
            masks = []
            for index in (0, 2, 4):
                image = Image.new("RGBA", (256, 256))
                sprite = e.art.rack_frame(action.RACK_SIZE, action.RACK_ANGLES[index],
                                          index in action.RACK_FOLDED)
                pos = held[index][1]
                e.stamp(image, sprite, (pos[0] - action.RACK_SIZE / 2, pos[1] - action.RACK_SIZE / 2), 1)
                masks.append({(x, y) for y in range(256) for x in range(256)
                              if image.getpixel((x, y))[3] > 144})
            for left, right in zip(masks, masks[1:]):
                self.assertLessEqual(len(left & right) / min(len(left), len(right)), 0.02)
            self.assertEqual(len(held), 6)
            self.assertEqual(sum(launched for i, pos, launched in held), 0)
            self.assertTrue(all(pos[0] > CENTER for i, pos, launched in held))
            self.assertTrue(all(held[i][1] == held[i + 1][1] for i in (0, 2, 4)))
            self.assertTrue(held[0][1][1] > held[2][1][1] > held[4][1][1])
            self.assertLess(action.RACK_STAGGER, 0.08)
            self.assertLess(action.RACK_EXIT_END, 0.8)
            self.assertAlmostEqual(action.RACK_END - action.RACK_EXIT_END, 0.30)
            self.assertEqual(len(set(action.RACK_ANGLES)), 3)
            self.assertTrue(all(action.RACK_ANGLES[i] == action.RACK_ANGLES[i + 1]
                                for i in (0, 2, 4)))
            self.assertEqual(action.RACK_FOLDED, (2, 3))
            folded = e.art.rack_frame(action.RACK_SIZE, 0, True).getbbox()
            straight = e.art.rack_frame(action.RACK_SIZE, 0).getbbox()
            self.assertAlmostEqual(folded[1], straight[1], delta=2)
            self.assertLess(folded[3], action.RACK_SIZE / 2 + 12)
            self.assertGreater(straight[3] - folded[3], 45)
            heights = [action.rack_layout(action.RACK_HOLD + t)[-1][1][1]
                       for t in (0, 0.04, 0.08, 0.12)]
            travel = [a - b for a, b in zip(heights, heights[1:])]
            self.assertTrue(all(b > a > 0 for a, b in zip(travel, travel[1:])))
            front = e.art.rack_frame(action.RACK_SIZE)
            x0, y0, x1, y1 = front.getbbox()
            self.assertGreater(y1 - y0, 110)
            self.assertGreater((y1 - y0) / (x1 - x0), 3)
            # The stored pair is filled across its shared edge, not two spaced
            # sprites. Either half can then depart independently.
            joined = e.art.rack_frame(action.RACK_SIZE, 0)
            alpha = joined.getchannel("A")
            for y in (25, 45, 85, 105):
                xs = [x for x in range(joined.width) if alpha.getpixel((x, y)) > 144]
                self.assertTrue(xs)
                self.assertTrue(all(alpha.getpixel((x, y)) > 144 for x in range(min(xs), max(xs) + 1)))
            self.assertLess(e.art.rack_frame(action.RACK_SIZE, 0, False, 0).getbbox()[2],
                            e.art.rack_frame(action.RACK_SIZE, 0, False, 1).getbbox()[2])
            if name == "フィンファンネル":
                from PIL import Image
                art = Image.open(e.art.sheet.parent / "フィンファンネル.収納正面.png").convert("RGBA")
                bounds = art.getchannel("A").point(lambda a: 255 if a >= 144 else 0).getbbox()
                art = art.crop(bounds)
                art.thumbnail((256, 512))
                bands = [y for y in range(art.height)
                         if sum(a > 180 and r > 140 and g > 90 and b < g * 0.65
                                for r, g, b, a in (art.getpixel((x, y)) for x in range(art.width)))
                         > art.width * 0.2]
                upper, lower = min(bands), art.height - 1 - max(bands)
                self.assertLess(abs(upper - lower) / max(upper, lower), 0.06)
                # One inset slot per white plate, and no long dividing line.
                for y0, y1, count in ((0.30, 0.37, 1), (0.66, 0.73, 1), (0.15, 0.20, 0)):
                    for side in (0, 1):
                        width = art.width / 2
                        dark = [any(a > 180 and max(r, g, b) < 170
                                    for r, g, b, a in (art.getpixel((x, y))
                                        for y in range(round(art.height * y0), round(art.height * y1))))
                                for x in range(round(width * (side + 0.15)), round(width * (side + 0.85)))]
                        runs = sum(v and (i == 0 or not dark[i - 1]) for i, v in enumerate(dark))
                        self.assertEqual(runs, count)
            for i in range(6):
                layout = action.rack_layout(action.RACK_HOLD + i * action.RACK_STAGGER + 0.01)
                self.assertEqual({index for index, pos, launched in layout if not launched}, set(range(5 - i)))
            first = action.rack_layout(action.RACK_HOLD + 0.05)
            self.assertEqual(first[-1][1][0], held[-1][1][0])
            self.assertLess(first[-1][1][1], held[-1][1][1])
            self.assertEqual(action.rack_layout(action.RACK_END), [])
            for elapsed in (action.RACK_EXIT_END, action.RACK_EXIT_END + 0.15, action.RACK_END - 0.001):
                self.assertEqual(action.rack_layout(elapsed), [])
                with mock_patch.object(e, "fly") as fly:
                    blank = e.step((0, 0), elapsed)
                    fly.assert_not_called()
                self.assertIsNone(blank.getbbox())
            e.step((0, 0), action.RACK_END)
            with mock_patch.object(e, "fly") as fly:
                e.step((0, 0), action.RACK_END + action.c["duration"] * 0.7)
                self.assertEqual(fly.call_count, 3)
                self.assertTrue(all(call.kwargs["deploying"] for call in fly.call_args_list))
            self.assertIsNone(e.step((0, 0), action.lifetime + 0.01))
        hi_nu = engine(["barrier"], cursor=CURSOR.with_name("Hi-νガンダム.cur")).layers[0]
        self.assertFalse(hi_nu.has_rack)
        self.assertEqual(hi_nu.lifetime, hi_nu.c["duration"])

    def test_independent_and_combined(self):
        for special, paths in SPECIAL.items():
            cursor = ROOT / "カーソル" / sorted(paths)[0]
            available = [g for g in FIELDS if g not in SPECIAL or g == special]
            for flags in product((False, True), repeat=len(available)):
                groups = [g for g, on in zip(available, flags) if on]
                self.check_combination(groups, cursor)

    def test_all_cursors_have_one_special_and_can_save_it(self):
        cursors = list((ROOT / "カーソル").glob("*/*.cur"))
        covered = [key for paths in SPECIAL.values() for key in paths]
        self.assertEqual(len(covered), len(set(covered)))
        self.assertEqual(set(covered), {f"{p.parent.name}/{p.name}" for p in cursors})
        with TemporaryDirectory() as temp:
            store = Settings(Path(temp) / "effects.json")
            for key in covered:
                group = special_group(key)
                binding = store.binding(key)
                self.assertTrue(binding["overrides"][group]["enabled"])
                binding["overrides"][group].update(button="右クリック", modifiers="Ctrl＋Alt")
                store.cursors[key] = binding
            store.write()
            self.assertEqual(Settings(store.path).cursors, store.cursors)

    def test_new_actions_render_full_lifetime_and_parameter_limits(self):
        for group, paths in SPECIAL.items():
            for key in paths:
                for radius, duration in ((FIELDS[group]["radius"].low, FIELDS[group]["duration"].low),
                                         (FIELDS[group]["radius"].high, FIELDS[group]["duration"].high)):
                    if group in ("spiral", "barrier"):
                        continue
                    with self.subTest(cursor=key, radius=radius, duration=duration):
                        e = engine([group], {group: {"radius": radius, "duration": duration}},
                                   ROOT / "カーソル" / key)
                        frames = []
                        for i in range(41):
                            t = i * duration / 40
                            events = [ClickEvent("left", (-40, 12), 0, 3)] if i == 0 else []
                            frame = e.step((-40, 12), t, events)
                            if frame is not None:
                                frames.append(frame.tobytes())
                                self.assertEqual(frame.getpixel((CENTER, CENTER))[3], 0)
                        self.assertGreater(len(set(frames)), 10)
                        self.assertIsNone(e.step((-40, 12), e.layers[0].lifetime + 0.01))

    def test_equipment_specific_behaviors(self):
        def action(group):
            key = sorted(SPECIAL[group])[0]
            e = engine([group], cursor=ROOT / "カーソル" / key)
            e.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
            return e, e.layers[0]

        for group in ("shield", "biton"):
            e, effect = action(group)
            with mock_patch.object(effect, "beam") as beam:
                for t in (0.3, 0.6, 1.0, 1.4):
                    e.step((0, 0), t)
                beam.assert_not_called()
        e, effect = action("incom")
        e.step((0, 0), 0.9)
        cable = effect.cable()
        self.assertEqual(cable[0], (CENTER, CENTER))
        with mock_patch.object(e, "fly") as fly:
            e.step((0, 0), 1.0)
            self.assertEqual(fly.call_count, 1)
            self.assertEqual(fly.call_args.args[1], effect.cable()[-1])
        e, effect = action("stun")
        with mock_patch.object(effect, "beam") as beam:
            e.step((0, 0), 0.9)
            self.assertEqual([(c.args[1], c.args[2]) for c in beam.call_args_list], effect.pairs())
        e, effect = action("missile")
        for i in range(6):
            xs = [effect.location(i, t / 10)[0] for t in range(11)]
            self.assertEqual(xs, sorted(xs))
        with mock_patch.object(e, "fly") as fly:
            e.step((0, 0), effect.lifetime * 0.98)
            fly.assert_not_called()

    def test_unicorn_spirals_docks_and_coasts_as_one_assembly(self):
        e = engine(["shield"], cursor=CURSOR.with_name("ユニコーン.cur"))
        effect = e.layers[0]
        duration = effect.c["duration"]
        e.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
        radii, angles = [], []
        for p in (0.04, 0.12, 0.24, 0.36, effect.JOIN_AT):
            e.step((0, 0), duration * p)
            pos, heading = effect.formation()[0]
            radii.append(math.dist(pos, effect.origin))
            angles.append(effect.rotation())
        self.assertEqual(radii, sorted(radii, reverse=True))
        self.assertGreater(radii[0], radii[-1] * 2)
        self.assertGreater(angles[-1] - angles[0], math.pi)
        joined_rotation = effect.rotation()
        base_angles = (-math.pi, -math.pi / 3, math.pi / 3)
        rotations = []
        for p in (effect.JOIN_AT, 0.54, 0.66, 0.78, effect.SPIN_END):
            e.step((0, 0), duration * p)
            formation = effect.formation()
            self.assertEqual(len(formation), 3)
            rotations.append(effect.rotation())
            for (pos, heading), base in zip(formation, base_angles):
                self.assertAlmostEqual(heading - effect.rotation(), base)
                # The artwork pivots around the disk IN THE MIDDLE of each shield.
                self.assertAlmostEqual(math.dist(pos, effect.origin), effect.HUB_RADIUS)
            for i in range(3):
                self.assertAlmostEqual(math.dist(formation[i][0], formation[(i + 1) % 3][0]),
                                       effect.HUB_RADIUS * math.sqrt(3))
        turns = (rotations[-1] - joined_rotation) / math.tau
        self.assertGreater(turns, 0.1)
        self.assertLess(turns, 0.3)
        sweeps = [b - a for a, b in zip(rotations, rotations[1:])]
        self.assertTrue(all(a > b > 0 for a, b in zip(sweeps, sweeps[1:])))
        stopped = effect.formation()
        with mock_patch.object(e, "stamp") as stamp:
            e.step((0, 0), duration * 0.94)
            self.assertEqual(stamp.call_count, 3)
        self.assertEqual(effect.formation(), stopped)
        e.step((0, 0), duration * 0.98)
        self.assertEqual(effect.formation(), stopped)

    def test_unicorn_docking_preserves_angular_velocity(self):
        e = engine(["shield"], cursor=CURSOR.with_name("ユニコーン.cur"))
        e.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
        effect = e.layers[0]
        self.assertEqual(effect.lifetime, effect.c["duration"])
        epsilon = 0.00001
        def rotation(p):
            e.now = p * effect.c["duration"]
            return effect.rotation()
        join = effect.JOIN_AT
        before = (rotation(join) - rotation(join - epsilon)) / epsilon
        after = (rotation(join + epsilon) - rotation(join)) / epsilon
        self.assertAlmostEqual(before, after, delta=0.01)
        speeds = [(rotation(p + epsilon) - rotation(p)) / epsilon for p in (0, 0.05, 0.15, 0.3)]
        self.assertTrue(all(a > b > 0 for a, b in zip(speeds, speeds[1:])))
        end = effect.SPIN_END
        self.assertLess((rotation(end) - rotation(end - epsilon)) / epsilon, 0.001)

    def test_unicorn_short_green_trails_end_at_rest(self):
        e = engine(["shield"], cursor=CURSOR.with_name("ユニコーン.cur"))
        e.step((0, 0), 0, [ClickEvent("left", (0, 0), 0, 3)])
        effect = e.layers[0]
        frame = e.step((0, 0), effect.c["duration"] * 0.55)
        paths = effect.trail_paths()
        self.assertEqual(len(paths), 6)
        self.assertTrue(all(2 < len(p) <= 9 and math.dist(p[0], p[-1]) > 1 for p in paths))
        draw = Mock()
        effect.draw(frame, draw)
        inks = [call.kwargs["fill"] for call in draw.line.call_args_list]
        self.assertTrue(inks)
        self.assertTrue(all(g > r and g > b and 0 <= a <= 255 for r, g, b, a in inks))
        e.step((0, 0), effect.c["duration"] * 0.98)
        self.assertTrue(all(math.dist(p[0], p[-1]) < 0.001 for p in effect.trail_paths()))
        draw.reset_mock()
        effect.draw(frame, draw)
        draw.line.assert_not_called()

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
        self.assertIsNone(e.step(origin, 0.1 + e.layers[0].lifetime + 0.01))

    def test_special_command_and_cooldown(self):
        pos = (10, 20)
        for path in (ROOT / "カーソル").glob("*/*.cur"):
            group = special_group(f"{path.parent.name}/{path.name}")
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
                    self.assertIsNone(e.step(pos, max(2.2, 0.2 + e.layers[0].lifetime + 0.01)))
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
            self.assertTrue(store.binding("ファンネル/サザビー.cur")["overrides"]["volley"]["enabled"])
            self.assertEqual(store.binding("自作/追加.cur")["overrides"], {})

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
