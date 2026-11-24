from pathlib import Path
from itertools import product
import unittest

from effect_engine import ClickEvent
from effect_settings import resolve
from trial_runtime import TrialDisplay, UNITS
from idle_motion import turn_frame

ROOT = Path(__file__).resolve().parent


class TrialIntegration(unittest.TestCase):
    def test_controls_and_fleet_playback(self):
        for name, count, fire, orientation in product(UNITS,range(4),(True,False),("fixed_upper_left","follow")):
            path = ROOT / "カーソル" / "ファンネル" / (name+".cur")
            group = "spiral" if name == "キュベレイ" else "volley"
            options = dict(enabled=True,escort_count=count,orientation_mode=orientation,click_fire_enabled=fire)
            display = TrialDisplay(path,resolve("ファンネル",{},{group:options})[0])
            pos, bounds = (-100,80), (-350,-30,0,300)
            def sample(t, events=()):
                return display.step(pos,t,events,bounds,1.25)
            self.assertTrue(sample(0).getbbox())
            self.assertEqual(len(display.control._last_output["items"]),count+1)
            sample(.03,[ClickEvent("left",pos,.02)])
            self.assertEqual(bool(display.control._last_output["primary_effects"]),fire)
            sample(.16,[ClickEvent("left_up",pos,.15)])
            self.assertEqual(bool(display.control._last_output["primary_effects"]),fire)
            sample(.2,[ClickEvent("left",pos,.19,3)])
            data = display.control._last_output
            self.assertEqual(data["fleet"]["anchor"],pos)
            self.assertEqual(len(data["departing_escorts"]),count)
            self.assertFalse(data["primary_effects"])
            self.assertEqual(display.control.fleet["frames"],94 if name=="キュベレイ" else 172)
            self.assertEqual(turn_frame(display.idle_sheet,0).size,(48,48))
            self.assertIsNone(display.step(None,.3,[],bounds))
            self.assertIsNone(display.control.special)

if __name__ == "__main__":
    unittest.main()
