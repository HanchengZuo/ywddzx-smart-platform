"""Shared service configuration: reading or saving never invokes a model."""
from flask import Blueprint,jsonify,request
from report_ai_memory import fingerprint
from service_report_data import serialize,chosen,scope
from service_report_analysis import (load_settings,normalize_settings,save_settings,read_phrases,
    ensure_phrases,behaviors,examples,category_groups)

def register_service_report(app,*,connect,authorize,period,fetch_inputs,fetch_catalog,has_permission,save_workspace,log_usage):
    bp=Blueprint('service_report',__name__)
    def context(cur,source):
        user=authorize(cur)
        start,end=period('on_site_service',source.get('month',''),dict(source))
        raw,visits,_=fetch_inputs(cur,user,start,end)
        catalog=fetch_catalog(cur,user); rows=serialize(raw,catalog); meta=load_settings(cur)
        return user,rows,visits,catalog,meta
    def signature(rows,catalog):return fingerprint({'issues':rows,'catalog':catalog})
    def response(cur,rows,visits,catalog,meta):
        settings=meta['settings'];selected=chosen(rows,settings);selected_visits=chosen(visits,settings)
        phrases=read_phrases(cur,catalog,settings)
        analysis=behaviors(connect,cur,selected,settings)
        photos=examples(connect,cur,selected,category_groups(selected),settings['examples'],3)
        behavior_photos=examples(connect,cur,selected,analysis['groups'][:4],settings['behavior_examples'],1)
        stations={}
        for row in [*visits,*rows]:
            stations.setdefault(row['station_id'],{'station_id':row['station_id'],'station_name':row['station_name'],'region':row.get('unit_name') or row.get('region'),'issue_count':0})
            if row.get('issue_id'):stations[row['station_id']]['issue_count']+=1
        from safety_report_data import unit_key
        return jsonify(success=True,meta=meta,settings=settings,data_signature=signature(rows,catalog),
            issues=selected,catalog=[dict(item,phrase=phrases.get(item['key'],'')) for item in catalog],
            stations=sorted(stations.values(),key=lambda r:(unit_key(r['region']),r['station_name'])),
            summary=scope(selected,selected_visits),modes=[scope(selected,selected_visits,mode) for mode in ('video','onsite')],
            category_groups=category_groups(selected),examples=photos,behaviors=analysis,behavior_examples=behavior_photos)
    def run(operation):
        conn=connect()
        try:
            result=operation(conn,conn.cursor());conn.commit();return result
        except PermissionError as exc:
            conn.rollback();return jsonify(error=str(exc)),403
        except (ValueError,TypeError) as exc:
            conn.rollback();return jsonify(error=str(exc)),400
        except Exception:
            conn.rollback();app.logger.exception('Service report configuration failed')
            return jsonify(error='现场服务配置处理失败，请稍后重试。'),500
        finally:conn.close()
    @bp.route('/api/inspection-reports/service-config',methods=['GET','PUT'])
    def configuration():
        def operation(conn,cur):
            source=(request.get_json(silent=True) or {}) if request.method=='PUT' else request.args
            user,rows,visits,catalog,meta=context(cur,source)
            if request.method=='PUT':
                if source.get('data_signature')!=signature(rows,catalog):raise ValueError('问题或规范数据已变化，请重新读取后再保存。')
                settings=normalize_settings(source.get('settings'))
                old=meta['settings']
                if settings['station_ids']!=old['station_ids'] and settings['station_ids'] is not None and not set(settings['station_ids'])<={r['station_id'] for r in [*rows,*visits]}:
                    raise ValueError('数据来源包含范围外站点。')
                for key,value in settings['phrases'].items():
                    if value!=old['phrases'].get(key) and key not in {r['key'] for r in catalog}:raise ValueError('环节短语引用了无效规范。')
                selected=chosen(rows,settings);by_id={r['issue_id']:r for r in selected}
                for key,value in settings['behavior_assignments'].items():
                    if value!=old['behavior_assignments'].get(key) and (not key.isdecimal() or int(key) not in by_id):raise ValueError('问题表现调整包含范围外问题。')
                analysis=behaviors(connect,cur,selected,settings)
                groups={'examples':{g['name']:set(g['issue_ids']) for g in category_groups(selected)},
                    'behavior_examples':{g['name']:set(g['issue_ids']) for g in analysis['groups']}}
                for section in groups:
                    for name,ids in settings[section].items():
                        if ids==old[section].get(name):continue
                        allowed=groups[section].get(name,set())
                        if any(i not in allowed or not by_id[i]['issue_photo'] for i in ids):raise ValueError('照片必须来自当前分类的有照片问题。')
                save_settings(cur,settings,int(source.get('revision',-1)),user)
                save_workspace(cur,'on_site_service',user,section='service_settings')
                meta=load_settings(cur)
            return response(cur,rows,visits,catalog,meta)
        return run(operation)
    @bp.post('/api/inspection-reports/service-analysis')
    def analysis():
        source=request.get_json(silent=True) or {}
        def operation(conn,cur):
            user,rows,visits,catalog,meta=context(cur,source)
            if not has_permission(cur,user,'generate_inspection_reports'):raise PermissionError('当前账号无生成AI报告权限，不能调用AI分析。')
            if source.get('revision')!=meta['revision'] or source.get('data_signature')!=signature(rows,catalog):raise ValueError('配置或数据已变化，请重新读取后再分析。')
            kind=source.get('kind');selected=chosen(rows,meta['settings']);usage=[]
            if kind not in ('phrases','examples','behaviors'):raise ValueError('请选择有效的分析任务。')
            conn.commit()  # Do not hold a read transaction during provider calls.
            if kind=='phrases':ensure_phrases(connect,catalog,meta['settings'],usage.append)
            if kind=='examples':examples(connect,None,selected,category_groups(selected),meta['settings']['examples'],3,True,usage.append)
            if kind=='behaviors':
                value=behaviors(connect,None,selected,meta['settings'],True,usage.append)
                examples(connect,None,selected,value['groups'][:4],meta['settings']['behavior_examples'],1,True,usage.append)
            for value in usage:log_usage(cur,user,value,'AI报告生成','现场服务面板分析',kind)
            conn.commit()
            # Re-read shared settings if a colleague saved while the provider was running.
            user,rows,visits,catalog,meta=context(cur,source)
            return response(cur,rows,visits,catalog,meta)
        return run(operation)
    app.register_blueprint(bp)
