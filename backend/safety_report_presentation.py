"""Editable safety template. Statistics and photos come only from the saved snapshot."""
from collections import Counter
from io import BytesIO
import math
from pathlib import Path
import re
import unicodedata
from PIL import Image, ImageOps
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.chart.data import CategoryChartData
from pptx_compatibility import _normalize_package_fonts
from safety_report_data import ONSITE_PAGES, VIDEO_PAGES, category_rows
from safety_report_analysis import photo_examples

TEMPLATE_FILE = Path(__file__).parent / 'assets/safety_report_template/template.pptx'
RENDERER_VERSION = 'safety-native-121-1'
FONT = 'Microsoft YaHei'
COLORS = ['4472C4', 'C0504D', '70AD47', '8064A2', 'F79646', '4BACC6', 'A5A5A5', '264478']
KEEP_OTHER_CONTINUATION = False


def remove(shape):
    shape._element.getparent().remove(shape._element)


def text_units(text):
    return sum(1 if unicodedata.east_asian_width(c) in 'WF' else .55 for c in str(text))


def textbox(slide, text, x, y, w, h, size=18, color='111111', bold=False, align=PP_ALIGN.LEFT):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = Inches(.025)
    frame.margin_top = frame.margin_bottom = Inches(.02)
    # Bound text before shrinking. Keep the complete source in notes if a legacy
    # scoring clause cannot fit its fixed template box.
    text = str(text or '暂无数据。')
    selected = size
    while selected > 10:
        lines = sum(max(1, math.ceil(text_units(line) / max(1, w * 72 / selected))) for line in text.splitlines())
        if lines * selected * 1.18 <= h * 72 - 4: break
        selected -= 1
    max_chars = max(16, int(w * 72 / selected) * max(1, int((h * 72 - 4) / (selected * 1.18))))
    if text_units(text) > max_chars:
        slide.notes_slide.notes_text_frame.text += '\n完整文字：\n' + text
        cut = max(8, int(max_chars))
        text = text[:cut-1] + '…'
    for index, line in enumerate(text.splitlines()):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.text = line; p.alignment = align; p.space_after = Pt(2); p.line_spacing = 1.12
        for run in p.runs:
            run.font.name = FONT; run.font.size = Pt(selected); run.font.bold = bold
            run.font.color.rgb = RGBColor.from_string(color)
    return shape


def clear_dynamic(slide):
    for shape in list(slide.shapes):
        is_bar = shape.has_text_frame and bool(re.match(r'^\s*\d+[.、]', shape.text)) and shape.top < Inches(1.6)
        if shape.top >= Inches(.99) and not is_bar: remove(shape)
    used = {v for node in slide._element.iter() for k, v in node.attrib.items()
            if k.startswith('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}')}
    for rel in list(slide.part.rels.values()):
        if rel.reltype.endswith(('/image', '/chart', '/comments')) and rel.rId not in used:
            slide.part.drop_rel(rel.rId)


def set_bar(slide, title):
    for shape in slide.shapes:
        if shape.has_text_frame and shape.top < Inches(1.6) and re.match(r'^\s*\d+[.、]', shape.text):
            shape.text_frame.text = title
            for p in shape.text_frame.paragraphs:
                for run in p.runs:
                    run.font.name = FONT; run.font.size = Pt(19); run.font.bold = True
                    run.font.color.rgb = RGBColor(255,255,255)


def chart(slide, rows, x, y, w, h, series=(('问题数量','count'),), pie=False):
    if not rows:
        textbox(slide, '当前范围暂无对应数据。', x, y+1, w, .5, 17, '64748B', align=PP_ALIGN.CENTER)
        return
    data = CategoryChartData(); data.categories = [r.get('name') or r.get('unit_name') or '' for r in rows]
    for label, key in series: data.add_series(label, [float(row.get(key) or 0) for row in rows])
    obj = slide.shapes.add_chart(XL_CHART_TYPE.PIE if pie else XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(x), Inches(y), Inches(w), Inches(h), data).chart
    obj.has_legend = pie
    if pie:
        obj.legend.position = XL_LEGEND_POSITION.RIGHT; obj.legend.font.name = FONT; obj.legend.font.size = Pt(10)
    else:
        obj.category_axis.tick_labels.font.name = FONT; obj.category_axis.tick_labels.font.size = Pt(9)
        obj.value_axis.minimum_scale = 0; obj.value_axis.tick_labels.font.name = FONT; obj.value_axis.tick_labels.font.size = Pt(10)
        if not any(float(r.get(key) or 0) for r in rows for _, key in series): obj.value_axis.maximum_scale = 1
    for plot in obj.plots:
        plot.has_data_labels = True
        labels = plot.data_labels; labels.font.name = FONT; labels.font.size = Pt(10)
        labels.show_percentage = pie; labels.show_value = not pie; labels.number_format = '0%' if pie else '0.########'
        labels.number_format_is_linked = False
    for index, item in enumerate(obj.series):
        if not pie:
            item.format.fill.solid(); item.format.fill.fore_color.rgb = RGBColor.from_string(COLORS[index%len(COLORS)])
        else:
            for i, point in enumerate(item.points):
                point.format.fill.solid(); point.format.fill.fore_color.rgb = RGBColor.from_string(COLORS[i%len(COLORS)])


def value_table(slide, rows, series, y=6.45):
    if not rows: return
    table = slide.shapes.add_table(len(series)+1, len(rows)+1, Inches(.55), Inches(y), Inches(12.2), Inches(.76)).table
    values = [['指标']+[r['unit_name'] for r in rows]] + [[label]+[str(r.get(key) or 0) for r in rows] for label,key in series]
    for i,line in enumerate(values):
        for j,value in enumerate(line):
            cell=table.cell(i,j); cell.text=value; cell.margin_left=cell.margin_right=Inches(.01)
            cell.margin_top=cell.margin_bottom=Inches(.01)
            for p in cell.text_frame.paragraphs:
                p.alignment=PP_ALIGN.CENTER
                for run in p.runs: run.font.name=FONT; run.font.size=Pt(8)


def photo(slide, issue, root, x, y, w, h):
    raw = str(issue.get('issue_photo') or '').lstrip('/')
    path = (root / raw).resolve()
    if raw and path.is_relative_to(root.resolve()) and path.is_file():
        try:
            with Image.open(path) as original:
                image = ImageOps.exif_transpose(original).convert('RGB')
                width,height=image.size
                output=BytesIO();image.save(output,format='JPEG',quality=92);output.seek(0)
            scale=min(w/width,h/height)
            slide.shapes.add_picture(output, Inches(x+(w-width*scale)/2), Inches(y+(h-height*scale)/2),
                width=Inches(width*scale),height=Inches(height*scale))
            return
        except (OSError,ValueError): pass
    textbox(slide,'暂无可用问题照片',x,y+h/2-.2,w,.4,15,'64748B',align=PP_ALIGN.CENTER)


def overview(slide, section):
    clear_dynamic(slide)
    label='（一）四不两直现场检查方面' if section['mode']=='onsite' else '（二）视频扫站方面'
    textbox(slide,label,.45,1.05,12.3,.38,18,bold=True)
    textbox(slide,section['overview'],.45,1.48,12.3,.65,17)
    textbox(slide,section['unit_text'] or '当前范围暂无问题记录。',.45,2.17,12.3,1.6,14)
    series=(('问题数量','issue_count'),('检查站点','station_count'))
    chart(slide,section['units'],.55,3.85,12.2,2.5,series)
    value_table(slide,section['units'],series)


def distribution_page(slide, section, causes=None):
    clear_dynamic(slide)
    rows=section['detail_distribution'] if causes is not None else section['category_distribution']
    text=f"本次检查共发现{'现场' if section['mode']=='onsite' else '视频'}问题{section['total_issue_count']}项。\n"
    text+='\n'.join(f"{r['name']}：{r['count']}项，占比{r['percentage']:.2f}%。" for r in rows)
    if causes is not None:
        text='问题分布\n'+text+'\n产生原因\n'+'\n'.join(f'{i+1}. {value}' for i,value in enumerate(causes))
    textbox(slide,text,.5,1.16,6.1,5.85,18 if causes is None else 15)
    chart(slide,rows,6.8,1.4,6.05,5.6,pie=True)


def evidence_page(slide, title, issues, analysis, chosen, intro, root):
    clear_dynamic(slide);set_bar(slide,title)
    textbox(slide,intro,.5,1.65,12.3,.78,17)
    selected=chosen[:3]
    if not selected:
        textbox(slide,'当前范围暂无可展示的问题证据。',.6,3.3,12.1,.6,18,'64748B',align=PP_ALIGN.CENTER)
    for i,issue in enumerate(selected):
        x=.5+i*4.18
        photo(slide,issue,root,x,2.55,3.95,2.25)
        textbox(slide,(issue.get('caption') or issue['description'])+'\n'+issue['station_name'],x,4.9,3.95,.85,14,align=PP_ALIGN.CENTER)
        requirement=issue.get('requirement') or '该规范未维护评分说明，请核查原规范。'
        textbox(slide,f'规范要求 {i+1}：\n'+requirement,x,5.94,3.95,1.31,12,'A12626')
        slide.notes_slide.notes_text_frame.text += f"\n照片{i+1}：问题ID {issue['issue_id']}，{issue['station_name']}\n问题原文：{issue['description']}\n评分说明：{requirement}\n"


def build_safety_presentation(report, output_path, storage_root=None):
    if report.get('safety_template_version') != 1:
        raise ValueError('安全质量报告已更换模板，请先重新生成报告。')
    prs=Presentation(TEMPLATE_FILE); source=list(prs.slides); root=Path(storage_root or '.')
    if len(source)!=31: raise ValueError('安全报告模板页数异常。')
    for slide in source:
        slide.notes_slide.notes_text_frame.text=''
        for rel in list(slide.part.rels.values()):
            if rel.reltype.endswith('/comments'): slide.part.drop_rel(rel.rId)
    label=report['month_label']
    for shape in source[0].shapes:
        if shape.has_text_frame and re.search(r'\d{4}年\s*\d+月',shape.text):
            for index, paragraph in enumerate(shape.text_frame.paragraphs):
                for j, run in enumerate(paragraph.runs):
                    run.text = label if index == 0 and j == 0 else ''
                    # Retain the template's explicit color, including its hidden date placeholder.
                    if run.text and len(label) > 12: run.font.size = Pt(20)
    sections={s['mode']:s for s in report['sections']}
    overview(source[2],sections['onsite']);overview(source[3],sections['video'])
    clear_dynamic(source[5])
    for i,finding in enumerate(report['typical_findings']):
        x=.65+i*6.3
        textbox(source[5],('现场' if finding['mode']=='onsite' else '视频')+'巡查典型问题',x,1.25,5.7,.5,21,bold=True)
        issue=(finding['issues'] or [{}])[0]
        photo(source[5],issue,root,x,1.9,5.7,3.5)
        caption=finding['summary']+ ('\n'+issue['station_name'] if issue.get('station_name') else '')
        textbox(source[5],caption,x,5.65,5.7,1.3,18,align=PP_ALIGN.CENTER)
    distribution_page(source[7],sections['onsite']);distribution_page(source[8],sections['video'])
    distribution_page(source[10],sections['onsite'],report['analysis_causes']['onsite'])
    distribution_page(source[11],sections['video'],report['analysis_causes']['video'])
    issues=report['safety_issues'];analyses=report['safety_analysis'];focus=report['focus_category']
    key='onsite:content:'+focus;value=analyses.get(key,{})
    selected=category_rows(issues,'onsite','content:'+focus)
    names='、'.join(g['name'] for g in value.get('groups',[])[:4])
    evidence_page(source[12],'1.月度重点工作类问题',selected,value,photo_examples(selected,value,3),
        f'本月重点工作类为{focus or "暂无"}，共{len(selected)}项。主要问题集中在{names or "暂无对应问题"}方面。',root)
    targets=[(13,'设备设施',0),(14,'设备设施',3),(15,'污染防治',0),(16,'能力培训和意识',0),(17,'风险合规',0),(18,'其他隐患类',0)]
    if KEEP_OTHER_CONTINUATION: targets.append((19,'其他隐患类',3))
    titles={key:title for key,title,_ in ONSITE_PAGES}
    for page,category,offset in targets:
        selected=category_rows(issues,'onsite',category);value=analyses.get('onsite:'+category,{})
        names='、'.join(g['name'] for g in value.get('groups',[])[:4])
        evidence_page(source[page],titles[category],selected,value,photo_examples(selected,value,offset+3)[offset:],
            f'本月{category}问题共{len(selected)}项，其中问题主要集中在{names or "暂无对应问题"}。',root)
    for page,(category,title) in enumerate(VIDEO_PAGES,20):
        selected=category_rows(issues,'video',category);value=analyses.get('video:'+category,{})
        unit_counts=Counter(row['unit_name'] for row in selected)
        most=sorted(unit_counts.items(),key=lambda item:(-item[1],item[0]))[:1]
        share=f"其中{most[0][0]}存在{most[0][1]}项，占比{most[0][1]/len(selected)*100:.1f}%。" if most else ''
        names='、'.join(g['name'] for g in value.get('groups',[])[:4])
        evidence_page(source[page],title,selected,value,photo_examples(selected,value,3),
            f'本月{category}问题共{len(selected)}项。{share}问题主要集中在{names or "暂无对应问题"}。',root)
    for page,key in [(25,'work_suggestions'),(29,'rectification_suggestions')]:
        clear_dynamic(source[page])
        items=report.get(key) or []
        body='\n\n'.join(f"{i+1}、{item['title']}\n{item['content']}" for i,item in enumerate(items))
        textbox(source[page],body or '当前范围暂无对应问题，无需新增建议。',.65,1.15,12,5.95,21)
    cutoff=(report.get('summary') or {}).get('date_to') or label
    for page,mode in [(27,'onsite'),(28,'video')]:
        clear_dynamic(source[page]);rows=report['pending_rectification'].get(mode) or []
        name='现场' if mode=='onsite' else '视频'
        narrative=f'各管理片区及合资公司{name}检查问题整改情况（数据截至{cutoff}）\n'
        narrative+='；'.join(f"{r['unit_name']}待签名{r['pending_sign']}项、待整改{r['pending_rectification']}项" for r in rows)
        textbox(source[page],narrative,.55,1.2,12.2,2.5,17)
        series=(('待签名','pending_sign'),('待整改','pending_rectification'))
        chart(source[page],rows,.55,3.85,12.2,2.5,series);value_table(source[page],rows,series)
    if not KEEP_OTHER_CONTINUATION:
        node=prs.slides._sldIdLst[19];prs.part.drop_rel(node.rId);prs.slides._sldIdLst.remove(node)
    _normalize_package_fonts(prs)
    output_path=Path(output_path);output_path.parent.mkdir(parents=True,exist_ok=True);prs.save(output_path)
    return {'ppt_path':str(output_path),'slide_count':len(prs.slides)}
