"""Adaptive editable two-column chapter, following reference slide 17."""
from copy import deepcopy
import re
import unicodedata
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE,MSO_CONNECTOR
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.text import PP_ALIGN
from safety_report_data import unit_label
from safety_report_presentation import photo,textbox

FONT='Microsoft YaHei'

def wrap(text,capacity=29):
    lines=[];line='';width=0
    for char in text:
        size=1 if unicodedata.east_asian_width(char) in ('W','F') else .55
        if width+size>capacity and line:lines.append(line);line='';width=0
        line+=char;width+=size
    if line:lines.append(line)
    return lines

def panels(category):
    """Bound lines before pagination, never crop descriptions or station lists."""
    intro=f"发现问题共{category['count']}次，涉及{'、'.join(category['station_names'])}。"
    lines=[(line,'',None) for line in wrap(intro)];output=[];photos=[]
    def flush():
        nonlocal lines,photos
        if lines:output.append({'category':category,'lines':lines,'photos':photos,'continued':bool(output)})
        lines=[];photos=[]
    # Very long station lists may need a continuation panel of their own.
    while len(lines)>12:
        output.append({'category':category,'lines':lines[:12],'photos':[],'continued':bool(output)})
        lines=lines[12:]
    for number,group in enumerate(category['groups'],1):
        prefix=f"{number}、{group['stage']}："
        body=(group['summary'] or '尚未准备环节概括')+f"（{'、'.join(group['station_names'])}）。"
        text_lines=wrap(prefix+body)
        if (len(lines)+len(text_lines)>12 or len(photos)>=2) and lines:flush()
        bold_remaining=len(prefix)
        for line in text_lines:
            if len(lines)>=12:flush()
            bold=line[:bold_remaining];bold_remaining=max(0,bold_remaining-len(line))
            lines.append((line,bold,group['key']))
            if group['photo_ids'] and not any(p['key']==group['key'] for p in photos):
                photos.append(group)
    flush()
    return output

def clone_slide(prs,source):
    slide=prs.slides.add_slide(source.slide_layout)
    for shape in list(slide.shapes):shape._element.getparent().remove(shape._element)
    for shape in source.shapes:
        element=deepcopy(shape._element)
        for node in element.iter():
            for key,value in list(node.attrib.items()):
                if key.startswith('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'):
                    if not value:
                        del node.attrib[key]
                        continue
                    rel=source.part.rels[value]
                    node.set(key,slide.part.relate_to(rel.target_ref if rel.is_external else rel.target_part,rel.reltype,rel.is_external))
        slide.shapes._spTree.insert_element_before(element,'p:extLst')
    return slide

def add_unit_chapter(prs,report,root):
    if 'unit_discoveries' not in report:return
    from service_report_presentation import walk,write
    divider=clone_slide(prs,prs.slides[1])
    for shape in walk(divider.shapes):
        if not shape.has_text_frame:continue
        if re.search(r'^0[12]$',shape.text.strip()) or '检查基本情况' in shape.text or '各片区问题' in shape.text:
            active='各片区问题' in shape.text or shape.text.strip()=='02'
            if '各片区问题' in shape.text:write(shape,['各片区问题发现'],21)
            for p in shape.text_frame.paragraphs:
                for run in p.runs:run.font.color.rgb=RGBColor.from_string('0D3063' if active else '858585')
    by_id={r['issue_id']:r for r in report['service_issues']}
    if not report['unit_discoveries']:
        slide=prs.slides.add_slide(prs.slides[12].slide_layout)
        for shape in list(slide.shapes):shape._element.getparent().remove(shape._element)
        textbox(slide,'各片区问题发现',.5,.25,11,.6,26,'364F83',True)
        textbox(slide,'当前数据范围暂无审核通过的现场服务问题。',1,3,11,1,20,'64748B')
        return
    for unit in report['unit_discoveries']:
        queue=[panel for category in unit['categories'] for panel in panels(category)]
        for offset in range(0,len(queue),2):
            slide=prs.slides.add_slide(prs.slides[12].slide_layout)
            for shape in list(slide.shapes):shape._element.getparent().remove(shape._element)
            textbox(slide,unit_label(unit['unit_name'])+('（续）' if offset else ''),.45,.22,11.5,.65,27,'364F83',True)
            line=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(6.67),Inches(.95),Inches(6.67),Inches(7.18))
            line.line.color.rgb=RGBColor.from_string('7189B7');line.line.width=Pt(1)
            line.line.dash_style=MSO_LINE_DASH_STYLE.DASH
            for side,panel in enumerate(queue[offset:offset+2]):
                x=.55+side*6.48;w=5.7;category=panel['category']
                heading=f"{category['number']}. {category['name']}"+('（续）' if panel['continued'] else '')
                shadow=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x+.06),Inches(1.10),Inches(w),Inches(.53))
                shadow.fill.solid();shadow.fill.fore_color.rgb=RGBColor.from_string('999999');shadow.line.fill.background()
                bar=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(1.04),Inches(w),Inches(.53))
                bar.fill.solid();bar.fill.fore_color.rgb=RGBColor.from_string('394F83');bar.line.fill.background()
                textbox(slide,heading,x+.1,1.1,w-.2,.42,18,'FFFFFF',True)
                body=slide.shapes.add_textbox(Inches(x),Inches(1.82),Inches(w),Inches(2.65))
                frame=body.text_frame;frame.word_wrap=False
                frame.margin_left=frame.margin_right=frame.margin_top=frame.margin_bottom=0
                for i,(text,bold,_) in enumerate(panel['lines']):
                    p=frame.paragraphs[0] if i==0 else frame.add_paragraph()
                    p.space_after=Pt(0);p.line_spacing=Pt(15.5)
                    spans=[(bold,True),(text[len(bold):],False)]
                    if text.startswith('发现问题共'):
                        spans=[(part,False) for part in re.split(r'(\d+次)',text)]
                    for part,strong in spans:
                        if not part:continue
                        run=p.add_run();run.text=part;run.font.name=FONT;run.font.size=Pt(13.5);run.font.bold=strong
                        run.font.color.rgb=RGBColor.from_string('C00000' if re.fullmatch(r'\d+次',part) else '111111')
                images=panel['photos'];count=len(images)
                image_top=max(3.25,1.82+len(panel['lines'])*15.5/72+.2)
                for i,group in enumerate(images):
                    image_width=(w-.18*(count-1))/count;left=x+i*(image_width+.18)
                    row=by_id.get(group['photo_ids'][0])
                    if not row:continue
                    image=photo(slide,row,root,left,image_top,image_width,6.62-image_top)
                    station=row['station_name'];station+= '' if station.endswith('加油站') else '加油站'
                    caption_top=min(6.69,(image.top+image.height)/914400+.07)
                    textbox(slide,f"【{station}】 # {row['issue_id']}\n{group['stage']}",left,caption_top,image_width,.65,10,'111111',True,PP_ALIGN.CENTER)
