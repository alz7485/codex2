import copy
from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import tempfile
import unittest

from catalog_studio.booklet import generate_pdf, snapshot


def project():
    return {
        "format": "catalog-studio-integrated", "version": 2, "name": "配管部品カタログ",
        "parameters": [{"id": "P1", "role": "大径側外径", "unit": "mm"},
                       {"id": "P2", "role": "小径側外径", "unit": "mm"},
                       {"id": "P3", "role": "全長", "unit": "mm"}],
        "cates": [{"id": "cate", "name": "レデューサー", "description": "突合せ溶接", "revision": "A"},
                  {"id": "unused-cate", "name": "未掲載", "description": "", "revision": "A"}],
        "definitions": [
            {"id": "gm", "name": "/RED-GM", "kind": "GMSET", "revision": "1", "elements": [
                {"id": "body", "name": "円錐台", "type": "cone", "attrs": {
                    "大径": "大径側外径", "小径": "小径側外径", "長さ": "全長", "位置": "全長 / 2", "方向": "Z"}}]},
            {"id": "pt", "name": "/RED-PT", "kind": "PTSET", "revision": "2", "elements": [
                {"id": "a", "name": "接続点1", "type": "point", "attrs": {"位置": "0", "方向": "-Z", "接続口径": "大径側外径"}},
                {"id": "b", "name": "接続点2", "type": "point", "attrs": {"位置": "全長", "方向": "Z", "接続口径": "小径側外径"}}]},
            {"id": "unused", "name": "/UNUSED", "kind": "GMSET", "revision": "1", "elements": []}],
        "scoms": [{"id": "s1", "name": "/RED-65X40", "cate_id": "cate", "size": "65 × 40", "revision": "3",
                   "gmset_id": "gm", "ptset_id": "pt", "values": {"P1": 76.3, "P2": 48.6, "P3": 102}},
                  {"id": "s2", "name": "/RED-80X50", "cate_id": "cate", "size": "80 × 50", "revision": "1",
                   "gmset_id": "gm", "ptset_id": "pt", "values": {"P1": 89.1, "P2": 60.5, "P3": 127}}],
        "specs": [{"id": "spec", "name": "/CS150", "description": "炭素鋼 150LB", "revision": "B", "entries": [
            {"id": "entry", "type": "REDU", "bore1": 65, "bore2": 40, "scom_id": "s1", "description": "同心レデューサー"}]}],
        "books": [],
    }


class BookSnapshotTests(unittest.TestCase):
    def test_snapshot_copies_dimensions_definitions_and_specs(self):
        data = project()
        book = snapshot(data, ["s1"], ["spec"], "カタログ保存版", "2026-A")
        self.assertEqual([item["id"] for item in book["scoms"]], ["s1"])
        self.assertEqual([item["id"] for item in book["cates"]], ["cate"])
        self.assertEqual([item["id"] for item in book["definitions"]], ["gm", "pt"])
        data["scoms"][0]["values"]["P1"] = 999
        data["definitions"][0]["elements"][0]["attrs"]["大径"] = "123"
        data["specs"][0]["entries"][0]["bore1"] = 999
        data["parameters"][0]["role"] = "変更"
        self.assertEqual(book["scoms"][0]["values"]["P1"], 76.3)
        self.assertEqual(book["definitions"][0]["elements"][0]["attrs"]["大径"], "大径側外径")
        self.assertEqual(book["specs"][0]["entries"][0]["bore1"], 65)
        self.assertEqual(book["parameters"][0]["role"], "大径側外径")

    def test_selected_spec_includes_referenced_scom_without_touching_project(self):
        data = project()
        before = copy.deepcopy(data)
        book = snapshot(data, [], ["spec"], "スペック集", "1")
        self.assertEqual([item["id"] for item in book["scoms"]], ["s1"])
        self.assertEqual(data, before)
        self.assertEqual(snapshot(data, None, [], "全部", "1")["specs"], [])

    def test_snapshot_timestamp_uses_japan_timezone(self):
        book = snapshot(project(), ["s1"], [], "保存版", "1")
        self.assertEqual(datetime.fromisoformat(book["created_at"]).utcoffset(), timedelta(hours=9))

    def test_missing_or_wrong_references_cannot_be_published(self):
        for mutation in (lambda d: d["specs"][0]["entries"][0].update(scom_id="missing"),
                         lambda d: d["scoms"][0].update(gmset_id="missing"),
                         lambda d: d["scoms"][0].update(ptset_id="gm"),
                         lambda d: d["scoms"][0].update(cate_id="missing")):
            data = project()
            mutation(data)
            with self.assertRaises(ValueError):
                snapshot(data, ["s1"], ["spec"], "保存版", "1")
        with self.assertRaises(ValueError):
            snapshot(project(), ["missing"], [], "保存版", "1")
        with self.assertRaises(ValueError):
            snapshot(project(), [], [], "空", "1")


@unittest.skipUnless(importlib.util.find_spec("reportlab") and importlib.util.find_spec("pypdf"),
                     "PDF validation requires reportlab and pypdf")
class BookPdfTests(unittest.TestCase):
    def test_invalid_dimensions_have_explicit_unavailable_diagram(self):
        from pypdf import PdfReader
        mutations = [
            (lambda d: d["scoms"][0]["values"].pop("P1"), "未定義のパラメータ"),
            (lambda d: d["scoms"][0]["values"].update(P3=-10), "寸法は正の値"),
            (lambda d: d["definitions"][0]["elements"][0]["attrs"].update(大径="未知の外径"), "未定義のパラメータ"),
            (lambda d: d["definitions"][0]["elements"][0]["attrs"].pop("長さ"), "未設定の属性"),
        ]
        for n, (mutation, expected) in enumerate(mutations):
            with self.subTest(case=n), tempfile.TemporaryDirectory() as folder:
                data = project()
                mutation(data)
                book = snapshot(data, ["s1"], [], "要確認の保存版", "A")
                output = generate_pdf(book, Path(folder) / "review.pdf")
                text = "\n".join(page.extract_text() for page in PdfReader(output).pages)
                self.assertIn("概略図を表示できません", text)
                self.assertIn(expected, text)
                self.assertNotIn("軸方向の概略図 ／ SCOM の値を使用", text)

    def test_pdf_contains_frozen_japanese_dimension_and_spec_tables(self):
        from pypdf import PdfReader
        data = project()
        data["scoms"][0]["name"] = "/RED-65X40 <&>"
        book = snapshot(data, ["s1"], ["spec"], "配管カタログ保存版", "A")
        data["scoms"][0]["values"]["P1"] = 999
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "catalog.pdf"
            self.assertEqual(generate_pdf(book, output), output)
            self.assertTrue(output.read_bytes().startswith(b"%PDF-"))
            reader = PdfReader(output)
            self.assertGreaterEqual(len(reader.pages), 5)
            self.assertEqual(reader.metadata.title, "配管カタログ保存版")
            text = "\n".join(page.extract_text() for page in reader.pages)
            for expected in ("大径側外径", "76.3", "/RED-65X40 <&>", "/CS150", "GMSET", "PTSET"):
                self.assertIn(expected, text)
            self.assertNotIn("999", text)
            self.assertEqual(list(Path(folder).iterdir()), [output])

    def test_long_spec_table_paginates_and_keeps_last_entry(self):
        from pypdf import PdfReader
        data = project()
        data["specs"][0]["entries"] = [
            {"id": f"row-{n}", "type": "REDU", "bore1": n + 1, "bore2": 40,
             "scom_id": "s1", "description": f"掲載行-{n:03}"} for n in range(100)]
        book = snapshot(data, [], ["spec"], "ページ分割検証", "A")
        with tempfile.TemporaryDirectory() as folder:
            output = generate_pdf(book, Path(folder) / "long.pdf")
            reader = PdfReader(output)
            self.assertGreater(len(reader.pages), 7)
            text = "\n".join(page.extract_text() for page in reader.pages)
            self.assertIn("掲載行-000", text)
            self.assertIn("掲載行-099", text)


if __name__ == "__main__":
    unittest.main()
