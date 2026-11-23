"""Replay one hour of 60 Hz movement/idle/clicks without waiting between samples."""

import argparse
import ctypes
import math
import os
import statistics
import time
from pathlib import Path

from cursor_art import APPEARANCES, load_sprite
from effect_engine import ClickEvent, EffectEngine
from effect_settings import SAMPLES, resolve


def memory_mib():
    if os.name != "nt":
        with open("/proc/self/statm", encoding="ascii") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**20

    class Counters(ctypes.Structure):
        _fields_ = [
            ("size", ctypes.c_uint32),
            ("faults", ctypes.c_uint32),
            ("peak", ctypes.c_size_t),
            ("working", ctypes.c_size_t),
            ("other", ctypes.c_size_t * 6),
        ]

    counters = Counters()
    counters.size = ctypes.sizeof(counters)
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.c_void_p(-1), ctypes.byref(counters), counters.size
    ):
        raise ctypes.WinError()
    return counters.working / 2**20


def benchmark(frames, moving=False):
    path = Path(__file__).with_name("カーソル") / "ファンネル" / "キュベレイ.cur"
    config = resolve("ファンネル", SAMPLES["戦闘モード"], {"followers": {"count": 3}})[0]
    e = EffectEngine(load_sprite(path), APPEARANCES[path.stem], config, path, seed=12)
    samples, memory = [], []
    cpu = time.process_time()
    for i in range(frames):
        now = i / 60
        phase = now % 120
        if not moving:
            phase = min(phase, 8)  # long idle and rare cues as well as active movement
        p = (round(100 * math.sin(phase * 2)) - 1800, round(75 * math.sin(phase * 5)) - 100)
        events = [ClickEvent(("left", "double", "right")[i % 3], p, now)] if i % 89 == 0 else []
        start = time.perf_counter()
        frame = e.step(p, now, events)
        if frame:
            frame.convert("RGBa").tobytes("raw", "BGRa")
        if i % 13 == 0:
            samples.append((time.perf_counter() - start) * 1000)
        if i % 3600 == 0 or i == frames - 1:
            memory.append(memory_mib())
    cpu = time.process_time() - cpu
    print(
        f"frames={frames} simulated_s={frames / 60:.1f} CPU_s={cpu:.2f} "
        f"CPU_at_60Hz={100 * cpu / (frames / 60):.2f}% of one core "
        f"p95_frame_ms={statistics.quantiles(samples, n=100)[94]:.3f} "
        f"working_MiB first={memory[0]:.1f} middle={memory[len(memory) // 2]:.1f} "
        f"last={memory[-1]:.1f} peak_sample={max(memory):.1f}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=216000)
    parser.add_argument("--moving", action="store_true", help="Keep moving for the entire run")
    args = parser.parse_args()
    benchmark(args.frames, args.moving)
