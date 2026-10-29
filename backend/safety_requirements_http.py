"""Explicit read/edit/generate endpoints for the shared safety requirements library."""
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from safety_requirements import (
    RequirementsBusy, RequirementsConflict, RequirementsGenerationError,
    catalog_signature, ensure_requirements, library_signature, load_requirements, save_requirements,
)


def register_safety_requirements(app, *, connect, authorize, has_permission, fetch_catalog,
                                 save_workspace, log_usage):
    """authorize(cur) retains page read access; only POST requires generation permission."""
    blueprint = Blueprint('safety_requirements', __name__)

    @blueprint.route('/api/inspection-reports/safety-requirements', methods=['GET', 'PUT', 'POST'])
    def requirements():
        conn = None
        try:
            conn = connect()
            with conn.cursor() as cur:
                user = authorize(cur)
                if not user:
                    raise PermissionError('当前账号无安全报告访问权限。')
                can_generate = bool(has_permission(cur, user, 'generate_inspection_reports'))
                if request.method == 'POST' and not can_generate:
                    raise PermissionError('当前账号无生成AI报告权限，不能生成规范要求。')
                catalog = fetch_catalog(cur, user)
                signature = catalog_signature(catalog)
                if request.method != 'GET':
                    if request.content_length and request.content_length > 262144:
                        raise RequestEntityTooLarge()
                    # Bound chunked bodies too, without changing unrelated app routes.
                    request.max_content_length = 262144
                    source = request.get_json()
                    if not isinstance(source, dict):
                        raise ValueError('请提交有效的规范要求JSON对象。')
                    if source.get('catalog_signature') != signature:
                        raise RequirementsConflict('安全规范目录已变化，请刷新后重试。')
                    if request.method == 'PUT':
                        if save_requirements(cur, catalog, source.get('changes'), user):
                            save_workspace(cur, 'safety_quality', user, section='safety_requirements')
                if request.method != 'POST':
                    rows = load_requirements(cur, catalog)
                    payload = dict(standards=rows, catalog_signature=signature,
                                   library_signature=library_signature(rows))
            if request.method == 'POST':
                # Finish authorization/catalog reads before any network operation.
                conn.commit()
                conn.close()
                conn = None
                def audit(result):
                    audit_conn = connect()
                    try:
                        with audit_conn.cursor() as audit_cur:
                            log_usage(audit_cur, user, result, 'AI报告生成', '安全规范要求库',
                                      str(result.get('requirements_counts') or {}))
                        audit_conn.commit()
                    except Exception:
                        audit_conn.rollback()
                        raise
                    finally:
                        audit_conn.close()

                rows, counts = ensure_requirements(connect, catalog, user, log_usage=audit,
                                                    save_workspace=save_workspace)
                payload = dict(standards=rows, catalog_signature=signature,
                               library_signature=library_signature(rows), **counts)
            elif request.method == 'PUT':
                conn.commit()
            else:
                # GET never initializes rows, touches the workspace, or invokes AI.
                conn.rollback()
            return jsonify(success=True, can_generate=can_generate, **payload)
        except PermissionError as exc:
            if conn:
                conn.rollback()
            return jsonify(success=False, error=str(exc)), 403
        except RequirementsConflict as exc:
            if conn:
                conn.rollback()
            return jsonify(success=False, error=str(exc)), 409
        except (BadRequest, RequestEntityTooLarge, UnsupportedMediaType, ValueError, TypeError) as exc:
            if conn:
                conn.rollback()
            return jsonify(success=False, error=str(exc)), 413 if isinstance(exc, RequestEntityTooLarge) else 400
        except RequirementsBusy as exc:
            if conn:
                conn.rollback()
            return jsonify(success=False, error=str(exc)), 409
        except RequirementsGenerationError as exc:
            if conn:
                conn.rollback()
            return jsonify(success=False, error=str(exc)), 502
        except Exception:
            if conn:
                conn.rollback()
            app.logger.exception('Safety requirements library failed')
            return jsonify(success=False, error='安全规范要求读取、保存或生成失败，请稍后重试。'), 500
        finally:
            if conn:
                conn.close()

    app.register_blueprint(blueprint)
