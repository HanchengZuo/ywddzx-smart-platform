"""Build an editable non-oil report from the approved PowerPoint template.

The final PPTX is the source of truth. Browser preview images are rendered from
that PPTX so the preview and downloaded deck share one layout and pagination.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import uuid
from copy import deepcopy
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import ChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import (
    XL_CHART_TYPE,
    XL_DATA_LABEL_POSITION,
    XL_LEGEND_POSITION,
)
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt


TEMPLATE_FILE = (
    Path(__file__).resolve().parent
    / "assets"
    / "non_oil_report_template"
    / "non_oil_report_template.pptx"
)
CANVAS_SIZE = (2560, 1440)
UNIT_ORDER = [
    "浦东", "闵普徐", "松金", "嘉青", "南汇", "宝静", "奉贤", "崇明",
    "中油奉贤", "中油同盛", "中油康桥", "中油农工商", "中油上海", "中油港汇",
    "中石油上港", "中油浦东", "中油华鑫", "中油中燃",
]
CHART_COLORS = [
    "4472C4", "ED7D31", "FFC000", "70AD47", "00B0F0",
    "A5A5A5", "5B9BD5", "264478", "C55A11",
]
BLUE = RGBColor(47, 117, 181)
GRID = RGBColor(217, 225, 233)
FONT_SANS = "Noto Sans CJK SC"
FONT_SERIF = "Noto Serif CJK SC"


def _unit_name(value):
    text = str(value or "").strip()
    return text[:-2] if text.endswith("片区") else text


def _unit_sort_key(item):
    name = _unit_name(item.get("unit_name"))
    try:
        return UNIT_ORDER.index(name), name
    except ValueError:
        return len(UNIT_ORDER), name


def _format_number(value, digits=0):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    return f"{number:.{digits}f}" if digits else str(int(round(number)))


def _shape_text(shape):
    if not getattr(shape, "has_text_frame", False):
        return ""
    return "\n".join(item.text for item in shape.text_frame.paragraphs).strip()


def _find_text_shape(slide, keyword):
    return next((shape for shape in slide.shapes if keyword in _shape_text(shape)), None)


def _capture_run_style(text_frame):
    paragraph = next(
        (item for item in text_frame.paragraphs if item.runs),
        text_frame.paragraphs[0],
    )
    run = paragraph.runs[0] if paragraph.runs else None
    font = run.font if run else None
    color = None
    if font is not None:
        try:
            color = font.color.rgb
        except (AttributeError, TypeError, ValueError):
            color = None
    return {
        "alignment": paragraph.alignment,
        "level": paragraph.level,
        "font_name": font.name if font else None,
        "font_size": font.size if font else None,
        "bold": font.bold if font else None,
        "italic": font.italic if font else None,
        "color": color,
    }


def _portable_font_name(source_name):
    value = str(source_name or "").lower()
    if any(keyword in value for keyword in ("仿宋", "小标宋", "宋体", "fangsong", "simsun")):
        return FONT_SERIF
    return FONT_SANS


def _set_run_typeface(run, font_name=None):
    typeface = font_name or _portable_font_name(run.font.name)
    run.font.name = typeface
    run_properties = run._r.get_or_add_rPr()
    for tag_name in ("a:latin", "a:ea", "a:cs"):
        typeface_element = run_properties.find(qn(tag_name))
        if typeface_element is None:
            typeface_element = OxmlElement(tag_name)
            run_properties.append(typeface_element)
        typeface_element.set("typeface", typeface)


def _normalize_text_frame_fonts(text_frame):
    for paragraph in text_frame.paragraphs:
        for run in paragraph.runs:
            _set_run_typeface(run, _portable_font_name(run.font.name))


def _normalize_shape_fonts(shape):
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for child in shape.shapes:
            _normalize_shape_fonts(child)
    if getattr(shape, "has_text_frame", False):
        _normalize_text_frame_fonts(shape.text_frame)
    if getattr(shape, "has_table", False):
        for row in shape.table.rows:
            for cell in row.cells:
                _normalize_text_frame_fonts(cell.text_frame)
    if getattr(shape, "has_chart", False):
        chart = shape.chart
        if chart.has_title:
            _normalize_text_frame_fonts(chart.chart_title.text_frame)
        try:
            chart.category_axis.tick_labels.font.name = FONT_SANS
            chart.value_axis.tick_labels.font.name = FONT_SANS
        except (AttributeError, ValueError):
            pass
        if chart.has_legend:
            chart.legend.font.name = FONT_SANS
        for plot in chart.plots:
            if getattr(plot, "has_data_labels", False):
                plot.data_labels.font.name = FONT_SANS


def _normalize_presentation_fonts(prs):
    for slide in prs.slides:
        for shape in slide.shapes:
            _normalize_shape_fonts(shape)


def _set_text_frame(text_frame, value, style=None, font_size=None, bold=None):
    style = style or _capture_run_style(text_frame)
    lines = str(value or "").split("\n")
    text_frame.clear()
    text_frame.word_wrap = True
    for index, line in enumerate(lines):
        paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
        paragraph.text = line
        paragraph.alignment = style.get("alignment")
        paragraph.level = style.get("level") or 0
        if not paragraph.runs:
            continue
        run = paragraph.runs[0]
        if style.get("font_name"):
            _set_run_typeface(run, _portable_font_name(style["font_name"]))
        else:
            _set_run_typeface(run, FONT_SANS)
        effective_font_size = font_size or style.get("font_size")
        if isinstance(effective_font_size, (int, float)) and effective_font_size < 1000:
            effective_font_size = Pt(effective_font_size)
        if effective_font_size:
            run.font.size = effective_font_size
        run.font.bold = bold if bold is not None else style.get("bold")
        run.font.italic = style.get("italic")
        if style.get("color"):
            run.font.color.rgb = style["color"]


def _replace_text_runs(shape, replacements):
    if not getattr(shape, "has_text_frame", False):
        return
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            value = run.text
            for old, new in replacements.items():
                value = value.replace(old, new)
            run.text = value


def _remove_shape(shape):
    element = shape._element
    element.getparent().remove(element)


def _delete_slide(prs, slide):
    for slide_id in list(prs.slides._sldIdLst):
        if prs.part.related_part(slide_id.rId) is slide.part:
            prs.part.drop_rel(slide_id.rId)
            prs.slides._sldIdLst.remove(slide_id)
            return


def _move_slide(prs, slide, target_index):
    for slide_id in list(prs.slides._sldIdLst):
        if prs.part.related_part(slide_id.rId) is slide.part:
            prs.slides._sldIdLst.remove(slide_id)
            prs.slides._sldIdLst.insert(target_index, slide_id)
            return


def _set_cell_text(cell, value, font_size=None, bold=None):
    _set_text_frame(
        cell.text_frame,
        value,
        style=_capture_run_style(cell.text_frame),
        font_size=font_size,
        bold=bold,
    )
    cell.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    for paragraph in cell.text_frame.paragraphs:
        paragraph.alignment = PP_ALIGN.CENTER


def _resize_table_rows(table, target_row_count):
    table_element = table._tbl
    while len(table.rows) < target_row_count:
        table_element.append(deepcopy(table_element.tr_lst[-1]))
    while len(table.rows) > target_row_count:
        table_element.remove(table_element.tr_lst[-1])


def _fill_table(shape, headers, rows, font_size=11):
    target_height = shape.height
    table = shape.table
    _resize_table_rows(table, len(rows) + 1)
    for column_index, header in enumerate(headers):
        _set_cell_text(table.cell(0, column_index), header, font_size=font_size, bold=True)
    for row_index, values in enumerate(rows, 1):
        for column_index, value in enumerate(values):
            _set_cell_text(
                table.cell(row_index, column_index),
                value,
                font_size=font_size,
                bold=False,
            )
    if len(rows) > 14:
        for table_row in table.rows:
            for cell in table_row.cells:
                cell.margin_top = 0
                cell.margin_bottom = 0
    header_height = min(Inches(0.48), int(target_height * 0.16))
    table.rows[0].height = header_height
    row_height = max(Inches(0.12), int((target_height - header_height) / max(1, len(rows))))
    for row in list(table.rows)[1:]:
        row.height = row_height
    shape.height = target_height


def _visual_text_units(value):
    units = 0.0
    for character in str(value or ""):
        if character == "\n":
            continue
        units += 0.55 if ord(character) < 128 else 1.0
    return units


def _estimate_scope_text_height(lines, width_inches, font_size):
    usable_width_points = max(120, (width_inches - 0.2) * 72)
    characters_per_line = max(12, usable_width_points / max(font_size, 1))
    wrapped_lines = sum(
        max(
            1,
            int(
                (_visual_text_units(line) + characters_per_line - 1)
                // characters_per_line
            ),
        )
        for line in lines
    )
    return wrapped_lines * font_size * 1.22 / 72 + 0.12


def _set_scope_text(text_frame, period_text, scope_text, font_size):
    text_frame.clear()
    text_frame.word_wrap = True
    text_frame.margin_top = Inches(0.04)
    text_frame.margin_bottom = Inches(0.04)
    for index, (label, value) in enumerate(
        (("巡检期间：", period_text), ("巡检范围：", scope_text))
    ):
        paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
        paragraph.alignment = PP_ALIGN.LEFT
        paragraph.line_spacing = 1.15
        label_run = paragraph.add_run()
        label_run.text = label
        label_run.font.size = Pt(font_size)
        label_run.font.bold = True
        _set_run_typeface(label_run, FONT_SERIF)
        value_run = paragraph.add_run()
        value_run.text = str(value or "-")
        value_run.font.size = Pt(font_size)
        value_run.font.bold = False
        _set_run_typeface(value_run, FONT_SERIF)


def _set_chart_fonts(chart, category_size=9):
    try:
        chart.category_axis.tick_labels.font.size = Pt(category_size)
        chart.category_axis.tick_labels.font.name = FONT_SANS
    except (AttributeError, ValueError):
        pass
    try:
        chart.value_axis.tick_labels.font.size = Pt(9)
        chart.value_axis.tick_labels.font.name = FONT_SANS
        chart.value_axis.has_major_gridlines = True
        chart.value_axis.major_gridlines.format.line.color.rgb = GRID
    except (AttributeError, ValueError):
        pass
    if chart.has_legend:
        chart.legend.font.size = Pt(9)
        chart.legend.font.name = FONT_SANS


def _add_empty_chart_message(slide, box, title):
    text_box = slide.shapes.add_textbox(*box)
    _set_text_frame(
        text_box.text_frame,
        f"{title}\n当前范围暂无数据",
        font_size=Pt(18),
    )
    for paragraph in text_box.text_frame.paragraphs:
        paragraph.alignment = PP_ALIGN.CENTER


def _add_column_chart(slide, box, categories, series, title):
    categories = [str(item or "-") for item in categories]
    if not categories:
        _add_empty_chart_message(slide, box, title)
        return None
    chart_data = ChartData()
    chart_data.categories = categories
    for name, values, _color in series:
        chart_data.add_series(name, [float(value or 0) for value in values])
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        *box,
        chart_data,
    ).chart
    chart.chart_style = 10
    chart.has_title = True
    chart.chart_title.text_frame.text = title
    title_run = chart.chart_title.text_frame.paragraphs[0].runs[0]
    title_run.font.size = Pt(14)
    title_run.font.bold = True
    _set_run_typeface(title_run, FONT_SANS)
    chart.has_legend = len(series) > 1
    if chart.has_legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
    plot = chart.plots[0]
    plot.gap_width = 65 if len(categories) <= 8 else 35
    plot.has_data_labels = True
    plot.data_labels.show_value = True
    plot.data_labels.position = XL_DATA_LABEL_POSITION.OUTSIDE_END
    plot.data_labels.font.size = Pt(8)
    for index, chart_series in enumerate(chart.series):
        color = series[index][2] if index < len(series) else CHART_COLORS[index % len(CHART_COLORS)]
        chart_series.format.fill.solid()
        chart_series.format.fill.fore_color.rgb = RGBColor.from_string(color)
        chart_series.format.line.color.rgb = RGBColor.from_string(color)
    _set_chart_fonts(chart, category_size=8 if len(categories) > 10 else 9)
    return chart


def _add_pie_chart(slide, box, rows, title):
    rows = [item for item in rows or [] if float(item.get("count") or 0) > 0]
    if not rows:
        _add_empty_chart_message(slide, box, title)
        return None
    chart_data = ChartData()
    chart_data.categories = [str(item.get("name") or "-") for item in rows]
    chart_data.add_series("问题数量", [float(item.get("count") or 0) for item in rows])
    chart = slide.shapes.add_chart(XL_CHART_TYPE.PIE, *box, chart_data).chart
    chart.chart_style = 10
    chart.has_title = True
    chart.chart_title.text_frame.text = title
    title_run = chart.chart_title.text_frame.paragraphs[0].runs[0]
    title_run.font.size = Pt(14)
    title_run.font.bold = True
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.RIGHT
    chart.legend.include_in_layout = False
    chart.legend.font.size = Pt(8)
    chart.legend.font.name = FONT_SANS
    plot = chart.plots[0]
    plot.has_data_labels = True
    plot.data_labels.show_percentage = True
    plot.data_labels.position = XL_DATA_LABEL_POSITION.BEST_FIT
    plot.data_labels.font.size = Pt(8)
    for index, point in enumerate(chart.series[0].points):
        color = CHART_COLORS[index % len(CHART_COLORS)]
        point.format.fill.solid()
        point.format.fill.fore_color.rgb = RGBColor.from_string(color)
    return chart


def _remove_large_visuals(slide):
    for shape in list(slide.shapes):
        if shape.shape_type == MSO_SHAPE_TYPE.CHART:
            _remove_shape(shape)
        elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE and shape.height > Inches(0.3):
            _remove_shape(shape)


def _edit_cover(slide, report):
    month_number = int(str(report.get("month") or "2000-01").split("-")[1])
    title_shape = _find_text_shape(slide, "盛大业务督导中心")
    if title_shape:
        _set_text_frame(
            title_shape.text_frame,
            f"盛大业务督导中心\n非油业务{month_number}月巡检报告",
            style=_capture_run_style(title_shape.text_frame),
        )
    name_shape = _find_text_shape(slide, "王昕怡")
    if name_shape:
        _set_text_frame(
            name_shape.text_frame,
            "XXX    XXX    XXX",
            style=_capture_run_style(name_shape.text_frame),
        )


def _edit_rectification_slide(slide, report):
    previous = report.get("previous_month_rectification") or {}
    narrative_shape = _find_text_shape(slide, "各片区整改情况")
    if narrative_shape:
        _set_text_frame(
            narrative_shape.text_frame,
            previous.get("narrative") or "当前范围暂无上期整改数据。",
        )
    _remove_large_visuals(slide)
    units = sorted(previous.get("units") or [], key=_unit_sort_key)
    _add_column_chart(
        slide,
        (Inches(1.25), Inches(2.08), Inches(10.85), Inches(4.55)),
        [_unit_name(item.get("unit_name")) for item in units],
        [
            ("全部问题", [item.get("total_count") for item in units], "4472C4"),
            ("待验收", [item.get("pending_acceptance_count") for item in units], "ED7D31"),
            ("待整改", [item.get("pending_rectification_count") for item in units], "70AD47"),
        ],
        "各片区待验收与待整改问题数量分布",
    )


def _edit_scope_slide(slide, report):
    title_id = slide.shapes.title.shape_id if slide.shapes.title else None
    text_shape = next(
        (
            shape for shape in slide.shapes
            if getattr(shape, "has_text_frame", False) and shape.shape_id != title_id
        ),
        None,
    )
    table_shape = next(shape for shape in slide.shapes if getattr(shape, "has_table", False))
    units = sorted(report.get("units") or [], key=_unit_sort_key)
    rows = [
        [
            str(index),
            _unit_name(item.get("unit_name")),
            str(item.get("station_count") or 0),
            "、".join(item.get("station_names") or []),
        ]
        for index, item in enumerate(units, 1)
    ]
    if text_shape:
        period_text = report.get("period_text") or "-"
        scope_text = report.get("scope_text") or "-"
        content_bottom = Inches(7.28)
        gap = Inches(0.1)
        minimum_table_height = Inches(
            min(4.85, max(3.35, 0.48 + max(1, len(rows)) * 0.2))
        )
        maximum_text_height = max(
            Inches(0.72),
            content_bottom - text_shape.top - gap - minimum_table_height,
        )
        selected_font_size = 15
        estimated_text_height = maximum_text_height / 914400
        for candidate_size in (20, 19, 18, 17, 16, 15):
            candidate_height = _estimate_scope_text_height(
                (period_text, scope_text),
                text_shape.width / 914400,
                candidate_size,
            )
            if Inches(candidate_height) <= maximum_text_height:
                selected_font_size = candidate_size
                estimated_text_height = candidate_height
                break
        text_shape.height = min(
            maximum_text_height,
            Inches(max(0.72, estimated_text_height)),
        )
        _set_scope_text(
            text_shape.text_frame,
            period_text,
            scope_text,
            selected_font_size,
        )
        table_shape.top = text_shape.top + text_shape.height + gap
        table_shape.height = max(Inches(3.2), content_bottom - table_shape.top)
    table_font_size = (
        7 if len(rows) > 16
        else 8 if len(rows) > 13
        else 9 if len(rows) > 10
        else 10
    )
    _fill_table(
        table_shape,
        ["序号", "所属片区", "站点数量", "站点"],
        rows,
        font_size=table_font_size,
    )


def _edit_unit_table_slide(slide, report):
    summary = report.get("summary") or {}
    narrative_shape = _find_text_shape(slide, "检查共发现")
    if narrative_shape:
        _set_text_frame(
            narrative_shape.text_frame,
            f"检查共发现{summary.get('total_issue_count') or 0}项问题，其中，各区问题数量如下：",
        )
    table_shape = next(shape for shape in slide.shapes if getattr(shape, "has_table", False))
    units = sorted(report.get("units") or [], key=_unit_sort_key)
    rows = []
    for index, item in enumerate(units, 1):
        station_text = "、".join(
            f"{row.get('station_name')}（{row.get('issue_count') or 0}）"
            for row in item.get("station_issue_rows") or []
        )
        rows.append(
            [
                str(index),
                _unit_name(item.get("unit_name")),
                str(item.get("station_count") or 0),
                str(item.get("issue_count") or 0),
                _format_number(item.get("average_issue_count"), 1),
                station_text,
            ]
        )
    _fill_table(
        table_shape,
        ["序号", "所属片区", "站点数量", "片区问题总项", "站平均问题数", "站点问题数"],
        rows,
        font_size=8 if len(rows) > 14 else (9 if len(rows) > 12 else 10),
    )


def _edit_overview_slide(slide, report):
    _remove_large_visuals(slide)
    title_id = slide.shapes.title.shape_id if slide.shapes.title else None
    summary_shape = next(
        (
            shape for shape in slide.shapes
            if getattr(shape, "has_text_frame", False)
            and shape.shape_id != title_id
            and shape.top > Inches(4.8)
        ),
        None,
    )
    if summary_shape:
        _set_text_frame(
            summary_shape.text_frame,
            report.get("unit_overview_text") or report.get("issue_overview_text") or "-",
        )
    units = sorted(report.get("units") or [], key=_unit_sort_key)
    _add_column_chart(
        slide,
        (Inches(0.25), Inches(1.05), Inches(7.55), Inches(4.15)),
        [_unit_name(item.get("unit_name")) for item in units],
        [
            ("站平均问题数", [item.get("average_issue_count") for item in units], "5B9BD5"),
            ("检查站点数", [item.get("station_count") for item in units], "C0504D"),
            ("问题总数", [item.get("issue_count") for item in units], "92D050"),
        ],
        "各片区非油问题数量汇总",
    )
    _add_pie_chart(
        slide,
        (Inches(7.85), Inches(1.08), Inches(5.15), Inches(4.05)),
        report.get("category_distribution") or [],
        "非油检查问题分布",
    )


def _copy_text_shape(source_shape, destination_slide):
    element = deepcopy(source_shape._element)
    destination_slide.shapes._spTree.insert_element_before(element, "p:extLst")
    return destination_slide.shapes[-1]


def _add_unit_slide(prs, source_slide, unit):
    slide = prs.slides.add_slide(source_slide.slide_layout)
    title_shape = slide.shapes.title
    title_style = _capture_run_style(source_slide.shapes.title.text_frame)
    unit_label = _unit_name(unit.get("unit_name"))
    if unit.get("unit_type") == "region":
        unit_label += "片区"
    if title_shape:
        _set_text_frame(
            title_shape.text_frame,
            f"二、片区问题汇总——{unit_label}",
            style=title_style,
        )
    source_summary = _find_text_shape(source_slide, "涉及站点数")
    if source_summary is None:
        raise ValueError("非油报告片区模板缺少汇总文本框。")
    summary_shape = _copy_text_shape(source_summary, slide)
    station_rows = unit.get("station_issue_rows") or []
    station_names = "、".join(item.get("station_name") or "" for item in station_rows)
    top_category = next(
        (item.get("name") for item in unit.get("category_distribution") or [] if item.get("count")),
        "非油业务管理",
    )
    summary = (
        f"涉及站点数：{unit.get('station_count') or 0}座（{station_names}）\n"
        f"问题总计：{unit.get('issue_count') or 0}项（占本次全盘通报问题总量的"
        f"{float(unit.get('percentage') or 0):.1f}%，主要集中于{top_category}）\n"
        f"站平均问题数：{float(unit.get('average_issue_count') or 0):.1f}项/站"
    )
    _set_text_frame(summary_shape.text_frame, summary)
    summary_shape.left = Inches(0.75)
    summary_shape.top = Inches(5.35)
    summary_shape.width = Inches(11.9)
    summary_shape.height = Inches(1.75)

    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0,
        Inches(5.22),
        prs.slide_width,
        Inches(0.06),
    )
    line.fill.solid()
    line.fill.fore_color.rgb = BLUE
    line.line.fill.background()

    categories = [item.get("station_name") or "-" for item in station_rows]
    category_names = [
        item.get("name")
        for item in unit.get("category_distribution") or []
        if item.get("count")
    ]
    series = [
        (
            category_name,
            [
                (station.get("category_counts") or {}).get(category_name, 0)
                for station in station_rows
            ],
            CHART_COLORS[index % len(CHART_COLORS)],
        )
        for index, category_name in enumerate(category_names)
    ]
    if not series:
        series = [
            (
                "问题数量",
                [station.get("issue_count") or 0 for station in station_rows],
                "4472C4",
            )
        ]
    _add_column_chart(
        slide,
        (Inches(0.45), Inches(1.15), Inches(7.0), Inches(3.85)),
        categories,
        series,
        f"{_unit_name(unit.get('unit_name'))}各站问题数量",
    )
    _add_pie_chart(
        slide,
        (Inches(7.55), Inches(1.15), Inches(5.25), Inches(3.85)),
        unit.get("category_distribution") or [],
        f"{_unit_name(unit.get('unit_name'))}问题分布",
    )
    return slide


def _edit_analysis_overview(slide, report):
    summary = report.get("summary") or {}
    overview_shape = _find_text_shape(slide, "随着非油业务")
    if not overview_shape:
        return
    original = _shape_text(overview_shape)
    updated = re.sub(
        r"随着非油业务.*?使用的方法包括：",
        (
            f"本期共统计{summary.get('total_issue_count') or 0}项审核通过问题，"
            f"覆盖{summary.get('category_count') or 0}个非油检查领域。"
            "本次分析旨在识别便利店运营流程中的潜在风险，使用的方法包括："
        ),
        original,
        count=1,
        flags=re.S,
    )
    _set_text_frame(overview_shape.text_frame, updated)


def _render_presentation_preview(pptx_path, output_dir):
    soffice = shutil.which("libreoffice") or shutil.which("soffice")
    pdftoppm = shutil.which("pdftoppm")
    if not soffice or not pdftoppm:
        raise RuntimeError("服务器缺少 LibreOffice 或 Poppler，无法生成PPT同源预览。")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("slide-*.jpg"):
        stale.unlink()

    with tempfile.TemporaryDirectory(prefix="non-oil-ppt-render-") as temp_dir:
        temp_path = Path(temp_dir)
        profile_uri = (temp_path / f"lo-profile-{uuid.uuid4().hex}").as_uri()
        subprocess.run(
            [
                soffice,
                "--headless",
                f"-env:UserInstallation={profile_uri}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(temp_path),
                str(pptx_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        pdf_path = temp_path / f"{Path(pptx_path).stem}.pdf"
        if not pdf_path.is_file():
            raise RuntimeError("PPT预览转换失败，未生成PDF中间文件。")
        prefix = temp_path / "page"
        subprocess.run(
            [
                pdftoppm,
                "-jpeg",
                "-scale-to-x",
                str(CANVAS_SIZE[0]),
                "-scale-to-y",
                str(CANVAS_SIZE[1]),
                "-jpegopt",
                "quality=95",
                str(pdf_path),
                str(prefix),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        rendered_pages = sorted(
            temp_path.glob("page-*.jpg"),
            key=lambda path: int(re.search(r"(\d+)$", path.stem).group(1)),
        )
        if not rendered_pages:
            raise RuntimeError("PPT预览转换失败，未生成幻灯片图片。")
        slide_files = []
        for index, source in enumerate(rendered_pages, 1):
            destination = output_dir / f"slide-{index:02d}.jpg"
            shutil.copy2(source, destination)
            slide_files.append(str(destination))
        return slide_files


def build_non_oil_template_presentation(report, output_dir, output_path):
    if not TEMPLATE_FILE.is_file():
        raise FileNotFoundError("非油检查报告PPT模板不存在。")
    output_dir = Path(output_dir)
    output_path = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prs = Presentation(TEMPLATE_FILE)
    if len(prs.slides) < 45:
        raise ValueError("非油检查报告PPT模板页数异常。")

    _edit_cover(prs.slides[0], report)
    _edit_rectification_slide(prs.slides[3], report)
    _edit_scope_slide(prs.slides[4], report)
    _edit_unit_table_slide(prs.slides[5], report)
    _edit_overview_slide(prs.slides[8], report)
    _edit_analysis_overview(prs.slides[21], report)

    source_unit_slide = prs.slides[9]
    old_unit_slides = [prs.slides[index] for index in range(9, 20)]
    units = sorted(report.get("units") or [], key=_unit_sort_key)
    new_unit_slides = [
        _add_unit_slide(prs, source_unit_slide, unit)
        for unit in units
    ]
    for slide in reversed(old_unit_slides):
        _delete_slide(prs, slide)
    for index, slide in enumerate(new_unit_slides):
        _move_slide(prs, slide, 9 + index)

    _normalize_presentation_fonts(prs)
    prs.save(output_path)
    slide_files = _render_presentation_preview(output_path, output_dir)
    return {
        "slide_count": len(slide_files),
        "slide_files": slide_files,
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
