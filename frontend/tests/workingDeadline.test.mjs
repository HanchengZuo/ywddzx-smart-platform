import test from 'node:test'
import assert from 'node:assert/strict'
import { workingRemaining, workingLabel } from '../src/utils/workingDeadline.js'
import { appealProgressSteps } from '../src/utils/appealPresentation.js'
const at = text => Date.parse(`${text}+08:00`)
const days = { '2026-09-11': true, '2026-09-12': false, '2026-09-13': false, '2026-09-14': true }
test('weekend pauses hours rather than counting wall-clock days', () => {
  const end = at('2026-09-14T12:00:00')
  assert.equal(workingRemaining(end, at('2026-09-11T12:00:00'), days), 24 * 3600000)
  assert.equal(workingRemaining(end, at('2026-09-12T12:00:00'), days), 12 * 3600000)
  assert.equal(workingRemaining(end, at('2026-09-13T22:00:00'), days), 12 * 3600000)
  assert.match(workingLabel(end, at('2026-09-13T22:00:00'), days), /非工作日暂停/)
  assert.equal(workingLabel(end, end, days), '期限已结束')
})
test('unknown calendar never guesses workdays and make-up Sunday counts', () => {
  assert.equal(workingRemaining(at('2027-01-02T12:00:00'), at('2027-01-01T00:00:00'), days), null)
  assert.equal(workingRemaining(at('2025-09-28T12:00:00'), at('2025-09-28T00:00:00'), { '2025-09-28': true }), 12 * 3600000)
})
test('area auto-approval continues to quality, both timeout actors remain visible', () => {
  const item = { status: 'quality_pending', area_at: 'now', area_timeout_at: 'now', timeout_at: 'now', timeout_stage: 'area_pending' }
  let steps = appealProgressSteps(item)
  assert.match(steps[1].label, /系统超时通过/)
  assert.equal(steps[2].state, 'active')
  steps = appealProgressSteps({ ...item, status: 'rejected', quality_at: 'later', quality_timeout_at: 'later' })
  assert.match(steps[1].handler, /系统/)
  assert.match(steps[2].label, /系统超时拒绝/)
})
