"""Management endpoints with explicit authentication and database dependencies."""
import logging
from flask import Blueprint, g, jsonify, request
from psycopg2.extras import RealDictCursor
from ai_model_settings import catalog, read_settings, save_settings, serialize_settings, SettingsConflict
from ai_routing import configure_routing, normalize_model_settings


def register_ai_model_management(app, *, connect, require_management_user):
    def load():
        conn = connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                return read_settings(cur)
        finally:
            conn.close()

    configure_routing(load)
    blueprint = Blueprint('ai_model_management', __name__)

    @blueprint.route('/api/management/ai-models', methods=['GET', 'PUT'])
    def settings():
        conn = None
        try:
            conn = connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                user = require_management_user(cur, str(g.current_user['id']), 'manage_ai_models')
                if request.method == 'PUT':
                    config = save_settings(cur, request.get_json(silent=True), user)
                else:
                    config = read_settings(cur)
                cur.execute('''SELECT actor_name, created_at, after_config FROM ai_model_setting_events
                    ORDER BY id DESC LIMIT 10''')
                events = [dict(row, created_at=str(row['created_at']),
                               after_config=normalize_model_settings(row['after_config'])) for row in cur.fetchall()]
                payload = dict(success=True, settings=serialize_settings(config), events=events, **catalog())
            conn.commit()
            return jsonify(payload)
        except PermissionError as exc:
            if conn:
                conn.rollback()
            return jsonify(success=False, error=str(exc)), 403
        except (ValueError, LookupError) as exc:
            if conn:
                conn.rollback()
            return jsonify(success=False, error=str(exc)), 409 if isinstance(exc, SettingsConflict) else 400
        except Exception:
            if conn:
                conn.rollback()
            logging.exception('AI model settings operation failed')
            return jsonify(success=False, error='大模型配置服务暂时不可用，请检查数据库迁移。'), 503
        finally:
            if conn:
                conn.close()

    app.register_blueprint(blueprint)
