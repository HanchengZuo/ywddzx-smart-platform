"""Shared selection validation and normative-text snapshots; never paid AI."""
from datetime import date
import unittest
from unittest.mock import MagicMock, patch
from flask import Flask
from report_ai_memory import fingerprint
from safety_report_data import serialize
from safety_report_http import register_safety_report
from safety_report_analysis import build_report, normalize_settings
from tests.test_safety_report import raw_issue, mock_analysis


class SafetyEvidenceHttpTest(unittest.TestCase):
    def setUp(self):
        self.conn=MagicMock();self.app=Flask(__name__);self.permission=False
        self.raw=[raw_issue(1,issue_photo='a.jpg'),raw_issue(2,issue_photo='b.jpg')]
        self.rows=[serialize(row) for row in self.raw]
        register_safety_report(self.app,connect=lambda:self.conn,authorize=lambda cur:{'id':7,'real_name':'真实操作人'},
            period=lambda *args:(date(2026,9,1),date(2026,10,1)),fetch_inputs=lambda *args:(self.raw,[],[]),
            has_permission=lambda *args:self.permission,save_workspace=MagicMock(),log_usage=MagicMock())
        self.client=self.app.test_client()
        self.analysis={'complete':True,'groups':[
            {'name':'接地','summary':'接地缺失','issue_ids':[1]},
            {'name':'防护','summary':'防护缺失','issue_ids':[2]}]}

    def test_manual_representative_must_be_photographed_in_its_own_effective_class(self):
        request={'settings':{'classifications':{'onsite:设备设施':{'representatives':{'接地':[1]}}}},
            'revision':0,'data_signature':fingerprint(self.rows),'user_id':999}
        with patch('safety_report_http.load_settings',return_value={'settings':{},'revision':0}),patch(
                'safety_report_http.cached_analysis',return_value=self.analysis),patch('safety_report_http.save_settings') as save,patch(
                'safety_report_http.with_representatives',side_effect=AssertionError('paid AI')):
            self.assertEqual(self.client.put('/api/inspection-reports/safety-config',json=request).status_code,200)
            self.assertEqual(save.call_args.args[-1]['id'],7)
            save.reset_mock()
            request['settings']['classifications']['onsite:设备设施']['representatives']['接地']=[2]
            response=self.client.put('/api/inspection-reports/safety-config',json=request)
            self.assertEqual(response.status_code,400)
            save.assert_not_called();self.conn.rollback.assert_called()
            request['settings']['classifications']['onsite:设备设施']['assignments']={'2':'接地'}
            self.assertEqual(self.client.put('/api/inspection-reports/safety-config',json=request).status_code,200)

    def test_explicit_ai_representative_selection_requires_generation_permission(self):
        with patch('safety_report_http.load_settings',return_value={'settings':{},'revision':0}),patch(
                'safety_report_http.with_representatives',side_effect=AssertionError('paid AI')):
            response=self.client.post('/api/inspection-reports/safety-analysis',json={
                'mode':'onsite','category':'设备设施','revision':0,'data_signature':fingerprint(self.rows)})
            self.assertEqual(response.status_code,403)
            self.conn.rollback.assert_called()

    def test_build_freezes_normative_text_instead_of_scoring_and_selection_inputs(self):
        requirements=[{'mode':'onsite','external_standard_id':'1234','status':'manual',
            'requirement':'配电柜门与柜体跨接有效。'}]
        settings=normalize_settings({'requirements_signature':'a'*64})
        with patch('safety_report_analysis.analyze',side_effect=mock_analysis),patch(
                'safety_report_examples.generate_representatives',return_value={'payload':{
                    'selections':[{'name':'装置维护不到位','issue_ids':[2,1]}]}}),patch(
                'safety_report_analysis.generate_analysis',return_value={'payload':{'groups':[],'causes':[],
                    'suggestions':[{'title':'整改','content':'完善连接'}]}}):
            report=build_report(date(2026,9,1),date(2026,10,1),self.raw,[],{'onsite':[],'video':[]},settings,
                requirements=requirements)
        self.assertEqual({i['requirement'] for i in report['safety_issues']},{'配电柜门与柜体跨接有效。'})
        self.assertEqual({i['requirement_status'] for i in report['safety_issues']},{'manual'})
        requirements[0]['requirement']='后续修改'
        self.assertEqual(report['safety_issues'][0]['requirement'],'配电柜门与柜体跨接有效。')
        self.assertEqual(report['safety_analysis']['onsite:设备设施']['groups'][0]['representative_issue_ids'],[2,1])
        self.assertEqual(report['safety_settings']['requirements_signature'],'a'*64)
