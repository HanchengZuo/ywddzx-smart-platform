"""HTTP adapters for manual transfers; app.py retains route/endpoint registration."""
from dataclasses import dataclass
from typing import Any, Callable

from flask import jsonify, request, send_file

from .transfers import BackupTaskBusy, BackupTransfers


@dataclass(frozen=True)
class BackupTransferEndpoints:
    get_connection: Callable[[], Any]
    require_management_user: Callable[..., Any]
    close_resources: Callable[..., None]
    transfers: BackupTransfers

    def export(self):
        data = request.get_json(silent=True) or {}
        user_id = str(data.get('user_id', '')).strip()
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            self.require_management_user(cur, user_id, 'manage_backups')
            self.close_resources(cur, conn)
            cur = None
            conn = None

            result = self.transfers.export()
            cos_result = result.get('cos') or {}
            cos_status = cos_result.get('status') or 'not_configured'
            response = send_file(
                result['path'],
                as_attachment=True,
                download_name=result['download_filename'],
                mimetype='application/zip',
            )
            response.headers['X-Backup-Path'] = result['path']
            response.headers['X-Backup-Size'] = str(result['size'])
            response.headers['X-COS-Backup-Status'] = cos_status
            response.headers['X-COS-Backup-Key'] = cos_result.get('key') or ''
            response.headers['Cache-Control'] = 'no-store'
            return response
        except BackupTaskBusy as exc:
            return jsonify({'success': False, 'error': str(exc)}), 409
        except PermissionError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 403
        except LookupError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 404
        except RuntimeError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 500
        except Exception as exc:
            return jsonify({'success': False, 'error': str(exc)}), 500
        finally:
            self.close_resources(cur, conn)

    def restore(self):
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            self.require_management_user(cur, None, 'manage_backups')
            self.close_resources(cur, conn)
            cur = None
            conn = None

            manifest = self.transfers.restore(lambda: request.files.get('file'))
            return jsonify({
                'success': True,
                'message': '完整备份已导入，数据库与上传文件目录已恢复。',
                'manifest': manifest,
            })
        except BackupTaskBusy as exc:
            return jsonify({'success': False, 'error': str(exc)}), 409
        except PermissionError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 403
        except LookupError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 404
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 500
        except Exception as exc:
            return jsonify({'success': False, 'error': str(exc)}), 500
        finally:
            self.close_resources(cur, conn)
