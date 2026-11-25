from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory
import unittest

from equipment_catalog import ACTIVE_EQUIPMENT, ACTIVE_FAMILIES, FROZEN_EQUIPMENT, equipment_key, is_frozen
from effect_settings import Settings
from effect_settings import SPECIAL
from render_special_preview import preview_candidates, render


ROOT = Path(__file__).resolve().parent
discover = run_path(str(ROOT / "FunnelCursorSwitcher.pyw"))["discover_cursors"]


def files(entries):
    return [p for group in entries.values() for p in group]


class CatalogScope(unittest.TestCase):
    def test_default_previews_exclude_frozen_equipment(self):
        active = {equipment_key(key) for group in SPECIAL for key in preview_candidates(group)}
        archived = {equipment_key(key) for group in SPECIAL for key in preview_candidates(group, True)}
        self.assertEqual(active, ACTIVE_EQUIPMENT)
        self.assertEqual(archived, ACTIVE_EQUIPMENT | FROZEN_EQUIPMENT)
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "frozen.gif"
            with self.assertRaisesRegex(ValueError, "凍結"):
                render(output, group="stun")
            self.assertFalse(output.exists())

    def test_only_twelve_active_equipment_in_default_menu(self):
        entries = discover(ROOT / "カーソル")
        self.assertEqual(len(ACTIVE_FAMILIES), 3)
        self.assertEqual(len(files(entries)), 5)
        self.assertEqual({equipment_key(p) for p in files(entries)}, ACTIVE_EQUIPMENT)
        self.assertEqual(set(entries), {"ファンネル"})
        self.assertEqual(entries["ファンネル"][0].stem, "フィンファンネル")

    def test_frozen_thirteen_are_preserved_in_archive(self):
        all_files = files(discover(ROOT / "カーソル", include_frozen=True))
        self.assertEqual(len(FROZEN_EQUIPMENT), 21)
        self.assertFalse(ACTIVE_EQUIPMENT & FROZEN_EQUIPMENT)
        self.assertEqual({equipment_key(p) for p in all_files}, ACTIVE_EQUIPMENT | FROZEN_EQUIPMENT)
        for path in all_files:
            self.assertTrue(path.is_file())
            self.assertTrue(path.with_suffix(".png").is_file())
            self.assertTrue((ROOT / "飛行アニメ" / path.parent.name / (path.stem + ".png")).is_file())

    def test_ani_alias_does_not_unfreeze_but_custom_cursors_still_work(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for key in ("ファンネル/フィンファンネル.cur", "ファンネル/ナイチンゲール.ANI",
                        "ビット/エルメス.cur", "自作/追加.ani"):
                path = root / key
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            entries = discover(root)
            self.assertEqual(set(entries), {"ファンネル", "自作"})
            self.assertEqual({p.stem for p in files(entries)}, {"フィンファンネル", "追加"})
            self.assertEqual(len(files(discover(root, include_frozen=True))), 4)

    def test_frozen_settings_and_previous_selection_survive_save(self):
        with TemporaryDirectory() as tmp:
            store = Settings(Path(tmp) / "effects.json")
            key = "ファンネル/ナイチンゲール.cur"
            binding = {"preset": "標準", "overrides": {"volley": {"enabled": True, "radius": 73}}}
            store.active = key
            store.cursors[key] = binding
            store.write()
            self.assertTrue(is_frozen(key))
            self.assertNotIn(key, {f"{p.parent.name}/{p.name}" for p in files(discover(ROOT / "カーソル"))})
            restored = Settings(store.path)
            self.assertEqual(restored.active, key)
            self.assertEqual(restored.binding(key), binding)
            restored.active = "ファンネル/フィンファンネル.cur"
            restored.cursors[restored.active] = restored.binding(restored.active)
            restored.write()
            self.assertEqual(Settings(store.path).binding(key), binding)


if __name__ == "__main__":
    unittest.main()
