"""One-time correction of pre-versioning service standards, without splitting visits."""
from psycopg2 import sql
from psycopg2.extras import Json

REASON = 'service-onsite-11039-11052-v2'


def correct_history(cur):
    cur.execute('''CREATE TABLE IF NOT EXISTS checklist_record_version_corrections (
        reason TEXT NOT NULL, record_kind TEXT NOT NULL, record_id INTEGER NOT NULL,
        before_data JSONB NOT NULL, corrected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(reason,record_kind,record_id))''')
    cur.execute("SELECT id,table_code FROM inspection_tables WHERE table_name='现场检查明细表（现场）' FOR UPDATE")
    table = cur.fetchone()
    if not table:
        return
    cur.execute('''SELECT id,fields FROM inspection_checklist_versions
        WHERE inspection_table_id=%s AND source_key='service-onsite-20260707' ''', (table['id'],))
    edition = cur.fetchone()
    if not edition:
        return
    cur.execute('''SELECT 1 FROM checklist_version_events WHERE inspection_table_id=%s
        AND action='纠正新版规范历史归属' AND detail->>'reason'=%s''', (table['id'], REASON))
    if cur.fetchone():
        return
    physical = 'inspection_table_' + table['table_code']
    cur.execute(sql.SQL('SELECT * FROM {} WHERE standard_id BETWEEN 11039 AND 11052 ORDER BY standard_id').format(sql.Identifier(physical)))
    standards = list(cur.fetchall())
    if len(standards) != 14 or any(s['checklist_version_id'] != edition['id'] for s in standards):
        raise ValueError('11039–11052新版规范不完整或版本不符，历史纠正已回滚。')
    # Blocks writers only during this short migration; no global bypass is left
    # in the runtime trigger. All DDL and archived originals roll back together.
    cur.execute('LOCK TABLE inspections,issues IN SHARE ROW EXCLUSIVE MODE')
    for name in ('inspections', 'issues'):
        cur.execute(sql.SQL('ALTER TABLE {} DISABLE TRIGGER checklist_record_version').format(sql.Identifier(name)))
    cur.execute('''INSERT INTO checklist_record_version_corrections(reason,record_kind,record_id,before_data)
        SELECT %s,'issues',i.id,to_jsonb(i) FROM issues i WHERE i.inspection_table_id=%s
        AND i.standard_id BETWEEN 11039 AND 11052 ON CONFLICT DO NOTHING''', (REASON, table['id']))
    changed = 0
    for standard in standards:
        detail = '\n'.join(f"{f['field_label']}：{str(standard.get(f['field_key']) or '').strip()}"
            for f in edition['fields'] if str(standard.get(f['field_key']) or '').strip())
        if not detail:
            raise ValueError('新版规范详情为空，历史纠正已回滚。')
        cur.execute('''UPDATE issues SET checklist_version_id=%s,standard_detail_text=%s
            WHERE inspection_table_id=%s AND standard_id=%s
            AND (checklist_version_id IS DISTINCT FROM %s OR standard_detail_text IS DISTINCT FROM %s)''',
            (edition['id'], detail, table['id'], standard['standard_id'], edition['id'], detail))
        changed += cur.rowcount
    # Mixed old/new visits retain their ID, signature and confirmation records;
    # their represented versions are derived from the issues when reading them.
    cur.execute('''SELECT ins.id FROM inspections ins WHERE ins.inspection_table_id=%s
        AND ins.checklist_version_id<>%s AND EXISTS(SELECT 1 FROM issues i WHERE i.inspection_id=ins.id)
        AND NOT EXISTS(SELECT 1 FROM issues i WHERE i.inspection_id=ins.id AND i.checklist_version_id<>%s)''',
        (table['id'], edition['id'], edition['id']))
    records = [r['id'] for r in cur.fetchall()]
    cur.execute('''INSERT INTO checklist_record_version_corrections(reason,record_kind,record_id,before_data)
        SELECT %s,'inspections',ins.id,to_jsonb(ins) FROM inspections ins WHERE ins.id=ANY(%s)
        ON CONFLICT DO NOTHING''', (REASON, records))
    cur.execute('UPDATE inspections SET checklist_version_id=%s WHERE id=ANY(%s)', (edition['id'], records))
    for name in ('inspections', 'issues'):
        cur.execute(sql.SQL('ALTER TABLE {} ENABLE TRIGGER checklist_record_version').format(sql.Identifier(name)))
    cur.execute('''INSERT INTO checklist_version_events(inspection_table_id,checklist_version_id,action,detail)
        VALUES(%s,%s,'纠正新版规范历史归属',%s)''',
        (table['id'], edition['id'], Json({'reason': REASON, 'issue_count': changed,
            'inspection_count': len(records), 'mixed_records': 'preserved; versions derived from issues'})))
