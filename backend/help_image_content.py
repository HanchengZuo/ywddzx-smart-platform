"""Version-compatible inline help figures; only bundled authenticated images are valid."""
import json

from system_manual import DOCUMENTS

IMAGE_PREFIX = '::help-image '
IMAGES = {item['id']: item for item in DOCUMENTS}


def image_nodes(body):
    nodes = []
    for line in body.splitlines():
        if not line.startswith('::help-image'):
            continue
        try:
            node = json.loads(line[len(IMAGE_PREFIX):]) if line.startswith(IMAGE_PREFIX) else None
        except (TypeError, ValueError):
            node = None
        if (not isinstance(node, dict) or set(node) - {'id', 'caption', 'width'}
                or not isinstance(node.get('id'), str) or node['id'] not in IMAGES
                or not isinstance(node.get('caption', ''), str) or len(node.get('caption', '')) > 160
                or '\x00' in node.get('caption', '') or '\n' in node.get('caption', '')
                or type(node.get('width', 100)) is not int or node.get('width', 100) not in (50, 75, 100)):
            raise ValueError('正文图片配置不正确，请重新插入流程图。')
        nodes.append(node)
    if len(nodes) > 12:
        raise ValueError('每篇帮助文档最多插入12张流程图。')
    return nodes


def inline_content(content):
    if content is None:
        return None
    result = dict(content)
    body = result.get('body') or ''
    # Old references become visible figures, without updating publication/audit metadata on reads.
    present = {node['id'] for node in image_nodes(body)}
    for identifier in result.get('attachments') or []:
        if identifier in IMAGES and identifier not in present:
            body += '\n\n' + IMAGE_PREFIX + json.dumps({
                'id': identifier, 'caption': IMAGES[identifier]['title'], 'width': 100}, ensure_ascii=False)
            present.add(identifier)
    result['body'] = body.strip()
    result['attachments'] = []
    return result
