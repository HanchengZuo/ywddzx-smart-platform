"""Thirteen editable template pages, adapted from 4:3 to 16:9 without rasterizing text/charts."""
from copy import deepcopy
from pathlib import Path
from collections import Counter
import math
import re
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx_compatibility import _normalize_package_fonts
from safety_report_presentation import photo,textbox
from safety_report_data import unit_label

TEMPLATE_FILE=Path(__file__).parent/'assets/service_report_template/template.pptx'
RENDERER_VERSION='service-native-124-1'
FONT='Microsoft YaHei'

def walk(shapes):
    for shape in shapes:
        yield shape
        if shape.shape_type==MSO_SHAPE_TYPE.GROUP:yield from walk(shape.shapes)

def adapt(prs):
    factor=(40/3)/(prs.slide_width/914400)
    for owner in [*prs.slide_masters,*prs.slide_layouts,*prs.slides]:
        for shape in owner.shapes:
            if shape.is_placeholder and not shape._element.xpath('./p:spPr/a:xfrm'):
                continue  # Inherited geometry is already adapted with its layout/master.
            left,width=shape.left,shape.width
            shape.left=int(left*factor)
            if shape.shape_type==MSO_SHAPE_TYPE.PICTURE and shape.height<Inches(1):
                shape.left+=int(width*(factor-1)/2)
            else:shape.width=int(width*factor)
            if shape.has_table:
                for column in shape.table.columns:column.width=int(column.width*factor)
    prs.slide_width=Inches(40/3);prs.slide_height=Inches(7.5)

def write(shape,lines,size=15,red=False,highlights=()):
    paragraphs=list(shape.text_frame.paragraphs)
    templates=[deepcopy(p._p) for p in paragraphs]
    shape.text_frame.clear();shape.text_frame.word_wrap=True
    # Preserve the original bullets and paragraph spacing while replacing only dynamic content.
    for index,line in enumerate(lines):
        p=shape.text_frame.paragraphs[0] if index==0 else shape.text_frame.add_paragraph()
        original=templates[min(index,len(templates)-1)]
        style=original.find('.//'+qn('a:rPr'))
        props=original.find(qn('a:pPr'))
        if props is not None:
            existing=p._p.find(qn('a:pPr'))
            if existing is not None:p._p.remove(existing)
            p._p.insert(0,deepcopy(props))
        pattern=r'\d+(?:\.\d+)?(?=[座个项])' if red else r'(?!)'
        if highlights:pattern='|'.join([*(re.escape(text) for text in highlights),pattern])
        offset=0
        for match in [*re.finditer(pattern,line),None]:
            end=match.start() if match else len(line)
            for text,color in [(line[offset:end],'222222'),(match[0] if match else '', 'C00000')]:
                if not text:continue
                run=p.add_run();run.text=text
                if style is not None:run._r.insert(0,deepcopy(style))
                run.font.name=FONT;run.font.size=Pt(size)
                if match and color=='C00000':run.font.color.rgb=RGBColor.from_string(color);run.font.bold=True
            offset=match.end() if match else len(line)
        p.space_after=Pt(4);p.line_spacing=1.12

def by_text(slide,prefix):
    return next(s for s in walk(slide.shapes) if s.has_text_frame and s.text.strip().startswith(prefix))

def chart(shape,categories,series,title=None):
    data=CategoryChartData();data.categories=categories or ['暂无数据']
    for name,values,fmt in series:data.add_series(name,values if categories else [0],number_format=fmt)
    for node in shape.chart._chartSpace.xpath('.//c:externalData'):
        identifier=node.get(qn('r:id'))
        if identifier and identifier in shape.chart.part.rels:shape.chart.part.drop_rel(identifier)
        node.getparent().remove(node)
    shape.chart.replace_data(data)
    for node in shape.chart._chartSpace.xpath('.//c:dLbl/c:tx'):
        node.getparent().remove(node)  # Original hand-edited labels must not survive new data.
    for node in shape.chart._chartSpace.xpath('.//c:scaling/c:max | .//c:scaling/c:min | .//c:valAx/c:majorUnit | .//c:valAx/c:minorUnit | .//c:minorGridlines'):
        node.getparent().remove(node)
    for plot in shape.chart._chartSpace.xpath('.//c:barChart | .//c:lineChart'):
        axis_ids={n.get('val') for n in plot.findall(qn('c:axId'))}
        formats=plot.xpath('.//c:val//c:formatCode')
        fmt=formats[0].text if formats else '0'
        values=[float(n.text) for n in plot.xpath('.//c:val//c:pt/c:v')]
        maximum=max(values,default=0)
        step=max(1,math.ceil(maximum/5)) if fmt=='0' else max(.1,round(maximum/5,1))
        limit=max(step,math.ceil(maximum/step)*step)
        if fmt=='0%':step,limit=.2,1
        for axis in shape.chart._chartSpace.xpath('.//c:valAx'):
            if axis.find(qn('c:axId')).get('val') not in axis_ids:continue
            scale=axis.find(qn('c:scaling'))
            for key,value in [('min',0),('max',limit)]:
                node=OxmlElement('c:'+key);node.set('val',str(value));scale.append(node)
            number=axis.find(qn('c:numFmt'))
            if number is not None:number.set('formatCode',fmt);number.set('sourceLinked','0')
            major=OxmlElement('c:majorUnit');major.set('val',str(step))
            following=next((n for n in axis if n.tag in (qn('c:dispUnits'),qn('c:extLst'))),None)
            if following is None:axis.append(major)
            else:axis.insert(axis.index(following),major)
    if title:
        shape.chart.has_title=True
        shape.chart.chart_title.text_frame.text=title
        for p in shape.chart.chart_title.text_frame.paragraphs:
            for r in p.runs:r.font.name=FONT;r.font.size=Pt(12);r.font.bold=True
    for node in shape.chart._chartSpace.xpath('.//c:axId | .//c:crossAx'):
        node.set('val',str(int(node.get('val'))%(2**32)))
    for series_obj,(_,_,fmt) in zip(shape.chart.series,series):
        # Freeze the cached number format for older WPS, rather than relying on workbook defaults.
        for node in series_obj._element.xpath('.//c:numCache/c:formatCode'):node.text=fmt
    for plot in shape.chart.plots:
        if not plot.has_data_labels:continue
        plot.data_labels.font.name=FONT
        plot.data_labels.font.size=Pt(9)

def table(shape,headers,rows,height=None):
    grid=shape.table
    if height:shape.height=Inches(height)
    template=deepcopy(grid._tbl.tr_lst[-1])
    while len(grid.rows)>len(rows)+1:grid._tbl.remove(grid._tbl.tr_lst[-1])
    while len(grid.rows)<len(rows)+1:grid._tbl.append(deepcopy(template))
    values=[headers,*rows]
    desired_height=shape.height
    widths=[c.width/914400 for c in grid.columns]
    weights=[max(1,max(math.ceil(len(str(text))/max(1,w*72/10)) for text,w in zip(row,widths))) for row in values]
    total=sum(weights)
    for index,row in enumerate(grid.rows):
        row.height=int(desired_height*weights[index]/total)
        for cell,text in zip(row.cells,values[index]):
            frame=cell.text_frame;frame.clear();frame.word_wrap=True
            cell.margin_top=cell.margin_bottom=Inches(.015)
            p=frame.paragraphs[0];p.text=str(text);p.space_after=Pt(0)
            for run in p.runs:
                run.font.name=FONT;run.font.size=Pt(10);run.font.bold=index==0
                run.font.color.rgb=RGBColor.from_string('FFFFFF' if index==0 else '1F2937')
            cell.fill.solid();cell.fill.fore_color.rgb=RGBColor.from_string('4F81BD' if index==0 else 'F2F6FC' if index%2==0 else 'FFFFFF')

def photo_slots(slide):
    pictures=[s for s in slide.shapes if s.shape_type==MSO_SHAPE_TYPE.PICTURE and s.top>Inches(1)]
    slots=[tuple(v/914400 for v in (s.left,s.top,s.width,s.height)) for s in pictures]
    for s in pictures:s._element.getparent().remove(s._element)
    return sorted(slots,key=lambda s:(round(s[1],1),s[0]))

def picture(slide,row,root,box,label=''):
    x,y,w,h=box
    if row:
        caption_height=.45 if label else .25
        photo(slide,row,root,x,y,w,max(.3,h-caption_height),bottom=True)
        caption=row['station_name']+' #'+str(row['issue_id'])+('\n'+label if label else '')
        textbox(slide,caption,x,y+h-caption_height,w,caption_height,9,'294B65',align=PP_ALIGN.CENTER)
    else:textbox(slide,'暂无对应问题照片',x,y+h/2-.15,w,.3,12,'64748B',align=PP_ALIGN.CENTER)

def build_service_presentation(report,output_path,storage_root):
    if report.get('data_policy_version')!='service-first-chapter-124-1':
        raise ValueError('现场服务报告模板已更新，请先重新生成报告。')
    prs=Presentation(TEMPLATE_FILE);adapt(prs);slides=list(prs.slides);root=Path(storage_root)
    if len(slides)!=13:raise ValueError('现场服务第一章模板页数应为13页。')
    label=report['month_label'];summary=report['summary'];scope=report['scope'];units=scope['units'];modes=report['mode_summaries']
    for shape in walk(slides[0].shapes):
        if shape.has_text_frame and '业务督导中心现场服务' in shape.text:
            years=(summary.get('date_from','')[:4],summary.get('date_to','')[:4])
            year_label=years[0]+('—'+years[1] if years[0]!=years[1] else '')+'年'
            write(shape,[year_label+'业务督导中心现场服务','巡检报告'],24)
        elif shape.has_text_frame and re.fullmatch(r'\d{4}年\d+月',shape.text.strip()):
            shape.width=Inches(3.62);shape.left=Inches(7.02);write(shape,[label],14 if '至' not in label else 12)
    for shape in walk(slides[1].shapes):
        if shape.has_text_frame and '月检查基本情况' in shape.text:write(shape,[label+'检查基本情况'],15 if '至' in label else 18)
        if shape.has_text_frame and shape.text=='CONTENTS':write(shape,['CONTENTS'],25)
    # Cumulative, cutoff-aware rectification replaces the original previous-month calculation.
    rect=report['cumulative_rectification'];s=slides[2]
    body=by_text(s,'截至')
    write(by_text(s,'上月问题整改情况'),['截至报告期末问题整改情况'],23)
    body.height=Inches(.9);write(body,[rect['narrative']],14,True)
    rows=rect['units'];graph=next(sh for sh in s.shapes if sh.has_chart)
    chart(graph,[unit_label(r['unit_name']) for r in rows],[('已整改',[r['rectified_count'] for r in rows],'0'),('未闭环',[r['pending_count'] for r in rows],'0'),('整改率',[r['rate'] for r in rows],'0%')],rect['cutoff']+'累计各片区整改情况')
    # Overall text and two rows of three real photos.
    s=slides[3];body=by_text(s,'2026年');write(body,[report['overview_text'],report['focus_text']],15,True,
        [row['name'] for row in scope['categories'][:3]])
    slots=photo_slots(s);groups=scope['categories'][:2];by_id={r['issue_id']:r for r in report['service_issues']}
    labels=[sh for sh in s.shapes if sh.has_text_frame and sh.text in ('暖心服务','安全管理')]
    for i,shape in enumerate(sorted(labels,key=lambda sh:sh.top)):write(shape,[groups[i]['name'] if i<len(groups) else '暂无问题类别'],15)
    for i,box in enumerate(slots[:6]):
        ids=report['category_examples'].get(groups[i//3]['name'],[]) if i//3<len(groups) else []
        picture(s,by_id.get(ids[i%3]) if i%3<len(ids) else None,root,box)
    # Unit scope and regional comparisons, always in the business's fixed unit order.
    grid=next(sh for sh in slides[4].shapes if sh.has_table)
    table(grid,['片区 / 单位','站点数','问题数','加油站列表'],[[unit_label(r['unit_name']),r['station_count'],r['issue_count'],'、'.join(r['station_names'])] for r in units],5.65)
    s=slides[5];body=by_text(s,'本月巡检');write(body,[f"本次巡检（视频+现场）覆盖{scope['station_count']}座加油站，共发现问题{scope['issue_count']}个，站均问题数{scope['average_issue_count']:.1f}个。"],15,True)
    graphs=[sh for sh in s.shapes if sh.has_chart]
    chart(graphs[0],[unit_label(r['unit_name']) for r in units],[('问题数',[r['issue_count'] for r in units],'0')],'片区 / 单位问题数量（个）')
    chart(graphs[1],[unit_label(r['unit_name']) for r in units],[('站均问题',[r['average_issue_count'] for r in units],'0.0')],'站均问题数量（个）')
    for index,mode in [(6,modes[0]),(7,modes[1])]:
        s=slides[index];name='视频' if mode['mode']=='video' else '现场';rows=mode['units']
        text=f"{name}巡检覆盖{mode['station_count']}座加油站，共发现问题{mode['issue_count']}个，站均问题数{mode['average_issue_count']:.1f}个。"
        above=[unit_label(r['unit_name']) for r in rows if r['average_issue_count']>mode['average_issue_count']]
        write(by_text(s,name+'巡检覆盖'),[text,'其中，'+('、'.join(above)+'站均问题数量高于整体平均。' if above else '各单位站均问题均不高于整体平均。')],15,True)
        chart(next(sh for sh in s.shapes if sh.has_chart),[unit_label(r['unit_name']) for r in rows],
            [('加油站数',[r['station_count'] for r in rows],'0'),('问题总数',[r['issue_count'] for r in rows],'0'),('站均问题数',[r['average_issue_count'] for r in rows],'0.0')])
    s=slides[8];graphs=[sh for sh in s.shapes if sh.has_chart]
    for i,mode in enumerate(modes):
        name='视频' if mode['mode']=='video' else '现场';rows=mode['categories']
        intro=[name+'巡检问题']+[f"{r['name']}类问题{r['count']}个，占比{r['percentage']:.1f}%。" for r in rows[:2]]
        if len(intro)==1:intro+=['当前范围暂无对应问题。']
        write(by_text(s,name+'巡检问题'),intro,15,True)
        chart(graphs[i],[r['name'] for r in rows],[('问题数',[r['count'] for r in rows],'0')],name+'巡检问题类别分布')
    for index,mode in [(9,modes[0]),(10,modes[1])]:
        s=slides[index];rows=mode['stages'][:4];name='视频' if mode['mode']=='video' else '现场'
        body=by_text(s,'分析问题发生的具体环节')
        write(body,[f'分析问题发生的具体环节，在{name}巡检中问题发生频率最高的环节包括：',
            *[f"{r['name']}：{r['count']}个问题，占本类检查问题的{r['percentage']:.1f}%。" for r in rows]],15,True)
        maximum=max((r['count'] for r in rows),default=0)
        chart(next(sh for sh in s.shapes if sh.has_chart),[r['name'] for r in rows],
            [('问题数',[r['count'] for r in rows],'0'),('对比余量',[maximum-r['count'] for r in rows],'0')])
        matrix=next(sh for sh in s.shapes if sh.has_table)
        matrix_rows=[]
        issues=[r for r in report['service_issues'] if r['mode']==mode['mode']]
        for unit in mode['units']:
            counts=Counter(r['stage'] for r in issues if r['unit_name']==unit['unit_name'])
            matrix_rows.append([unit_label(unit['unit_name']),*[counts[r['name']] for r in rows],*['']*(4-len(rows))])
        table(matrix,['片区 / 单位',*[r['name'] for r in rows],*['—']*(4-len(rows))],matrix_rows,3.9)
    s=slides[11];rows=report['behavior_analysis']['groups'];grid=next(sh for sh in s.shapes if sh.has_table)
    table(grid,['问题具体表现','问题数','占比'],[[r['name'],r['count'],f"{r['percentage']:.1f}%"] for r in rows[:6]],2.3)
    slots=photo_slots(s)
    for shape in list(s.shapes):
        if shape.has_text_frame and shape.top>Inches(3) and shape.text not in ('问题行为表现',):shape._element.getparent().remove(shape._element)
    for i,box in enumerate(slots[:4]):
        group=rows[i] if i<len(rows) else None
        ids=report['behavior_examples'].get(group['name'],[]) if group else []
        picture(s,by_id.get(ids[0]) if ids else None,root,box,group['name'] if group else '')
    # Page 13 remains the supplied explanatory matrix, not model-invented risk scores.
    for slide in slides:
        if slide.has_notes_slide:slide.notes_slide.notes_text_frame.text=''
        used={value for node in slide._element.iter() for key,value in node.attrib.items()
            if key.startswith('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}')}
        for rel in list(slide.part.rels.values()):
            if rel.reltype.endswith('/image') and rel.rId not in used:slide.part.drop_rel(rel.rId)
    for part in list(prs.part.package.iter_parts()):
        element=getattr(part,'_element',None)
        if element is not None:
            for node in element.iter(qn('a:buChar')):
                font=node.getparent().find(qn('a:buFont'))
                symbol_font=font is not None and 'wingdings' in font.get('typeface','').lower()
                if symbol_font or any(0xE000<=ord(char)<=0xF8FF for char in node.get('char','')):node.set('char','■')
        for rel in list(part.rels.values()):
            if rel.reltype.endswith(('/comments','/commentAuthors')):part.drop_rel(rel.rId)
    _normalize_package_fonts(prs)
    output_path=Path(output_path);output_path.parent.mkdir(parents=True,exist_ok=True);prs.save(output_path)
    return {'ppt_path':str(output_path),'slide_count':13}
