import test from 'node:test'
import assert from 'node:assert/strict'
import { getRegisterStandardPreview, getRegisterStandardLabel } from '../src/utils/registerStandardPresentation.js'
import { createLatestRequest } from '../src/utils/latestRequest.js'

test('candidate display uses only register-visible fields and table', () => {
  const standard = { standard_id: '1000', inspection_table_name: '计量检查表',
    register_display_text: '检查项目：器具管理', standard_detail_text: '不可用于摘要的字段', check_content: '隐藏字段' }
  assert.equal(getRegisterStandardLabel(standard), '1000｜计量检查表')
  assert.equal(getRegisterStandardPreview(standard), '检查项目：器具管理')
  assert.equal(getRegisterStandardPreview({ ...standard, register_display_text: '' }), '未设置登记展示字段')
  assert.equal(getRegisterStandardPreview({ standard_detail_text: '隐藏字段' }), '未设置登记展示字段')
})

test('a new match or edited description makes prior responses unusable', () => {
  const requests = createLatestRequest()
  const first = requests.start()
  const second = requests.start()
  assert.equal(first.isCurrent(), false)
  assert.equal(first.signal.aborted, true)
  assert.equal(second.isCurrent(), true)
  requests.cancel()
  assert.equal(second.isCurrent(), false)
  assert.equal(second.signal.aborted, true)
  assert.equal(requests.start().isCurrent(), true)
})
