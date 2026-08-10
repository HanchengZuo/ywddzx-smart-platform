"""Build editable PowerPoint files from saved inspection-report snapshots."""

from __future__ import annotations

import base64
import os
import re
from io import BytesIO
from typing import Iterable, Sequence

from PIL import Image
from pptx import Presentation
from pptx.chart.data import ChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)
FONT_FAMILY = "Microsoft YaHei"

INK = RGBColor(15, 23, 42)
SLATE = RGBColor(71, 85, 105)
MUTED = RGBColor(100, 116, 139)
LINE = RGBColor(226, 232, 240)
PAPER = RGBColor(248, 250, 252)
WHITE = RGBColor(255, 255, 255)
BLUE = RGBColor(14, 116, 144)
SKY = RGBColor(14, 165, 233)
TEAL = RGBColor(13, 148, 136)
AMBER = RGBColor(217, 119, 6)
RED = RGBColor(220, 38, 38)
CHART_COLORS = [
    RGBColor(14, 116, 144),
    RGBColor(20, 184, 166),
    RGBColor(245, 158, 11),
    RGBColor(59, 130, 246),
    RGBColor(239, 68, 68),
    RGBColor(100, 116, 139),
]


def _text(value, fallback="-"):
    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    return normalized or fallback


def _short(value, limit=120):
    value = _text(value)
    return value if len(value) <= limit else f"{value[: max(1, limit - 1)]}…"


def _chunks(values: Sequence, size: int):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _as_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _format_metric(value):
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.1f}"
    return str(_as_int(value))


class InspectionReportPresentation:
    def __init__(self, report_type, report, storage_root, include_photos=True):
        self.report_type = str(report_type or "").strip()
        self.report = report if isinstance(report, dict) else {}
        self.storage_root = os.path.abspath(storage_root)
        self.include_photos = bool(include_photos)
        self.prs = Presentation()
        self.prs.slide_width = SLIDE_WIDTH
        self.prs.slide_height = SLIDE_HEIGHT
        self.page_number = 0

    def build(self, output_path):
        self._add_cover()
        self._add_scope_overview()
        builders = {
            "quality_measurement": self._build_quality_measurement,
            "safety_quality": self._build_safety_quality,
            "finance": self._build_finance,
            "on_site_service": self._build_on_site_service,
            "equipment_facilities": self._build_equipment_facilities,
        }
        builder = builders.get(self.report_type)
        if not builder:
            raise ValueError("当前报告类型暂不支持导出PPT。")
        builder()
        self._add_ending()
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        self.prs.save(output_path)
        return {"slide_count": len(self.prs.slides)}

    def _blank_slide(self, background=PAPER, footer=True):
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        background_fill = slide.background.fill
        background_fill.solid()
        background_fill.fore_color.rgb = background
        if footer:
            self.page_number += 1
            self._add_footer(slide)
        return slide

    def _add_footer(self, slide):
        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0.55),
            Inches(7.1),
            Inches(12.23),
            Inches(0.012),
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = LINE
        shape.line.fill.background()
        self._add_text(
            slide,
            f"业务督导中心  ·  {_text(self.report.get('title'), '巡检分析报告')}",
            0.62,
            7.14,
            10.8,
            0.2,
            size=8,
            color=MUTED,
        )
        self._add_text(
            slide,
            f"{self.page_number:02d}",
            11.75,
            7.11,
            0.9,
            0.25,
            size=9,
            bold=True,
            color=BLUE,
            align=PP_ALIGN.RIGHT,
        )

    def _add_text(
        self,
        slide,
        value,
        x,
        y,
        width,
        height,
        *,
        size=16,
        color=INK,
        bold=False,
        align=PP_ALIGN.LEFT,
        valign=MSO_ANCHOR.TOP,
        margin=0.04,
    ):
        box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(height))
        frame = box.text_frame
        frame.clear()
        frame.word_wrap = True
        frame.margin_left = Inches(margin)
        frame.margin_right = Inches(margin)
        frame.margin_top = Inches(margin)
        frame.margin_bottom = Inches(margin)
        frame.vertical_anchor = valign
        paragraph = frame.paragraphs[0]
        paragraph.text = str(value or "")
        paragraph.alignment = align
        paragraph.font.name = FONT_FAMILY
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = color
        return box

    def _add_rich_lines(self, slide, lines, x, y, width, height, size=14, bullet=False):
        box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(height))
        frame = box.text_frame
        frame.clear()
        frame.word_wrap = True
        frame.margin_left = Inches(0.08)
        frame.margin_right = Inches(0.08)
        frame.margin_top = Inches(0.06)
        frame.margin_bottom = Inches(0.06)
        for index, line in enumerate(lines):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.text = _text(line, "")
            paragraph.font.name = FONT_FAMILY
            paragraph.font.size = Pt(size)
            paragraph.font.color.rgb = SLATE
            paragraph.space_after = Pt(7)
            if bullet:
                paragraph.text = f"• {paragraph.text}"
        return box

    def _add_title(self, slide, title, kicker="REPORT", subtitle="", ai=False):
        accent = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.6),
            Inches(0.55),
            Inches(0.11),
            Inches(0.76),
        )
        accent.fill.solid()
        accent.fill.fore_color.rgb = TEAL
        accent.line.fill.background()
        self._add_text(slide, kicker.upper(), 0.86, 0.52, 5.8, 0.24, size=9, color=TEAL, bold=True)
        self._add_text(slide, title, 0.83, 0.76, 10.8, 0.62, size=24, bold=True)
        if subtitle:
            self._add_text(slide, subtitle, 0.85, 1.35, 11.6, 0.38, size=10, color=MUTED)
        if ai:
            self._add_ai_badge(slide)

    def _add_ai_badge(self, slide, label="AI生成内容"):
        badge = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(11.25),
            Inches(0.6),
            Inches(1.35),
            Inches(0.38),
        )
        badge.fill.solid()
        badge.fill.fore_color.rgb = RGBColor(224, 242, 254)
        badge.line.color.rgb = RGBColor(125, 211, 252)
        self._set_shape_text(badge, label, 9, BLUE, True)

    def _set_shape_text(self, shape, value, size, color=INK, bold=False, align=PP_ALIGN.CENTER):
        frame = shape.text_frame
        frame.clear()
        frame.word_wrap = True
        frame.margin_left = Inches(0.05)
        frame.margin_right = Inches(0.05)
        frame.margin_top = Inches(0.02)
        frame.margin_bottom = Inches(0.02)
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        paragraph = frame.paragraphs[0]
        paragraph.text = str(value or "")
        paragraph.alignment = align
        paragraph.font.name = FONT_FAMILY
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = color

    def _add_cover(self):
        slide = self._blank_slide(background=INK, footer=False)
        glow = slide.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Inches(9.1),
            Inches(-1.5),
            Inches(5.6),
            Inches(5.6),
        )
        glow.fill.solid()
        glow.fill.fore_color.rgb = BLUE
        glow.fill.transparency = 35
        glow.line.fill.background()
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0.8),
            Inches(0.72),
            Inches(1.2),
            Inches(0.08),
        )
        line.fill.solid()
        line.fill.fore_color.rgb = RGBColor(45, 212, 191)
        line.line.fill.background()
        self._add_text(slide, "AI INSPECTION REPORT", 0.8, 0.92, 5.5, 0.3, size=10, color=RGBColor(94, 234, 212), bold=True)
        self._add_text(
            slide,
            _text(self.report.get("title"), "巡检分析报告"),
            0.78,
            1.45,
            10.8,
            1.35,
            size=34,
            color=WHITE,
            bold=True,
            valign=MSO_ANCHOR.MIDDLE,
        )
        self._add_text(
            slide,
            _text(self.report.get("month_label"), "月度报告"),
            0.82,
            2.86,
            6.5,
            0.5,
            size=19,
            color=RGBColor(186, 230, 253),
        )
        scope = self.report.get("source_selection") or {}
        scope_label = "全部可用站点" if scope.get("mode") != "custom" else f"自定义 {len(scope.get('station_ids') or [])} 个站点"
        meta = self.report.get("snapshot") or {}
        generated_at = meta.get("generated_at") or (self.report.get("summary") or {}).get("generated_at") or "-"
        self._add_text(slide, f"数据范围  {scope_label}", 0.82, 5.72, 4.4, 0.36, size=11, color=RGBColor(203, 213, 225))
        self._add_text(slide, f"报告生成  {generated_at}", 0.82, 6.12, 5.5, 0.36, size=11, color=RGBColor(203, 213, 225))
        self._add_text(slide, "业务督导中心数智管理平台", 8.15, 6.18, 4.3, 0.36, size=10, color=RGBColor(148, 163, 184), align=PP_ALIGN.RIGHT)

    def _add_scope_overview(self):
        slide = self._blank_slide()
        self._add_title(slide, "报告口径与数据范围", "DATA SCOPE")
        note = _text(self.report.get("data_scope_note"), "按当前报告模板与账号数据权限统计。")
        self._add_panel(slide, 0.82, 1.9, 11.7, 1.18, "统计口径", note, TEAL)
        source = self.report.get("source_selection") or {}
        metrics = [
            ("统计站点", source.get("station_count") or (self.report.get("summary") or {}).get("station_count"), "座"),
            ("涉及片区", source.get("region_count") or (self.report.get("summary") or {}).get("region_count"), "个"),
            ("巡检记录", source.get("inspection_count"), "条"),
            ("审核通过问题", source.get("issue_count") or (self.report.get("summary") or {}).get("total_issue_count"), "项"),
        ]
        self._add_kpis(slide, metrics, y=3.42)
        targets = self.report.get("target_tables") or []
        self._add_text(slide, "关联检查表", 0.85, 5.22, 2, 0.3, size=11, color=MUTED, bold=True)
        self._add_rich_lines(slide, [f"{index + 1:02d}  {_text(name)}" for index, name in enumerate(targets)], 0.85, 5.58, 11.4, 1.08, size=14)

    def _add_panel(self, slide, x, y, width, height, heading, body, accent=BLUE):
        panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(width), Inches(height))
        panel.fill.solid()
        panel.fill.fore_color.rgb = WHITE
        panel.line.color.rgb = LINE
        marker = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x + 0.22), Inches(y + 0.23), Inches(0.08), Inches(height - 0.46))
        marker.fill.solid()
        marker.fill.fore_color.rgb = accent
        marker.line.fill.background()
        self._add_text(slide, heading, x + 0.46, y + 0.2, width - 0.7, 0.28, size=11, color=accent, bold=True)
        self._add_text(slide, body, x + 0.46, y + 0.52, width - 0.7, height - 0.68, size=13, color=SLATE, valign=MSO_ANCHOR.MIDDLE)

    def _add_kpis(self, slide, metrics, y=2.0):
        metrics = list(metrics)
        gap = 0.17
        width = (11.7 - gap * max(0, len(metrics) - 1)) / max(1, len(metrics))
        for index, (label, value, unit) in enumerate(metrics):
            x = 0.82 + index * (width + gap)
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(width), Inches(1.38))
            card.fill.solid()
            card.fill.fore_color.rgb = WHITE
            card.line.color.rgb = LINE
            self._add_text(slide, label, x + 0.18, y + 0.18, width - 0.36, 0.3, size=10, color=MUTED, bold=True)
            self._add_text(slide, f"{_format_metric(value)}{unit}", x + 0.16, y + 0.52, width - 0.32, 0.62, size=25, color=BLUE, bold=True, valign=MSO_ANCHOR.MIDDLE)

    def _add_section(self, chapter, title, subtitle=""):
        slide = self._blank_slide(background=INK)
        self._add_text(slide, chapter, 0.86, 1.3, 2.7, 0.34, size=11, color=RGBColor(94, 234, 212), bold=True)
        self._add_text(slide, title, 0.83, 1.9, 10.8, 1.05, size=31, color=WHITE, bold=True, valign=MSO_ANCHOR.MIDDLE)
        if subtitle:
            self._add_text(slide, subtitle, 0.85, 3.15, 10.6, 1.2, size=16, color=RGBColor(203, 213, 225))
        stripe = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.86), Inches(5.95), Inches(4.2), Inches(0.08))
        stripe.fill.solid()
        stripe.fill.fore_color.rgb = TEAL
        stripe.line.fill.background()
        return slide

    def _add_narrative_slide(self, title, narrative, *, kicker="OVERVIEW", ai=False, metrics=None):
        slide = self._blank_slide()
        self._add_title(slide, title, kicker, ai=ai)
        self._add_panel(slide, 0.82, 1.9, 11.7, 2.12, "情况概述", _text(narrative), TEAL)
        if metrics:
            self._add_kpis(slide, metrics, y=4.4)
        return slide

    def _add_chart_slides(self, title, items, *, name_key="name", value_keys=("count",), series_names=("问题数量",), kicker="DATA ANALYSIS", narrative="", chunk_size=12):
        items = [item for item in (items or []) if isinstance(item, dict)]
        if not items:
            self._add_empty_slide(title, "当前范围暂无可展示的统计数据。", kicker)
            return
        for page_index, chunk in enumerate(_chunks(items, chunk_size), 1):
            slide = self._blank_slide()
            page_title = title if len(items) <= chunk_size else f"{title}（{page_index}）"
            self._add_title(slide, page_title, kicker, subtitle=narrative if page_index == 1 else "")
            chart_data = ChartData()
            chart_data.categories = [_short(item.get(name_key), 14) for item in chunk]
            for series_index, value_key in enumerate(value_keys):
                values = [_as_float(item.get(value_key)) for item in chunk]
                chart_data.add_series(series_names[series_index], values)
            y = 2.03 if narrative else 1.85
            height = 4.62 if narrative else 4.8
            chart = slide.shapes.add_chart(
                XL_CHART_TYPE.COLUMN_CLUSTERED,
                Inches(0.86),
                Inches(y),
                Inches(11.55),
                Inches(height),
                chart_data,
            ).chart
            chart.has_legend = len(value_keys) > 1
            if chart.has_legend:
                chart.legend.position = XL_LEGEND_POSITION.BOTTOM
                chart.legend.include_in_layout = False
                chart.legend.font.name = FONT_FAMILY
                chart.legend.font.size = Pt(9)
            chart.value_axis.has_major_gridlines = True
            chart.value_axis.major_gridlines.format.line.color.rgb = LINE
            chart.value_axis.tick_labels.font.name = FONT_FAMILY
            chart.value_axis.tick_labels.font.size = Pt(9)
            chart.category_axis.tick_labels.font.name = FONT_FAMILY
            chart.category_axis.tick_labels.font.size = Pt(9)
            chart.plots[0].has_data_labels = True
            for series_index, series in enumerate(chart.series):
                series.format.fill.solid()
                series.format.fill.fore_color.rgb = CHART_COLORS[series_index % len(CHART_COLORS)]
                series.format.line.fill.background()
            labels = chart.plots[0].data_labels
            labels.position = 0
            labels.font.name = FONT_FAMILY
            labels.font.size = Pt(9)

    def _add_table_slides(self, title, headers, rows, *, kicker="DATA TABLE", rows_per_slide=11, ai=False):
        normalized_rows = [list(row) for row in (rows or [])]
        if not normalized_rows:
            self._add_empty_slide(title, "当前范围暂无明细数据。", kicker)
            return
        for page_index, chunk in enumerate(_chunks(normalized_rows, rows_per_slide), 1):
            slide = self._blank_slide()
            page_title = title if len(normalized_rows) <= rows_per_slide else f"{title}（{page_index}）"
            self._add_title(slide, page_title, kicker, ai=ai)
            shape = slide.shapes.add_table(
                len(chunk) + 1,
                len(headers),
                Inches(0.72),
                Inches(1.75),
                Inches(11.88),
                Inches(5.08),
            )
            table = shape.table
            column_width = int(Inches(11.88) / max(1, len(headers)))
            for column in table.columns:
                column.width = column_width
            for column_index, header in enumerate(headers):
                cell = table.cell(0, column_index)
                cell.fill.solid()
                cell.fill.fore_color.rgb = BLUE
                self._set_cell_text(cell, header, 9, WHITE, True)
            for row_index, row in enumerate(chunk, 1):
                for column_index in range(len(headers)):
                    cell = table.cell(row_index, column_index)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = WHITE if row_index % 2 else RGBColor(241, 245, 249)
                    self._set_cell_text(cell, _short(row[column_index] if column_index < len(row) else "", 80), 8, SLATE)

    def _set_cell_text(self, cell, value, size, color, bold=False):
        cell.margin_left = Inches(0.05)
        cell.margin_right = Inches(0.05)
        cell.margin_top = Inches(0.04)
        cell.margin_bottom = Inches(0.04)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        frame = cell.text_frame
        frame.clear()
        frame.word_wrap = True
        paragraph = frame.paragraphs[0]
        paragraph.text = str(value or "")
        paragraph.alignment = PP_ALIGN.CENTER
        paragraph.font.name = FONT_FAMILY
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = color

    def _add_empty_slide(self, title, message, kicker="REPORT"):
        slide = self._blank_slide()
        self._add_title(slide, title, kicker)
        self._add_panel(slide, 2.15, 2.65, 9.0, 1.55, "暂无数据", message, MUTED)

    def _resolve_image_source(self, raw_path):
        value = str(raw_path or "").strip()
        if not value or not self.include_photos:
            return None
        if value.startswith("data:image/") and ";base64," in value:
            try:
                return BytesIO(base64.b64decode(value.split(",", 1)[1], validate=True))
            except (ValueError, TypeError):
                return None
        clean = value.split("?", 1)[0].replace("\\", "/")
        if "/storage/" in clean:
            clean = clean.split("/storage/", 1)[1]
        clean = clean.lstrip("/")
        candidate = os.path.abspath(os.path.join(self.storage_root, clean))
        try:
            if os.path.commonpath([self.storage_root, candidate]) != self.storage_root:
                return None
        except ValueError:
            return None
        return candidate if os.path.isfile(candidate) else None

    def _add_picture_contain(self, slide, image_source, x, y, width, height):
        source = self._resolve_image_source(image_source)
        if not source:
            placeholder = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(width), Inches(height))
            placeholder.fill.solid()
            placeholder.fill.fore_color.rgb = RGBColor(241, 245, 249)
            placeholder.line.color.rgb = LINE
            self._set_shape_text(placeholder, "暂无照片" if self.include_photos else "照片未导出", 10, MUTED)
            return
        try:
            if hasattr(source, "seek"):
                source.seek(0)
            with Image.open(source) as image:
                image_width, image_height = image.size
            if hasattr(source, "seek"):
                source.seek(0)
            ratio = min(width / image_width, height / image_height)
            target_width = image_width * ratio
            target_height = image_height * ratio
            left = x + (width - target_width) / 2
            top = y + (height - target_height) / 2
            slide.shapes.add_picture(source, Inches(left), Inches(top), Inches(target_width), Inches(target_height))
        except Exception:
            placeholder = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(width), Inches(height))
            placeholder.fill.solid()
            placeholder.fill.fore_color.rgb = RGBColor(254, 242, 242)
            placeholder.line.color.rgb = RGBColor(254, 202, 202)
            self._set_shape_text(placeholder, "照片读取失败", 10, RED)

    def _add_issue_slides(self, title, issues, *, kicker="TYPICAL ISSUES", ai=False, subtitle="", max_issues=12):
        issues = [item for item in (issues or []) if isinstance(item, dict)][:max_issues]
        if not issues:
            self._add_empty_slide(title, "当前范围暂无可展示的问题。", kicker)
            return
        per_slide = 4 if self.include_photos else 6
        for page_index, chunk in enumerate(_chunks(issues, per_slide), 1):
            slide = self._blank_slide()
            page_title = title if len(issues) <= per_slide else f"{title}（{page_index}）"
            self._add_title(slide, page_title, kicker, subtitle=subtitle if page_index == 1 else "", ai=ai)
            columns = 2
            card_width = 5.7
            card_height = 2.2 if per_slide == 4 else 1.4
            start_y = 1.85
            for index, issue in enumerate(chunk):
                row = index // columns
                column = index % columns
                x = 0.82 + column * 5.95
                y = start_y + row * (card_height + 0.18)
                card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(card_width), Inches(card_height))
                card.fill.solid()
                card.fill.fore_color.rgb = WHITE
                card.line.color.rgb = LINE
                photo_width = 1.65 if self.include_photos else 0
                if self.include_photos:
                    self._add_picture_contain(slide, issue.get("issue_photo"), x + 0.16, y + 0.16, photo_width, card_height - 0.32)
                text_x = x + 0.18 + photo_width + (0.14 if self.include_photos else 0)
                text_width = card_width - (text_x - x) - 0.16
                station = issue.get("station_name") or issue.get("unit_name") or issue.get("management_unit") or "问题明细"
                category = issue.get("category_name") or issue.get("inspection_item") or issue.get("project") or issue.get("service_area") or ""
                heading = f"{station}{f' · {category}' if category else ''}"
                self._add_text(slide, _short(heading, 34), text_x, y + 0.18, text_width, 0.34, size=11, color=BLUE, bold=True)
                description = issue.get("description") or issue.get("inspection_content") or issue.get("summary") or "暂无问题描述"
                self._add_text(slide, _short(description, 135), text_x, y + 0.57, text_width, card_height - 0.75, size=10, color=SLATE)

    def _add_analysis_cards(self, title, items, *, kicker="AI ANALYSIS", ai=True):
        items = [item for item in (items or []) if isinstance(item, dict)]
        if not items:
            self._add_empty_slide(title, "当前报告暂无可展示的分析内容。", kicker)
            return
        for page_index, chunk in enumerate(_chunks(items, 4), 1):
            slide = self._blank_slide()
            page_title = title if len(items) <= 4 else f"{title}（{page_index}）"
            self._add_title(slide, page_title, kicker, ai=ai and any(item.get("ai_generated", True) for item in chunk))
            for index, item in enumerate(chunk):
                y = 1.82 + index * 1.22
                number = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.85), Inches(y), Inches(0.62), Inches(0.62))
                number.fill.solid()
                number.fill.fore_color.rgb = RGBColor(204, 251, 241)
                number.line.fill.background()
                self._set_shape_text(number, f"{(page_index - 1) * 4 + index + 1:02d}", 11, TEAL, True)
                self._add_text(slide, _text(item.get("title"), "分析事项"), 1.68, y - 0.02, 10.5, 0.38, size=14, bold=True)
                self._add_text(slide, _short(item.get("content"), 220), 1.68, y + 0.38, 10.55, 0.72, size=11, color=SLATE)

    def _build_quality_measurement(self):
        summary = self.report.get("summary") or {}
        self._add_section("CHAPTER 01", "总体情况", _text(self.report.get("overview_text"), "质量计量监督检查总体情况"))
        self._add_narrative_slide(
            "总体情况",
            self.report.get("overview_text"),
            metrics=[
                ("受检站点", summary.get("station_count"), "座"),
                ("发现问题", summary.get("total_issue_count"), "项"),
                ("一般问题", summary.get("general_issue_count"), "项"),
                ("禁止项", summary.get("prohibited_issue_count"), "项"),
            ],
        )
        rows = self.report.get("rows") or []
        self._add_table_slides(
            "二级单位问题汇总",
            ["二级单位", "类型", "受检站点", "一般问题", "禁止项", "问题合计"],
            [[item.get("unit_name"), item.get("unit_type_label"), item.get("station_count"), item.get("general_issue_count"), item.get("prohibited_issue_count"), item.get("total_issue_count")] for item in rows],
        )
        self._add_section("CHAPTER 02", "检查发现 · 问题分布")
        finding = self.report.get("finding_summary") or {}
        distribution = finding.get("business_flow_distribution") or []
        self._add_chart_slides("业务流程问题分布", distribution, narrative=finding.get("finding_text") or "")
        self._add_section("CHAPTER 03", "检查发现 · 禁止项问题")
        examples = self.report.get("prohibited_examples") or []
        self._add_table_slides(
            "禁止项典型问题",
            ["所属单位", "单位类型", "禁止项管理规定（具体问题描述）"],
            [[item.get("unit_name"), item.get("unit_type_label"), item.get("description")] for item in examples],
            rows_per_slide=8,
        )
        deep = self.report.get("deep_analysis") or {}
        self._add_section("CHAPTER 04", "重点问题与管理追溯", "突出问题、管理追溯和工作计划中的AI内容均已明确标识。")
        for flow in deep.get("flow_highlights") or []:
            self._add_issue_slides(
                f"{_text(flow.get('flow_name'), '业务环节')} · 突出问题",
                flow.get("highlighted_issues") or [],
                ai=bool(flow.get("ai_generated")),
                subtitle=_text(flow.get("summary"), ""),
                max_issues=8,
            )
        trace = deep.get("management_trace") or {}
        trace_items = [
            {"title": "执行层面", "content": trace.get("execution_analysis"), "ai_generated": trace.get("ai_generated")},
            {"title": "监督层面", "content": trace.get("supervision_analysis"), "ai_generated": trace.get("ai_generated")},
            {"title": "管理层面", "content": trace.get("management_analysis"), "ai_generated": trace.get("ai_generated")},
            {"title": "综合结论", "content": trace.get("conclusion"), "ai_generated": trace.get("ai_generated")},
        ]
        self._add_analysis_cards("管理追溯", trace_items, ai=bool(trace.get("ai_generated")))
        measures = trace.get("improvement_measures") or []
        if measures:
            self._add_analysis_cards(
                "改进措施",
                [{"title": item.get("level"), "content": item.get("content"), "ai_generated": trace.get("ai_generated")} for item in measures],
                ai=bool(trace.get("ai_generated")),
            )
        self._add_analysis_cards("工作计划", deep.get("work_plan") or [], ai=bool(deep.get("work_plan_ai_generated")))

    def _build_safety_quality(self):
        summary = self.report.get("summary") or {}
        self._add_section("CHAPTER 01", "总体情况", "视频扫站与四不两直现场检查分线统计。")
        self._add_narrative_slide(
            "安全质量检查概览",
            "视频扫站和现场检查分别统计，图表中的站点数与审核通过问题数来自当前报告快照。",
            metrics=[
                ("视频站点", summary.get("video_station_count"), "座"),
                ("视频问题", summary.get("video_issue_count"), "项"),
                ("现场站点", summary.get("onsite_station_count"), "座"),
                ("现场问题", summary.get("onsite_issue_count"), "项"),
            ],
        )
        for section in self.report.get("sections") or []:
            self._add_chart_slides(
                f"{section.get('label')} · 单位分布",
                section.get("units") or [],
                name_key="unit_name",
                value_keys=("issue_count", "station_count"),
                series_names=("问题数量", "检查站点"),
                narrative=section.get("narrative") or "",
            )
            self._add_chart_slides(
                f"{section.get('label')} · {section.get('category_field') or '问题分类'}",
                section.get("category_distribution") or [],
                narrative=section.get("category_text") or "",
            )
        deep = self.report.get("deep_analysis") or {}
        self._add_section("CHAPTER 02", "典型问题与重点问题", "AI辅助筛选高频典型问题与分类重点问题。")
        for finding in deep.get("typical_findings") or []:
            self._add_issue_slides(
                f"{finding.get('label') or finding.get('mode') or '典型问题'}",
                finding.get("issues") or ([finding.get("representative_issue")] if finding.get("representative_issue") else []),
                ai=bool(finding.get("ai_generated")),
                subtitle=finding.get("summary") or "",
                max_issues=8,
            )
        for highlight in (deep.get("category_highlights") or [])[:10]:
            self._add_issue_slides(
                f"{highlight.get('label') or ''} · {highlight.get('category_name') or '重点问题'}",
                highlight.get("issues") or [],
                ai=bool(highlight.get("ai_generated")),
                subtitle=highlight.get("summary") or "",
                max_issues=6,
            )
        self._add_section("CHAPTER 03", "问题分析与工作建议")
        self._add_analysis_cards("问题分析", deep.get("problem_analysis") or [], ai=True)
        self._add_analysis_cards("工作建议", deep.get("work_suggestions") or [], ai=True)

    def _build_finance(self):
        summary = self.report.get("summary") or {}
        self._add_section("CHAPTER 01", "总体情况", "按单位、站点、项目和关键环节统计财务检查结果。")
        self._add_narrative_slide(
            "财务检查概览",
            self.report.get("overview_text") or self.report.get("scope_text"),
            metrics=[
                ("检查站点", summary.get("station_count"), "座"),
                ("管理片区", summary.get("region_count"), "个"),
                ("控参股单位", summary.get("holding_unit_count"), "个"),
                ("发现问题", summary.get("total_issue_count"), "项"),
            ],
        )
        units = self.report.get("units") or []
        self._add_chart_slides("单位问题与站点分布", units, name_key="unit_name", value_keys=("issue_count", "station_count"), series_names=("问题数量", "检查站点"))
        self._add_chart_slides("检查项目分布", self.report.get("project_distribution") or [], narrative=self.report.get("project_distribution_text") or "")
        self._add_chart_slides("关键环节分布", self.report.get("key_link_distribution") or [], narrative=self.report.get("key_link_distribution_text") or "")
        self._add_section("CHAPTER 02", "各站结果通报")
        station_rows = self.report.get("station_reports") or []
        self._add_table_slides(
            "站点问题概览",
            ["所属单位", "站点", "巡检时间", "问题数量", "问题摘要"],
            [[item.get("unit_name"), item.get("station_name"), item.get("date_range"), item.get("issue_count"), "；".join(_short(issue.get("description"), 42) for issue in (item.get("issues") or [])[:3])] for item in station_rows],
            rows_per_slide=8,
        )
        photographed = []
        for station in station_rows:
            for issue in station.get("issues") or []:
                issue = dict(issue)
                issue.setdefault("station_name", station.get("station_name"))
                photographed.append(issue)
        self._add_issue_slides("各站代表问题", photographed, max_issues=12)
        deep = self.report.get("deep_analysis") or {}
        self._add_section("CHAPTER 03", "检查结果分析与建议")
        self._add_analysis_cards("检查结果分析", deep.get("result_analysis") or [], ai=True)
        self._add_analysis_cards("检查内容建议", deep.get("content_suggestions") or [], ai=True)

    def _build_equipment_facilities(self):
        summary = self.report.get("summary") or {}
        self._add_section("CHAPTER 01", "总体情况", "按片区与站点两个维度分析设备设施问题。")
        self._add_narrative_slide(
            "设备设施检查概览",
            self.report.get("overview_text"),
            metrics=[
                ("检查单位", summary.get("unit_count"), "个"),
                ("受检站点", summary.get("station_count"), "座"),
                ("发现问题", summary.get("total_issue_count"), "项"),
                ("站均问题", summary.get("average_issue_count"), "项"),
            ],
        )
        self._add_chart_slides("按片区划分", self.report.get("region_rows") or [], name_key="unit_name", value_keys=("issue_count", "station_count", "average_issue_count"), series_names=("问题数量", "受检站点", "平均问题"), narrative=self.report.get("region_text") or "")
        rankings = self.report.get("station_ranking") or []
        self._add_table_slides("站点问题数量排名", ["排名", "站点", "所属单位", "检查日期", "问题数量"], [[item.get("rank"), item.get("station_name"), item.get("management_unit"), item.get("date_range") or item.get("report_date"), item.get("issue_count")] for item in rankings], rows_per_slide=12)
        self._add_section("CHAPTER 02", "问题数据统计分析")
        self._add_chart_slides("所属区域问题分布", self.report.get("area_distribution") or [], narrative=self.report.get("area_distribution_text") or "")
        self._add_chart_slides("检查事项问题分布", self.report.get("item_distribution") or [], narrative=self.report.get("item_distribution_text") or "")
        deep = self.report.get("deep_analysis") or {}
        self._add_section("CHAPTER 03", "典型问题、分析与建议")
        typical = deep.get("typical_finding") or {}
        representative = typical.get("representative_issue")
        self._add_issue_slides("检查发现 · 典型问题", [representative] if representative else [], ai=bool(typical.get("ai_generated")), subtitle=typical.get("summary") or "")
        self._add_analysis_cards("问题分析", deep.get("problem_analysis") or [], ai=True)
        self._add_analysis_cards("工作建议", deep.get("work_suggestions") or [], ai=True)

    def _build_on_site_service(self):
        summary = self.report.get("summary") or {}
        self._add_section("CHAPTER 01", "检查基本情况", "线上与线下巡检分线统计，并结合上月整改情况进行分析。")
        self._add_narrative_slide(
            "现场服务检查概览",
            self.report.get("overview_text"),
            metrics=[
                ("检查站次", summary.get("station_visit_count"), "座"),
                ("发现问题", summary.get("total_issue_count"), "项"),
                ("视频站均", summary.get("video_average_issue_count"), "项"),
                ("现场站均", summary.get("onsite_average_issue_count"), "项"),
            ],
        )
        self._add_chart_slides("各单位问题与站均问题对比", self.report.get("unit_comparison") or [], name_key="unit_name", value_keys=("issue_count", "average_issue_count"), series_names=("问题总数", "站均问题"))
        previous = self.report.get("previous_month_rectification") or {}
        self._add_chart_slides("上月各单位整改情况", previous.get("units") or [], name_key="unit_name", value_keys=("unreceived_count", "pending_count", "rectified_count"), series_names=("未签收", "未整改", "已整改"), narrative=previous.get("narrative") or "")
        for mode in self.report.get("mode_summaries") or []:
            self._add_chart_slides(f"{mode.get('label')} · 单位站均问题", mode.get("units") or [], name_key="unit_name", value_keys=("average_issue_count",), series_names=("站均问题",), narrative=mode.get("narrative") or "")
        self._add_section("CHAPTER 02", "分环节汇总")
        for section in self.report.get("category_sections") or []:
            items = section.get("items") or []
            self._add_chart_slides(f"{section.get('label')} · 分类分布", items, name_key="name", narrative=section.get("narrative") or "")
        deep = self.report.get("deep_analysis") or {}
        self._add_section("CHAPTER 03", "各单位问题分析", "AI按服务环节筛选重点问题并保留原始描述与照片。")
        for unit in (deep.get("unit_analyses") or [])[:20]:
            areas = unit.get("areas") or unit.get("area_analyses") or []
            issues = []
            for area in areas:
                for issue in area.get("issues") or area.get("highlighted_issues") or []:
                    item = dict(issue)
                    item.setdefault("station_name", unit.get("unit_name"))
                    item.setdefault("service_area", area.get("area_name") or area.get("name"))
                    issues.append(item)
            self._add_issue_slides(f"{unit.get('unit_name') or '单位'} · 重点问题", issues, ai=bool(unit.get("ai_generated", True)), subtitle=unit.get("summary") or "", max_issues=8)
        self._add_section("CHAPTER 04", "问题总结与下一步建议")
        self._add_analysis_cards("问题总结", deep.get("problem_summary") or [], ai=True)
        self._add_analysis_cards("下一步建议", deep.get("next_steps") or [], ai=True)

    def _add_ending(self):
        slide = self._blank_slide(background=INK, footer=False)
        self._add_text(slide, "END", 0.84, 1.48, 2.0, 0.38, size=11, color=RGBColor(94, 234, 212), bold=True)
        self._add_text(slide, "数据驱动检查\n闭环推动改进", 0.8, 2.0, 7.8, 1.75, size=34, color=WHITE, bold=True, valign=MSO_ANCHOR.MIDDLE)
        self._add_text(slide, "本演示文稿由业务督导中心数智管理平台生成", 0.84, 5.72, 8.0, 0.4, size=12, color=RGBColor(148, 163, 184))


def build_inspection_report_presentation(report_type, report, storage_root, output_path, include_photos=True):
    builder = InspectionReportPresentation(
        report_type=report_type,
        report=report,
        storage_root=storage_root,
        include_photos=include_photos,
    )
    return builder.build(output_path)
