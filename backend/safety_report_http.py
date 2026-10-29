"""Safety-only shared configuration. Reads and saves never generate a report."""
import uuid
from flask import Blueprint, jsonify, request
from safety_report_data import serialize, scope, period_label, category_rows, focus_topics, unit, ONSITE_PAGES, VIDEO_PAGES
from safety_report_analysis import (load_settings, normalize_settings, save_settings, cached_analysis,
    effective_analysis, analyze)
from report_ai_memory import fingerprint, begin_report_ai_memory, end_report_ai_memory, report_ai_generation_log


def selected_issues(rows, settings):
    ids = settings['station_ids']
    return [row for row in rows if ids is None or row['station_id'] in ids]


def config_categories(issues, settings):
    options = [('onsite', '__typical__', '现场典型问题'), ('video', '__typical__', '视频典型问题')]
    options += [('onsite', key, title) for key, title, _ in ONSITE_PAGES]
    options += [('video', key, title) for key, title in VIDEO_PAGES]
    focus_options = focus_topics(issues)
    focus = settings['focus_category']
    if focus not in {item['name'] for item in focus_options}: focus = focus_options[0]['name'] if focus_options else ''
    if focus: options.append(('onsite', 'topic:' + focus, '1. 月度重点：' + focus))
    return options, focus_options, focus


def register_safety_report(app, *, connect, authorize, period, fetch_inputs, has_permission, save_workspace, log_usage):
    blueprint = Blueprint('safety_report', __name__)

    def read_context(cur, source):
        user = authorize(cur)
        start, end = period('safety_quality', source.get('month', ''), dict(source))
        raw, visits, _ = fetch_inputs(cur, user, start, end)
        all_issues = [serialize(row) for row in raw]
        meta = load_settings(cur)
        settings = normalize_settings(meta['settings'])
        return user, start, end, all_issues, visits, meta, settings

    @blueprint.route('/api/inspection-reports/safety-config', methods=['GET', 'PUT'])
    def configuration():
        conn = None
        try:
            source = (request.get_json(silent=True) or {}) if request.method == 'PUT' else request.args
            conn = connect(); cur = conn.cursor()
            user, start, end, all_issues, visits, meta, settings = read_context(cur, source)
            if request.method == 'PUT':
                new = normalize_settings(source.get('settings'))
                available_stations = {row['station_id'] for row in all_issues} | {row['station_id'] for row in visits}
                if new['station_ids'] != settings['station_ids'] and new['station_ids'] is not None and not set(new['station_ids']).issubset(available_stations):
                    raise ValueError('数据来源包含当前范围不可用的站点。')
                eligible = selected_issues(all_issues, new)
                for mode, issue_id in new['typical_issue_ids'].items():
                    if issue_id != settings['typical_issue_ids'].get(mode) and not any(row['issue_id'] == issue_id and row['mode'] == mode for row in eligible):
                        raise ValueError('典型问题必须来自对应现场或视频问题库。')
                if new['focus_category'] != settings['focus_category'] and new['focus_category'] and new['focus_category'] not in {row['topic'] for row in eligible if row['mode'] == 'onsite'}:
                    raise ValueError('月度重点检查主题不在当前现场数据中。')
                for key, value in new['classifications'].items():
                    mode, category = key.split(':', 1)
                    allowed = {row['issue_id'] for row in category_rows(eligible, mode, category)}
                    previous = settings['classifications'].get(key, {}).get('assignments', {})
                    for issue_id, name in value.get('assignments', {}).items():
                        if previous.get(issue_id) != name and int(issue_id) not in allowed:
                            raise ValueError('再分类调整包含当前类别以外的问题。')
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
            options, focus_options, focus = config_categories(issues, settings)
            categories = []
            for mode, category, name in options:
                chosen = category_rows(issues, mode, category)
                key = mode + ':' + category
                value = cached_analysis(cur, chosen, mode, category)
                categories.append({'key': key, 'mode': mode, 'category': category, 'name': name,
                    'issues': chosen, 'analysis': effective_analysis(value, chosen, settings['classifications'].get(key) or {})})
            conn.commit()
            return jsonify(success=True, settings=settings, meta=meta, issues=issues, categories=categories,
                stations=list(candidates.values()), focus_categories=focus_options, focus_category=focus,
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
