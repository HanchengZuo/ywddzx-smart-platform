"""Move saved assignments into/out of a shared durable shelf, atomically with tasks."""
import logging
from collections import defaultdict

from flask import g, jsonify, request
from inspection_schedule import (VIEW_PERMISSION, EDIT_PERMISSION, integer, read_board,
                                  save_cell, validate_edits)
from schedule_common import ScheduleConflict, lock_schedule, today
from schedule_shelf_store import event, park_item
from scheduling_map import period


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
            key=(row['station_id'], 'row' if chosen['mode']=='offline' else edit['column_key'],
                 cell['scheduled_date'], tuple(sorted(p['id'] for p in cell['assignees'])))
            buckets[key].append(cell)
    cards=[]
    rows={row['station_id']:row for _,row,_ in selected}
    for (sid,key,_,_),cells in buckets.items():
        cards.append(park_item(cur,actor,chosen['mode'],rows[sid],key,cells,action))
    if clear:
        for edit,_,cell in selected:
            if cell['assignees']:
                save_cell(cur,actor,{**edit,'inspector_ids':[]},chosen,start,end)
    return cards


def apply_dispatch(cur,actor,data,chosen,start,end):
    lock_schedule(cur)
    board=read_board(cur,chosen,start,end)
    action=data.get('action')
    if action in ('park','place'):
        edits=data.get('cells')
        validate_edits(cur,edits,chosen,start,end)
        if len({e['station_id'] for e in edits})!=1 or (chosen['mode']=='online' and len(edits)!=1):
            raise ValueError('现场一次调度一整站，视频一次调度一个单元格。')
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
        if not saved or saved['mode']!=chosen['mode'] or not start<=saved['scheduled_date']<end:
            raise ScheduleConflict('待选安排不属于当前周期，请载入最新待选区。')
        if saved['status']!='waiting' or saved['revision']!=version:
            raise ScheduleConflict('这条待选安排已被其他用户处理，请查看最新排班。')
        if action=='place':
            # Preserve occupied destinations in the same transaction so a two-way swap cannot lose a plan.
            displaced=park_saved(cur,actor,chosen,start,end,selected,clear=False,action='displaced')
            cache={}
            for edit,_,_ in selected:
                save_cell(cur,actor,{**edit,'inspector_ids':saved['inspector_ids'],
                          'scheduled_date':saved['scheduled_date'].isoformat()},chosen,start,end,cache)
            cur.execute('''UPDATE inspection_schedule_shelf SET status='assigned',revision=revision+1,
              target_station_id=%s,target_column_key=%s,updated_by=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s''',
              (edits[0]['station_id'],'row' if chosen['mode']=='offline' else edits[0]['column_key'],actor['id'],sid))
            event(cur,actor,sid,'assigned',dict(station_id=edits[0]['station_id'],inspector_ids=saved['inspector_ids'],displaced_ids=displaced))
            return dict(parked_count=len(displaced),message='已直接安排到目标站点，个人待办已同步。')
        cur.execute("UPDATE inspection_schedule_shelf SET status='discarded',revision=revision+1,updated_by=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s",(actor['id'],sid))
        event(cur,actor,sid,'discarded',dict(name=saved['name'],inspector_ids=saved['inspector_ids']))
        return dict(message='待选安排已移除，保留调度历史。')
    if action=='clear_today':
        if not start<=today()<end: raise ValueError('请切换到本季度或本月后清空今日排班。')
        if data.get('board_token')!=board['board_token']:
            raise ScheduleConflict('排班已变化，请载入最新排班后再清空今日安排。')
        selected=[]
        for row in board['rows']:
            for key,cell in row['cells'].items():
                if cell['status']=='assigned' and cell['scheduled_date']==today().isoformat():
                    selected.append((dict(station_id=row['station_id'],column_key=key,revision=cell['revision']),row,cell))
        cards=park_saved(cur,actor,chosen,start,end,selected)
        return dict(parked_count=len(cards),cleared_count=len(selected),message=f'今日计划已移入待选区（{len(cards)}项），实际检查及其他日期安排保持不变。')
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
            result['board']=dict(read_board(cur,chosen,start,end),can_edit=True)
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
