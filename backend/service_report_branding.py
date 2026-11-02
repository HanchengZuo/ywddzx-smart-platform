"""Use the supplied brand assets at their intrinsic aspect ratios after adaptation."""

from pathlib import Path
from PIL import Image
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches

ASSETS = Path(__file__).parent / 'assets/service_report_template'


def contain(shapes, file, x, y, width, height, name):
    with Image.open(file) as image:
        ratio = image.width / image.height
    w, h = min(width, height * ratio), min(height, width / ratio)
    picture = shapes.add_picture(str(file), Inches(x+(width-w)/2), Inches(y+(height-h)/2),
        width=Inches(w), height=Inches(h))
    picture.name = name
    return picture


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
    contain(cover.shapes, ASSETS/'petrochina-wordmark.png', .55, .55, 3.2, .84, 'service-cover-wordmark')
    for slide in list(prs.slides)[1:]:
        contain(slide.shapes, ASSETS/'petrochina-icon.png', 12.65, .19, .47, .47, 'service-header-icon')
