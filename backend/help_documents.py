"""Help content and publication rules. Caller owns permission checks and transaction."""
from datetime import timezone
import uuid

from psycopg2.extras import Json
from system_manual import DOCUMENTS

PERMISSION = 'edit_help_documents'
ATTACHMENT_IDS = {item['id'] for item in DOCUMENTS}


class EditConflict(ValueError):
    pass


def normalize_content(data):
    if not isinstance(data, dict):
        raise ValueError('请填写帮助文档内容。')
    result = {}
    for key, name, low, high in [('title', '标题', 2, 100), ('category', '分类', 2, 40),
                                  ('summary', '摘要', 0, 300), ('body', '正文', 2, 16000)]:
        value = data.get(key, '')
        if not isinstance(value, str) or not low <= len(value.strip()) <= high or '\x00' in value:
            raise ValueError(f'{name}应为{low}至{high}字。')
        result[key] = value.strip()
    tags = data.get('tags', [])
    if not isinstance(tags, list) or len(tags) > 12 or any(not isinstance(tag, str) or not 1 <= len(tag.strip()) <= 30 or '\x00' in tag for tag in tags):
        raise ValueError('标签最多12个，每个1至30字。')
    result['tags'] = list(dict.fromkeys(tag.strip() for tag in tags))
    attachments = data.get('attachments', [])
    if not isinstance(attachments, list) or len(attachments) > len(ATTACHMENT_IDS) or any(not isinstance(item, str) or item not in ATTACHMENT_IDS for item in attachments):
        raise ValueError('请选择现有的参考附件。')
    result['attachments'] = list(dict.fromkeys(attachments))
    return result


def stamp(value):
    return value.astimezone(timezone.utc).isoformat() if value else ''


def serialize(row, workspace=False):
    return {'id': row['id'], 'revision': row['revision'],
            'content': (row.get('draft') or row.get('published')) if workspace else row.get('published'),
            'published_content': row.get('published') if workspace else None,
            'has_draft': row.get('draft') is not None if workspace else False,
            'archived': row['archived'],
            'updated_by': row['updated_by_name'] if workspace else row['published_by_name'],
            'updated_at': stamp(row['updated_at'] if workspace else row['published_at']),
            'published_at': stamp(row['published_at'])}


def list_documents(cur, workspace=False):
    columns = 'id,published,revision,archived,published_by_name,published_at,updated_by_name,updated_at'
    if workspace:
        columns += ',draft'
    cur.execute('SELECT ' + columns + ' FROM help_documents' +
                ('' if workspace else ' WHERE published IS NOT NULL AND NOT archived') +
                " ORDER BY CASE WHEN id='getting-started' THEN 0 ELSE 1 END,created_at,id LIMIT 300")
    return [serialize(row, workspace) for row in cur.fetchall()]


def change_document(cur, identifier, payload, actor):
    if not isinstance(payload, dict):
        raise ValueError('请求格式不正确。')
    action = payload.get('action')
    if action not in ('draft', 'publish', 'archive', 'restore'):
        raise ValueError('请选择保存草稿、发布、下架或重新上架。')
    revision = payload.get('revision')
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise ValueError('文档版本不正确，请刷新后重试。')
    content = normalize_content(payload.get('content')) if action in ('draft', 'publish') else None
    creating = identifier is None
    if creating:
        if action not in ('draft', 'publish') or revision != 0:
            raise ValueError('新文档只能保存草稿或发布。')
        identifier = uuid.uuid4().hex
        cur.execute('INSERT INTO help_documents(id) VALUES(%s)', [identifier])
    cur.execute('SELECT * FROM help_documents WHERE id=%s FOR UPDATE', [identifier])
    row = cur.fetchone()
    if not row:
        raise LookupError('帮助文档不存在。')
    if row['revision'] != revision:
        raise EditConflict('文档已被其他人更新，请保留当前输入，重新读取后再编辑。')
    if action in ('archive', 'restore') and row['published'] is None:
        raise ValueError('这份文档尚未发布，请先完成编辑并发布。')
    name = actor.get('real_name') or actor.get('username') or str(actor['id'])
    if action == 'publish':
        cur.execute('''UPDATE help_documents SET published=%s,draft=NULL,archived=FALSE,
            published_at=CURRENT_TIMESTAMP,published_by_name=%s WHERE id=%s''', [Json(content), name, identifier])
    elif action == 'draft':
        cur.execute('UPDATE help_documents SET draft=%s WHERE id=%s', [Json(content), identifier])
    else:
        cur.execute('UPDATE help_documents SET archived=%s WHERE id=%s', [action == 'archive', identifier])
    cur.execute('''UPDATE help_documents SET revision=revision+1,updated_by_name=%s,updated_at=CURRENT_TIMESTAMP
        WHERE id=%s RETURNING *''', [name, identifier])
    result = serialize(cur.fetchone(), True)
    identity = {key: actor.get(key) for key in ('id', 'username', 'real_name', 'role')}
    if actor.get('_impersonator'):
        identity['impersonator_id'] = actor['_impersonator'].get('id')
    cur.execute('''INSERT INTO help_document_events(document_id,action,revision,actor,content)
        VALUES(%s,%s,%s,%s,%s)''', [identifier, action, result['revision'], Json(identity), Json(content) if content else None])
    return result
