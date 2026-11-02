"""Editable horizontal rankings with deterministic labels and bounded plot areas."""

from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_DATA_LABEL_POSITION, XL_TICK_MARK
from pptx.util import Inches, Pt


def ranking_chart(slide, block, index, top, bottom, textbox):
    rows = block.get('chart_rows') or []
    title = textbox(slide, block['chart_title'], 7.0, top, 5.95, .36, 15, '294B65', True)
    title.name = f'safety-ranking-title-{index}'
    note = f"共 {block.get('count', 0)} 项 · 按问题数量排序"
    if block.get('omitted_count'):
        note += f" · 其余 {block['omitted_count']} 项未列入前六"
    textbox(slide, note, 7.0, top+.39, 5.95, .25, 10, '64748B')
    if not rows:
        textbox(slide, '当前范围暂无可统计的问题。', 7.15, top+1, 5.5, .5, 15, '64748B')
        return
    data = CategoryChartData()
    # Percentage denominator is the whole selected theme, never only the top six.
    data.categories = [f"{r['name']}  {r['percentage']:.1f}%" for r in rows]
    data.add_series('问题数量（项）', [r['count'] for r in rows], number_format='0')
    shape = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(6.95), Inches(top+.73),
        Inches(6.15), Inches(min(bottom-top-.77, .62*len(rows)+.4)), data)
    shape.name = f'safety-key-problem-chart-{index}'
    chart = shape.chart
    chart.has_legend = False
    chart.has_title = False
    plot = chart.plots[0]
    plot.gap_width = 65 if len(rows) > 3 else 100
    plot.has_data_labels = True
    labels = plot.data_labels
    labels.position = XL_DATA_LABEL_POSITION.OUTSIDE_END
    labels.show_value = True
    labels.show_category_name = labels.show_series_name = False
    labels.number_format = '0'
    labels.font.name = 'Microsoft YaHei'
    labels.font.size = Pt(12 if bottom-top > 4 else 10)
    labels.font.bold = True
    labels.font.color.rgb = RGBColor.from_string('1F3E53')
    cat, val = chart.category_axis, chart.value_axis
    cat.reverse_order = True
    cat.major_tick_mark = cat.minor_tick_mark = XL_TICK_MARK.NONE
    cat.tick_labels.font.name = 'Microsoft YaHei'
    cat.tick_labels.font.size = Pt(12 if bottom-top > 4 else 10)
    cat.tick_labels.font.color.rgb = RGBColor.from_string('294B65')
    cat.format.line.fill.background()
    val.minimum_scale = 0
    val.maximum_scale = max(r['count'] for r in rows) * 1.3
    val.visible = False
    val.has_major_gridlines = False
    for i, point in enumerate(chart.series[0].points):
        point.format.fill.solid()
        point.format.fill.fore_color.rgb = RGBColor.from_string('23799A' if i < 2 else '7FB6C8')
        point.format.line.fill.background()
    return shape
