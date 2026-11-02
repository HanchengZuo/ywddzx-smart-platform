"""Native styles measured from reference 0804, pages 7, 8, 29, 30 and 32.

Only these five page kinds use this module. Existing snapshot data, pagination,
photos and the shared transparent logo remain authoritative.
"""
import re
import unicodedata

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

RENDERER_VERSION = 'quality-0804-v12.6.5-1'
BLACK, WHITE = RGBColor.from_string('000000'), RGBColor.from_string('FFFFFF')
COLORS = {'ink': BLACK, 'red': RGBColor.from_string('FF0000'),
    'blue': RGBColor.from_string('2E75B6'), 'label': RGBColor.from_string('4472C4'),
    'typical': RGBColor.from_string('C00000')}
FONT = 'Microsoft YaHei'


def _lines(text, width, size, indent=0):
    capacity = max(1, width*72/size)
    used, lines = indent*72/size, 1
    for char in str(text):
        if char == '\n':
            lines += 1; used = 0
            continue
        units = 1 if unicodedata.east_asian_width(char) in ('F', 'W') else .55
        if used+units > capacity:
            lines += 1; used = 0
        used += units
    return lines


def text(slide, blocks, box, size=18, *, minimum=11, spacing=1.5,
         margins=(.1, .1, .05, .05), align=PP_ALIGN.LEFT, name='quality-reference-text'):
    x, y, width, height = box
    left, right, top, bottom = margins
    # Fit complete paragraphs, including first-line indents and explicit breaks.
    chosen = size
    while chosen > minimum:
        required = sum(_lines(''.join(str(r.get('text') or '') for r in b['runs']),
            width-left-right, chosen, b.get('indent', 0))*chosen*spacing/72
            + b.get('after', 0)/72 for b in blocks)
        if required <= height-top-bottom:
            break
        chosen -= .5
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(height))
    shape.name = name
    frame = shape.text_frame
    frame.clear(); frame.word_wrap = True; frame.vertical_anchor = MSO_ANCHOR.TOP
    frame.margin_left, frame.margin_right = Inches(left), Inches(right)
    frame.margin_top, frame.margin_bottom = Inches(top), Inches(bottom)
    for index, block in enumerate(blocks):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.alignment = align; p.line_spacing = spacing
        p.space_before = Pt(0); p.space_after = Pt(block.get('after', 0))
        ppr = p._p.get_or_add_pPr()
        ppr.set('marL', '0'); ppr.set('indent', str(Inches(block.get('indent', 0))))
        ppr.append(OxmlElement('a:buNone'))
        p.font.name = FONT; p.font.size = Pt(chosen); p.font.bold = True
        for item in block['runs']:
            run = p.add_run(); run.text = str(item.get('text') or '')
            run.font.name = FONT; run.font.size = Pt(chosen); run.font.bold = True
            run.font.color.rgb = COLORS.get(item.get('tone'), BLACK)
    return shape


def _block(value, tone='ink', **kwargs):
    return {'runs': [{'text': value, 'tone': tone}], **kwargs}


def _rect(slide, box, color, name):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *(Inches(v) for v in box))
    shape.name = name; shape.fill.solid(); shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    shape._element.spPr.append(OxmlElement('a:effectLst'))
    for effect in shape._element.xpath('./p:style/a:effectRef'):
        effect.set('idx', '0')
    return shape


def _slide(builder, data, title, accent='', position=(.6931, .3372)):
    slide = builder._blank_slide(background=WHITE, footer=False)
    builder.page_number += 1
    prefix = data.get('title_prefix') or data.get('title') or title
    if accent and prefix.endswith(accent):
        prefix = prefix[:-len(accent)]
    header = text(slide, [{'runs': [{'text': prefix}, {'text': accent, 'tone': 'blue'}]}],
        (*position, 10.9, .5359), size=28, minimum=28, spacing=1,
        name='quality-reference-header')
    for run in header.text_frame.paragraphs[0].runs:
        run.font.size = Pt(20 if run.text == accent and accent else 28)
    _rect(slide, (0, .8837, builder.prs.slide_width/Inches(1), .0781),
        RGBColor.from_string('3F95D2'), 'quality-reference-rule')
    builder._add_quality_logo(slide)
    return slide


def _band(slide, title, box):
    x, y, w, h = box
    _rect(slide, (x+.08, y+.08, w, h), RGBColor(128, 128, 128), 'quality-band-shadow')
    _rect(slide, box, RGBColor.from_string('2E75B6'), 'quality-band')
    shape = text(slide, [_block(title)], box, size=24, minimum=24, spacing=1,
        name='quality-band-label')
    shape.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    for run in shape.text_frame.paragraphs[0].runs:
        run.font.color.rgb = WHITE


def _table(builder, slide, headers, rows, box, columns, *, header_height, row_heights, narrative=False):
    table = builder._quality_table(slide, headers, rows, *box, weights=columns,
        header_fill=RGBColor.from_string('88E4F6'), header_color=BLACK, body_fills=(WHITE,))
    table.rows[0].height = Inches(header_height)
    for ri, height in enumerate(row_heights, 1):
        table.rows[ri].height = Inches(height)
    for ri, row in enumerate(table.rows):
        for ci, cell in enumerate(row.cells):
            cell.margin_left = cell.margin_right = Inches(.015)
            cell.margin_top = cell.margin_bottom = Inches(.015)
            size = 14 if ri == 0 else 11 if narrative and ci >= 2 else 12
            size = builder._fit_quality_text_size(cell.text, columns[ci]-.03,
                row.height/Inches(1), maximum=size, minimum=8, line_height=1.1)
            p = cell.text_frame.paragraphs[0]
            p.font.size = Pt(size); p.font.bold = False; p.font.color.rgb = BLACK
            p.line_spacing = 1.1; p.space_before = p.space_after = Pt(0)
            # Explicit DrawingML edges survive WPS/Office table-style differences.
            tcpr = cell._tc.get_or_add_tcPr()
            for edge_index, edge in enumerate(('lnL', 'lnR', 'lnT', 'lnB')):
                for node in list(tcpr):
                    if node.tag.rsplit('}', 1)[-1] == edge:
                        tcpr.remove(node)
                line = OxmlElement('a:'+edge)
                line.set('w', '6350'); line.set('cap', 'flat'); line.set('cmpd', 'sng')
                fill = OxmlElement('a:solidFill'); color = OxmlElement('a:srgbClr')
                color.set('val', '000000'); fill.append(color); line.append(fill)
                dash = OxmlElement('a:prstDash'); dash.set('val', 'solid'); line.append(dash)
                tcpr.insert(edge_index, line)
    return table


def finding(builder, data):
    slide = _slide(builder, data, '二、检查发现-', data.get('title_accent') or '发现问题')
    source = data.get('text_blocks') or [_block(value) for value in data.get('text_lines') or []]
    blocks = []
    for index, block in enumerate(source):
        runs = [dict(r) for r in block.get('runs') or []]
        if runs:
            runs[0]['text'] = str(runs[0].get('text') or '').lstrip('\u3000')
        blocks.append({'runs': runs, 'indent': .59375 if index else 0})
    text(slide, blocks, (.7424, 1.5344, 6.4792, 5.1173), size=20, minimum=14,
        name='quality-finding-narrative')
    records = data.get('rows') or []
    rows = [[r.get('sequence'), r.get('section'), r.get('problem_type'), r.get('count'), r.get('percentage')] for r in records]
    table = _table(builder, slide, ['序号', '环节排前三', '问题类型', '问题数量', '占比/%'], rows,
        (7.6812, 1.2114, 4.5455, 5.7647), [.5578, 1.0458, 1.0458, .948, .948],
        header_height=.8993, row_heights=[4.8654/max(1, len(rows))]*len(rows))
    for ri, row in enumerate(records, 1):
        for ci in range(1, 5):
            if row.get('section') == '油站环节' or (row.get('sequence') == '合计' and ci == 3):
                table.cell(ri, ci).text_frame.paragraphs[0].font.color.rgb = COLORS['red']


def prohibited(builder, data):
    slide = _slide(builder, data, '二、检查发现-', data.get('title_accent') or '发现问题')
    _band(slide, data.get('subtitle') or '1.禁止项问题', (.5757, 1.0674, 11.5194, .6299))
    narrative = str(data.get('narrative') or '')
    parts = re.split(r'(禁止项问题[^，。]*|油库环节[^、，。]*|运输环节[^、，。]*|油站环节[^、，。]*)', narrative)
    runs = []
    for value in parts:
        if value.startswith('禁止项问题'):
            runs.extend([{'text': '禁止项问题'}, {'text': value[len('禁止项问题'):], 'tone': 'red'}])
        else:
            tone = 'blue' if value.startswith(('油库环节', '运输环节')) else 'red' if value.startswith('油站环节') else 'ink'
            runs.append({'text': value, 'tone': tone})
    text(slide, [{'runs': runs}], (.5757, 1.8914, 11.7202, .74), size=20, minimum=16,
        margins=(.1, .1, .02, .02),
        name='quality-prohibited-narrative')
    rows = [[r.get('sequence'), '加油站环节', r.get('unit_name'), r.get('description'), r.get('penalty') or ''] for r in data.get('rows') or []]
    if not rows:
        rows = [['-', '加油站环节', '-', '当前月份暂无禁止项问题', '']]
    heights = [max(.4, _lines(r[3] or '', 4.9889, 11)*11*1.15/72+.08) for r in rows]
    factor = min(1, (4.2-.4336)/sum(heights))
    heights = [h*factor for h in heights]
    _table(builder, slide, ['序号', '环节', '基层单位名称', '禁止项管理规定', '处罚情况'], rows,
        (.6885, 2.6814, 11.7202, .4336+sum(heights)), [1.1226, 1.4245, 1.3868, 5.0189, 2.7673],
        header_height=.4336, row_heights=heights, narrative=True)


def management_trace(builder, data):
    slide = _slide(builder, data, '三、管理追溯', position=(.6368, .3897))
    _band(slide, '典型问题：', (0, 1.1201, 8.3104, .6299))
    issue = data.get('typical_issue') or {}
    station = str(issue.get('station_name') or '典型问题')
    description = builder._issue_description(issue)
    text(slide, [_block('典型问题：', 'typical'), _block(station+'：'+description, 'typical', indent=.5)],
        (.6924, 1.95, 8.1035, 1.12), size=20, minimum=14, name='quality-typical-issue')
    blocks = [{'runs': [{'text': str(r.get('label') or '').rstrip('：:')+'：', 'tone': 'label'},
        {'text': r.get('content') or '-'}]} for r in data.get('analysis_items') or []]
    text(slide, blocks, (.6924, 3.1465, 7.9688, 3.7347), size=18,
        align=PP_ALIGN.JUSTIFY, name='quality-trace-causes')
    # Match the rectangular photo slot, but never crop a replacement issue photo.
    x, y, w, h = 8.7958, 1.75, 4.284, 5.0306
    frame = _rect(slide, (x, y, w, h), RGBColor(248, 249, 251), 'quality-trace-photo-frame')
    source, iw, ih = builder._prepare_picture_source(issue.get('issue_photo'))
    if source:
        pw, ph = builder._contain_size(iw, ih, w-.12, h-.12)
        slide.shapes.add_picture(source, Inches(x+(w-pw)/2), Inches(y+(h-ph)/2),
            width=Inches(pw), height=Inches(ph))
    else:
        builder._set_shape_text(frame, '暂无问题照片', 11, RGBColor(100, 116, 139))


def trace_analysis(builder, data):
    slide = _slide(builder, data, '三、管理追溯', position=(.6368, .3897))
    _band(slide, data.get('subtitle') or '典型问题分析', (0, 1.1201, 8.3104, .6299))
    conclusion = re.sub(r'^综上所述[：:]\s*', '', str(data.get('conclusion') or '暂无分析结论。'))
    blocks = [{'runs': [{'text': '综上所述：', 'tone': 'label'}, {'text': conclusion}]},
        _block(''), _block('改进措施：', 'label')]
    blocks += [_block(f"{i}、{r.get('level') or ''}：{r.get('content') or ''}")
        for i, r in enumerate(data.get('improvement_measures') or [], 1)]
    text(slide, blocks, (.8375, 1.9444, 11.5076, 5.1785), size=18,
        align=PP_ALIGN.JUSTIFY, name='quality-trace-conclusion')


def work_plan(builder, data):
    slide = _slide(builder, data, '四、工作计划', position=(.7835, .2713))
    blocks = []
    for i, row in enumerate(data.get('items') or [], 1):
        blocks += [_block(f"{i}、{row.get('title') or ''}", 'label', indent=.5),
            _block(row.get('content') or '', indent=.5)]
    text(slide, blocks, (.7833, 1.0924, 11.6458, 6.0514), size=18,
        align=PP_ALIGN.JUSTIFY, name='quality-work-plan')
