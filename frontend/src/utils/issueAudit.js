const AUDIT_STATUS_LABELS = {
  approved: '通过',
  rejected: '否决',
  pending: '待审核'
}

const normalizedAuditStatus = (value) => (
  Object.prototype.hasOwnProperty.call(AUDIT_STATUS_LABELS, value) ? value : 'pending'
)

const displayStatusAfterAudit = (issue, auditStatus) => {
  if (auditStatus === 'pending') return '待审核'
  const workflowStatus = issue?.raw_status || issue?.workflow_status || issue?.status || ''
  const inspectionSigned = Boolean(
    issue?.inspection_signed
    || issue?.inspection_sign_status === '已签名确认'
    || issue?.station_manager_signed_at
    || issue?.station_manager_signature_path
    || issue?.station_manager_signed_name
  )
  return workflowStatus === '待整改' && !inspectionSigned ? '待签名' : workflowStatus
}

export const buildOptimisticAuditIssue = (issue, requestedStatus) => {
  const auditStatus = normalizedAuditStatus(requestedStatus)
  return {
    ...issue,
    audit_status: auditStatus,
    audit_status_label: AUDIT_STATUS_LABELS[auditStatus],
    audit_submission_pending: true,
    is_auto_audited: false,
    audit_source: auditStatus === 'pending' ? '' : 'manual',
    is_excellent: auditStatus === 'rejected' ? false : issue?.is_excellent,
    status: displayStatusAfterAudit(issue, auditStatus)
  }
}

export const replaceIssueById = (rows, issueId, replacement) => (
  (rows || []).map((row) => (
    Number(row?.id) === Number(issueId)
      ? (typeof replacement === 'function' ? replacement(row) : replacement)
      : row
  ))
)

export const mergeCompletedAuditIssue = (current, serverIssue, fallbackStatus) => {
  const auditStatus = normalizedAuditStatus(serverIssue?.audit_status || fallbackStatus)
  const merged = {
    ...current,
    ...(serverIssue || {}),
    audit_status: auditStatus,
    audit_status_label: serverIssue?.audit_status_label || AUDIT_STATUS_LABELS[auditStatus],
    audit_submission_pending: false
  }
  return {
    ...merged,
    is_excellent: auditStatus === 'rejected' ? false : merged.is_excellent,
    status: serverIssue?.status || displayStatusAfterAudit(merged, auditStatus)
  }
}
