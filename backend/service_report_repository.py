"""Service-only evidence queries with the platform's existing data-scope predicates."""
from psycopg2 import sql
from service_report_data import TABLES

def fetch_catalog(cur,user,*,removed,table_scope,permissions,physical_name,exists,metadata):
    clauses=['t.is_active=TRUE',"REPLACE(t.table_name,%s,'') IN (%s,%s)"]
    params=[removed,TABLES['video'],TABLES['onsite']]
    if not table_scope(cur,user,clauses,params,'t.id','limit_plan_inspection_table_scope',permissions=permissions):return []
    cur.execute('SELECT t.id,t.table_code,t.table_name,t.checklist_mode FROM inspection_tables t WHERE '+' AND '.join(clauses)+' ORDER BY t.id',params)
    tables=list(cur.fetchall()); result=[]
    cur.execute('SELECT standard_id FROM external_standard_status WHERE NOT is_active')
    disabled={int(row['standard_id']) for row in cur.fetchall()}
    for table in tables:
        physical=physical_name(table['table_code'])
        if not physical or not exists(cur,physical):continue
        columns=metadata(cur,table['id'])
        cur.execute(sql.SQL('SELECT * FROM {} ORDER BY standard_id').format(sql.Identifier(physical)))
        for row in cur.fetchall():
            if int(row['standard_id']) in disabled:continue
            mode='video' if table['checklist_mode']=='online' else 'onsite'
            identifier=str(row['standard_id'])
            result.append({'key':mode+':'+identifier,'mode':mode,'external_standard_id':identifier,
                'fields':{'检查表':table['table_name'],**{label:str(row.get(key) or '').strip() for key,label in columns}}})
    return result

def fetch_inputs(cur,user,start,end,*,cumulative=False,removed,table_scope,region_scope,permissions):
    clauses=["REPLACE(t.table_name,%s,'') IN (%s,%s)","COALESCE(ins.inspection_date::date,i.created_at::date)<%s"]
    params=[removed,TABLES['video'],TABLES['onsite'],end]
    table_allowed=table_scope(cur,user,clauses,params,'i.inspection_table_id','limit_plan_inspection_table_scope',permissions=permissions)
    region_allowed=region_scope(cur,user,clauses,params,'s.region','limit_plan_station_region_scope',permissions=permissions)
    if not table_allowed or not region_allowed:return [],[],[]
    if cumulative:clauses.append('i.created_at::date<%s');params.append(end)
    else:
        clauses.extend(['t.is_active=TRUE',"COALESCE(ins.inspection_date::date,i.created_at::date)>=%s","COALESCE(i.audit_status,'pending')='approved'"])
        params.append(start)
    cur.execute('''SELECT i.id,i.station_id,i.standard_id,i.standard_detail_text,i.description,i.photo_path AS issue_photo,
        i.status,i.audit_status,i.audited_at,i.rectification_at,i.review_at,i.review_result,ins.station_manager_signed_at,
        s.station_name,s.region,t.table_name,t.checklist_mode,
        COALESCE(ins.inspection_date::date,i.created_at::date) AS report_date
        FROM issues i JOIN inspections ins ON ins.id=i.inspection_id JOIN stations s ON s.id=i.station_id
        JOIN inspection_tables t ON t.id=i.inspection_table_id WHERE '''+' AND '.join(clauses)+' ORDER BY i.id',params)
    rows=[dict(r) for r in cur.fetchall()]
    if cumulative:
        cur.execute('SELECT issue_id,action_type,to_status,created_at FROM inspection_issue_flow_history WHERE issue_id=ANY(%s) AND created_at<%s ORDER BY created_at,id',([r['id'] for r in rows],end))
        return rows,[],[dict(r) for r in cur.fetchall()]
    clauses=["REPLACE(t.table_name,%s,'') IN (%s,%s)",'t.is_active=TRUE',
        'ins.inspection_date::date>=%s','ins.inspection_date::date<%s',"ins.inspector_completion_status='已确认完成'"]
    params=[removed,TABLES['video'],TABLES['onsite'],start,end]
    table_allowed=table_scope(cur,user,clauses,params,'ins.inspection_table_id','limit_plan_inspection_table_scope',permissions=permissions)
    region_allowed=region_scope(cur,user,clauses,params,'s.region','limit_plan_station_region_scope',permissions=permissions)
    if not table_allowed or not region_allowed:return rows,[],[]
    cur.execute('''SELECT DISTINCT ins.station_id,s.station_name,s.region,t.checklist_mode FROM inspections ins
        JOIN stations s ON s.id=ins.station_id JOIN inspection_tables t ON t.id=ins.inspection_table_id WHERE '''+' AND '.join(clauses)+' ORDER BY ins.station_id,t.checklist_mode',params)
    return rows,[dict(r) for r in cur.fetchall()],[]
