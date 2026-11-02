"""Shared brand replacement for native report pictures, including inherited logos.

Only inspected brand-image fingerprints are replaced, never photos or similarly
positioned artwork. Historical decks stay untouched; their exported copies change.
"""
import hashlib
from pathlib import Path

from PIL import Image
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

LOGO_FILE = Path(__file__).parent / 'assets/operations_center_logo.png'
BRANDING_VERSION = 'operations-center-v12.6.4-1'
LEGACY_LOGO_DIGESTS = frozenset({
    '79cdf48ae3d1cf03385d80f2833a19ab2d94cfb906e7da372e42df8f4147ef4b',
    'ce5a3c8bff340a128f6fc6ef9dbddba46122d3158634b47b3d7d74ba539dc774',
    '38d25a44be63bdec82ed31263ef14618eaf2f697879d4370e44f1335b798fe59',
    'c0325a2959bf7796c1510ac01d89ac344304d24e65a39d460ab7d98e2e9c6e37',
    '3276f701d1efecf9ade1f3e482ca8c97c9b8d3f4e50922a75a2946a541d34fb5',
    '5582a430eb44d2f342331b5862086f25de9b783f6684cf8257be301cf7436b00',
    'a47c7756b18ced4db151f60f073b326a7af06440f52c439e49da6efe21c87748',
    '0699b6649a2234d83bf18b1572438f2a7455ef7e9529683f2c902e10797f1e93',
    '77021d457cb7c4ab49fe8852ad7d9d13b756b5b459dd0888925b22da5d248db6',
    '52e20c04f3562d2b7c1e371f11aa4c181502a5c0d4c1e41268b856de7d524f60',
})


def branding_key():
    return BRANDING_VERSION + ':' + hashlib.sha256(LOGO_FILE.read_bytes()).hexdigest()


def add_logo(shapes, x, y, width, height, *, name='report-brand-logo'):
    """Contain-fit EMU geometry; caller chooses the existing template's placement."""
    with Image.open(LOGO_FILE) as image:
        ratio = image.width / image.height
    w, h = min(width, height*ratio), min(height, width/ratio)
    shape = shapes.add_picture(str(LOGO_FILE), int(x+(width-w)/2), int(y+(height-h)/2),
        width=int(w), height=int(h))
    shape.name = name
    return shape


def _pictures(shapes):
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _pictures(shape.shapes)
        elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            yield shape


def apply_report_branding(prs):
    changed = False
    masters = list(prs.slide_masters)
    layouts = [layout for master in masters for layout in master.slide_layouts]
    for owner in [*masters, *layouts, *prs.slides]:
        old_relations = set()
        for shape in _pictures(owner.shapes):
            if hashlib.sha256(shape.image.blob).hexdigest() not in LEGACY_LOGO_DIGESTS:
                continue
            left, top, width, height = shape.left, shape.top, shape.width, shape.height
            # A full-wordmark slot becomes a compact logo, anchored to the same
            # corner. Other marks keep their center and fit wholly inside the slot.
            with Image.open(LOGO_FILE) as image:
                ratio = image.width / image.height
            w, h = min(width, height*ratio), min(height, width/ratio)
            x = left+(width-w)/2
            if width > height*2:
                x = left if left < prs.slide_width/2 else left+width-w
            _, rid = shape.part.get_or_add_image_part(str(LOGO_FILE))
            blip = shape._element.blipFill.blip
            old_relations.add(blip.get(qn('r:embed')))
            blip.set(qn('r:embed'), rid)
            shape.left, shape.top, shape.width, shape.height = int(x), int(top+(height-h)/2), int(w), int(h)
            shape.crop_left = shape.crop_right = shape.crop_top = shape.crop_bottom = 0
            changed = True
        for rel in list(owner.part.rels.values()):
            if (not rel.is_external and rel.reltype.endswith('/image')
                    and hashlib.sha256(rel.target_part.blob).hexdigest() in LEGACY_LOGO_DIGESTS):
                old_relations.add(rel.rId)
                # Image fills can also inherit brand artwork from a master.
                for blip in owner._element.xpath('.//a:blip'):
                    if blip.get(qn('r:embed')) == rel.rId:
                        _, rid = owner.part.get_or_add_image_part(str(LOGO_FILE))
                        blip.set(qn('r:embed'), rid)
                        changed = True
        # Remove only unused image relationships. Keep any relation still used
        # by another XML object, so photos/backgrounds cannot disappear.
        used = {value for node in owner._element.iter() for key, value in node.attrib.items()
            if key.startswith('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}')}
        for rid in old_relations-used:
            if rid and rid in owner.part.rels:
                owner.part.drop_rel(rid)
    return changed
