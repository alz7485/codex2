"""Current development scope. Frozen equipment remains on disk and in settings."""

from pathlib import Path


ACTIVE_FAMILIES = {
    "フィンファンネル系": (
        "ファンネル/フィンファンネル",
        "ファンネル/Hi-νガンダム",
        "ファンネル/νガンダムHWS",
        "ファンネル/ロングレンジ・フィン・ファンネル（RX-93ff）",
    ),
    "キュベレイ系": (
        "ファンネル/キュベレイ",
        "ファンネル/キュベレイMk-II（プル機）",
        "ファンネル/キュベレイMk-II（プルツー機）",
    ),
    "サザビー": ("ファンネル/サザビー",),
    "ユニコーン": ("ファンネル/ユニコーン",),
    "ドラグーン": ("ドラグーン/ストライクフリーダム", "ドラグーン/レジェンドガンダム"),
    "インコム": ("インコム/Sガンダム",),
}
ACTIVE_EQUIPMENT = frozenset(key for family in ACTIVE_FAMILIES.values() for key in family)
FROZEN_EQUIPMENT = frozenset((
    "ファンネル/α・アジール",
    "ファンネル/クィン・マンサ",
    "ファンネル/クシャトリヤ",
    "ファンネル/ヤクト・ドーガ",
    "ファンネル/ナイチンゲール",
    "ビット/エルメス",
    "ビット/ガンダムサバーニャ",
    "ビット/ガンダム・エアリアル",
    "ビット/ガンダム・キャリバーン",
    "ビット/ガンダム・ファラクト",
    "ビット/ガンダム・ルブリス",
    "ファンネルミサイル/Ξガンダム",
    "機動兵装ポッド/カオスガンダム",
))


def equipment_key(cursor):
    path = Path(cursor)
    return f"{path.parent.name}/{path.stem}"


def is_frozen(cursor):
    return equipment_key(cursor) in FROZEN_EQUIPMENT
