"""Bundled, read-only system documentation for every authenticated user."""
from pathlib import Path

from flask import g, jsonify, request, send_file


ASSET_ROOT = Path(__file__).resolve().parent / 'assets' / 'system_manual'
DOCUMENTS = (
    {
        'id': 'inspection-workflow', 'title': '巡检流程设计图', 'category': '巡检流程',
        'description': '从巡检登记、记录确认、问题审核到站点验收、申诉、整改与复核，查看完整流转。',
        'tags': ['巡检登记', '巡检记录', '问题审核', '签名验收', '整改复核'],
        'format': 'PDF', 'pages': 1, 'filename': '巡检流程设计图.pdf',
        'original': 'inspection-workflow.pdf', 'preview': 'inspection-workflow-preview.png',
        'mimetype': 'application/pdf',
    },
    {
        'id': 'issue-appeal-workflow', 'title': '问题申诉流程说明', 'category': '问题申诉',
        'description': '了解适用检查表、站点发起申诉、片区初审、质安部终审以及结果退回或销毁的处理。',
        'tags': ['申诉空间', '申诉时限', '片区初审', '质安部终审', '站点角色'],
        'format': 'PNG', 'pages': 1, 'filename': '问题申诉流程说明.png',
        'original': 'issue-appeal-workflow.png', 'preview': 'issue-appeal-workflow.png',
        'mimetype': 'image/png',
    },
)


def register_system_manual(app):
    def require_user():
        # The main app verifies signed tokens, account state and forced password changes.
        if not getattr(g, 'current_user', None):
            return jsonify(success=False, error='请先登录。'), 401
        return None

    @app.get('/api/system-manual/documents')
    def system_manual_documents():
        denied = require_user()
        if denied:
            return denied
        items = []
        for document in DOCUMENTS:
            item = {key: document[key] for key in (
                'id', 'title', 'category', 'description', 'tags', 'format', 'pages', 'filename')}
            try:
                item['file_size'] = (ASSET_ROOT / document['original']).stat().st_size
            except OSError:
                return jsonify(success=False, error='帮助文档附件暂不可用，请稍后重试。'), 503
            base = '/api/system-manual/documents/' + document['id']
            item.update(preview_url=base + '/preview', download_url=base + '/original?download=1')
            items.append(item)
        response = jsonify(success=True, items=items)
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    @app.get('/api/system-manual/documents/<document_id>/<variant>')
    def system_manual_file(document_id, variant):
        denied = require_user()
        if denied:
            return denied
        document = next((item for item in DOCUMENTS if item['id'] == document_id), None)
        if document is None or variant not in ('original', 'preview'):
            return jsonify(success=False, error='帮助文档附件不存在。'), 404
        path = ASSET_ROOT / document[variant]
        if not path.is_file():
            return jsonify(success=False, error='帮助文档附件暂不可用，请稍后重试。'), 503
        response = send_file(path, mimetype=document['mimetype'] if variant == 'original' else 'image/png',
                             as_attachment=variant == 'original' and request.args.get('download') == '1',
                             download_name=document['filename'] if variant == 'original' else document['id'] + '.png',
                             conditional=True, max_age=0)
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
