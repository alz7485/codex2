"""Current development scope. Frozen equipment remains on disk and in settings."""

from pathlib import Path


ACTIVE_FAMILIES = {
    "フィンファンネル系": ("ファンネル/フィンファンネル",),
    "キュベレイ系": ("ファンネル/キュベレイ",),
    "サザビー": ("ファンネル/サザビー",),
}
ACTIVE_EQUIPMENT = frozenset(key for family in ACTIVE_FAMILIES.values() for key in family)
FROZEN_EQUIPMENT = frozenset((
    'インコム/Sガンダム',
    'ドラグーン/ストライクフリーダム',
    'ドラグーン/レジェンドガンダム',
    'ファンネル/Hi-νガンダム',
    'ファンネル/νガンダムHWS',
    'ファンネル/キュベレイMk-II（プルツー機）',
    'ファンネル/キュベレイMk-II（プル機）',
    'ファンネル/ユニコーン',
    'ファンネル/ロングレンジ・フィン・ファンネル（RX-93ff）',

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
