"""Native, editable equipment detail pages following the supplied template layouts."""
from copy import deepcopy
import colorsys
import math
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt
from pptx.opc.packuri import PackURI
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE_TYPE
from non_oil_report_presentation import _delete_slide, _move_slide, _remove_shape, _add_picture_contain, _set_chart_fonts
from equipment_report_analysis import canonical_unit, unit_order, phrase_distribution


def wrap(text, width, size):
    capacity = max(4, (width*72-8)/size)
    result = []
    for paragraph in str(text).split('\n'):
        line, used = '', 0
        for char in paragraph:
            units = .55 if ord(char) < 128 else 1
            if used+units > capacity:
                result.append(line)
                line, used = '', 0
            line += char
            used += units
        result.append(line)
    return result


def pages(text, width, height, size):
    lines = wrap(text, width, size)
    per = max(1, math.floor(height*72/(size*1.35)))
    return ['\n'.join(lines[i:i+per]) for i in range(0, len(lines), per)] or ['']


def fitted_text(slide, value, x, y, w, h, size=18, **kwargs):
    # Fit the entire semantic block; headings and summary cards must not paginate.
    while size > 6 and len(wrap(value, w, size))*size*1.35 > h*72:
        size -= .5
    return text(slide, '\n'.join(wrap(value, w, size)), x, y, w, h, size, **kwargs)


def legend_layout(rows, width, height):
    labels = [f"{r['name']}  {r['count']}项 / {r['percentage']}%" for r in rows]
    for size in (14, 13, 12, 11, 10, 9, 8, 7, 6):
        for columns in range(1, 5):
            per = max(1, math.ceil(len(labels)/columns))
            column_width = width/columns
            chunks = [labels[i:i+per] for i in range(0, len(labels), per)]
            heights = [[max(.22, len(wrap(label, column_width-.28, size))*size*1.35/72+.04)
                        for label in chunk] for chunk in chunks]
            if all(sum(values) <= height for values in heights):
                return size, column_width, chunks, heights
    raise ValueError('设备设施短语数量超出单页图例容量，请检查规范短语配置。')


def text(slide, value, x, y, w, h, size=18, color='111111', bold=False, fill=None):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor.from_string(fill)
    frame = shape.text_frame
    frame.margin_top = frame.margin_bottom = Pt(0)
    frame.margin_left = frame.margin_right = Pt(2)
    frame.word_wrap = True
    frame.text = value
    for paragraph in frame.paragraphs:
        paragraph.font.name = 'Microsoft YaHei'
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = RGBColor.from_string(color)
        paragraph.line_spacing = 1.2
        paragraph.space_after = Pt(0)
    return shape


def new_page(prs, source, suffix=None, ai=False):
    slide = prs.slides.add_slide(source.slide_layout)
    for shape in list(slide.shapes):
        _remove_shape(shape)
    for shape in source.shapes:
        if shape.has_text_frame and shape.top < Inches(.9):
            slide.shapes._spTree.insert_element_before(deepcopy(shape._element), 'p:extLst')
    if suffix:
        for shape in list(slide.shapes):
            _remove_shape(shape)
        text(slide, '三、检查发现', .69, .24, 2.5, .6, 28, bold=True)
        text(slide, '——'+suffix, 3.18, .24, 9.1, .6, 26, 'C00000', True)
    if ai:
        text(slide, 'AI辅助选题；选题证据及人工调整详见报告面板', .35, 7.18, 11.8, .2, 9, '64748B')
    _move_slide(prs, slide, len(prs.slides)-2)
    return slide


def photos(slide, issues, box, storage_root):
    x, y, w, h = box
    if not issues:
        text(slide, '暂无对应选题', x, y, w, h, 18, '64748B')
        return
    width = (w-.12*(len(issues)-1))/len(issues)
    for i, issue in enumerate(issues):
        first = len(slide.shapes)
        _add_picture_contain(slide, issue.get('issue_photo'),
            tuple(Inches(v) for v in (x+i*(width+.12), y, width, h-.45)), storage_root)
        # Keep the image's contain geometry, extending only its background frame
        # to include the reserved caption band inside the same card.
        slide.shapes[first].height = Inches(h)
        for shape in list(slide.shapes)[first:]:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        run.font.color.rgb = RGBColor.from_string('64748B')
        has_picture = any(s.shape_type == MSO_SHAPE_TYPE.PICTURE for s in list(slide.shapes)[first:])
        label = f"{issue.get('station_name', '')} · 问题ID：{issue['issue_id']}" if has_picture else issue.get('station_name', '')
        caption = fitted_text(slide, label, x+i*(width+.12)+.12, y+h-.36, width-.24, .25, 11, color='526477')
        for paragraph in caption.text_frame.paragraphs:
            paragraph.alignment = PP_ALIGN.CENTER


def build_details(prs, original, report, storage_root):
    analysis = report.get('equipment_analysis') or {}
    issues = analysis.get('issues') or []
    distribution = phrase_distribution(issues) if 'issues' in analysis else analysis.get('phrase_distribution') or []
    for old in original[10:39]:
        _delete_slide(prs, old)
    # python-pptx allocates new slide part names from the current slide count.
    # Compact survivors first: the retained slide40 would otherwise collide once
    # enough evidence pages are added. Relationships follow the part objects.
    for index, existing in enumerate(prs.slides, 1):
        existing.part.partname = PackURI(f'/ppt/slides/slide{index}.xml')
    # One pie page, including all phrases in an adaptive multi-column legend.
    slide = new_page(prs, original[10])
    text(slide, '加油站设备设施各类问题占比情况', .4, 1.03, 12.4, .5, 22, '0000FF', True)
    data = CategoryChartData()
    data.categories = [r['name'] for r in distribution] or ['暂无问题']
    data.add_series('问题数', [r['count'] for r in distribution] or [0])
    chart = slide.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(.2), Inches(1.65), Inches(4.7), Inches(4.7), data).chart
    chart.has_legend = False
    chart.has_title = False
    plot = chart.plots[0]
    colors = [''.join(f'{round(c*255):02X}' for c in colorsys.hls_to_rgb((i*.618034) % 1, .48, .65))
              for i in range(len(distribution))]
    for point, color in zip(chart.series[0].points, colors):
        point.format.fill.solid()
        point.format.fill.fore_color.rgb = RGBColor.from_string(color)
    plot.has_data_labels = True
    plot.data_labels.show_percentage = True
    plot.data_labels.show_value = False
    plot.data_labels.show_category_name = False
    plot.data_labels.position = XL_LABEL_POSITION.BEST_FIT
    if len(distribution) > 10:
        plot.has_data_labels = False
    _set_chart_fonts(chart, category_size=11)
    maximum = distribution[0]['count'] if distribution else 0
    leaders = [r for r in distribution if r['count'] == maximum]
    if leaders:
        lead = leaders[0]
        note = f"{lead['name']}是单类问题{'并列' if len(leaders)>1 else ''}最多的项，共 {lead['count']} 个问题，占比 {lead['percentage']}%，是本次巡检最集中的单一问题。"
    else:
        note = '本次报告问题库暂无参与统计的问题。'
    fitted_text(slide, note, .45, 6.5, 12.4, .58, 18, color='C00000', bold=True)
    size, width, chunks, heights = legend_layout(distribution, 7.95, 4.7)
    color_index = 0
    for column, (labels, row_heights) in enumerate(zip(chunks, heights)):
        x, y = 5.0+column*width, 1.65
        for label, height in zip(labels, row_heights):
            text(slide, '', x, y+.035, .13, .13, fill=colors[color_index])
            text(slide, '\n'.join(wrap(label, width-.28, size)), x+.2, y, width-.28, height, size)
            color_index += 1
            y += height

    groups = analysis.get('high_groups') or []
    for start in range(0, max(1, len(groups)), 2):
        pair = groups[start:start+2]
        slide = new_page(prs, original[11], ai=True)
        text(slide, '加油站设备设施高频问题原因分析', .49, 1.0, 12, .55, 23, '0000FF', True)
        if not pair:
            text(slide, '本次暂无经AI确认的高频问题。', .8, 2, 11, 1)
        for i, group in enumerate(pair):
            x = 3.69 if len(pair) == 1 else .35+i*6.65
            fitted_text(slide, f"{start+i+1}、{group['phrase']}（{len(group['issues'])}项）", x, 1.7, 5.95, 1.05, 20, bold=True)
            representatives = sorted(group['issues'], key=lambda r: (not bool(r.get('issue_photo')), r['issue_id']))[:2]
            photos(slide, representatives, (x, 2.85, 5.95, 2.25), storage_root)
            fitted_text(slide, '原因（参考表原文）：'+'；'.join(group['causes']), x, 5.22, 5.95, 1.85, 17)

    special_ids = set(analysis.get('special_issue_ids') or [])
    for region in sorted(report.get('region_rows') or [], key=lambda r: unit_order(r['unit_name'])):
        unit = canonical_unit(region['unit_name'])
        stations = [s for s in report.get('station_ranking', []) if canonical_unit(s['management_unit']) == unit]
        unit_issues = [i for i in issues if i['management_unit'] == unit]
        special = [i for i in unit_issues if i['issue_id'] in special_ids]
        names = '、'.join(s['station_name'] for s in stations)
        stats = f"• 检查站数：{region['station_count']}站（{names}）\n\n• 问题总数：{region['issue_count']}项\n\n• 站均问题数：{region['average_issue_count']}项"
        chunks = [special[i:i+3] for i in range(0, len(special), 3)] or [[]]
        for chosen in chunks:
            slide = new_page(prs, original[13], unit, ai=True)
            fitted_text(slide, stats, .3, 1.25, 6.1, 2.2, 18, bold=True)
            text(slide, '', 6.85, 1.2, 6.15, 2.45, fill='E8EBF2')
            text(slide, '特性问题：', 6.95, 1.35, 5.9, .45, 21, '0000FF', True)
            detail = '\n'.join(f"{i['station_name']}：{i['description']}" for i in chosen) or '本片区暂无选定的特性问题。'
            fitted_text(slide, detail, 6.95, 1.88, 5.9, 1.65, 17)
            text(slide, '主要问题类型：', .4, 3.72, 12, .45, 22, '0000FF', True)
            width = (12.4-.25*max(0,len(chosen)-1))/max(1,len(chosen))
            for index, item in enumerate(chosen):
                x = .45+index*(width+.25)
                fitted_text(slide, '• '+item['phrase'], x, 4.22, width, .55, 17, bold=True)
                photos(slide, [item], (x, 4.85, width, 2.2), storage_root)
        for station in stations:
            station_issues = [i for i in unit_issues if i.get('station_id') == station['station_id']]
            station_special = [i for i in station_issues if i['issue_id'] in special_ids]
            description = '主要问题：\n'+'\n'.join(i['description'] for i in station_issues) if station_issues else '本次未发现参与报告的问题。'
            main_pages = pages(description, 4.5, 4.5, 17)
            photo_chunks = [station_special[i:i+2] for i in range(0,len(station_special),2)] or [[]]
            for page_index in range(max(len(main_pages),len(photo_chunks))):
                slide = new_page(prs, original[14], unit, ai=True)
                text(slide, '', .15, 1.15, 4.8, 5.9, fill='E8EBF2')
                text(slide, station['station_name'], .3, 1.35, 4.5, .65, 24, '0000FF', True)
                text(slide, f"问题总数：{len(station_issues)}个", .3, 2.08, 4.5, .45, 20, bold=True)
                text(slide, main_pages[page_index] if page_index<len(main_pages) else '主要问题详见本站前页。', .3, 2.65, 4.5, 4.4, 17)
                text(slide, '特性问题', 5.3, 1.25, 7.5, .6, 24, bold=True)
                selected = photo_chunks[page_index] if page_index<len(photo_chunks) else []
                for i, item in enumerate(selected):
                    fitted_text(slide, item['phrase'], 5.25+i*3.9, 1.95, 3.7, 1, 17)
                photos(slide, selected, (5.25, 3.05, 7.6, 3.95), storage_root)

    severe = [i for i in issues if i['issue_id'] in set(analysis.get('severe_issue_ids') or [])]
    for start in range(0, max(1,len(severe)), 3):
        selected = severe[start:start+3]
        slide = new_page(prs, original[38], ai=True)
        if not selected:
            text(slide, '本次暂无选定的重点问题。', .8, 2, 11, 1)
        width = (12.6-.3*max(0,len(selected)-1))/max(1,len(selected))
        for i, issue in enumerate(selected):
            x = .35+i*(width+.3)
            # Full descriptions remain in station pages and the evidence panel.
            text(slide, '\n'.join(wrap(issue['phrase'], width, 18)), x, 1.25, width, 1.15, 18, bold=True)
            photos(slide, [issue], (x, 2.5, width, 4.0), storage_root)
            text(slide, issue['management_unit'], x, 6.6, width, .45, 14)
