import test from 'node:test'
import assert from 'node:assert/strict'
import { appealProgressSteps } from '../src/utils/appealPresentation.js'
import { rectificationDraftFor } from '../src/utils/issueWorkflow.js'

test('progress identifies station, region and authorized reviewers', () => {
  const steps = appealProgressSteps({ status: 'area_pending', station_name: '测试站', region: '浦东' }, ['审核甲'])
  assert.equal(steps[0].owner, '测试站')
  assert.equal(steps[1].owner, '浦东')
  assert.equal(steps[1].state, 'active')
  assert.match(steps[2].handler, /审核甲/)
})
test('area rejection does not imply quality approval', () => {
  const steps = appealProgressSteps({ status: 'rejected', area_at: 't1' })
  assert.equal(steps[1].state, 'rejected')
  assert.equal(steps[2].label, '未进入终审')
})
test('quality rejection preserves the earlier successful initial review', () => {
  const steps = appealProgressSteps({ status: 'rejected', area_at: 't1', quality_at: 't2' })
  assert.equal(steps[1].state, 'done')
  assert.equal(steps[2].state, 'rejected')
})
test('appeal return starts a fresh rectification draft', () => {
  const draft = rectificationDraftFor({ appeal_rejected: true, rectification_result: '已整改', rectification_note: '旧说明', rectification_photo_path: 'old.jpg' })
  assert.equal(draft.rectificationResult, '')
  assert.equal(draft.rectificationNote, '')
  assert.equal(draft.rectificationPhotoPreview, '')
})
