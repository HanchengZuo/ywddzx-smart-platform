"""Frozen v12.7 data migration. Never commits or starts work at import time."""
import json
import re
from pathlib import Path
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor

ASSETS = Path(__file__).parent/'assets/checklist_versions'


def install_physical(cur, physical):
    cur.execute(sql.SQL('ALTER TABLE {} ADD COLUMN IF NOT EXISTS checklist_version_id INTEGER REFERENCES inspection_checklist_versions(id)').format(sql.Identifier(physical)))
    cur.execute(sql.SQL('DROP TRIGGER IF EXISTS checklist_standard_version ON {}').format(sql.Identifier(physical)))
    cur.execute(sql.SQL('CREATE TRIGGER checklist_standard_version BEFORE INSERT OR UPDATE OR DELETE ON {} FOR EACH ROW EXECUTE FUNCTION checklist_bind_standard_version()').format(sql.Identifier(physical)))


def install(cur):
    cur.execute((Path(__file__).with_name('checklist_version_schema.sql')).read_text())
    cur.execute('''INSERT INTO inspection_checklist_versions(inspection_table_id,version_number,version_name,fields)
        SELECT t.id,1,'初始版本',COALESCE((SELECT jsonb_agg(to_jsonb(f) ORDER BY f.sort_order,f.id)
        FROM inspection_table_fields f WHERE f.inspection_table_id=t.id),'[]'::jsonb)
        FROM inspection_tables t ON CONFLICT(inspection_table_id,version_number) DO NOTHING;
        UPDATE inspection_tables t SET active_version_id=v.id FROM inspection_checklist_versions v
        WHERE v.inspection_table_id=t.id AND v.version_number=1 AND t.active_version_id IS NULL;
        INSERT INTO inspection_report_version_bindings SELECT id,active_version_id FROM inspection_tables ON CONFLICT DO NOTHING;''')
    cur.execute("SELECT to_regclass('inspection_table_original_files') AS present")
    if cur.fetchone()['present']:
        cur.execute('''UPDATE inspection_checklist_versions v SET original_document=to_jsonb(d)
            FROM inspection_table_original_files d WHERE d.inspection_table_id=v.inspection_table_id
            AND v.version_number=1 AND v.original_document='{}'::jsonb''')
    cur.execute('SELECT id,table_code,active_version_id FROM inspection_tables ORDER BY id')
    tables = cur.fetchall()
    for table in tables:
        if not re.fullmatch(r'[a-z][a-z0-9_]{1,41}', table['table_code']):
            raise ValueError('非法检查表物理表编码，迁移已停止。')
        physical = 'inspection_table_'+table['table_code']
        cur.execute('SELECT to_regclass(%s) AS present', (physical,))
        if not cur.fetchone()['present']:
            continue
        cur.execute(sql.SQL('ALTER TABLE {} ADD COLUMN IF NOT EXISTS checklist_version_id INTEGER REFERENCES inspection_checklist_versions(id)').format(sql.Identifier(physical)))
        cur.execute(sql.SQL('UPDATE {} SET checklist_version_id=%s WHERE checklist_version_id IS NULL').format(sql.Identifier(physical)), (table['active_version_id'],))
        cur.execute(sql.SQL('''INSERT INTO checklist_standard_registry(standard_id,inspection_table_id,checklist_version_id)
            SELECT standard_id,%s,checklist_version_id FROM {} ON CONFLICT(standard_id) DO NOTHING''').format(sql.Identifier(physical)), (table['id'],))
        cur.execute(sql.SQL('''SELECT s.standard_id FROM {} s JOIN checklist_standard_registry r USING(standard_id)
            WHERE r.inspection_table_id<>%s LIMIT 1''').format(sql.Identifier(physical)), (table['id'],))
        if cur.fetchone():
            raise ValueError('发现跨表重复规范ID，迁移已回滚。')
        install_physical(cur, physical)
    for name in ('inspections', 'issues', 'inspection_highlights'):
        cur.execute('SELECT to_regclass(%s) AS present', (name,))
        if not cur.fetchone()['present']:
            continue
        cur.execute(sql.SQL('ALTER TABLE {} ADD COLUMN IF NOT EXISTS checklist_version_id INTEGER REFERENCES inspection_checklist_versions(id)').format(sql.Identifier(name)))
        cur.execute(sql.SQL('''UPDATE {} b SET checklist_version_id=t.active_version_id FROM inspection_tables t
            WHERE b.inspection_table_id=t.id AND b.checklist_version_id IS NULL''').format(sql.Identifier(name)))
        cur.execute(sql.SQL('ALTER TABLE {} ALTER COLUMN checklist_version_id SET NOT NULL').format(sql.Identifier(name)))
        cur.execute(sql.SQL('CREATE INDEX IF NOT EXISTS {} ON {}(checklist_version_id,id)').format(sql.Identifier(name+'_checklist_version'), sql.Identifier(name)))
        cur.execute(sql.SQL('DROP TRIGGER IF EXISTS checklist_record_version ON {}').format(sql.Identifier(name)))
        cur.execute(sql.SQL('CREATE TRIGGER checklist_record_version BEFORE INSERT OR UPDATE ON {} FOR EACH ROW EXECUTE FUNCTION checklist_bind_record_version()').format(sql.Identifier(name)))
    cur.execute('''DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='checklist_active_version_family') THEN
        ALTER TABLE inspection_tables ADD CONSTRAINT checklist_active_version_family FOREIGN KEY(id,active_version_id)
        REFERENCES inspection_checklist_versions(inspection_table_id,id) DEFERRABLE INITIALLY DEFERRED;
        END IF; END $$;
        DROP TRIGGER IF EXISTS checklist_initial_version ON inspection_tables;
        CREATE TRIGGER checklist_initial_version AFTER INSERT ON inspection_tables FOR EACH ROW EXECUTE FUNCTION checklist_create_initial_version();''')
    seed_service(cur)


def seed_service(cur):
    cur.execute("SELECT id,table_code,active_version_id FROM inspection_tables WHERE table_name='现场检查明细表（现场）' FOR UPDATE")
    table = cur.fetchone()
    if not table:
        return
    cur.execute("SELECT id FROM inspection_checklist_versions WHERE inspection_table_id=%s AND source_key='service-onsite-20260707'", (table['id'],))
    if cur.fetchone():
        return
    physical = 'inspection_table_'+table['table_code']
    cur.execute(sql.SQL('SELECT count(*) AS n FROM {} WHERE standard_id BETWEEN 11039 AND 11052').format(sql.Identifier(physical)))
    count = cur.fetchone()['n']
    if count == 0:
        return
    if count != 14:
        raise ValueError('11039–11052规范不完整，未移动任何规范，请补齐后重试。')
    payload = json.loads((ASSETS/'service_onsite_v2.json').read_text())
    fields = [{'field_key':'f_service_onsite_v2_'+key, 'field_label':label, 'sort_order':i,
        'is_filterable':key!='standard', 'is_register_visible':True, 'is_long_text':key=='standard', 'is_scorable':False}
        for i,(key,label) in enumerate([('project','项目'),('content','内容'),('standard','检查评比标准'),('method','检查方式')],1)]
    doc = {'asset':'service_onsite_v2.pdf','original_filename':'现场检查明细表（现场巡检）.pdf', 'file_size':(ASSETS/'service_onsite_v2.pdf').stat().st_size}
    cur.execute('''INSERT INTO inspection_checklist_versions(inspection_table_id,version_number,version_name,description,fields,original_document,source_key)
        SELECT %s,MAX(version_number)+1,'2026年7月新版','项目 / 内容 / 检查评比标准 / 检查方式',%s,%s,'service-onsite-20260707'
        FROM inspection_checklist_versions WHERE inspection_table_id=%s RETURNING id''', (table['id'],Json(fields),Json(doc),table['id']))
    new_id = cur.fetchone()['id']
    for f in fields:
        cur.execute(sql.SQL('ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} TEXT').format(sql.Identifier(physical),sql.Identifier(f['field_key'])))
    cur.execute("SELECT set_config('ywddzx.allow_standard_reassignment','on',TRUE)")
    for row in payload:
        cur.execute(sql.SQL('UPDATE {} SET checklist_version_id=%s,{}=%s,{}=%s,{}=%s,{}=%s WHERE standard_id=%s').format(
            sql.Identifier(physical),*[sql.Identifier(f['field_key']) for f in fields]),
            (new_id,row['project'],row['content'],row['standard'],row['method'],row['standard_id']))
    cur.execute("SELECT set_config('ywddzx.allow_standard_reassignment','off',TRUE)")
    # Only the active compatibility projection changes; old fields/values and all
    # issue snapshots remain in their original version.
    cur.execute('DELETE FROM inspection_table_fields WHERE inspection_table_id=%s', (table['id'],))
    for f in fields:
        cur.execute('''INSERT INTO inspection_table_fields(inspection_table_id,field_key,field_label,is_filterable,is_register_visible,is_long_text,is_scorable,sort_order)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)''', (table['id'],*[f[k] for k in ['field_key','field_label','is_filterable','is_register_visible','is_long_text','is_scorable','sort_order']]))
    cur.execute('UPDATE inspection_tables SET active_version_id=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s', (new_id,table['id']))
    cur.execute('''INSERT INTO checklist_version_events(inspection_table_id,checklist_version_id,action,detail)
        VALUES(%s,%s,'导入并启用新版',%s)''', (table['id'],new_id,Json({'moved_standard_ids':list(range(11039,11053)), 'historical_snapshots':'preserved'})))
