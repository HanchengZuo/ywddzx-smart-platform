"""Render the non-oil report from the approved slide template.

The web preview and exported PowerPoint intentionally share the same rendered
slide images. This keeps the two outputs pixel-identical and prevents browser
CSS from drifting away from the approved presentation layout.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.util import Inches


CANVAS_SIZE = (1280, 720)
SLIDE_WIDTH = Inches(13.333333)
SLIDE_HEIGHT = Inches(7.5)
BLUE = "#2f75b5"
CYAN = "#5b9bd5"
RED = "#dc2626"
INK = "#111111"
MUTED = "#4b5563"
GRID = "#d1d5db"
LIGHT_BLUE = "#d9e7f5"
TEMPLATE_BG = "#f3f3f3"
TEMPLATE_RED = "#c00000"
TABLE_RED = "#c0504d"
TABLE_PINK = "#e6b8b7"
UNIT_ORDER = [
    "浦东", "闵普徐", "松金", "嘉青", "南汇", "宝静", "奉贤", "崇明",
    "中油奉贤", "中油同盛", "中油康桥", "中油农工商", "中油上海", "中油港汇",
    "中石油上港", "中油浦东", "中油华鑫", "中油中燃",
]
CHART_COLORS = [
    "#4472c4", "#ed7d31", "#ffc000", "#70ad47", "#00b0f0",
    "#a5a5a5", "#5b9bd5", "#264478", "#c55a11",
]


def _font_path():
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    return next((path for path in candidates if os.path.isfile(path)), None)


FONT_PATH = _font_path()


def _font(size, bold=False):
    if FONT_PATH:
        return ImageFont.truetype(FONT_PATH, size=max(8, int(size)), index=0)
    return ImageFont.load_default()


def _text_width(draw, text, font):
    return draw.textbbox((0, 0), str(text), font=font)[2]


def _wrap_text(draw, value, font, max_width):
    text = str(value or "").strip()
    if not text:
        return []
    lines = []
    current = ""
    for char in text:
        candidate = current + char
        if current and _text_width(draw, candidate, font) > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_wrapped(draw, text, box, size=24, fill=INK, bold=False, spacing=8, max_lines=None):
    x, y, width, height = box
    font = _font(size, bold=bold)
    lines = _wrap_text(draw, text, font, width)
    if max_lines:
        lines = lines[:max_lines]
    line_height = size + spacing
    while lines and len(lines) * line_height > height and size > 12:
        size -= 1
        font = _font(size, bold=bold)
        lines = _wrap_text(draw, text, font, width)
        if max_lines:
            lines = lines[:max_lines]
        line_height = size + spacing
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _clear_body(image, top=105, bottom=720):
    ImageDraw.Draw(image).rectangle((0, top, 1280, bottom), fill=TEMPLATE_BG)


def _draw_title(draw, title):
    draw.rectangle((122, 0, 1280, 104), fill=TEMPLATE_BG)
    draw.text((136, 38), title, font=_font(36, bold=True), fill=TEMPLATE_RED)


def _format_number(value, digits=0):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    return f"{number:.{digits}f}" if digits else str(int(round(number)))


def _unit_name(value):
    text = str(value or "").strip()
    return text[:-2] if text.endswith("片区") else text


def _unit_sort_key(item):
    name = _unit_name(item.get("unit_name"))
    try:
        return UNIT_ORDER.index(name), name
    except ValueError:
        return len(UNIT_ORDER), name


def _draw_grouped_bars(draw, box, rows, series, title=""):
    x, y, width, height = box
    if title:
        title_font = _font(19, bold=True)
        tw = _text_width(draw, title, title_font)
        draw.text((x + max(0, (width - tw) / 2), y), title, font=title_font, fill=INK)
        y += 34
        height -= 34
    rows = list(rows or [])
    if not rows:
        draw.text((x + 20, y + height / 2), "当前范围暂无数据", font=_font(19), fill=MUTED)
        return
    max_value = max([float(row.get(key) or 0) for row in rows for key, _label, _color in series] + [1])
    chart_left = x + 52
    chart_bottom = y + height - 45
    chart_top = y + 18
    chart_width = width - 66
    chart_height = chart_bottom - chart_top
    for step in range(5):
        gy = chart_bottom - chart_height * step / 4
        draw.line((chart_left, gy, chart_left + chart_width, gy), fill=GRID, width=1)
        label = _format_number(max_value * step / 4)
        draw.text((chart_left - 44, gy - 8), label, font=_font(12), fill=MUTED)
    group_width = chart_width / max(1, len(rows))
    bar_width = min(24, max(6, group_width / (len(series) + 1)))
    for row_index, row in enumerate(rows):
        center = chart_left + group_width * (row_index + 0.5)
        total_bars_width = bar_width * len(series)
        for series_index, (key, _label, color) in enumerate(series):
            value = float(row.get(key) or 0)
            bar_height = chart_height * value / max_value
            bx = center - total_bars_width / 2 + series_index * bar_width
            by = chart_bottom - bar_height
            draw.rectangle((bx, by, bx + bar_width - 2, chart_bottom), fill=color)
            if value:
                number = _format_number(value, 1 if not value.is_integer() else 0)
                font = _font(11)
                draw.text((bx + (bar_width - _text_width(draw, number, font)) / 2, by - 18), number, font=font, fill=INK)
        label = _unit_name(row.get("name") or row.get("unit_name") or row.get("station_name"))
        label = label[:7]
        font = _font(12)
        tw = _text_width(draw, label, font)
        draw.text((center - tw / 2, chart_bottom + 8), label, font=font, fill=INK)
    legend_slot = width / max(1, len(series))
    for index, (_key, label, color) in enumerate(series):
        legend_x = x + 12 + index * legend_slot
        draw.rectangle((legend_x, y, legend_x + 12, y + 12), fill=color)
        display_label = str(label or "")[:10]
        draw.text((legend_x + 17, y - 2), display_label, font=_font(11), fill=MUTED)


def _draw_pie(draw, box, rows, title=""):
    x, y, width, height = box
    if title:
        font = _font(19, bold=True)
        tw = _text_width(draw, title, font)
        draw.text((x + max(0, (width - tw) / 2), y), title, font=font, fill=INK)
        y += 32
        height -= 32
    rows = [row for row in rows or [] if float(row.get("count") or 0) > 0]
    total = sum(float(row.get("count") or 0) for row in rows)
    if not rows or total <= 0:
        draw.text((x + 20, y + height / 2), "当前范围暂无数据", font=_font(18), fill=MUTED)
        return
    diameter = min(height - 20, width * 0.52)
    pie_box = (x + 5, y + (height - diameter) / 2, x + 5 + diameter, y + (height + diameter) / 2)
    angle = -90
    legend_x = x + diameter + 32
    legend_y = y + 16
    for index, row in enumerate(rows):
        value = float(row.get("count") or 0)
        sweep = value / total * 360
        color = CHART_COLORS[index % len(CHART_COLORS)]
        draw.pieslice(pie_box, angle, angle + sweep, fill=color, outline="white", width=2)
        draw.rectangle((legend_x, legend_y, legend_x + 13, legend_y + 13), fill=color)
        label = f"{row.get('name')} {_format_number(value)}项"
        _draw_wrapped(draw, label, (legend_x + 20, legend_y - 2, width - diameter - 55, 34), size=12, max_lines=2)
        legend_y += 37
        angle += sweep


def _draw_table(
    draw,
    box,
    headers,
    rows,
    widths,
    font_size=17,
    header_height=40,
    header_fill=CYAN,
    row_fills=(LIGHT_BLUE, "#edf3f9"),
    header_text_fill="white",
):
    x, y, width, height = box
    widths = [width * ratio / sum(widths) for ratio in widths]
    row_count = max(1, len(rows))
    row_height = min(42, max(24, (height - header_height) / row_count))
    positions = [x]
    for item_width in widths:
        positions.append(positions[-1] + item_width)
    draw.rectangle((x, y, x + width, y + header_height), fill=header_fill, outline=INK)
    for col, header in enumerate(headers):
        cell_x = positions[col]
        cell_width = widths[col]
        lines = _wrap_text(draw, header, _font(font_size, bold=True), cell_width - 10)[:2]
        ty = y + (header_height - len(lines) * (font_size + 2)) / 2
        for line in lines:
            tw = _text_width(draw, line, _font(font_size, bold=True))
            draw.text((cell_x + (cell_width - tw) / 2, ty), line, font=_font(font_size, bold=True), fill=header_text_fill)
            ty += font_size + 2
        draw.line((cell_x, y, cell_x, y + header_height + row_height * row_count), fill="white", width=1)
    draw.line((x + width, y, x + width, y + header_height + row_height * row_count), fill="white", width=1)
    for row_index, row in enumerate(rows):
        top = y + header_height + row_index * row_height
        fill = row_fills[row_index % len(row_fills)]
        draw.rectangle((x, top, x + width, top + row_height), fill=fill, outline=INK)
        for col, value in enumerate(row):
            cell_x = positions[col]
            cell_width = widths[col]
            font = _font(max(11, min(font_size, int(row_height * 0.48))))
            lines = _wrap_text(draw, value, font, cell_width - 8)[:2]
            ty = top + (row_height - len(lines) * (font.size + 1)) / 2
            for line in lines:
                tw = _text_width(draw, line, font)
                draw.text((cell_x + max(4, (cell_width - tw) / 2), ty), line, font=font, fill=INK)
                ty += font.size + 1
            draw.line((cell_x, top, cell_x, top + row_height), fill="white", width=1)
    return y + header_height + row_height * row_count


def _base_slide(template_dir, number):
    image = Image.open(Path(template_dir) / f"slide-{number:02d}.jpg").convert("RGB")
    if image.size != CANVAS_SIZE:
        image = image.resize(CANVAS_SIZE, Image.Resampling.LANCZOS)
    return image


def _render_cover(template_dir, report):
    image = _base_slide(template_dir, 1)
    draw = ImageDraw.Draw(image)
    draw.rectangle((120, 96, 1160, 520), fill=TEMPLATE_BG)
    month_number = int(str(report.get("month") or "2000-01").split("-")[1])
    heading = "盛大业务督导中心"
    heading_font = _font(39, bold=True)
    draw.text(((1280 - _text_width(draw, heading, heading_font)) / 2, 125), heading, font=heading_font, fill=TEMPLATE_RED)
    title = f"非油业务 {month_number} 月巡检报告"
    title_font = _font(59, bold=True)
    draw.text(((1280 - _text_width(draw, title, title_font)) / 2, 220), title, font=title_font, fill=TEMPLATE_RED)
    names = "XXX    XXX    XXX"
    font = _font(27)
    draw.text(((1280 - _text_width(draw, names, font)) / 2, 435), names, font=font, fill=MUTED)
    return image


def _render_rectification(template_dir, report):
    image = _base_slide(template_dir, 4)
    _clear_body(image)
    draw = ImageDraw.Draw(image)
    _draw_title(draw, "一、总体情况概述")
    previous = report.get("previous_month_rectification") or {}
    narrative = previous.get("narrative") or "当前范围暂无上期整改数据。"
    _draw_wrapped(draw, narrative, (95, 98, 1090, 82), size=25, bold=True, spacing=7, max_lines=2)
    _draw_grouped_bars(
        draw,
        (105, 205, 1070, 430),
        previous.get("units") or [],
        [
            ("total_count", "全部问题", "#4472c4"),
            ("pending_acceptance_count", "待验收", "#ed7d31"),
            ("pending_rectification_count", "待整改", "#70ad47"),
        ],
        "各单位整改问题分布",
    )
    return image


def _render_scope(template_dir, report):
    image = _base_slide(template_dir, 5)
    _clear_body(image)
    draw = ImageDraw.Draw(image)
    _draw_title(draw, "一、总体情况概述")
    _draw_wrapped(draw, report.get("period_text"), (85, 118, 1110, 35), size=22, bold=True, max_lines=1)
    _draw_wrapped(draw, report.get("scope_text"), (85, 158, 1110, 72), size=20, spacing=5, max_lines=2)
    units = sorted(report.get("units") or [], key=_unit_sort_key)
    rows = [
        [index, _unit_name(item.get("unit_name")), item.get("station_count") or 0, "、".join(item.get("station_names") or [])]
        for index, item in enumerate(units, 1)
    ]
    _draw_table(
        draw,
        (105, 240, 1070, 420),
        ["序号", "所属片区", "站点数量", "站点"],
        rows,
        [0.08, 0.18, 0.14, 0.60],
        font_size=16,
        header_fill=TABLE_RED,
        row_fills=(TABLE_PINK,),
        header_text_fill=INK,
    )
    return image


def _render_unit_table(template_dir, report):
    image = _base_slide(template_dir, 6)
    _clear_body(image)
    draw = ImageDraw.Draw(image)
    _draw_title(draw, "一、总体情况概述")
    summary = report.get("summary") or {}
    draw.text((95, 120), f"检查共发现{summary.get('total_issue_count') or 0}项问题，其中，各区问题数量如下：", font=_font(22, bold=True), fill=INK)
    units = sorted(report.get("units") or [], key=_unit_sort_key)
    rows = []
    for index, item in enumerate(units, 1):
        stations = item.get("station_issue_rows") or []
        station_text = "、".join(f"{row.get('station_name')}（{row.get('issue_count') or 0}）" for row in stations)
        rows.append([
            index,
            _unit_name(item.get("unit_name")),
            item.get("station_count") or 0,
            item.get("issue_count") or 0,
            _format_number(item.get("average_issue_count"), 1),
            station_text,
        ])
    _draw_table(
        draw,
        (70, 155, 1140, 505),
        ["序号", "所属片区", "站点数量", "片区问题总项", "站平均问题数", "站点问题数"],
        rows,
        [0.06, 0.14, 0.10, 0.12, 0.12, 0.46],
        font_size=14,
        header_fill=TABLE_RED,
        row_fills=(TABLE_PINK,),
        header_text_fill=INK,
    )
    return image


def _render_overview(template_dir, report):
    image = _base_slide(template_dir, 9)
    _clear_body(image)
    draw = ImageDraw.Draw(image)
    _draw_title(draw, "二、片区问题汇总——总体概况")
    units = sorted(report.get("units") or [], key=_unit_sort_key)
    _draw_grouped_bars(
        draw,
        (45, 105, 735, 410),
        units,
        [
            ("average_issue_count", "站平均问题数", "#5b9bd5"),
            ("station_count", "检查站点数", TABLE_RED),
            ("issue_count", "问题总数", "#92d050"),
        ],
        "各片区非油问题数量汇总",
    )
    _draw_pie(draw, (790, 110, 445, 390), report.get("category_distribution") or [], "非油检查问题分布")
    _draw_wrapped(draw, report.get("unit_overview_text") or report.get("issue_overview_text"), (75, 545, 1130, 125), size=20, bold=True, spacing=7, max_lines=4)
    return image


def _render_unit_slide(template_dir, report, unit):
    image = _base_slide(template_dir, 10)
    _clear_body(image)
    draw = ImageDraw.Draw(image)
    unit_name = _unit_name(unit.get("unit_name"))
    suffix = "片区" if unit.get("unit_type") == "region" and not unit_name.endswith("片区") else ""
    _draw_title(draw, f"二、片区问题汇总——{unit_name}{suffix}")
    stations = unit.get("station_issue_rows") or []
    category_rows = (unit.get("category_distribution") or [])[:4]
    category_series = [
        (item.get("name"), item.get("name"), CHART_COLORS[index % len(CHART_COLORS)])
        for index, item in enumerate(category_rows)
    ]
    station_chart_rows = []
    for item in stations:
        station_chart_rows.append({
            "name": item.get("station_name"),
            "issue_count": item.get("issue_count") or 0,
            **(item.get("category_counts") or {}),
        })
    _draw_grouped_bars(
        draw,
        (45, 105, 735, 400),
        station_chart_rows,
        category_series or [("issue_count", "问题数量", "#4472c4")],
        f"{unit_name}各站问题数量",
    )
    _draw_pie(draw, (790, 110, 445, 380), unit.get("category_distribution") or [], f"{unit_name}问题分布")
    station_names = "、".join(item.get("station_name") or "" for item in stations)
    top_category = next((item.get("name") for item in unit.get("category_distribution") or [] if item.get("count")), "非油业务管理")
    summary = (
        f"涉及站点数：{unit.get('station_count') or 0}座（{station_names}）\n"
        f"问题总计：{unit.get('issue_count') or 0}项（占本次全盘通报问题总量的"
        f"{_format_number(unit.get('percentage'), 1)}%，主要集中于{top_category}）\n"
        f"站平均问题数：{_format_number(unit.get('average_issue_count'), 1)}项/站"
    )
    _draw_wrapped(draw, summary, (85, 535, 1110, 145), size=22, bold=True, spacing=8, max_lines=5)
    return image


def _render_analysis_overview(template_dir, report):
    image = _base_slide(template_dir, 22)
    _clear_body(image)
    draw = ImageDraw.Draw(image)
    _draw_title(draw, "三、重点问题分析")
    draw.text((90, 118), "1. 检查总体情况", font=_font(27, bold=True), fill=INK)
    summary = report.get("summary") or {}
    metrics = [
        (summary.get("total_issue_count") or 0, "问题总数", "#f5b400"),
        (summary.get("category_count") or 0, "问题覆盖领域", "#00b050"),
        (report.get("key_issue_count") or 0, "重点问题数", "#ef4444"),
        (_format_number(report.get("key_issue_percentage"), 0) + "%", "重点问题占比", "#123579"),
    ]
    for index, (value, label, color) in enumerate(metrics):
        left = 85 + index * 290
        draw.rounded_rectangle((left, 185, left + 255, 300), radius=16, fill="#fbfbfb", outline="#e5e7eb")
        draw.rectangle((left, 185, left + 7, 300), fill=color)
        text = str(value)
        font = _font(48, bold=True)
        draw.text((left + (255 - _text_width(draw, text, font)) / 2, 198), text, font=font, fill=color)
        label_font = _font(20, bold=True)
        draw.text((left + (255 - _text_width(draw, label, label_font)) / 2, 258), label, font=label_font, fill=INK)
    draw.text((90, 350), "2. 分析方法", font=_font(27, bold=True), fill=INK)
    method_text = (
        "随着非油业务在站点利润结构中的占比提升，便利店的运营效率与合规成为管理重点。"
        "本次分析通过定量评估、关联分析、风险识别和归因优化，识别高频问题领域，"
        "建立重点问题与检查项目的映射关系，并形成后续改善依据。"
    )
    _draw_wrapped(draw, method_text, (105, 405, 1070, 190), size=24, spacing=11, max_lines=6)
    return image


def _save_slide(image, output_dir, number):
    path = Path(output_dir) / f"slide-{number:02d}.jpg"
    image.save(path, "JPEG", quality=92, optimize=True)
    return str(path)


def build_non_oil_template_presentation(report, output_dir, output_path):
    template_dir = Path(__file__).resolve().parent / "assets" / "non_oil_report_template"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    units = sorted(report.get("units") or [], key=_unit_sort_key)
    rendered = []
    rendered.append(_save_slide(_render_cover(template_dir, report), output_dir, len(rendered) + 1))
    for template_number in (2, 3):
        rendered.append(_save_slide(_base_slide(template_dir, template_number), output_dir, len(rendered) + 1))
    rendered.append(_save_slide(_render_rectification(template_dir, report), output_dir, len(rendered) + 1))
    rendered.append(_save_slide(_render_scope(template_dir, report), output_dir, len(rendered) + 1))
    rendered.append(_save_slide(_render_unit_table(template_dir, report), output_dir, len(rendered) + 1))
    for template_number in (7, 8):
        rendered.append(_save_slide(_base_slide(template_dir, template_number), output_dir, len(rendered) + 1))
    rendered.append(_save_slide(_render_overview(template_dir, report), output_dir, len(rendered) + 1))
    for unit in units:
        rendered.append(_save_slide(_render_unit_slide(template_dir, report, unit), output_dir, len(rendered) + 1))
    rendered.append(_save_slide(_base_slide(template_dir, 21), output_dir, len(rendered) + 1))
    rendered.append(_save_slide(_render_analysis_overview(template_dir, report), output_dir, len(rendered) + 1))
    for template_number in range(23, 46):
        rendered.append(_save_slide(_base_slide(template_dir, template_number), output_dir, len(rendered) + 1))

    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT
    blank_layout = prs.slide_layouts[6]
    for slide_path in rendered:
        slide = prs.slides.add_slide(blank_layout)
        slide.shapes.add_picture(slide_path, 0, 0, width=SLIDE_WIDTH, height=SLIDE_HEIGHT)
    if prs.slides and len(prs.slides) > len(rendered):
        slide_id = prs.slides._sldIdLst[0]
        prs.part.drop_rel(slide_id.rId)
        del prs.slides._sldIdLst[0]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)
    return {
        "slide_count": len(rendered),
        "slide_files": rendered,
        "ppt_path": str(output_path),
    }


def copy_existing_non_oil_presentation(report, destination, storage_root=None):
    presentation = report.get("presentation") or {}
    source = str(presentation.get("ppt_path") or "").strip()
    if source and not os.path.isabs(source) and storage_root:
        source = os.path.join(storage_root, source)
    if not source or not os.path.isfile(source):
        return None
    os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
    shutil.copy2(source, destination)
    return {"slide_count": int(presentation.get("slide_count") or 0)}
