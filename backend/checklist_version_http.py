"""Version maintenance uses the existing checklist/original permissions."""
import copy
import logging
from pathlib import Path

from flask import jsonify, request, send_file
from psycopg2.extras import Json
import checklist_versions as editions


def register_checklist_versions(app, *, db, current_user, has_permission, normalize_fields,
        ensure_columns, physical_name, upsert_fields, save_pdf, storage_path):
    def authorize(cur, user, permission='manage_checklists'):
        if not has_permission(cur, user, permission):
            raise PermissionError('当前账号无权维护检查表版本。')

    def event(cur, table, selected, action, user, detail=None):
        cur.execute('''INSERT INTO checklist_version_events(inspection_table_id,checklist_version_id,action,actor_id,detail)
            VALUES(%s,%s,%s,%s,%s)''', (table,selected,action,user['id'],Json(detail or {})))

    def protected_fields(cur, selected, incoming):
        old = [(f['field_key'],f['field_label']) for f in selected['fields']]
        new = [(f['field_key'],f['field_label']) for f in incoming]
        if old != new:
            cur.execute('''SELECT EXISTS(SELECT 1 FROM issues WHERE checklist_version_id=%s UNION ALL
                SELECT 1 FROM inspections WHERE checklist_version_id=%s UNION ALL
                SELECT 1 FROM inspection_highlights WHERE checklist_version_id=%s UNION ALL
                SELECT 1 FROM checklist_standard_registry WHERE checklist_version_id=%s) AS used''', (selected['id'],)*4)
            if cur.fetchone()['used']:
                raise ValueError('此版本已有规范或业务记录，不能改变历史字段结构。请新增版本；显示、筛选和评分开关仍可调整。')
        cur.execute('''SELECT 1 FROM inspection_checklist_versions v,jsonb_array_elements(v.fields) f
            WHERE v.id<>%s AND f->>'field_key'=ANY(%s) LIMIT 1''', (selected['id'],[f['field_key'] for f in incoming]))
        if cur.fetchone():
            raise ValueError('字段标识已属于其他版本，请新增字段并使用系统生成的标识。')

    @app.route('/api/management/checklists/<int:table_id>/versions', methods=['GET','POST'])
    def checklist_versions(table_id):
        conn = None
        try:
            user = current_user(); conn = db(); cur = conn.cursor(); authorize(cur,user)
            current = editions.version(cur,table_id,lock=request.method=='POST')
            if request.method=='POST':
                data = request.get_json(silent=True) or {}
                name = str(data.get('version_name') or '').strip()
                if not name or len(name)>80:
                    raise ValueError('请填写版本名称，最多80字。')
                # Copy structure, never IDs or standard rows. New fields get their
                # own physical columns so previous versions cannot be overwritten.
                raw = copy.deepcopy(data.get('fields') or current['fields'])
                if not isinstance(raw,list) or any(not isinstance(f,dict) for f in raw):
                    raise ValueError('字段结构必须为字段列表。')
                for f in raw: f.pop('field_key',None)
                fields = normalize_fields(raw,current['table_code'])
                ensure_columns(cur,physical_name(current['table_code']),fields)
                cur.execute('''INSERT INTO inspection_checklist_versions(inspection_table_id,version_number,version_name,description,fields,created_by,updated_by)
                    SELECT %s,MAX(version_number)+1,%s,%s,%s,%s,%s FROM inspection_checklist_versions
                    WHERE inspection_table_id=%s RETURNING id''',
                    (table_id,name,str(data.get('description') or '')[:1000],Json(fields),user['id'],user['id'],table_id))
                identifier = cur.fetchone()['id']
                event(cur,table_id,identifier,'创建版本',user,{'field_labels':[f['field_label'] for f in fields]})
                conn.commit()
                return jsonify(success=True,version_id=identifier,message='新版本已创建，尚未启用。请维护新规范后再启用；旧版不受影响。')
            return jsonify(success=True,versions=editions.versions(cur,table_id))
        except PermissionError as exc:
            if conn: conn.rollback()
            return jsonify(error=str(exc)),403
        except ValueError as exc:
            if conn: conn.rollback()
            return jsonify(error=str(exc)),400
        except Exception:
            if conn: conn.rollback()
            logging.exception('Checklist version request failed')
            return jsonify(error='版本操作失败，未保存本次修改。'),500
        finally:
            if conn: conn.close()

    @app.route('/api/management/checklists/<int:table_id>/versions/<int:version_id>', methods=['PUT'])
    def update_version(table_id,version_id):
        conn = None
        try:
            user=current_user(); conn=db(); cur=conn.cursor(); authorize(cur,user)
            selected=editions.version(cur,table_id,version_id,lock=True)
            data=request.get_json(silent=True) or {}
            if data.get('revision')!=selected['revision']:
                return jsonify(error='版本已被其他用户更新，请刷新后再编辑。'),409
            name=str(data.get('version_name') or selected['version_name']).strip()
            if len(name)>80: raise ValueError('版本名称最多80字。')
            fields=normalize_fields(data.get('fields'),selected['table_code'])
            protected_fields(cur,selected,fields)
            ensure_columns(cur,physical_name(selected['table_code']),fields)
            cur.execute('''UPDATE inspection_checklist_versions SET version_name=%s,description=%s,fields=%s,
                revision=revision+1,updated_by=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s''',
                (name,str(data.get('description') or '')[:1000],Json(fields),user['id'],version_id))
            if selected['active_version_id']==version_id:
                upsert_fields(cur,table_id,fields)
            event(cur,table_id,version_id,'更新版本设置',user,{'field_labels':[f['field_label'] for f in fields]})
            conn.commit()
            return jsonify(success=True,message='版本设置已保存，历史问题快照不变。')
        except PermissionError as exc:
            if conn:conn.rollback()
            return jsonify(error=str(exc)),403
        except ValueError as exc:
            if conn:conn.rollback()
            return jsonify(error=str(exc)),400
        except Exception:
            if conn:conn.rollback()
            logging.exception('Checklist version update failed')
            return jsonify(error='版本保存失败，未保存本次修改。'),500
        finally:
            if conn:conn.close()

    @app.route('/api/management/checklists/<int:table_id>/versions/<int:version_id>/activate', methods=['POST'])
    def activate_version(table_id,version_id):
        conn=None
        try:
            user=current_user();conn=db();cur=conn.cursor();authorize(cur,user)
            selected=editions.version(cur,table_id,version_id,lock=True)
            data=request.get_json(silent=True) or {}
            if data.get('expected_active_version_id')!=selected['active_version_id']:
                return jsonify(error='启用版本已变化，请刷新后重试。'),409
            cur.execute('SELECT count(*) AS n FROM checklist_standard_registry WHERE checklist_version_id=%s AND NOT is_deleted',(version_id,))
            if not selected['fields'] or not cur.fetchone()['n']:
                raise ValueError('请先配置字段并维护至少一条规范，再启用此版本。')
            cur.execute('UPDATE inspection_tables SET active_version_id=%s,is_active=TRUE,updated_at=CURRENT_TIMESTAMP WHERE id=%s',(version_id,table_id))
            upsert_fields(cur,table_id,selected['fields'])
            event(cur,table_id,version_id,'启用版本',user,{'previous_version_id':selected['active_version_id']})
            conn.commit()
            return jsonify(success=True,message='此版本已启用，其他版本仅供历史查询，不能用于新登记。')
        except PermissionError as exc:
            if conn:conn.rollback()
            return jsonify(error=str(exc)),403
        except ValueError as exc:
            if conn:conn.rollback()
            return jsonify(error=str(exc)),400
        except Exception:
            if conn:conn.rollback()
            logging.exception('Checklist activation failed')
            return jsonify(error='启用失败，原版本保持不变。'),500
        finally:
            if conn:conn.close()

    @app.route('/api/checklist-versions/<int:version_id>/original',methods=['GET','POST'])
    def version_original(version_id):
        conn=None; uploaded=None
        try:
            user=current_user();conn=db();cur=conn.cursor()
            permission='manage_checklist_originals' if request.method=='POST' else 'view_checklist_originals'
            if not has_permission(cur,user,permission):raise PermissionError('当前账号无权访问检查表原件。')
            cur.execute('SELECT inspection_table_id FROM inspection_checklist_versions WHERE id=%s',(version_id,))
            found=cur.fetchone()
            if not found:raise ValueError('检查表版本不存在。')
            selected=editions.version(cur,found['inspection_table_id'],version_id,lock=request.method=='POST')
            document=selected['original_document']
            if request.method=='POST':
                uploaded,name,size=save_pdf(request.files.get('pdf') or request.files.get('file'))
                doc={'file_path':uploaded,'original_filename':name,'file_size':size,'uploaded_by_name':user.get('real_name') or user.get('username')}
                cur.execute('UPDATE inspection_checklist_versions SET original_document=%s,updated_by=%s,updated_at=CURRENT_TIMESTAMP,revision=revision+1 WHERE id=%s', (Json(doc),user['id'],version_id))
                event(cur,found['inspection_table_id'],version_id,'更新原件',user,{'previous_document':document,'document':doc})
                conn.commit();uploaded=None
                return jsonify(success=True,message='此版本原件已更新，旧原件保留在版本操作记录中。')
            if document.get('asset'):
                assets=Path(__file__).parent/'assets/checklist_versions'
                path=(assets/document['asset']).resolve()
                if path.parent!=assets.resolve():raise ValueError('原件路径无效。')
            elif document.get('file_path'):path=Path(storage_path(document['file_path']))
            else:return jsonify(error='此版本尚未上传原件。'),404
            if not path.is_file():return jsonify(error='此版本尚未上传原件。'),404
            return send_file(path,mimetype='application/pdf',download_name=document.get('original_filename') or '检查表.pdf')
        except PermissionError as exc:
            if conn:conn.rollback()
            return jsonify(error=str(exc)),403
        except ValueError as exc:
            if conn:conn.rollback()
            return jsonify(error=str(exc)),400
        except Exception:
            if conn:conn.rollback()
            logging.exception('Checklist original request failed')
            return jsonify(error='原件操作失败。'),500
        finally:
            if uploaded:
                path=Path(storage_path(uploaded))
                if path.is_file():path.unlink()
            if conn:conn.close()
