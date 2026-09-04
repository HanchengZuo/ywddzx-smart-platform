import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildOptimisticAuditIssue,
  mergeCompletedAuditIssue,
  replaceIssueById
} from '../src/utils/issueAudit.js'

const pendingIssue = id => ({
  id,
  audit_status: 'pending',
  audit_status_label: '待审核',
  status: '待审核',
  raw_status: '待整改',
  inspection_signed: false,
  is_excellent: true
})

test('optimistic approval immediately releases the pending-audit row', () => {
  const issue = buildOptimisticAuditIssue(pendingIssue(1), 'approved')

  assert.equal(issue.audit_status, 'approved')
  assert.equal(issue.audit_status_label, '通过')
  assert.equal(issue.status, '待签名')
  assert.equal(issue.audit_submission_pending, true)
})

test('concurrent audit updates and rollback remain isolated by issue id', () => {
  const originals = [pendingIssue(1), pendingIssue(2), pendingIssue(3)]
  let rows = replaceIssueById(originals, 1, buildOptimisticAuditIssue(originals[0], 'approved'))
  rows = replaceIssueById(rows, 2, buildOptimisticAuditIssue(originals[1], 'rejected'))

  rows = replaceIssueById(rows, 1, originals[0])
  assert.equal(rows[0].audit_status, 'pending')
  assert.equal(rows[1].audit_status, 'rejected')
  assert.equal(rows[1].audit_submission_pending, true)
  assert.equal(rows[2].audit_status, 'pending')
})

test('server response finalizes only the matching optimistic item', () => {
  const original = pendingIssue(7)
  const optimistic = buildOptimisticAuditIssue(original, 'rejected')
  const completed = mergeCompletedAuditIssue(optimistic, {
    id: 7,
    audit_status: 'rejected',
    audit_status_label: '否决',
    audited_by_name: '审核员'
  }, 'rejected')

  assert.equal(completed.audit_submission_pending, false)
  assert.equal(completed.is_excellent, false)
  assert.equal(completed.audited_by_name, '审核员')
})
