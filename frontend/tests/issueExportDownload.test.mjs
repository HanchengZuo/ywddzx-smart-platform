import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { issueExportFilterChips, beginIssueExportDownload } from '../src/utils/issueExport.js'

test('export summaries translate both field naming conventions and every audit enum', () => {
  assert.deepEqual(issueExportFilterChips({ audit_status: 'approved', auditState: 'done', excellent: 'starred', date_from: '2026-10-01', region: ['浦东', '松金'], month: '' }), [
    { key: 'audit_status', label: '审核结论', value: '通过' },
    { key: 'auditState', label: '审核状态', value: '已审核' },
    { key: 'excellent', label: '优秀问题', value: '已标星' },
    { key: 'date_from', label: '检查开始日期', value: '2026-10-01' },
    { key: 'region', label: '站点所属地', value: '浦东、松金' },
  ])
  assert.equal(issueExportFilterChips({auditStatus:'rejected'})[0].value,'否决')
  assert.equal(issueExportFilterChips({audit_state:'pending'})[0].value,'未审核')
  assert.equal(issueExportFilterChips({audit_status:'pending'})[0].value,'待审核')
})

test('native download uses the exact same-origin task route, no blob or bearer in the URL', () => {
  const actions = []
  const link = {click:()=>actions.push('click'),remove:()=>actions.push('remove')}
  const document = {createElement:()=>link,body:{appendChild:()=>actions.push('append')}}
  beginIssueExportDownload('one', '/api/issues/export-tasks/one/download', '问题.xlsx', document, 'https://example.test')
  assert.equal(link.href,'https://example.test/api/issues/export-tasks/one/download')
  assert.equal(link.download,'问题.xlsx')
  assert.deepEqual(actions,['append','click','remove'])
  for (const url of ['https://evil.test/api/issues/export-tasks/one/download', 'javascript:alert(1)', '/api/issues/export-tasks/two/download', '/api/issues/export-tasks/one/download?auth_token=secret']) {
    assert.throws(()=>beginIssueExportDownload('one',url,'file',document,'https://example.test'))
  }
  const source=readFileSync(new URL('../src/views/inspection/IssuesView.vue',import.meta.url),'utf8')
  const handler=source.slice(source.indexOf('const downloadIssueExport ='),source.indexOf('const showActionMessage ='))
  assert.ok(!handler.includes("responseType: 'blob'"))
  assert.ok(!handler.includes('createObjectURL'))
  assert.match(handler,/download-link/)
})
