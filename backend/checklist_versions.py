"""Version identity is separate from the stable checklist/permission identity."""
import json
import re
from psycopg2 import sql
from psycopg2.extras import Json


def available(cur):
    cur.execute("SELECT to_regclass('inspection_checklist_versions') AS table_name")
    row = cur.fetchone()
    return isinstance(row, dict) and str(row.get('table_name') or '').split('.')[-1] == 'inspection_checklist_versions'


def version(cur, table_id, version_id=None, *, lock=False):
    cur.execute('''SELECT v.*,t.table_name,t.table_code,t.active_version_id,
        (t.is_active AND t.active_version_id=v.id) AS is_active,
        COALESCE(u.real_name,u.username,'系统迁移') AS updated_by_name
        FROM inspection_checklist_versions v JOIN inspection_tables t ON t.id=v.inspection_table_id
        LEFT JOIN users u ON u.id=COALESCE(v.updated_by,v.created_by)
        WHERE t.id=%s AND v.id=COALESCE(%s,t.active_version_id)'''+(' FOR UPDATE OF t,v' if lock else ''),
        (table_id, version_id))
    row = cur.fetchone()
    if not row:
        raise ValueError('检查表版本不存在或不属于当前检查表。')
    return dict(row)


def versions(cur, table_id):
    cur.execute('''SELECT v.*,t.active_version_id,t.is_active AND t.active_version_id=v.id AS is_active,
        (SELECT count(*) FROM checklist_standard_registry r WHERE r.checklist_version_id=v.id AND NOT r.is_deleted) AS standard_count,
        COALESCE(u.real_name,u.username,'系统迁移') AS updated_by_name
        FROM inspection_checklist_versions v JOIN inspection_tables t ON t.id=v.inspection_table_id
        LEFT JOIN users u ON u.id=COALESCE(v.updated_by,v.created_by)
        WHERE v.inspection_table_id=%s ORDER BY v.version_number DESC''', (table_id,))
    return [dict(row) for row in cur.fetchall()]


def catalog(cur, table_ids=None):
    cur.execute('''SELECT t.id,t.table_name,t.active_version_id,t.is_active,
        v.id AS version_id,v.version_number,v.version_name,t.is_active AND t.active_version_id=v.id AS version_active
        FROM inspection_tables t JOIN inspection_checklist_versions v ON v.inspection_table_id=t.id
        WHERE (%s::integer[] IS NULL OR t.id=ANY(%s)) ORDER BY t.id,v.version_number DESC''', (table_ids, table_ids))
    result = {}
    for row in cur.fetchall():
        entry = result.setdefault(row['id'], {'id':row['id'], 'table_name':row['table_name'], 'versions':[]})
        entry['versions'].append({'id':row['version_id'], 'version_number':row['version_number'],
            'version_name':row['version_name'], 'is_active':bool(row['version_active'])})
    return list(result.values())


def sync_active_fields(cur, table_id, fields):
    if available(cur):
        cur.execute('''UPDATE inspection_checklist_versions SET fields=%s,updated_at=CURRENT_TIMESTAMP
            WHERE id=(SELECT active_version_id FROM inspection_tables WHERE id=%s)''', (Json(fields),table_id))


def require_active(cur, table_id):
    cur.execute('SELECT active_version_id,is_active FROM inspection_tables WHERE id=%s FOR SHARE', (table_id,))
    row = cur.fetchone()
    if not row or not row.get('active_version_id') or not row['is_active']:
        raise ValueError('检查表未启用，请重新选择。')
    return int(row['active_version_id'])


def standard_metadata(cur, identifiers=None):
    cur.execute('''SELECT r.standard_id,r.inspection_table_id,r.checklist_version_id,r.is_deleted,
        v.version_number,v.version_name,v.fields,
        (NOT r.is_deleted AND t.is_active AND t.active_version_id=v.id AND COALESCE(s.is_active,TRUE)) AS is_active,
        COALESCE(s.is_active,TRUE) AS standard_enabled
        FROM checklist_standard_registry r JOIN inspection_checklist_versions v ON v.id=r.checklist_version_id
        JOIN inspection_tables t ON t.id=r.inspection_table_id
        LEFT JOIN external_standard_status s ON s.standard_id=r.standard_id
        WHERE (%s::bigint[] IS NULL OR r.standard_id=ANY(%s))''', (identifiers, identifiers))
    return {int(r['standard_id']):dict(r) for r in cur.fetchall()}


def standard_ids(cur, version_id):
    cur.execute('SELECT standard_id FROM checklist_standard_registry WHERE checklist_version_id=%s AND NOT is_deleted', (version_id,))
    return {int(r['standard_id']) for r in cur.fetchall()}


def require_standard_version(cur, standard_id, version_id):
    cur.execute('SELECT checklist_version_id FROM checklist_standard_registry WHERE standard_id=%s AND NOT is_deleted', (standard_id,))
    row = cur.fetchone()
    if not row or row['checklist_version_id'] != version_id:
        raise ValueError('规范不属于当前所选版本，请刷新后重试。')


def attach_rows(cur, rows, kind='issues'):
    if not rows or not available(cur):
        return rows
    if kind not in ('issues', 'inspections', 'inspection_highlights'):
        raise ValueError('Invalid version source')
    ids = [r.get('id') for r in rows if r.get('id')]
    if not ids:
        return rows
    cur.execute(sql.SQL('''SELECT b.id,v.id AS checklist_version_id,v.version_number,v.version_name
        FROM {} b JOIN inspection_checklist_versions v ON v.id=b.checklist_version_id WHERE b.id=ANY(%s)''').format(sql.Identifier(kind)), (ids,))
    mapping = {r['id']:dict(r) for r in cur.fetchall()}
    represented = {}
    if kind == 'inspections':
        cur.execute('''SELECT DISTINCT i.inspection_id,v.id AS checklist_version_id,v.version_number,v.version_name
            FROM issues i JOIN inspection_checklist_versions v ON v.id=i.checklist_version_id
            WHERE i.inspection_id=ANY(%s) ORDER BY i.inspection_id,v.version_number''', (ids,))
        for item in cur.fetchall():
            represented.setdefault(item['inspection_id'], []).append(dict(item))
    for row in rows:
        item = mapping.get(row.get('id'))
        if item:
            row.update({k:v for k,v in item.items() if k!='id'})
            name = row.get('inspection_table_name') or row.get('table_name') or ''
            editions = represented.get(row.get('id')) or [item]
            row['checklist_versions'] = [{k:e[k] for k in ('checklist_version_id','version_number','version_name')} for e in editions]
            row['inspection_table_display_name'] = name + ' · ' + ' / '.join(f"v{e['version_number']}" for e in editions)
    return rows


def append_filter(where, params, values, *, table_column='t.table_name', version_column='i.checklist_version_id'):
    clauses = []
    plain = []
    for value in values or []:
        match = re.fullmatch(r'(.+) · v([1-9][0-9]*)', str(value))
        if match:
            if version_column == 'ins.checklist_version_id':
                version_match = '''EXISTS(SELECT 1 FROM inspection_checklist_versions filter_v
                    WHERE filter_v.version_number=%s AND filter_v.inspection_table_id=ins.inspection_table_id
                    AND (EXISTS(SELECT 1 FROM issues filter_i WHERE filter_i.inspection_id=ins.id
                        AND filter_i.checklist_version_id=filter_v.id)
                        OR (ins.checklist_version_id=filter_v.id AND NOT EXISTS(
                            SELECT 1 FROM issues filter_i WHERE filter_i.inspection_id=ins.id))))'''
            else:
                version_match = f'{version_column} IN (SELECT id FROM inspection_checklist_versions WHERE version_number=%s)'
            clauses.append(f'({table_column}=%s AND {version_match})')
            params.extend([match[1], int(match[2])])
        else:
            plain.append(str(value))
    if plain:
        clauses.append(f'{table_column} = ANY(%s)'); params.append(plain)
    if clauses:
        where.append('('+' OR '.join(clauses)+')')


def report_supported_versions_sql():
    # Only the service adapter explicitly understands both schemas. Future
    # versions and all other templates retain the original compatibility gate.
    return '''SELECT checklist_version_id FROM inspection_report_version_bindings
        UNION SELECT v.id FROM inspection_checklist_versions v JOIN inspection_tables t ON t.id=v.inspection_table_id
        WHERE t.table_name='现场检查明细表（现场）' AND v.source_key='service-onsite-20260707'
        AND (SELECT array_agg(f->>'field_label' ORDER BY (f->>'sort_order')::integer)
            FROM jsonb_array_elements(v.fields) f)=ARRAY['项目','内容','检查评比标准','检查方式']'''


def report_guard(cur, table_names):
    if not available(cur):
        return
    cur.execute('''SELECT t.table_name,v.version_number,v.version_name,bv.version_number AS required_version
        FROM inspection_tables t JOIN inspection_report_version_bindings b ON b.inspection_table_id=t.id
        JOIN inspection_checklist_versions bv ON bv.id=b.checklist_version_id
        LEFT JOIN inspection_checklist_versions v ON v.id=t.active_version_id
        WHERE REPLACE(t.table_name,'加油站','')=ANY(%s) AND (NOT t.is_active OR t.active_version_id IS NULL
            OR t.active_version_id NOT IN ('''+report_supported_versions_sql()+'))', ([n.replace('加油站','') for n in table_names],))
    rows = cur.fetchall()
    if rows:
        details = '；'.join(f"{r['table_name']}：报告模板需要v{r['required_version']}，当前启用v{r['version_number']}" for r in rows)
        raise ValueError('检查表版本与报告模板不兼容，暂不能生成新报告。'+details+'。历史成稿仍可查看和导出。')
