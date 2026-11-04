import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { canAccessIssueQueue, canSubmitIssueQueue, legacyIssueQueuePath, issueQueuePaths, departmentReviewRoles } from '../src/utils/issueQueueAccess.js'

test('rectification and review have separate routes, views and actions', () => {
  const station = { view_my_rectification_issues: true }
  assert.equal(canAccessIssueQueue('station_manager', station, 'rectification'), true)
  assert.equal(canSubmitIssueQueue('station_manager', station, 'rectification'), false)
  assert.equal(canSubmitIssueQueue('station_manager', { ...station, submit_my_rectification: true }, 'rectification'), true)
  assert.equal(canAccessIssueQueue('station_manager', { view_my_review_issues: true }, 'review'), false)
  assert.equal(legacyIssueQueuePath('station_manager'), issueQueuePaths.rectification)
  assert.equal(legacyIssueQueuePath('supervisor'), issueQueuePaths.review)
})

test('department and supervisor review switches are independent of issue-list scope and audit', () => {
  for (const role of [...departmentReviewRoles, 'supervisor', 'supervisor_manager']) {
    assert.equal(canAccessIssueQueue(role, {}, 'review'), false)
    const p = { view_my_review_issues: true, submit_my_issue_reviews: true }
    assert.equal(canAccessIssueQueue(role, p, 'review'), true)
    assert.equal(canSubmitIssueQueue(role, p, 'review'), true)
    assert.equal(canSubmitIssueQueue(role, { ...p, view_my_review_issues: false }, 'review'), false)
    assert.equal(canAccessIssueQueue(role, { view_all_inspection_issues: true }, 'review'), false)
    assert.equal(canAccessIssueQueue(role, p, 'rectification'), false)
  }
  assert.equal(canAccessIssueQueue('area_account', { view_my_review_issues: true }, 'review'), false)
  for (const kind of ['review', 'rectification']) assert.equal(canSubmitIssueQueue('root', {}, kind), true)
})

test('actual router guards separately enforce each queue, including direct URL access', () => {
  const source = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
  const guard = source.slice(source.indexOf('const canAccessPath = '), source.indexOf('const resolveFallbackPath = '))
  const access = new Function('canAccessIssueQueue', 'issueQueuePaths', 'operationsPages', 'hasPermission',
    `${guard}; return canAccessPath`)(canAccessIssueQueue, issueQueuePaths, [], () => false)
  assert.equal(access(issueQueuePaths.review, 'finance', {}), false)
  assert.equal(access(issueQueuePaths.review, 'finance', { view_my_review_issues: true }), true)
  assert.equal(access(issueQueuePaths.rectification, 'finance', { view_my_review_issues: true }), false)
  assert.equal(access(issueQueuePaths.rectification, 'station_manager', { view_my_rectification_issues: true }), true)
  assert.equal(access(issueQueuePaths.review, 'station_manager', { view_my_rectification_issues: true }), false)
  assert.equal(access(issueQueuePaths.rectification, 'station_manager', { submit_my_rectification: true }), false)
})
