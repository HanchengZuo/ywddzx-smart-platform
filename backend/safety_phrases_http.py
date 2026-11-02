"""Global statistical phrase maintenance; manual edits never call the AI provider."""

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from report_ai_memory import fingerprint, ReportMemoryUnavailable
from safety_report_analysis import load_settings, normalize_settings, save_settings
from safety_report_phrases import load_phrases, phrase_catalog, phrases_signature, ensure_phrases, text


def register_safety_phrases(app, *, connect, authorize, has_permission, fetch_catalog, save_workspace, log_usage):
    blueprint = Blueprint('safety_phrases', __name__)

    @blueprint.route('/api/inspection-reports/safety-phrases', methods=['GET', 'PUT', 'POST'])
    def phrases():
        conn = None
        try:
            conn = connect()
            cur = conn.cursor()
            user = authorize(cur)
            if not user:
                raise PermissionError('当前账号无安全报告访问权限。')
            can_generate = bool(has_permission(cur, user, 'generate_inspection_reports'))
            catalog = fetch_catalog(cur, user)
            source_signature = fingerprint(phrase_catalog(catalog))
            meta = load_settings(cur)
            settings = normalize_settings(meta['settings'])
            if request.method != 'GET':
                request.max_content_length = 131072
                source = request.get_json()
                if not isinstance(source, dict):
                    raise ValueError('请提交有效的统计短语配置。')
                if source.get('catalog_signature') != source_signature or source.get('revision') != meta['revision']:
                    return jsonify(success=False, error='规范或配置已被更新，请重新读取后再保存。'), 409
                if request.method == 'POST' and not can_generate:
                    raise PermissionError('当前账号无生成AI报告权限，不能生成视频评分项短语。')
                if request.method == 'PUT':
                    changes = source.get('changes')
                    eligible = {row['key'] for row in phrase_catalog(catalog)}
                    if not isinstance(changes, dict) or len(changes) > 256 or not set(changes) <= eligible:
                        raise ValueError('统计短语修改包含范围外的来源。')
                    settings['analysis_phrases'].update({key: text(value) for key, value in changes.items()})
                    try:
                        save_settings(cur, settings, meta['revision'], user)
                    except ValueError as exc:
                        conn.rollback()
                        return jsonify(success=False, error=str(exc)), 409
                    save_workspace(cur, 'safety_quality', user, section='safety_phrases')
                    conn.commit()
                    meta = load_settings(cur)
            if request.method == 'POST':
                conn.commit()
                conn.close()
                conn = None
                def audit(result):
                    audit_conn = connect()
                    try:
                        with audit_conn.cursor() as audit_cur:
                            log_usage(audit_cur, user, result, 'AI报告生成', '安全报告统计短语', '视频评分项短语生成')
                            if result.get('usage', {}).get('ai_called'):
                                save_workspace(audit_cur, 'safety_quality', user, section='safety_phrases')
                        audit_conn.commit()
                    except Exception:
                        audit_conn.rollback()
                        raise
                    finally:
                        audit_conn.close()
                ensure_phrases(connect, catalog, settings, audit)
                conn = connect()
                cur = conn.cursor()
                # A concurrent human edit always wins over a generated phrase.
                meta = load_settings(cur)
                settings = normalize_settings(meta['settings'])
            rows = load_phrases(cur, catalog, settings)
            conn.rollback()
            return jsonify(success=True, rows=rows, catalog_signature=source_signature,
                library_signature=phrases_signature(rows), meta=meta, can_generate=can_generate)
        except PermissionError as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 403
        except ReportMemoryUnavailable as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 409
        except (BadRequest, UnsupportedMediaType, RequestEntityTooLarge, ValueError, TypeError) as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 413 if isinstance(exc, RequestEntityTooLarge) else 400
        except Exception:
            if conn: conn.rollback()
            app.logger.exception('Safety statistical phrases failed')
            return jsonify(success=False, error='统计短语读取、保存或生成失败，请稍后重试。'), 500
        finally:
            if conn: conn.close()

    app.register_blueprint(blueprint)
