import copy
import importlib.util
import json
import os
import tempfile
import unittest
import uuid
from datetime import date,datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from contextlib import contextmanager
from zipfile import ZipFile
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask,g,request
from pptx import Presentation
from PIL import Image
from service_report_data import (serialize,category_label,scope,cumulative,build_report,period_label,POLICY)
from service_report_analysis import (normalize_settings,validate,phrase_context,read_phrases,ensure_phrases,
    behavior_context,behaviors,examples,category_groups,run_ai,load_settings)
from service_report_presentation import build_service_presentation,TEMPLATE_FILE
from service_report_http import register_service_report
from safety_report_data import UNIT_ORDER
from service_report_units import hierarchy,unit_discoveries,evidence_context

def catalog():
    return [{'key':f'{mode}:{i}','mode':mode,'external_standard_id':str(i),
        'fields':{'检查表':'现场检查明细表','检查类别':'暖心服务','检查内容':'礼貌坚决劝阻顾客抽烟、打手机等不安全行为',
            '考察类别区域':'区域管理（20分）','考察类别项目':'油罐区及卸油区'}} for mode,i in [('video',10001),('onsite',11001)]]

def raw(index=1,mode='video',**extra):
    return dict(dict(id=index,station_id=index,station_name=f'测试站{index}',region=UNIT_ORDER[(index-1)%len(UNIT_ORDER)],
        standard_id=10001 if mode=='video' else 11001,checklist_mode='online' if mode=='video' else 'offline',
        description='顾客打手机未被劝阻',issue_photo='',audit_status='approved',audited_at=date(2026,9,2)),**extra)

def fixture_report(photo='',count=36):
    standards=catalog();raw_rows=[raw(i+1,'video' if i%2==0 else 'onsite',issue_photo=photo) for i in range(count)]
    issues=serialize(raw_rows,standards);visits=[dict(r) for r in raw_rows]
    settings=normalize_settings({});start,end=date(2026,9,1),date(2026,10,1)
    groups=[{'name':'未劝阻手机使用','issue_ids':[r['issue_id'] for r in issues],'count':len(issues),'percentage':100 if issues else 0}]
    analysis={'groups':groups if issues else [],'assignments':{str(r['issue_id']):'未劝阻手机使用' for r in issues},'complete':True}
    photos={group['name']:group['issue_ids'][:3] for group in category_groups(issues)}
    behavior_photos={'未劝阻手机使用':[issues[0]['issue_id']]} if issues else {}
    return build_report(start,end,issues,visits,cumulative(raw_rows,[],end,settings),settings,
        {'video:10001':'礼貌劝阻','onsite:11001':'油罐区及卸油区'},analysis,photos,behavior_photos)

class ServiceDataTests(unittest.TestCase):
    def test_unit_hierarchy_and_strict_summary_photo_references(self):
        rows=serialize([raw(2,'onsite'),raw(1,issue_photo='photo.jpg'),raw(3,region=UNIT_ORDER[0])],catalog())
        units=hierarchy(rows,{'video:10001':'礼貌劝阻'})
        self.assertEqual([u['unit_name'] for u in units],UNIT_ORDER[:2])
        self.assertEqual(units[0]['categories'][0]['count'],2)
        group=units[0]['categories'][0]['groups'][0]
        self.assertEqual(group['issue_ids'],[1,3])
        context=evidence_context([(units[0]['unit_name'],units[0]['categories'][0]['name'],group)],{r['issue_id']:r for r in rows})
        for value in [{'summary':'','photo_ids':['I1']},{'summary':'未劝阻手机使用','photo_ids':['I3']},
            {'summary':'x'*161,'photo_ids':['I1']},{'summary':'未劝阻手机使用','photo_ids':[]}]:
            with self.assertRaises(ValueError):validate({'items':{'G1':value}},context)
        self.assertEqual(validate({'items':{'G1':{'summary':'未劝阻手机使用','photo_ids':['I1']}}},context)['items']['G1']['photo_ids'],['I1'])

    def test_two_column_chapter_keeps_first_chapter_and_paginates_without_losing_evidence(self):
        from service_report_unit_presentation import panels
        report=fixture_report(count=6)
        units=hierarchy(report['service_issues'],{'video:10001':'礼貌劝阻'})
        for unit in units:
            for category in unit['categories']:
                for group in category['groups']:group.update(summary='员工未及时劝阻顾客在加油现场使用手机。',photo_ids=[])
        report['unit_discoveries']=units
        # A long clause must continue rather than be truncated or disappear into notes.
        category=copy.deepcopy(units[0]['categories'][0]);group=category['groups'][0]
        group['summary']='描述较长但必须全部保留。'*15
        group['station_names']=['很长的站点名称'+str(i) for i in range(40)]
        category['station_names']=group['station_names']
        chunks=panels(category)
        self.assertGreater(len(chunks),1)
        self.assertTrue(all(len(p['lines'])<=12 for p in chunks))
        text=''.join(line[0] for p in chunks for line in p['lines'])
        self.assertIn(group['summary'],text);self.assertIn(group['station_names'][-1],text)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'units.pptx';build_service_presentation(report,path,directory)
            prs=Presentation(path)
            self.assertGreater(len(prs.slides),14)
            for slide in list(prs.slides)[14:]:
                for shape in slide.shapes:
                    self.assertLessEqual(shape.left+shape.width,prs.slide_width+10000)
                    self.assertLessEqual(shape.top+shape.height,prs.slide_height+10000)
            self.assertIn('礼貌劝阻',''.join(s.text for sl in list(prs.slides)[14:] for s in sl.shapes if s.has_text_frame))
            # Prefix text and existing counts remain identical to chapter-one output.
            del report['unit_discoveries'];first=Path(directory)/'first.pptx';build_service_presentation(report,first,directory)
            old=Presentation(first)
            self.assertEqual([[s.text for s in slide.shapes if s.has_text_frame] for slide in old.slides],
                [[s.text for s in slide.shapes if s.has_text_frame] for slide in list(prs.slides)[:13]])
    def test_repository_denied_scope_never_reads_business_rows(self):
        from service_report_repository import fetch_inputs,fetch_catalog
        cur=MagicMock()
        self.assertEqual(fetch_inputs(cur,{},date(2026,9,1),date(2026,10,1),removed='',
            table_scope=lambda *a,**k:False,region_scope=lambda *a,**k:True,permissions={}),([],[],[]))
        cur.execute.assert_not_called()
        self.assertEqual(fetch_catalog(cur,{},removed='',table_scope=lambda *a,**k:False,permissions={},
            physical_name=lambda code:code,exists=lambda *a:True,metadata=lambda *a:[]),[])
        cur.execute.assert_not_called()
    def test_current_fields_score_suffix_retired_filter_and_business_unit_order(self):
        self.assertEqual(category_label('加管3.0系统风控管理 （20分）'),'加管3.0系统风控管理')
        self.assertEqual(category_label('服务（含夜间）'),'服务（含夜间）')
        rows=serialize([raw(),raw(2,'onsite'),raw(3,standard_id=99999)],catalog())
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[1]['category'],'区域管理')
        self.assertEqual(rows[1]['content'],'油罐区及卸油区')
        self.assertEqual(rows[0]['category'],'暖心服务')
        report=fixture_report()
        self.assertEqual([r['unit_name'] for r in report['scope']['units']],UNIT_ORDER)
        self.assertEqual(report['scope']['station_count'],36)
        self.assertEqual(report['mode_summaries'][0]['issue_count'],18)
        self.assertEqual(report['summary']['total_issue_count'],36)

    def test_unique_station_denominators_completed_zero_issue_visits_and_custom_scope(self):
        from service_report_data import chosen
        rows=serialize([raw(),raw(2,station_id=1)],catalog())
        visits=[raw(station_id=1),raw(3,station_id=2)]
        result=scope(rows,visits)
        self.assertEqual(result['station_count'],2);self.assertEqual(result['average_issue_count'],1)
        selected=normalize_settings({'station_ids':[]})
        self.assertEqual(chosen(rows,selected),[])
        self.assertEqual(period_label(date(2026,9,1),date(2026,10,1)),'2026年09月')
        self.assertIn('至',period_label(date(2026,9,15),date(2026,11,1)))

    def test_cumulative_uses_cutoff_not_present_closure_and_excludes_destroyed(self):
        rows=[raw(1,review_result='整改通过',review_at=date(2026,10,2)),raw(2),raw(3),raw(4,audited_at=date(2026,10,2))]
        history=[{'issue_id':2,'action_type':'review_submitted','to_status':'已闭环','created_at':date(2026,9,20)},
            {'issue_id':3,'action_type':'appeal_final_approved','to_status':'已销毁','created_at':date(2026,9,20)}]
        value=cumulative(rows,history,date(2026,10,1),normalize_settings({}))
        self.assertEqual(value['total_count'],3);self.assertEqual(value['rectified_count'],1);self.assertEqual(value['pending_count'],2)
        self.assertEqual(value['cutoff'],'2026-09-30')

    def test_cumulative_counts_all_open_states_and_excludes_destroyed_legacy_rows(self):
        from service_report_data import historical_status
        end=date(2026,10,1)
        rows=[raw(1,audit_status='pending',audited_at=None,status='待整改'),
            raw(2,status='待整改'),raw(3,status='待整改',station_manager_signed_at=date(2026,9,3)),
            raw(4,status='待复核'),raw(5,status='申诉中'),raw(6,status='已闭环'),
            raw(7,status='已销毁'),raw(8,audit_status='rejected',status='待整改'),
            raw(9,status='站级无法整改')]
        self.assertEqual([historical_status(row,[],end) for row in rows],
            ['待审核','待签名','待整改','待复核','申诉中','已闭环',None,None,'站级无法整改'])
        value=cumulative(rows,[],end,normalize_settings({}))
        self.assertEqual((value['total_count'],value['rectified_count'],value['pending_count'],value['unable_count']),(7,1,5,1))
        # A later closure must not turn a historical pending issue into a closed one.
        self.assertEqual(historical_status(raw(status='已闭环',review_result='整改通过',review_at=date(2026,10,2)),[],end),'待签名')
        # Audit resets and rejected appeals take precedence over earlier events.
        history=[dict(issue_id=1,action_type='audit_changed',to_status='审核通过',created_at=date(2026,9,2)),
            dict(issue_id=1,action_type='audit_changed',to_status='待审核',created_at=date(2026,9,3))]
        self.assertEqual(historical_status(rows[0],history,end),'待审核')

    def test_strict_ai_reference_validation_and_manual_settings(self):
        context=behavior_context(serialize([raw(),raw(2)],catalog()),[])
        for payload in [{'items':{'R1':'礼貌劝阻'}},{'items':{'R1':'A','R2':'B','R3':'C'}},{'items':{'R1':[],'R2':'B'}}]:
            with self.assertRaises(ValueError):validate(payload,context)
        self.assertEqual(validate({'items':{'R1':'礼貌劝阻','R2':'礼貌劝阻'}},context)['items']['R2'],'礼貌劝阻')
        for raw_settings in [{'station_ids':['1']},{'behavior_assignments':{'bad':'未问好'}},{'phrases':{'video:1':''}},{'examples':{'x':[1,1]}}]:
            with self.assertRaises(ValueError):normalize_settings(raw_settings)

    def test_editable_thirteen_pages_widescreen_no_comments_and_no_old_month_chart(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);Image.new('RGB',(180,300),'white').save(root/'photo.jpg')
            report=fixture_report('photo.jpg');path=root/'report.pptx'
            build_service_presentation(report,path,root)
            prs=Presentation(path)
            self.assertEqual(len(prs.slides),13)
            self.assertAlmostEqual(prs.slide_width/prs.slide_height,16/9,places=5)
            text='\n'.join(shape.text for slide in prs.slides for shape in slide.shapes if shape.has_text_frame)
            self.assertNotIn('上月问题整改',text);self.assertNotIn('在上月',text);self.assertIn('2026年09月',text);self.assertIn('2026年09月30日',text)
            self.assertIn('截至至今问题整改情况',text)
            self.assertEqual(sum(shape.has_chart for slide in prs.slides for shape in slide.shapes),9)
            self.assertTrue(any(shape.has_table for shape in prs.slides[4].shapes))
            for slide in prs.slides:
                for shape in slide.shapes:
                    self.assertLessEqual(shape.left+shape.width,prs.slide_width+10000)
                    self.assertLessEqual(shape.top+shape.height,prs.slide_height+10000)
            with ZipFile(path) as archive:
                self.assertFalse(any('/comments/' in name for name in archive.namelist()))
                self.assertGreaterEqual(len([name for name in archive.namelist() if name.endswith('.xlsx')]),9)
                for name in archive.namelist():
                    if name.startswith('ppt/charts/_rels/'):
                        self.assertNotIn(b'TargetMode="External"',archive.read(name))
            # Original risk matrix text remains, rather than fabricated monthly risk scores.
            original=Presentation(TEMPLATE_FILE)
            self.assertEqual([s.text for s in original.slides[12].shapes if s.has_text_frame],
                [s.text for s in prs.slides[12].shapes if s.has_text_frame])

    def test_empty_report_does_not_add_overflow_slides(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'empty.pptx';build_service_presentation(fixture_report(count=0),path,directory)
            self.assertEqual(len(Presentation(path).slides),13)

@unittest.skipUnless(os.environ.get('SERVICE_REPORT_TEST_DSN'),'requires explicit isolated PostgreSQL database')
class ServicePersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ['SERVICE_REPORT_TEST_DSN']
        if 'dbname=test_' not in cls.dsn:raise RuntimeError('An isolated test_ database is mandatory')
        cls.schema='service_'+uuid.uuid4().hex
        conn=psycopg2.connect(cls.dsn);conn.autocommit=True
        with conn.cursor() as cur:cur.execute(f'CREATE SCHEMA {cls.schema}')
        conn.close()
        with cls.connect() as conn,conn.cursor() as cur:
            cur.execute('''CREATE TABLE users(id INTEGER PRIMARY KEY);INSERT INTO users VALUES(1),(2);
                CREATE TABLE inspection_report_jobs(task_id varchar(64) PRIMARY KEY,ai_generation_log jsonb);
                CREATE TABLE inspection_report_ai_memory(cache_key varchar(64) PRIMARY KEY,operation text,report_type text,
                    issue_ids bigint[],payload jsonb,model text,source_task_id text,created_at timestamptz DEFAULT now());''')
            path=Path(__file__).parents[1]/'migrations/versions/20261101_004_service_report.py'
            spec=importlib.util.spec_from_file_location('service_migration',path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
            migration.op=SimpleNamespace(execute=cur.execute);migration.upgrade();migration.upgrade()
    @classmethod
    def connect(cls):return psycopg2.connect(cls.dsn,options=f'-c search_path={cls.schema}',cursor_factory=RealDictCursor)
    @classmethod
    def tearDownClass(cls):
        conn=psycopg2.connect(cls.dsn);conn.autocommit=True
        with conn.cursor() as cur:cur.execute(f'DROP SCHEMA {cls.schema} CASCADE')
        conn.close()
    def setUp(self):
        with self.connect() as conn,conn.cursor() as cur:cur.execute('TRUNCATE inspection_report_service_settings,inspection_report_ai_memory')
        self.app=Flask(__name__)
        @self.app.before_request
        def auth():
            if request.headers.get('X-User'):g.user={'id':int(request.headers['X-User']),'real_name':'测试用户'}
        def authorize(cur):
            if not getattr(g,'user',None):raise PermissionError('请先登录')
            return g.user
        register_service_report(self.app,connect=self.connect,authorize=authorize,
            period=lambda *args:(date(2026,9,1),date(2026,10,1)),fetch_inputs=lambda *args:([raw(),raw(2,'onsite')],[],[]),
            fetch_catalog=lambda *args:catalog(),has_permission=lambda cur,user,key:user['id']==1,
            save_workspace=lambda *args,**kwargs:None,log_usage=lambda *args:None)
        self.client=self.app.test_client()
    def call(self,path='/api/inspection-reports/service-config',method='get',user=1,**kwargs):
        return getattr(self.client,method)(path,headers={'X-User':str(user)},**kwargs)
    def test_get_and_save_do_not_call_ai_global_shared_and_stale_revision_rolls_back(self):
        with patch('service_report_analysis.run_ai',side_effect=AssertionError('No paid AI')):
            self.assertEqual(self.client.get('/api/inspection-reports/service-config').status_code,403)
            value=self.call().json
            self.assertEqual(value['summary']['issue_count'],2)
            settings=value['settings'];settings['station_ids']=[1]
            request_body={'settings':settings,'revision':0,'data_signature':value['data_signature']}
            self.assertEqual(self.call(method='put',user=2,json=request_body).status_code,200)
            self.assertEqual(self.call().json['settings']['station_ids'],[1])
            self.assertEqual(self.call(method='put',json=request_body).status_code,400)
            self.assertEqual(self.call().json['meta']['revision'],1)
            self.assertEqual(self.call('/api/inspection-reports/service-analysis','post',user=2,json={'kind':'phrases'}).status_code,403)
    def test_outside_scope_and_invalid_photos_cannot_be_saved(self):
        value=self.call().json
        for settings in [{**value['settings'],'station_ids':[999]}, {**value['settings'],'examples':{'暖心服务':[999]}},
            {**value['settings'],'phrases':{'video:999':'非法规范'}}]:
            self.assertEqual(self.call(method='put',json={'settings':settings,'revision':0,'data_signature':value['data_signature']}).status_code,400)
        self.assertEqual(self.call().json['meta']['revision'],0)

    def test_unit_manual_edits_shared_and_bad_group_or_photo_rolls_back(self):
        with patch('service_report_units.run_ai',side_effect=AssertionError('Reading/saving must not call AI')):
            value=self.call().json;group=value['unit_discoveries'][0]['categories'][0]['groups'][0]
            settings=value['settings'];settings['unit_evidence'][group['key']]={'summary':'人工归纳的问题表现','photo_ids':[]}
            body={'settings':settings,'revision':0,'data_signature':value['data_signature']}
            self.assertEqual(self.call(method='put',json=body).status_code,200)
            self.assertEqual(self.call(user=2).json['unit_discoveries'][0]['categories'][0]['groups'][0]['summary'],'人工归纳的问题表现')
            for key,entry in [('outside',{'summary':'范围外组'}),(group['key'],{'summary':'新文本','photo_ids':[2]})]:
                bad=copy.deepcopy(settings);bad['unit_evidence'][key]=entry
                self.assertEqual(self.call(method='put',json={**body,'settings':bad,'revision':1}).status_code,400)
            self.assertEqual(self.call().json['meta']['revision'],1)

    def test_unit_memory_reuses_unchanged_groups_and_reanalyzes_only_changed_group(self):
        rows=serialize([raw(1,issue_photo='one.jpg'),raw(2,'onsite',issue_photo='two.jpg')],catalog())
        settings=normalize_settings({});client=MagicMock();client.with_options.return_value=client
        def response(**kwargs):
            evidence=json.loads(kwargs['messages'][1]['content'])
            payload={'items':{g['ref']:{'summary':'根据组内描述归纳的实际问题表现','photo_ids':[next(r['ref'] for r in g['issues'] if r['photo'])]} for g in evidence['items']}}
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])
        client.chat.completions.create.side_effect=response
        with patch('ai_utils.get_deepseek_client',return_value=client),patch('ai_routing._loader',None):
            first=unit_discoveries(self.connect,None,rows,{},settings,True)
            second=unit_discoveries(self.connect,None,rows,{},settings,True)
            self.assertEqual(first,second);self.assertEqual(client.chat.completions.create.call_count,1)
            rows[0]['description']='改变第一个环节的问题描述'
            unit_discoveries(self.connect,None,rows,{},settings,True)
            self.assertEqual(client.chat.completions.create.call_count,2)
            last=json.loads(client.chat.completions.create.call_args.kwargs['messages'][1]['content'])
            self.assertEqual(len(last['items']),1)
    def test_ai_cache_reuses_across_calls_invalid_results_not_saved_and_scene_routed(self):
        client=MagicMock();client.with_options.return_value=client
        client.chat.completions.create.return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"items":{"R1":"礼貌劝阻"}}'))])
        context=phrase_context([catalog()[0]])
        with patch('ai_utils.get_deepseek_client',return_value=client),patch('ai_routing._loader',None):
            first=run_ai(self.connect,'service_phrases',context)
            second=run_ai(self.connect,'service_phrases',context)
            self.assertEqual(first,second);self.assertEqual(client.chat.completions.create.call_count,1)
            self.assertEqual(client.chat.completions.create.call_args.kwargs['model'],'deepseek-v4-pro')
            bad=copy.deepcopy(context);bad['items'][0]['fields']['检查内容']='新的规范内容'
            client.chat.completions.create.return_value.choices[0].message.content='{"items":{}}'
            with self.assertRaises(ValueError):run_ai(self.connect,'service_phrases',bad)
            with self.connect() as conn,conn.cursor() as cur:
                cur.execute('SELECT count(*) AS n FROM inspection_report_ai_memory');self.assertEqual(cur.fetchone()['n'],1)
    def test_phrase_cache_is_per_standard_and_manual_changes_require_no_ai(self):
        standards=catalog();settings=normalize_settings({});client=MagicMock();client.with_options.return_value=client
        client.chat.completions.create.return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"items":{"R1":"礼貌劝阻"}}'))])
        with patch('ai_utils.get_deepseek_client',return_value=client),patch('ai_routing._loader',None):
            self.assertEqual(ensure_phrases(self.connect,standards,settings)['video:10001'],'礼貌劝阻')
            count=client.chat.completions.create.call_count
            self.assertEqual(ensure_phrases(self.connect,standards,settings)['onsite:11001'],'油罐区及卸油区')
            self.assertEqual(client.chat.completions.create.call_count,count)
            settings['phrases']['video:10001']='人工环节'
            with self.connect() as conn,conn.cursor() as cur:self.assertEqual(read_phrases(cur,standards,settings)['video:10001'],'人工环节')

    def test_concurrent_identical_requests_call_provider_once_and_scene_override_is_used(self):
        from concurrent.futures import ThreadPoolExecutor
        client=MagicMock();client.with_options.return_value=client
        client.chat.completions.create.return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"items":{"R1":"礼貌劝阻"}}'))])
        context=phrase_context([catalog()[0]])
        with patch('ai_utils.get_deepseek_client',return_value=client),patch('ai_routing._loader',lambda:{'default_model':'deepseek-v4-pro','overrides':{'service_insights':'qwen3.8-flash'}}):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda _:run_ai(self.connect,'service_phrases',context),range(2)))
            self.assertEqual(results[0],results[1])
            self.assertEqual(client.chat.completions.create.call_count,1)
            self.assertEqual(client.chat.completions.create.call_args.kwargs['model'],'qwen3.8-flash')
