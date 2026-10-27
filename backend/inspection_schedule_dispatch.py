"""Move saved assignments into/out of a shared durable shelf, atomically with tasks."""
import logging
import json
from collections import defaultdict

from flask import g, jsonify, request
from inspection_schedule import (VIEW_PERMISSION, EDIT_PERMISSION, integer, read_board,
                                  save_cell, validate_edits)
from schedule_common import ScheduleConflict, lock_schedule, today
from schedule_shelf_store import event, park_item, expire_shelf
from schedule_period import period, field_mode


def checked_cells(board, edits):
    rows={r['station_id']:r for r in board['rows']}
    result=[]
    for edit in edits:
        row=rows.get(edit['station_id'])
        if not row: raise PermissionError('本站已不在当前排班名单内。')
        cell=row['cells'][edit['column_key']]
        if cell['revision']!=edit['revision'] or cell['status'] not in ('assigned','unassigned'):
            raise ScheduleConflict('排班或实际记录已经变化，请载入最新排班后再调度。')
        result.append((edit,row,cell))
    return result


def park_saved(cur,actor,chosen,start,end,selected,*,clear=True,action='parked'):
    buckets=defaultdict(list)
    for edit,row,cell in selected:
        if cell['assignees']:
            if not cell['scheduled_date']:
                raise ValueError('旧排班缺少计划日期，请先补齐日期后再调度。')
            if cell['scheduled_date'] < today().isoformat():
                raise ScheduleConflict('过期计划不能移入调度待选区，请直接核对历史排班。')
            key=(row['station_id'], 'row',
                 cell['scheduled_date'], tuple(sorted(p['id'] for p in cell['assignees'])))
            buckets[key].append(cell)
    cards=[]
    rows={row['station_id']:row for _,row,_ in selected}
    for (sid,key,_,_),cells in buckets.items():
        cards.append(park_item(cur,actor,field_mode(chosen['mode']),rows[sid],key,cells,action))
    if clear:
        for edit,_,cell in selected:
            if cell['assignees']:
                save_cell(cur,actor,{**edit,'inspector_ids':[]},chosen,start,end)
    return cards


def apply_dispatch(cur,actor,data,chosen,start,end):
    lock_schedule(cur)
    expire_shelf(cur, already_locked=True)
    board=read_board(cur,chosen,start,end)
    action=data.get('action')
    if action in ('park','place'):
        edits=data.get('cells')
        validate_edits(cur,edits,chosen,start,end)
        if len({e['station_id'] for e in edits})!=1:
            raise ValueError('一次只能调度一个站点的整行未检查项。')
        selected=checked_cells(board,edits)
    if action=='park':
        if not any(c['assignees'] for _,_,c in selected):
            raise ScheduleConflict('该位置已经没有计划，请查看最新排班及待选区。')
        cards=park_saved(cur,actor,chosen,start,end,selected)
        return dict(parked_count=len(cards),message='原计划已撤下并保存至待选区，实际检查记录不变。')
    if action in ('place','discard'):
        sid=integer(data.get('shelf_id'),'待选安排')
        version=integer(data.get('revision'),'待选版本')
        cur.execute('SELECT * FROM inspection_schedule_shelf WHERE id=%s FOR UPDATE',(sid,))
        saved=cur.fetchone()
        if not saved or saved['mode']!=field_mode(chosen['mode']) or saved['scheduled_date']<today() or not start<=saved['scheduled_date']<end:
            raise ScheduleConflict('待选安排不在当前模式或周期内，或已经过期，请重新载入调度待选区。')
        if saved['status']!='waiting' or saved['revision']!=version:
            raise ScheduleConflict('这条待选安排已被其他用户处理，请查看最新排班。')
        if action=='place':
            # The board was read under the cross-worker dispatch lock. Check the
            # live, deduplicated capacity, not a client badge or an old shelf ID.
            available=next((card for card in board['shelf']
                            if card['day']==saved['scheduled_date'].isoformat() and sorted(card['ids'])==sorted(saved['inspector_ids'])),None)
            if not available or available['remaining']<=0:
                raise ScheduleConflict('该组或人员在所选日期的待派站数已为0，不能继续派站。请调整站数目标或撤下该日未开始的排班后再试。')
            # Preserve occupied destinations in the same transaction so a two-way swap cannot lose a plan.
            displaced=park_saved(cur,actor,chosen,start,end,selected,clear=False,action='displaced')
            cache={}
            for edit,_,_ in selected:
                save_cell(cur,actor,{**edit,'inspector_ids':saved['inspector_ids'],
                          'scheduled_date':saved['scheduled_date'].isoformat()},chosen,start,end,cache)
            cur.execute('''UPDATE inspection_schedule_shelf SET status=%s,revision=revision+1,
              target_station_id=%s,target_column_key=%s,updated_by=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s''',
              ('waiting' if saved['source_column_key']=='personnel' else 'assigned',edits[0]['station_id'],'row',actor['id'],sid))
            event(cur,actor,sid,'assigned',dict(station_id=edits[0]['station_id'],inspector_ids=saved['inspector_ids'],displaced_ids=displaced))
            return dict(parked_count=len(displaced),message='已直接安排到目标站点，个人待办已同步。')
        # A displayed card represents a person/team, not one of its old station
        # transfers. Removing it must not reveal a hidden duplicate afterwards.
        ids=json.dumps(saved['inspector_ids'])
        cur.execute('''UPDATE inspection_schedule_shelf SET status='discarded',revision=revision+1,
          updated_by=%s,updated_at=CURRENT_TIMESTAMP WHERE mode=%s AND scheduled_date=%s
          AND status='waiting' AND inspector_ids @> %s::jsonb AND inspector_ids <@ %s::jsonb RETURNING id''',
          (actor['id'],saved['mode'],saved['scheduled_date'],ids,ids))
        removed=list(cur.fetchall())
        for item in removed:
            event(cur,actor,item['id'],'discarded',dict(name=saved['name'],inspector_ids=saved['inspector_ids']))
        return dict(message='待选安排已移除，保留调度历史。')
    if action=='clear_today':
        if not start<=today()<end: raise ValueError('请切换到本季度、本年度或本月后清空今日排班。')
        if data.get('board_token')!=board['board_token']:
            raise ScheduleConflict('排班已变化，请载入最新排班后再清空今日安排。')
        selected=[]
        for row in board['rows']:
            if row.get('locked'): continue
            for key,cell in row['cells'].items():
                if cell['status']=='assigned' and cell['scheduled_date']==today().isoformat():
                    selected.append((dict(station_id=row['station_id'],column_key=key,revision=cell['revision']),row,cell))
        cards=park_saved(cur,actor,chosen,start,end,selected,action='cleared_to_shelf')
        stations=len({row['station_id'] for _,row,_ in selected})
        return dict(parked_count=len(cards),cleared_count=len(selected),cleared_station_count=stations,discarded_count=0,
                    message=f'已撤下 {stations} 站今日未完成排班，转入调度待选区 {len(cards)} 项；原有待选安排、实际检查及其他日期安排保持不变。')
    raise ValueError('请选择移入待选区、安排、移除或清空今日排班。')


def register_schedule_dispatch(app,*,connect,has_permission):
    @app.post('/api/inspection-schedule/dispatch')
    def schedule_dispatch():
        actor=getattr(g,'current_user',None)
        if not actor: return jsonify(success=False,error='请先登录。'),401
        conn=cur=None
        try:
            conn=connect();cur=conn.cursor()
            if not has_permission(cur,actor,VIEW_PERMISSION) or not has_permission(cur,actor,EDIT_PERMISSION):
                raise PermissionError('当前账号无权调度巡检排班。')
            data=request.get_json(silent=True)
            if not isinstance(data,dict): raise ValueError('请提交有效调度数据。')
            chosen,start,end=period(data)
            cur.execute("SET LOCAL lock_timeout='3s'; SET LOCAL statement_timeout='10s'")
            result=apply_dispatch(cur,actor,data,chosen,start,end)
            result['board']=dict(read_board(cur,chosen,start,end),can_edit=True,current_user_id=actor['id'])
            conn.commit()
            response=jsonify(success=True,**result)
            response.headers['Cache-Control']='private, no-store'
            return response
        except (ValueError,PermissionError) as exc:
            if conn: conn.rollback()
            return jsonify(success=False,error=str(exc)),409 if isinstance(exc,ScheduleConflict) else 403 if isinstance(exc,PermissionError) else 400
        except Exception:
            if conn: conn.rollback()
            logging.exception('Schedule shelf dispatch failed')
            return jsonify(success=False,error='调度暂未完成，请核对最新排班与待选区后重试。'),500
        finally:
            if cur: cur.close()
            if conn: conn.close()
