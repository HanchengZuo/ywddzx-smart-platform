import test from 'node:test'
import assert from 'node:assert/strict'
import { deadlineLabel, deadlineExpired, deadlineRemaining } from '../src/utils/deadline.js'
import { appealProgressSteps } from '../src/utils/appealPresentation.js'
import { buildFilterSummary } from '../src/utils/filterSummary.js'

test('countdown handles a three-day period and exact deadline', () => {
  assert.equal(deadlineLabel(259200000, 0), '剩余 3天 0小时 0分')
  assert.equal(deadlineLabel(1000, 1000), '期限已结束')
  assert.equal(deadlineExpired(1000,1000), true)
  assert.equal(deadlineRemaining(1000,2000), 0)
  assert.equal(deadlineLabel(null,0), '期限同步中')
})
test('automatic approval during initial review does not impersonate quality approval', () => {
  const steps = appealProgressSteps({ status: 'approved', area_at: 't', timeout_at: 't', timeout_stage: 'area_pending' })
  assert.equal(steps[1].label, '系统超时通过')
  assert.equal(steps[2].label, '未进入终审')
  assert.equal(steps[2].state, 'waiting')
})
test('automatic rejection at final review identifies system, not a human reviewer', () => {
  const steps = appealProgressSteps({ status: 'rejected', area_at: 't1', quality_at: 't2', timeout_at: 't2', timeout_stage: 'quality_pending' })
  assert.equal(steps[1].state, 'done')
  assert.equal(steps[2].label, '系统超时拒绝')
  assert.match(steps[2].handler, /非人员审核/)
})
test('automatic acceptance filter has a readable applied summary', () => {
  const fields = buildFilterSummary([['signStatus', '验收方式']], { signStatus: 'automatic' })
  assert.equal(fields[0].value, '系统超时自动验收')
})
