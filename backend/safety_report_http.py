"""Safety-only shared configuration. Reads and saves never generate a report."""
import uuid
from flask import Blueprint, jsonify, request
from safety_report_data import serialize, scope, period_label, category_rows, focus_topics, focus_topic_options, unit, unit_key, ONSITE_PAGES, VIDEO_PAGES
from safety_report_analysis import (load_settings, normalize_settings, save_settings, cached_analysis,
    effective_analysis, analyze)
from report_ai_memory import fingerprint, begin_report_ai_memory, end_report_ai_memory, report_ai_generation_log
from safety_report_examples import cached_representatives, with_representatives, apply_representative_overrides
from safety_video_themes import selected_video_group, selected_video_issue


def selected_issues(rows, settings):
    ids = settings['station_ids']
    return [row for row in rows if ids is None or row['station_id'] in ids]


def config_categories(issues, settings, catalog=None):
    options = [('onsite', '__typical__', '现场典型问题'), ('video', '__typical__', '视频典型问题')]
    options += [('onsite', key, title) for key, title, _ in ONSITE_PAGES]
    options += [('video', key, title) for key, title in VIDEO_PAGES]
    ranked = focus_topics(issues)
    focus_options = focus_topic_options(issues, catalog)
    focus = settings['focus_category']
    if focus not in {item['name'] for item in ranked}: focus = ranked[0]['name'] if ranked else ''
    if focus: options.append(('onsite', 'topic:' + focus, '1. 月度重点：' + focus))
    return options, focus_options, focus


def register_safety_report(app, *, connect, authorize, period, fetch_inputs, has_permission, save_workspace, log_usage, fetch_topics=None, fetch_requirements=None):
    blueprint = Blueprint('safety_report', __name__)

    def read_context(cur, source):
        user = authorize(cur)
        start, end = period('safety_quality', source.get('month', ''), dict(source))
        raw, visits, _ = fetch_inputs(cur, user, start, end)
        all_issues = [serialize(row) for row in raw]
        meta = load_settings(cur)
        settings = normalize_settings(meta['settings'])
        if fetch_requirements:
            from safety_requirements import attach_requirements, requirements_signature
            requirements = fetch_requirements(cur,user)
            all_issues = attach_requirements(all_issues,requirements)
            settings['requirements_signature'] = requirements_signature(requirements)
        return user, start, end, all_issues, visits, meta, settings

    def selected_analysis(cur, chosen, mode, category, override):
        value = effective_analysis(cached_analysis(cur,chosen,mode,category),chosen,override)
        if category != '__typical__':
            value = cached_representatives(cur,value,chosen,mode,category)
            value = apply_representative_overrides(value,chosen,override)
        return value

    @blueprint.route('/api/inspection-reports/safety-config', methods=['GET', 'PUT'])
    def configuration():
        conn = None
        try:
            source = (request.get_json(silent=True) or {}) if request.method == 'PUT' else request.args
            conn = connect(); cur = conn.cursor()
            user, start, end, all_issues, visits, meta, settings = read_context(cur, source)
            if request.method == 'PUT':
                new = normalize_settings(source.get('settings'))
                if new['requirements_signature'] != settings['requirements_signature']:
                    raise ValueError('规范要求已更新，请重新读取配置后再保存。')
                available_stations = {row['station_id'] for row in all_issues} | {row['station_id'] for row in visits}
                if new['station_ids'] != settings['station_ids'] and new['station_ids'] is not None and not set(new['station_ids']).issubset(available_stations):
                    raise ValueError('数据来源包含当前范围不可用的站点。')
                eligible = selected_issues(all_issues, new)
                if new['typical_video_category'] and new['typical_video_category'] != settings['typical_video_category']:
                    video = category_rows(eligible,'video','__typical__')
                    analysis = cached_analysis(cur,video,'video','__typical__')
                    analysis = effective_analysis(analysis,video,new['classifications'].get('video:__typical__') or {})
                    if not analysis.get('complete') or new['typical_video_category'] not in {g['name'] for g in analysis['groups']}:
                        raise ValueError('视频典型问题类别已变化，请先读取完整分类后再选择。')
                for mode, issue_id in new['typical_issue_ids'].items():
                    if issue_id != settings['typical_issue_ids'].get(mode) and not any(row['issue_id'] == issue_id and row['mode'] == mode for row in eligible):
                        raise ValueError('典型问题必须来自对应现场或视频问题库。')
                    if mode=='video' and (issue_id != settings['typical_issue_ids'].get(mode)
                            or new['typical_video_category'] != settings['typical_video_category']):
                        video = category_rows(eligible,'video','__typical__')
                        analysis = selected_analysis(cur,video,'video','__typical__',new['classifications'].get('video:__typical__') or {})
                        group = selected_video_group(video,analysis,new['typical_video_category'])
                        photo = selected_video_issue(video,group,issue_id)
                        if not analysis.get('complete') or not photo or photo['issue_id'] != issue_id:
                            raise ValueError('视频典型照片必须来自当前所选类别且有照片，请重新选择。')
                if new['focus_category'] != settings['focus_category'] and new['focus_category'] and new['focus_category'] not in {row['topic'] for row in eligible if row['mode'] == 'onsite'}:
                    raise ValueError('月度重点检查主题不在当前现场数据中。')
                for key, value in new['classifications'].items():
                    mode, category = key.split(':', 1)
                    allowed = {row['issue_id'] for row in category_rows(eligible, mode, category)}
                    previous = settings['classifications'].get(key, {}).get('assignments', {})
                    for issue_id, name in value.get('assignments', {}).items():
                        if previous.get(issue_id) != name and int(issue_id) not in allowed:
                            raise ValueError('再分类调整包含当前类别以外的问题。')
                    representatives = value.get('representatives') or {}
                    old_representatives = settings['classifications'].get(key,{}).get('representatives') or {}
                    if representatives and (representatives != old_representatives or value.get('assignments',{}) != previous):
                        chosen = category_rows(eligible,mode,category)
                        analysis = effective_analysis(cached_analysis(cur,chosen,mode,category),chosen,value)
                        photos = {row['issue_id'] for row in chosen if row.get('issue_photo')}
                        members = {g['name']:set(g['issue_ids']) & photos for g in analysis['groups']}
                        for name,ids in representatives.items():
                            if name not in members or not set(ids)<=members[name]:
                                raise ValueError('代表问题必须有照片且属于对应的问题表现分类，请重新选择。')
                if source.get('data_signature') != fingerprint(all_issues): raise ValueError('问题库已变化，请重新读取后再保存。')
                save_settings(cur, new, int(source.get('revision', -1)), user)
                save_workspace(cur, 'safety_quality', user, section='safety_settings')
                conn.commit()
                settings, meta = new, load_settings(cur)
            issues = selected_issues(all_issues, settings)
            selected_visits = [v for v in visits if settings['station_ids'] is None or v['station_id'] in settings['station_ids']]
            sections = [scope(issues, selected_visits, mode, period_label(start, end)) for mode in ('onsite', 'video')]
            candidates = {}
            for row in [*visits, *all_issues]:
                station_id = row['station_id']
                candidates.setdefault(station_id, {'station_id': station_id, 'station_name': row.get('station_name'),
                    'unit_name': row.get('unit_name') or unit(row), 'onsite_count': 0, 'video_count': 0})
            for row in all_issues: candidates[row['station_id']][row['mode'] + '_count'] += 1
            options, focus_options, focus = config_categories(issues, settings, fetch_topics(cur, user) if fetch_topics else None)
            categories = []
            for mode, category, name in options:
                chosen = category_rows(issues, mode, category)
                key = mode + ':' + category
                override = settings['classifications'].get(key) or {}
                value = selected_analysis(cur,chosen,mode,category,override)
                categories.append({'key': key, 'mode': mode, 'category': category, 'name': name,
                    'issues': chosen, 'analysis': value, 'slot_limit': 6 if mode=='onsite' and category in ('设备设施','其他隐患类') else 3})
            conn.commit()
            return jsonify(success=True, settings=settings, meta=meta, issues=issues, categories=categories,
                stations=sorted(candidates.values(), key=lambda s:(unit_key(s['unit_name']),s['station_name'] or '')), focus_categories=focus_options, focus_category=focus,
                summary={'region_count': len({row['unit_name'] for row in candidates.values() if settings['station_ids'] is None or row['station_id'] in settings['station_ids']}),
                    'station_count': len({row['station_id'] for row in issues} | {row['station_id'] for row in selected_visits}),
                    'issue_count': len(issues), 'onsite_count': sections[0]['total_issue_count'], 'video_count': sections[1]['total_issue_count']},
                can_generate=has_permission(cur, user, 'generate_inspection_reports'), data_signature=fingerprint(all_issues))
        except PermissionError as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 403
        except (ValueError, TypeError) as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 400
        except Exception:
            if conn: conn.rollback()
            app.logger.exception('Safety configuration failed')
            return jsonify(success=False, error='安全报告配置读取或保存失败，请重试。'), 500
        finally:
            if conn: conn.close()

    @blueprint.get('/api/inspection-reports/safety-analysis')
    def read_analysis():
        conn = None
        try:
            conn = connect(); cur = conn.cursor()
            _, _, _, all_issues, _, meta, settings = read_context(cur, request.args)
            issues = selected_issues(all_issues, settings)
            mode, category = request.args.get('mode'), str(request.args.get('category') or '')
            options, focuses, _ = config_categories(issues, settings)
            allowed = {(m, c) for m, c, _ in options} | {('onsite', 'topic:' + item['name']) for item in focuses}
            if (mode, category) not in allowed: raise ValueError('请选择当前报告的有效检查主题。')
            chosen = category_rows(issues, mode, category)
            key = mode + ':' + category
            value = selected_analysis(cur,chosen,mode,category,settings['classifications'].get(key) or {})
            conn.commit()
            return jsonify(success=True, analysis=value, issues=chosen, revision=meta['revision'], data_signature=fingerprint(all_issues))
        except PermissionError as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 403
        except (ValueError, TypeError) as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 400
        except Exception:
            if conn: conn.rollback()
            app.logger.exception('Safety analysis read failed')
            return jsonify(success=False, error='主题分析读取失败，请稍后重试。'), 500
        finally:
            if conn: conn.close()

    @blueprint.post('/api/inspection-reports/safety-analysis')
    def classify():
        conn = token = None
        try:
            source = request.get_json(silent=True) or {}
            conn = connect(); cur = conn.cursor()
            user, _, _, all_issues, _, meta, settings = read_context(cur, source)
            if not has_permission(cur, user, 'generate_inspection_reports'):
                raise PermissionError('当前账号无生成AI报告权限，不能调用AI重新分析。')
            if source.get('data_signature') != fingerprint(all_issues) or source.get('revision') != meta['revision']:
                raise ValueError('数据或配置已更新，请重新读取后再分析。')
            issues = selected_issues(all_issues, settings)
            mode, category = source.get('mode'), str(source.get('category') or '')
            options, focuses, _ = config_categories(issues, settings)
            allowed = {(m, c) for m, c, _ in options} | {('onsite', 'topic:' + item['name']) for item in focuses}
            if (mode, category) not in allowed: raise ValueError('请选择当前报告的有效分析类别。')
            chosen = category_rows(issues, mode, category)
            conn.commit(); conn.close(); conn = None
            token = begin_report_ai_memory(connect, 'safety-panel-' + uuid.uuid4().hex, 'safety_quality')
            usage = []
            result = analyze(chosen, mode, category, usage.append)
            override = settings['classifications'].get(mode+':'+category) or {}
            result = effective_analysis(result,chosen,override)
            if category != '__typical__':
                result = with_representatives(result,chosen,mode,category,usage.append)
                result = apply_representative_overrides(result,chosen,override)
            conn = connect(); cur = conn.cursor()
            for item in usage: log_usage(cur, user, item, 'AI报告生成', '安全报告面板再分类', category)
            conn.commit()
            return jsonify(success=True, analysis=result, ai_generation_log=report_ai_generation_log())
        except PermissionError as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 403
        except (ValueError, TypeError) as exc:
            if conn: conn.rollback()
            return jsonify(success=False, error=str(exc)), 400
        except Exception:
            if conn: conn.rollback()
            app.logger.exception('Safety panel AI analysis failed')
            return jsonify(success=False, error='安全问题再分类失败，请稍后重试；原配置未改变。'), 500
        finally:
            end_report_ai_memory(token)
            if conn: conn.close()

    app.register_blueprint(blueprint)
