"""Immutable catalogue editions and printable PDF books for the mockup.

Only SCOM records supply numerical dimensions.  Shared GMSET/PTSET
definitions remain expressions, and an edition copies both together so a
later project edit cannot change an already issued catalogue.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import uuid
from xml.sax.saxutils import escape
from . import presets

JST = timezone(timedelta(hours=9), name="JST")


def snapshot(data, scom_ids=None, spec_ids=None, title="カタログ本", edition="1"):
    """Copy a self-contained edition; include SCOMs referenced by chosen specs.

    ``None`` selects every record of that kind; an empty list selects none.
    The returned dict is JSON serializable and never shares mutable objects
    with the editable project.  Referenced CATEs and definitions are included.
    """
    if not isinstance(title, str) or not title.strip():
        raise ValueError("カタログ本のタイトルを入力してください。")
    indexes = {}
    for key in ("scoms", "specs", "cates", "definitions", "texts", "tables"):
        items = data.get(key, [])
        indexes[key] = {item["id"]: item for item in items}
        if len(indexes[key]) != len(items):
            raise ValueError(f"{key} の識別子が重複しています。")

    def selection(key, ids):
        chosen = set(indexes[key] if ids is None else ids)
        missing = chosen.difference(indexes[key])
        if missing:
            raise ValueError(f"{key} の選択先が見つかりません：{', '.join(sorted(missing))}")
        return chosen

    selected_scoms = selection("scoms", scom_ids)
    selected_specs = selection("specs", spec_ids)
    text_ids=set()
    for spec_id in selected_specs:
        for entry in indexes["specs"][spec_id].get("entries", []):
            scom_id = entry.get("scom_id")
            if scom_id not in indexes["scoms"]:
                raise ValueError("スペックの参照先 SCOM が見つかりません。")
            selected_scoms.add(scom_id)
            for key,kind in (('sdte_id','SDTE'),('smte_id','SMTE')):
                ident=entry.get(key,'')
                if not ident:continue
                if ident not in indexes['texts'] or indexes['texts'][ident]['type'] != kind:raise ValueError('スペックのテキスト参照先が不正です。')
                text_ids.add(ident)
    cate_ids, definition_ids = set(), set()
    for scom_id in selected_scoms:
        scom = indexes["scoms"][scom_id]
        cate_id = scom.get("cate_id")
        if cate_id not in indexes["cates"]:
            raise ValueError("SCOM の参照先 CATE が見つかりません。")
        cate_ids.add(cate_id)
        for key, kind in (("gmset_id", "GMSET"), ("ptset_id", "PTSET"),('ngmset_id','NGMSET'),('gmsset_id','GMSSET'),('ptsset_id','PTSSET')):
            definition_id = scom.get(key)
            if key not in ('gmset_id','ptset_id') and not definition_id:continue
            if definition_id not in indexes["definitions"]:
                raise ValueError(f"SCOM の参照先 {kind} が見つかりません。")
            if indexes["definitions"][definition_id].get("kind") != kind:
                raise ValueError(f"SCOM の {kind} 参照先の種類が一致しません。")
            definition_ids.add(definition_id)
    if not selected_scoms and not selected_specs:
        raise ValueError("掲載する SCOM またはスペックを選択してください。")
    book = {
        "id": uuid.uuid4().hex,
        "title": title.strip(),
        "edition": str(edition),
        "created_at": datetime.now(JST).isoformat(timespec="seconds"),
        "project_name": data.get("name", ""),
        "parameters": copy.deepcopy(data.get("parameters", [])),
        "reference_roles":copy.deepcopy(data.get("reference_roles",{})),
    }
    for key, ids in (("scoms", selected_scoms), ("specs", selected_specs),
                     ("cates", cate_ids), ("definitions", definition_ids)):
        book[key] = copy.deepcopy([item for item in data.get(key, []) if item["id"] in ids])
    book['texts']=copy.deepcopy([r for r in data.get('texts',[]) if r['id'] in text_ids])
    # Shared tables are project context; freeze the complete table collection.
    book['tables']=copy.deepcopy(data.get('tables',[]))
    owners={r.get('parent_id') for r in book['texts']+book['tables']}
    for cate in data.get('cates',[]):
        if cate['id'] in owners and cate['id'] not in cate_ids:book['cates'].append(copy.deepcopy(cate))
    used_presets={presets.selected_id(data,r) for key in ('scoms','definitions') for r in book[key]} - {''}
    for ident in used_presets:
        if not presets.get(data,ident):raise ValueError('掲載データの PARAM プリセットが見つかりません：'+ident)
    book['parameter_presets']=copy.deepcopy([p for p in data.get('parameter_presets',[]) if p['id'] in used_presets])
    return book


def generate_pdf(book, path):
    """Write an A4 catalogue containing frozen dimensions, specs and formulas.

    Japanese text uses the standard PDF Japanese CID font.  ReportLab is
    loaded lazily so the rest of the desktop tool works without PDF support.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import (
            KeepTogether, LongTable, PageBreak, Paragraph,
            SimpleDocTemplate, Spacer, TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("PDF 出力には reportlab が必要です。pip install reportlab を実行してください。") from exc

    font = "HeiseiKakuGo-W5"
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(font))
    blue = colors.HexColor("#176B88")
    ink = colors.HexColor("#20344D")
    muted = colors.HexColor("#67788B")
    pale = colors.HexColor("#EAF2F7")
    paper_width, _paper_height = A4
    margin = 48
    width = paper_width - margin * 2
    styles = {
        "body": ParagraphStyle("body", fontName=font, fontSize=9, leading=14,
                               textColor=ink, wordWrap="CJK", spaceAfter=4),
        "small": ParagraphStyle("small", fontName=font, fontSize=8, leading=12,
                                textColor=muted, wordWrap="CJK", spaceAfter=4),
        "h1": ParagraphStyle("h1", fontName=font, fontSize=20, leading=28,
                             textColor=ink, wordWrap="CJK", spaceAfter=15),
        "h2": ParagraphStyle("h2", fontName=font, fontSize=13, leading=19,
                             textColor=blue, wordWrap="CJK", spaceBefore=10, spaceAfter=8),
        "title": ParagraphStyle("title", fontName=font, fontSize=28, leading=38,
                                textColor=ink, wordWrap="CJK", spaceAfter=24),
        "label": ParagraphStyle("label", fontName=font, fontSize=9, leading=13,
                                textColor=colors.white, wordWrap="CJK"),
    }

    def p(text, style="body"):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), styles[style])

    def table(rows, col_widths):
        rendered = [[p(value, "label" if n == 0 else "body") for value in row]
                    for n, row in enumerate(rows)]
        result = LongTable(rendered, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
        result.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), blue),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, pale]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LINEBELOW", (0, 0), (-1, 0), .7, blue),
        ]))
        return result

    def number(value):
        if type(value) in (int, float) and math.isfinite(value):
            return f"{value:g}"
        return "—" if value is None else str(value)

    created = book.get("created_at", "")
    try:
        created = datetime.fromisoformat(created).astimezone(JST).strftime("%Y-%m-%d %H:%M JST")
    except (ValueError, KeyError):
        created = str(created)
    scoms = book.get("scoms", [])
    specs = book.get("specs", [])
    parameters = book.get("parameters", [])
    definitions = {item["id"]: item for item in book.get("definitions", [])}
    text_index={r['id']:r for r in book.get('texts',[])}
    scom_index = {item["id"]: item for item in scoms}
    story = [Spacer(1, 55), p("CATALOG STUDIO", "h2"),
             p(book.get("title", "カタログ本"), "title"),
             p(f"版：{book.get('edition', '1')}　／　発行日時：{created}"),
             p(book.get("project_name", "")), Spacer(1, 22),
             table([["収録内容", "件数"], ["SCOM ／ 寸法", len(scoms)],
                    ["スペック", len(specs)], ["共通定義 GMSET・PTSET", len(definitions)]],
                   [width * .7, width * .3]), Spacer(1, 18),
             p("本書は発行時点の SCOM 実数値、参照先定義、スペックをまとめた保存版です。"),
             p("モックアップの参考出力です。形状は概略図で、E3D での動作確認は別途必要です。", "small"),
             PageBreak(), p("収録一覧", "h1")]
    contents = [["区分", "名称", "改訂 / 件数"]]
    for cate in book.get("cates", []):
        members = [scom for scom in scoms if scom.get("cate_id") == cate["id"]]
        contents.append(["CATE", cate.get("name", ""), f"{cate.get('revision', '')} / {len(members)} SCOM"])
    for spec in specs:
        contents.append(["SPEC", spec.get("name", ""), f"{spec.get('revision', '')} / {len(spec.get('entries', []))} 行"])
    story.append(table(contents, [70, width - 215, 145]))
    for cate in book.get("cates", []):
        members = [scom for scom in scoms if scom.get("cate_id") == cate["id"]]
        story.extend([PageBreak(), p(cate.get("name", "CATE"), "h1"),
                      p(f"CATE　改訂：{cate.get('revision', '')}", "small"),
                      p(cate.get("description", "")), p("サイズ別寸法表", "h2")])
        groups={}
        for member in members:groups.setdefault(presets.selected_id(book,member),[]).append(member)
        for ident,group in groups.items():
            rules=presets.rules(book,group[0])
            story.append(p('PARAM プリセット：'+presets.label(book,group[0]),'h2'))
            chunks=[rules[n:n+4] for n in range(0,len(rules),4)] or [[]]
            for chunk in chunks:
                header=['SCOM','呼び径','改訂']+[f"{parameter['id']}\n{parameter.get('role','')}\n{parameter.get('unit','')}" for parameter in chunk]
                rows=[header]+[[scom.get('name',''),scom.get('size',''),scom.get('revision','')]+[number(scom.get('values',{}).get(parameter['id'])) for parameter in chunk] for scom in group]
                col_widths=[130,55,42]
                if chunk:col_widths += [(width-sum(col_widths))/len(chunk)]*len(chunk)
                else:col_widths[0] += width-sum(col_widths)
                story.extend([table(rows,col_widths),Spacer(1,12)])
        for scom in members:
            gmset = definitions.get(scom.get("gmset_id"), {})
            ptset = definitions.get(scom.get("ptset_id"), {})
            preset_problem=''
            try:
                for d in (gmset,ptset):presets.require_compatible(book,scom,d)
            except ValueError as exc:preset_problem=str(exc)
            summary = [p(f"{scom.get('name', '')}　／　{ scom.get('size', '')}", "h2"),
                       p(f"GMSET：{gmset.get('name', '')}（改訂 {gmset.get('revision', '')}）\n"
                         f"PTSET：{ptset.get('name', '')}（改訂 {ptset.get('revision', '')}）", "small"),
                       _schematic(scom, gmset, ptset, presets.rules(book,scom), font, width,preset_problem)]
            story.extend([KeepTogether(summary), Spacer(1, 8)])
    for spec in specs:
        story.extend([PageBreak(), p(spec.get("name", "SPEC"), "h1"),
                      p(f"スペック　改訂：{spec.get('revision', '')}", "small"),
                      p(spec.get("description", ""))])
        rows = [["部品種別", "口径1", "口径2", "参照 SCOM", "説明"]]
        for entry in spec.get("entries", []):
            scom = scom_index.get(entry.get("scom_id"), {})
            rows.append([entry.get("type", ""), entry.get("bore1", ""), entry.get("bore2", ""),
                         scom.get("name", "参照なし"), entry.get("description", "")+'\n'+ '\n'.join(kind+': '+text_index.get(entry.get(key,''),{}).get('name','未設定') for key,kind in (('sdte_id','SDTE'),('smte_id','SMTE')))])
        story.append(table(rows, [70, 48, 48, 145, width - 311]))
    if definitions:
        story.extend([PageBreak(), p("共通定義とパラメータ", "h1"),
                      p("GMSET・PTSET は式として保存し、実数値は SCOM の寸法表に掲載しています。")])
        story.append(p("既存規則（従来データ）", "h2"))
        rows = [["番号", "役割・日本語説明", "単位"]] + [[parameter["id"], presets.caption(parameter),
                                                     parameter.get("unit", "")] for parameter in parameters]
        story.append(table(rows, [65, width - 130, 65]))
        if book.get('reference_roles'):
            story.append(table([['参照種類','番号','役割']]+[[family,pid,role] for family,roles in book['reference_roles'].items() for pid,role in roles.items()],[120,60,width-180]))
        for preset in book.get('parameter_presets',[]):
            story.append(p('PARAM プリセット：'+preset['name'],'h2'))
            story.append(p('登録時期：'+preset['period']+' / コンポーネント：'+preset['component'],'small'))
            story.append(p(preset['description']))
            rows=[['番号','表示名・日本語説明','単位・値型']]+[[r['id'],r['role']+'\n'+r.get('description',''),r['unit']+' / '+r.get('value_type','number')] for r in preset['parameters']]
            story.append(table(rows,[65,width-160,95]))
            if preset.get('reference_roles'):story.append(table([['参照種類','番号','役割']]+[[family,pid,role] for family,roles in preset['reference_roles'].items() for pid,role in roles.items()],[120,60,width-180]))
        for definition in definitions.values():
            story.extend([p(definition.get("name", ""), "h2"),
                          p(f"{definition.get('kind', '')}　／　改訂：{definition.get('revision', '')}", "small")])
            from . import element_schema
            story.append(p('PARAM プリセット：'+presets.label(book,definition),'small'))
            rows = [["要素 / 種類", "属性・役割", "設定式・値"]]
            for key,value in definition.get('attrs',{}).items():rows.append(['セットの親属性',key,value])
            for element in element_schema.walk(definition.get("elements", [])):
                first = True
                if not element.get('attrs'):rows.append([element.get('name','')+'\n'+element.get('type',''),'子要素の管理',''])
                for key, value in element.get("attrs", {}).items():
                    label = f"{element.get('name', '')}\n{element.get('type', '')}" if first else ""
                    rows.append([label, key+'\n'+element_schema.meaning(element['type'],key), value])
                    first = False
            if len(rows) == 1:
                rows.append(["要素なし", "", ""])
            story.append(table(rows, [145, 85, width - 230]))

    for collection,title in (('texts','説明・材質テキスト'),('tables','発行時点の共通テーブル')):
        records=book.get(collection,[])
        if not records:continue
        story.extend([PageBreak(),p(title,'h1')])
        if collection=='tables':story.append(p('プロジェクト内の共通テーブルを発行時点で固定しています。','small'))
        from . import catalogue
        for record in records:
            story.append(p(record['type']+' '+record['name'],'h2'))
            story.append(p('親：'+record['parent_id']+' / 改訂：'+record['revision'],'small'))
            rows=[['属性','役割','値']]+[[key,catalogue.MEANINGS.get(key,'原文属性'),str(value)] for key,value in record['attrs'].items()]
            if len(rows)>1:story.append(table(rows,[70,150,width-220]))

    path = Path(path)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")

    def page_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CAD8E2"))
        canvas.line(margin, 40, paper_width - margin, 40)
        canvas.setFont(font, 8)
        canvas.setFillColor(muted)
        canvas.drawString(margin, 26, str(book.get("title", "カタログ本"))[:55])
        canvas.drawRightString(paper_width - margin, 26, f"版 {book.get('edition', '1')}　|　{document.page}")
        canvas.restoreState()

    try:
        doc = SimpleDocTemplate(str(temporary), pagesize=A4, rightMargin=margin,
                                leftMargin=margin, topMargin=48, bottomMargin=57,
                                title=book.get("title", "カタログ本"), author="Catalog Studio")
        doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _schematic(scom, gmset, ptset, parameters, font, width,preset_problem=''):
    """A deliberately labelled axial schematic, evaluated with this SCOM only."""
    from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, Circle, String
    from reportlab.lib import colors
    from .model import evaluate

    height = 155
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#F5F8FB"),
                     strokeColor=colors.HexColor("#D5E0E8"), strokeWidth=.5))
    # Omit missing values from the evaluator.  Inventing a zero here can make
    # an incomplete SCOM appear to have a valid position or usable shape.
    values = scom.get("values", {})
    numerical_parameters = [dict(parameter, value=values[parameter["id"]])
                            for parameter in parameters if parameter["id"] in values]
    shapes, points = [], []
    errors = [preset_problem] if preset_problem else []

    def value(element, key):
        attrs = element.get("attrs", {})
        if key not in attrs:
            raise ValueError(f"未設定の属性：{key}")
        result = evaluate(str(attrs[key]), numerical_parameters)
        if abs(result) > 1_000_000:
            raise ValueError("概略図の寸法範囲を超えています。")
        return result

    for element in gmset.get("elements", []):
        try:
            if element.get("attrs", {}).get("方向") not in ("Z", "-Z"):
                raise ValueError("軸方向以外は概略図の対象外です。")
            kind = element.get("type")
            if kind not in ("cone", "cylinder", "box"):
                raise ValueError("概略図で未対応の要素です。")
            position = value(element, "位置")
            length = value(element, "奥行き" if kind == "box" else "長さ")
            d1 = value(element, "幅" if kind == "box" else ("大径" if kind == "cone" else "直径"))
            d2 = value(element, "小径") if kind == "cone" else d1
            if length <= 0 or min(d1, d2) <= 0:
                raise ValueError("寸法は正の値が必要です。")
            if kind == "box" and value(element, "高さ") <= 0:
                raise ValueError("寸法は正の値が必要です。")
            sign = -1 if element.get("attrs", {}).get("方向") == "-Z" else 1
            position *= sign
            if sign < 0:
                d1, d2 = d2, d1
            shapes.append((position - length / 2, position + length / 2, d1, d2))
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"{element.get('name', '形状')}：{exc}")
    for element in ptset.get("elements", []):
        try:
            if element.get("attrs", {}).get("方向") not in ("Z", "-Z"):
                raise ValueError("軸方向以外は概略図の対象外です。")
            if value(element, "接続口径") <= 0:
                raise ValueError("接続口径は正の値が必要です。")
            points.append((value(element, "位置"), element.get("name", "ポイント"),
                           element.get("attrs", {}).get("方向")))
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"{element.get('name', 'ポイント')}：{exc}")
    if errors:
        # Show no partial silhouette: a valid-looking remainder would hide a
        # failed dimension/point expression.  Original values and formulas
        # remain visible in the surrounding catalogue tables.
        drawing.add(String(width / 2, 98, "概略図を表示できません", fontName=font,
                           fontSize=11, textAnchor="middle", fillColor=colors.HexColor("#9A6130")))
        message = errors[0]
        for n in range(0, min(len(message), 96), 48):
            drawing.add(String(width / 2, 76 - n / 48 * 15, message[n:n + 48], fontName=font,
                               fontSize=8, textAnchor="middle", fillColor=colors.HexColor("#67788B")))
        drawing.add(String(width / 2, 25, "SCOM の値・設定式、表示対応する要素と方向を確認してください。",
                           fontName=font, fontSize=8, textAnchor="middle",
                           fillColor=colors.HexColor("#67788B")))
        return drawing
    extents = [coordinate for shape in shapes for coordinate in shape[:2]] + [point[0] for point in points]
    lo, hi = min(extents, default=0), max(extents, default=100)
    diameter = max((max(shape[2:]) for shape in shapes), default=50)
    scale = min((width - 110) / max(hi - lo, 1), 70 / max(diameter, 1))
    left = width / 2 - (lo + hi) / 2 * scale
    cy = 77
    drawing.add(Line(35, cy, width - 35, cy, strokeColor=colors.HexColor("#AABCCC"),
                     strokeDashArray=[4, 3]))
    for start, end, d1, d2 in shapes:
        x1, x2 = left + start * scale, left + end * scale
        r1, r2 = d1 * scale / 2, d2 * scale / 2
        drawing.add(Polygon([x1, cy - r1, x1, cy + r1, x2, cy + r2, x2, cy - r2],
                            fillColor=colors.HexColor("#BCD9E6"), strokeColor=colors.HexColor("#397891"),
                            strokeWidth=1))
    for n, (position, name, direction) in enumerate(points):
        x = left + position * scale
        dx = -18 if direction == "-Z" else 18 if direction == "Z" else 0
        dy = 0 if dx else 18
        drawing.add(Line(x, cy, x + dx, cy + dy, strokeColor=colors.HexColor("#D58523"), strokeWidth=1.5))
        tip_x, tip_y = x + dx, cy + dy
        if dx:
            back_x = tip_x - (5 if dx > 0 else -5)
            arrow = [tip_x, tip_y, back_x, tip_y + 3, back_x, tip_y - 3]
        else:
            arrow = [tip_x, tip_y, tip_x - 3, tip_y - 5, tip_x + 3, tip_y - 5]
        drawing.add(Polygon(arrow, fillColor=colors.HexColor("#D58523"), strokeColor=None))
        drawing.add(Circle(x, cy, 3, fillColor=colors.white, strokeColor=colors.HexColor("#D58523")))
        drawing.add(String(x, 27 if n % 2 == 0 else 118, str(name)[:22], fontName=font,
                           fontSize=8, textAnchor="middle", fillColor=colors.HexColor("#7E5E31")))
    note = "軸方向の概略図 ／ SCOM の値を使用"
    if not shapes:
        note += " ／ 表示可能な形状なし"
    drawing.add(String(10, 10, note, fontName=font, fontSize=7,
                       fillColor=colors.HexColor("#67788B")))
    return drawing
