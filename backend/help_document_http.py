"""Authenticated help readers and explicitly authorized editors; no import-time I/O."""
import logging

from flask import Blueprint, g, jsonify, request
from psycopg2.extras import RealDictCursor

from help_documents import PERMISSION, EditConflict, change_document, list_documents
from system_manual import DOCUMENTS


def register_help_documents(app, *, connect, has_permission):
    blueprint = Blueprint('help_documents', __name__)

    def execute(callback):
        user = getattr(g, 'current_user', None)
        if not user:
            return jsonify(success=False, error='请先登录。'), 401
        conn = None
        try:
            conn = connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                can_edit = has_permission(cur, user, PERMISSION)
                if (request.method != 'GET' or request.args.get('workspace') == '1') and not can_edit:
                    raise PermissionError('当前账号没有帮助文档编辑权限，请联系Root授权。')
                result = callback(cur, user, can_edit)
            conn.commit()
            response = jsonify(success=True, **result)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except PermissionError as exc:
            if conn:
                conn.rollback()
            return jsonify(success=False, error=str(exc)), 403
        except (ValueError, LookupError) as exc:
            if conn:
                conn.rollback()
            return jsonify(success=False, error=str(exc)), 409 if isinstance(exc, EditConflict) else 404 if isinstance(exc, LookupError) else 400
        except Exception:
            if conn:
                conn.rollback()
            logging.exception('Help document operation failed')
            return jsonify(success=False, error='帮助文档服务暂不可用，请确认数据库已升级后重试。'), 503
        finally:
            if conn:
                conn.close()

    @blueprint.route('/api/help-documents', methods=['GET', 'POST'])
    def documents():
        def operation(cur, user, can_edit):
            if request.method == 'POST':
                return {'item': change_document(cur, None, request.get_json(silent=True), user)}
            workspace = request.args.get('workspace') == '1'
            return {'items': list_documents(cur, workspace), 'can_edit': can_edit,
                    'attachments': [{'id': item['id'], 'title': item['title'], 'format': item['format'],
                        'filename': item['filename'], 'preview_url': '/api/system-manual/documents/' + item['id'] + '/preview',
                        'download_url': '/api/system-manual/documents/' + item['id'] + '/original?download=1'} for item in DOCUMENTS]}
        return execute(operation)

    @blueprint.put('/api/help-documents/<identifier>')
    def update(identifier):
        return execute(lambda cur, user, can_edit: {'item': change_document(cur, identifier, request.get_json(silent=True), user)})

    @blueprint.get('/api/help-documents/<identifier>/history')
    def history(identifier):
        def operation(cur, user, can_edit):
            if not can_edit:
                raise PermissionError('当前账号没有帮助文档编辑权限。')
            cur.execute('''SELECT action,revision,actor,created_at FROM help_document_events
                WHERE document_id=%s ORDER BY id DESC LIMIT 20''', [identifier])
            return {'items': [dict(row, created_at=row['created_at'].isoformat()) for row in cur.fetchall()]}
        return execute(operation)

    app.register_blueprint(blueprint)
