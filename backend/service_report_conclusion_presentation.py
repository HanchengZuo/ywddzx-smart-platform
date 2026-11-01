"""Editable final five slides matching source pages 36-40, adapted to 16:9."""
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.text import PP_ALIGN
from service_report_unit_presentation import clone_slide,wrap
from safety_report_presentation import textbox

FONT='Microsoft YaHei'
BLUE='0D3063'

def divider(prs,number):
    from service_report_presentation import walk
    slide=clone_slide(prs,prs.slides[1])
    labels={'01':'检查基本情况','02':'各片区问题','03':'问题、亮点总结','04':'下一步建议'}
    for shape in walk(slide.shapes):
        if not shape.has_text_frame:continue
        text=shape.text.strip()
        for key,label in labels.items():
            if text==key or label in text:
                for p in shape.text_frame.paragraphs:
                    for r in p.runs:r.font.color.rgb=RGBColor.from_string(BLUE if key==number else '858585')
                break
    return slide

def page(prs,title):
    slide=prs.slides.add_slide(prs.slides[12].slide_layout)
    for shape in list(slide.shapes):shape._element.getparent().remove(shape._element)
    textbox(slide,title,.45,.22,11.5,.65,27,'364F83',True)
    return slide

def oval(slide,text,x,y,w,h,color,size):
    shape=slide.shapes.add_shape(MSO_SHAPE.OVAL,Inches(x),Inches(y),Inches(w),Inches(h))
    shape.fill.solid();shape.fill.fore_color.rgb=RGBColor.from_string(color);shape.line.fill.background()
    textbox(slide,text,x,y+h/2-.2,w,.42,size,'FFFFFF',True,PP_ALIGN.CENTER)

def points(slide,items,x,y,w,h):
    size=15
    while size>11:
        lines=sum(len(wrap(text,w*72/size-2)) for text in items)
        if lines*size*1.25+len(items)*6<=h*72:break
        size-=.5
    top=y
    for text in items:
        lines=wrap(text,w*72/size-2);height=len(lines)*size*1.25/72
        arrow=slide.shapes.add_shape(MSO_SHAPE.CHEVRON,Inches(x),Inches(top+.05),Inches(.09),Inches(.1))
        arrow.fill.solid();arrow.fill.fore_color.rgb=RGBColor.from_string('111111');arrow.line.fill.background()
        body=slide.shapes.add_textbox(Inches(x+.22),Inches(top),Inches(w-.22),Inches(height+.03))
        body.text_frame.margin_left=body.text_frame.margin_right=body.text_frame.margin_top=body.text_frame.margin_bottom=0
        body.text_frame.word_wrap=False
        for i,line in enumerate(lines):
            p=body.text_frame.paragraphs[0] if not i else body.text_frame.add_paragraph()
            p.space_after=Pt(0);p.line_spacing=Pt(size*1.25)
            run=p.add_run();run.text=line;run.font.name=FONT;run.font.size=Pt(size);run.font.bold=False;run.font.color.rgb=RGBColor.from_string('111111')
        top+=height+6/72

def add_conclusion(prs,report):
    conclusion=report.get('service_conclusion')
    if not conclusion:return
    divider(prs,'03')
    for start in (0,2):
        slide=page(prs,'问题总结')
        textbox(slide,'本次巡检发现的共性问题，具体总结如下：',.45,1.02,11,.42,13,'595E64',True)
        oval(slide,'共性问题',1.05,3.0,2.35,2.37,BLUE,22)
        for index,item in enumerate(conclusion['themes'][start:start+2]):
            y=1.73+index*2.8
            oval(slide,f'{start+index+1:02}',3.8,y+.5,.58,.65,'4F66B1' if index==0 else '619FD1',14)
            textbox(slide,item['title'],4.78,y,7.95,.58,22,BLUE,True)
            points(slide,item['points'],4.78,y+.73,7.9,1.98)
    divider(prs,'04')
    slide=page(prs,'下一步建议')
    frame=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(.35),Inches(.98),Inches(12.58),Inches(6.06))
    frame.adjustments[0]=.16;frame.fill.solid();frame.fill.fore_color.rgb=RGBColor.from_string('FFFFFF')
    frame.line.color.rgb=RGBColor.from_string('292B5C');frame.line.width=Pt(1.5);frame.line.dash_style=MSO_LINE_DASH_STYLE.DASH_DOT
    # Fit complete AI paragraphs inside the fixed frame, never hide overflow in notes.
    items=conclusion['recommendations'];size=17
    while size>11:
        heights=[.43+len(wrap(item['content'],11.15*72/size))*size*1.4/72+.18 for item in items]
        if sum(heights)<=5.45:break
        size-=.5
    y=1.22
    for index,(item,height) in enumerate(zip(items,heights)):
        textbox(slide,f"（{'一二三'[index]}）{item['title']}",1.1,y,11.1,.4,size,'1D2C38',True)
        body=slide.shapes.add_textbox(Inches(1.1),Inches(y+.48),Inches(11.15),Inches(height-.48))
        body.text_frame.word_wrap=False;body.text_frame.margin_left=body.text_frame.margin_right=body.text_frame.margin_top=body.text_frame.margin_bottom=0
        for i,line in enumerate(wrap(item['content'],11.15*72/size)):
            p=body.text_frame.paragraphs[0] if not i else body.text_frame.add_paragraph()
            p.space_after=Pt(0);p.line_spacing=Pt(size*1.4)
            r=p.add_run();r.text=line;r.font.name=FONT;r.font.size=Pt(size);r.font.bold=True;r.font.color.rgb=RGBColor.from_string('1D2C38')
        y+=height
