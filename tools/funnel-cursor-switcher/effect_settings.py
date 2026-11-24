"""Settings shared by the editor, preview, renderer and preset exchange."""

import json
import os
import re
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Field:
    label: str
    default: object
    low: object = None
    high: object = None
    choices: tuple = ()

    def check(self, value):
        if self.choices:
            return value in self.choices
        if isinstance(self.default, bool):
            return isinstance(value, bool)
        if isinstance(self.default, str):
            return isinstance(value, str) and (
                value == "機体色" or bool(re.fullmatch(r"#[0-9a-fA-F]{6}", value))
            )
        number = type(value) in (int, float) and self.low <= value <= self.high
        return number and (not isinstance(self.default, int) or isinstance(value, int))


def choice(label, *values):
    return Field(label, values[0], choices=values)


COLOR = Field("色", "機体色")
ALPHA = Field("透明度（1で不透明）", 0.85, 0, 1)
STRENGTH = Field("強度", 0.85, 0, 1)
RESPONSE = Field("速度反応", 0.8, 0, 1)
NAMES = dict(
    boost="ブースト噴射",
    trail="移動残像・軌跡",
    click="クリック",
    idle="待機光・浮遊",
    particles="粒子",
    followers="随伴ファンネル",
    deploy="展開・収束",
    rare="レア演出",
    spiral="螺旋ビット放出",
    barrier="Δ型Iフィールド",
    volley="ファンネル・ビット包囲射撃",
    dragoon="ドラグーン展開射撃",
    pods="機動兵装ポッド分離射撃",
    rifle="GNライフルビット一斉射撃",
    shield="シールド・ファンネル三つ羽集合",
    gund="ガンビット分離射撃・再集合",
    biton="ガンビット集合・ビットオン",
    stun="コラキ・スタンビーム",
    incom="有線インコム射出・回収",
    missile="ファンネル・ミサイル斉射",
    cannon="ロングレンジ・フィン・ファンネル射撃",
)
FIELDS = {
    "boost": dict(
        intensity=STRENGTH,
        shape=choice("ノズル", "機体別", "単針", "広口", "二連", "扇形", "リボン"),
        length=Field("長さ倍率", 1.0, 0.2, 1.6),
        width=Field("太さ倍率", 1.0, 0.3, 2),
        minimum=Field("低速噴射長 px", 11, 2, 32),
        maximum=Field("高速噴射長 px", 25, 2, 38),
        response=RESPONSE,
        smoothing=Field("滑らかさ", 0.5, 0, 1),
        color=COLOR,
        opacity=ALPHA,
    ),
    "trail": dict(
        count=Field("残像数", 14, 2, 48),
        style=choice("軌跡", "曲線", "残像", "粒子", "直線", "ワイヤー"),
        interval=Field("間隔 ms", 14, 8, 100),
        duration=Field("残留 ms", 180, 60, 1200),
        width=Field("太さ px", 2, 1, 6),
        response=RESPONSE,
        color=COLOR,
        opacity=ALPHA,
    ),
    "click": dict(
        radius=Field("半径 px", 18, 4, 36),
        **{
            k: choice(label, *styles)
            for k, label, styles in (
                ("left", "左クリック", ("光輪", "六角形", "閃光", "ビーム")),
                ("right", "右クリック", ("六角形", "光輪", "閃光", "ビーム")),
                ("double", "ダブルクリック", ("閃光", "光輪", "六角形", "ビーム")),
            )
        },
        growth=Field("拡大倍率", 1.4, 0.3, 2.5),
        duration=Field("持続 ms", 300, 80, 1200),
        left_color=COLOR,
        right_color=Field("右の色", "#b699ff"),
        double_color=Field("ダブルの色", "#fff0ad"),
        intensity=STRENGTH,
        opacity=ALPHA,
    ),
    "idle": dict(
        intensity=STRENGTH,
        delay=Field("開始まで 秒", 0.9, 0.1, 8),
        period=Field("明滅周期 秒", 1.8, 0.3, 6),
        drift=Field("浮遊幅 px", 2, 0, 6),
        fade=Field("切替時間 ms", 180, 40, 600),
        color=COLOR,
        opacity=ALPHA,
        motion=choice("待機モーション", "なし", "横回転"),
        turn_period=Field("横回転 1周の秒数", 2.4, 0.8, 8),
        turn_direction=choice("回転方向", "順回転", "逆回転"),
    ),
    "particles": dict(
        rate=Field("発生数／秒", 20, 1, 80),
        style=choice("粒の形", "微光", "火花", "推進剤", "煙", "破片"),
        maximum=Field("同時上限", 48, 1, 96),
        size=Field("大きさ px", 2, 1, 6),
        life=Field("寿命 秒", 0.48, 0.1, 2),
        spread=Field("拡散角 度", 75, 5, 360),
        gravity=Field("重力 px/s²", 18, -80, 100),
        response=RESPONSE,
        moving=Field("移動中", True),
        resting=Field("待機中", True),
        burst=Field("クリック時", True),
        color=COLOR,
        opacity=ALPHA,
    ),
    "followers": dict(
        count=Field("機数", 2, 1, 3),
        style=choice("外観", "装備画像", "光の菱形", "輪郭"),
        scale=Field("画像倍率", 0.42, 0.20, 0.70),
        distance=Field("距離 px", 42, 24, 68),
        lag=Field("追従時間 秒", 0.18, 0.04, 0.6),
        formation=choice("隊列", "扇形", "縦列", "横列"),
        orbit=Field("旋回速度 回／秒", 0.16, 0.02, 0.8),
        color=COLOR,
        opacity=ALPHA,
    ),
    "spiral": dict(
        count=Field("放出数", 6, 2, 10),
        radius=Field("広がり px", 76, 32, 96),
        turns=Field("回転数", 1.1, 0.4, 2),
        duration=Field("飛行時間 秒", 1.25, 0.4, 1.6),
        color=COLOR,
        opacity=ALPHA,
    ),
    "deploy": dict(
        distance=Field("展開半径 px", 30, 12, 72),
        trigger=choice("きっかけ", "すべて", "停止", "移動再開", "クリック"),
        opening=Field("展開 ms", 170, 50, 1000),
        hold=Field("保持 ms", 140, 30, 1000),
        closing=Field("収束 ms", 240, 50, 1500),
        rotation=Field("回転 度", 75, -180, 180),
        ease=choice("補間", "滑らか", "機械的"),
        color=COLOR,
        opacity=ALPHA,
    ),
    "rare": dict(
        frequency=Field("平均回数／分", 1.4, 0.2, 12),
        cooldown=Field("再発生間隔 秒", 30, 3, 180),
        spin=Field("回転", True),
        formation=Field("隊列変化", True),
        flash=Field("閃光", True),
        color=COLOR,
        opacity=ALPHA,
    ),
}
SPECIAL = {
    "spiral": {
        "ファンネル/キュベレイ.cur",
        "ファンネル/キュベレイMk-II（プル機）.cur",
        "ファンネル/キュベレイMk-II（プルツー機）.cur",
    },
    "barrier": {
        "ファンネル/フィンファンネル.cur",
        "ファンネル/νガンダムHWS.cur",
        "ファンネル/Hi-νガンダム.cur",
    },
    "volley": {
        f"ファンネル/{name}.cur" for name in
        ("サザビー", "ヤクト・ドーガ", "ナイチンゲール", "クシャトリヤ", "クィン・マンサ", "α・アジール")
    } | {"ビット/エルメス.cur"},
    "dragoon": {f"ドラグーン/{name}.cur" for name in ("ストライクフリーダム", "レジェンドガンダム")},
    "pods": {"機動兵装ポッド/カオスガンダム.cur"},
    "rifle": {"ビット/ガンダムサバーニャ.cur"},
    "shield": {"ファンネル/ユニコーン.cur"},
    "gund": {f"ビット/{name}.cur" for name in ("ガンダム・エアリアル", "ガンダム・ルブリス")},
    "biton": {"ビット/ガンダム・キャリバーン.cur"},
    "stun": {"ビット/ガンダム・ファラクト.cur"},
    "incom": {"インコム/Sガンダム.cur"},
    "missile": {"ファンネルミサイル/Ξガンダム.cur"},
    "cannon": {"ファンネル/ロングレンジ・フィン・ファンネル（RX-93ff）.cur"},
}
# Internal modifier mask shared by the Tk and Windows input adapters.
MODIFIERS = {
    "Ctrl＋Shift": 3,
    "Ctrl＋Alt": 6,
    "Shift＋Alt": 5,
    "Ctrl＋Shift＋Alt": 7,
    "Ctrl": 2,
    "Shift": 1,
    "Alt": 4,
}
BUTTONS = {"左クリック": "left", "中クリック": "middle", "右クリック": "right"}
FIELDS["barrier"] = dict(
    radius=Field("半径 px", 58, 28, 84),
    duration=Field("持続 秒", 1.4, 0.7, 2.4),
    color=Field("色", "#8cecd9"),
    opacity=ALPHA,
)
for group in (g for g in SPECIAL if g not in ("spiral", "barrier")):
    FIELDS[group] = dict(
        radius=Field("展開距離 px", 64, 32, 84),
        duration=Field("持続 秒", 1.8, 0.8, 2.4),
        color=COLOR,
        opacity=ALPHA,
    )
FIELDS["shield"]["duration"] = Field("持続 秒", 3.0, 0.8, 4.8)
FIELDS["cannon"]["duration"] = Field("持続 秒", 2.4, 0.8, 4.8)
for group in SPECIAL:
    FIELDS[group].update(modifiers=choice("発動キー", *MODIFIERS), button=choice("発動ボタン", *BUTTONS))
for key, fields in FIELDS.items():
    fields["enabled"] = Field("有効", key in ("boost", "trail"))
FIELDS["click"]["left_color"] = Field("左の色", "機体色")
for group in ("spiral", "volley", "barrier"):
    FIELDS[group].update(
        click_fire_enabled=Field("クリック・ドラッグで射撃", True),
        orientation_mode=choice("主機の向き", * (("fixed_upper_left","follow") if group=="barrier" else ("follow","fixed_upper_left"))),
    )

CATEGORY = {
    "ファンネル": {"followers": {"orbit": 0.12}},
    "ビット": {"boost": {"width": 1.25}, "followers": {"lag": 0.25}},
    "ドラグーン": {"trail": {"style": "直線"}, "deploy": {"ease": "機械的"}},
    "インコム": {"trail": {"style": "ワイヤー"}},
    "ファンネルミサイル": {"boost": {"response": 1.0}, "particles": {"style": "煙", "life": 0.3}},
    "機動兵装ポッド": {"followers": {"formation": "横列"}, "deploy": {"ease": "機械的"}},
}
STANDARD = "標準"
SAMPLES = {
    STANDARD: {},
    "控えめ": {"boost": {"intensity": 0.45}, "trail": {"opacity": 0.4, "duration": 130}},
    "戦闘モード": {key: {"enabled": True} for key in FIELDS if key not in SPECIAL},
}


def special_group(cursor):
    return next((group for group, cursors in SPECIAL.items() if cursor in cursors), None)


def default_binding(cursor):
    group = special_group(cursor)
    return {"preset": STANDARD, "overrides": {group: {"enabled": True}} if group else {}}


def valid_name(name):
    return (
        isinstance(name, str) and bool(name.strip()) and len(name) <= 100 and all(ord(c) >= 32 for c in name)
    )


def patch(data, strict=False):
    if not isinstance(data, dict):
        raise ValueError("演出設定の形式を確認してください。")
    result = {}
    for group, values in data.items():
        if group not in FIELDS:
            continue
        if not isinstance(values, dict):
            raise ValueError("演出の項目を読み取れません。")
        for key, value in values.items():
            field = FIELDS[group].get(key)
            if field and field.check(value):
                result.setdefault(group, {})[key] = value
            elif field and strict:
                raise ValueError(f"「{NAMES[group]}」の「{field.label}」の値を確認してください。")
    return result


def resolve(category, preset, overrides, cursor_key=None):
    values = {g: {k: f.default for k, f in fields.items()} for g, fields in FIELDS.items()}
    origins = {g: dict.fromkeys(fields, "共通") for g, fields in FIELDS.items()}
    if cursor_key == "ファンネル/フィンファンネル.cur":
        values["barrier"]["color"] = "#d479ca"
        origins["barrier"]["color"] = "機体"
    if cursor_key in ("ファンネル/キュベレイ.cur", "ファンネル/サザビー.cur"):
        values["followers"].update(enabled=True, count=3)
        origins["followers"].update(enabled="機体", count="機体")
    for layer, title in ((CATEGORY.get(category, {}), "分類"), (preset, "プリセット"), (overrides, "個別")):
        for group, fields in layer.items():
            values[group].update(fields)
            origins[group].update(dict.fromkeys(fields, title))
    return values, origins


def difference(values, base):
    return patch({g: {k: v for k, v in fields.items() if base[g][k] != v} for g, fields in values.items()})


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
            temporary = Path(f.name)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def encode(data):
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8")


def read_preset(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not valid_name(data.get("name")):
        raise ValueError("バージョン1のプリセットJSONを選んでください。")
    return data["name"], patch(data.get("effects"), strict=True)


class Settings:
    def __init__(self, path):
        self.path = path
        self.warning = ""
        self.presets = {}
        self.cursors = {}
        self.active = ""
        self.original = None
        try:
            self.original = path.read_bytes()
            data = json.loads(self.original.decode("utf-8-sig"))
            if not isinstance(data, dict) or data.get("schema_version") != 1:
                raise ValueError("設定バージョンを読み込めません。")
            presets = data.get("presets", {})
            cursors = data.get("cursors", {})
            if not isinstance(presets, dict) or not isinstance(cursors, dict):
                raise ValueError("設定の構造を読み込めません。")
            self.presets = {n: patch(v) for n, v in presets.items() if valid_name(n) and n not in SAMPLES}
            for cursor, binding in cursors.items():
                if isinstance(binding, dict):
                    name = binding.get("preset")
                    self.cursors[cursor] = dict(
                        preset=name if isinstance(name, str) and name in self.choices() else STANDARD,
                        overrides=patch(binding.get("overrides", {})),
                    )
            self.active = data.get("active_cursor", "") if isinstance(data.get("active_cursor"), str) else ""
        except FileNotFoundError:
            pass
        except (ValueError, OSError, RecursionError):
            self.presets, self.cursors, self.active = {}, {}, ""
            self.warning = "設定を初期値で開きました。次回保存時に元データを .bak に退避します。"

    def choices(self):
        return {**SAMPLES, **self.presets}

    def binding(self, cursor):
        return deepcopy(self.cursors[cursor]) if cursor in self.cursors else default_binding(cursor)

    def write(self):
        data = encode(
            dict(schema_version=1, active_cursor=self.active, presets=self.presets, cursors=self.cursors)
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Serialize compare-and-replace across instances. Windows releases this lock on process exit.
        with self.path.with_suffix(".lock").open("a+b") as guard:
            if os.name == "nt":
                import msvcrt

                guard.seek(0)
                msvcrt.locking(guard.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                latest = self.path.read_bytes()
            except FileNotFoundError:
                latest = None
            if latest != self.original:
                raise ValueError("設定が別の画面で更新されました。再起動して読み直してください。")
            if self.warning and latest is not None:
                atomic_write(self.path.with_suffix(".bak"), latest)
            atomic_write(self.path, data)
        self.original, self.warning = data, ""
