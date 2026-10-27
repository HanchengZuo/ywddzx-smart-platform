"""Smart planning projections and atomic replacement of unstarted daily intent."""
from inspection_schedule import read_board, save_cell
from schedule_row_state import today_assignments
from schedule_common import today, day_value
from schedule_period import period


def planning_board(board,day, *, reserved=(), replace_days=()):
    replacing = {d.isoformat() for d in replace_days} | {day.isoformat()}
    rows=[]
    for row in board['rows']:
        cells={}
        for key,cell in row['cells'].items():
            planned = cell.get('scheduled_date') or ''
            clear=not row['locked'] and cell['status']=='assigned' and (planned in replacing or planned < today().isoformat())
            cells[key]=dict(cell,status='unassigned',assignees=[],plan_team=None,scheduled_date=None,overdue=False) if clear else dict(cell)
        rows.append(dict(row,cells=cells))
    if reserved:
        chosen,start,end = period(board['period'])
        lookup = {row['station_id']: row for row in rows}
        for group in reserved:
            if not start <= day_value(group['day']) < end: continue
            mode = chosen['mode']
            cells = group.get('metering_cells', []) if mode == 'annual' else group['cells'] if mode == group['mode'] else []
            row = lookup.get(group['station_id'])
            if not row: continue
            for entry in cells:
                key = entry['column_key']
                if key in row['cells'] and row['cells'][key]['status']=='unassigned':
                    row['cells'][key] = dict(row['cells'][key], status='assigned', scheduled_date=group['day'],
                                            assignees=[dict(id=uid) for uid in group['inspector_ids']])
    return dict(board,rows=rows)


def replacement_summary(boards,day):
    tasks=today_assignments(boards,day)
    return dict(stations=sum(not s['locked'] for g in tasks for s in g['stations']),
                protected=sum(s['locked'] for g in tasks for s in g['stations']))


def protected_daily_counts(boards,day):
    return {(g['mode'],tuple(sorted(p['id'] for p in g['people']))):sum(s['locked'] for s in g['stations'])
            for g in today_assignments(boards,day)}


def apply_smart_plan(cur,actor,result,periods,day):
    # Same outer transaction and global schedule lock as confirmation. Never use
    # a second HTTP call/commit between removing old intent and saving new work.
    cache={}
    cleared=0
    for mode in ('offline','annual','online'):
        chosen,start,end=periods[mode]
        board=read_board(cur,chosen,start,end)
        for row in board['rows']:
            if row['locked']: continue
            for key,cell in row['cells'].items():
                if cell['status']=='assigned' and cell['scheduled_date']==day.isoformat():
                    save_cell(cur,actor,dict(station_id=row['station_id'],column_key=key,revision=cell['revision'],inspector_ids=[]),chosen,start,end,cache)
                    cleared+=1
    current={mode:read_board(cur,*p) for mode,p in periods.items()}
    versions={(mode,r['station_id'],key):c['revision'] for mode,b in current.items() for r in b['rows'] for key,c in r['cells'].items()}
    cache={}
    for group in result['groups']:
        mode='annual' if group.get('metering_cells') else group['mode']
        chosen,start,end=periods[mode]
        for cell in group.get('metering_cells') or group['cells']:
            save_cell(cur,actor,dict(station_id=cell['station_id'],column_key=cell['column_key'],
                revision=versions[(mode,cell['station_id'],cell['column_key'])],
                inspector_ids=group['inspector_ids'],scheduled_date=day.isoformat()),chosen,start,end,cache)
    return cleared
