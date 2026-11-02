"""Use the supplied brand assets at their intrinsic aspect ratios after adaptation."""

from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches
from report_branding import add_logo, apply_report_branding


def replace_branding(prs):
    # Remove inherited small header icons as well as direct slide copies. Never
    # touch the tall left background, photos or other template illustrations.
    for owner in [*prs.slide_masters, *prs.slide_layouts, *prs.slides]:
        for shape in list(owner.shapes):
            if (shape.shape_type == MSO_SHAPE_TYPE.PICTURE and shape.top < Inches(1.15)
                    and shape.left > Inches(10.5) and shape.height < Inches(1.1)):
                shape._element.getparent().remove(shape._element)
    cover = prs.slides[0]
    for shape in list(cover.shapes):
        if (shape.shape_type == MSO_SHAPE_TYPE.PICTURE and shape.top < Inches(1.5)
                and shape.left < Inches(4) and shape.height < Inches(1.1)):
            shape._element.getparent().remove(shape._element)
    add_logo(cover.shapes, Inches(.55), Inches(.55), Inches(.84), Inches(.84), name='service-cover-wordmark')
    for slide in list(prs.slides)[1:]:
        add_logo(slide.shapes, Inches(12.65), Inches(.19), Inches(.47), Inches(.47), name='service-header-icon')
    apply_report_branding(prs)
