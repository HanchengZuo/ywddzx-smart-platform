import { isSupervisorRole } from './roles.js'

export const departmentReviewRoles = ['quality_safety', 'development_plan', 'oil_gas', 'non_oil', 'finance']
export function reviewQueuePerspective(role) {
  if (isSupervisorRole(role)) return '督导中心视角'
  const departments = { quality_safety: '质安部', development_plan: '发展计划部', oil_gas: '油气事业部', non_oil: '非油事业部', finance: '财务部' }
  return departments[role] ? departments[role] + '视角' : '全部待复核'
}
export const issueQueuePaths = {
  rectification: '/inspection/my-rectifications',
  review: '/inspection/my-reviews',
}

export function canAccessIssueQueue(role, permissions = {}, kind = 'review') {
  if (role === 'root') return true
  if (kind === 'rectification') {
    return role === 'station_manager' && Boolean(permissions.view_my_rectification_issues)
  }
  return (isSupervisorRole(role) || departmentReviewRoles.includes(role)) && Boolean(permissions.view_my_review_issues)
}

export function canSubmitIssueQueue(role, permissions = {}, kind) {
  return canAccessIssueQueue(role, permissions, kind) &&
    (role === 'root' || Boolean(permissions[kind === 'rectification' ? 'submit_my_rectification' : 'submit_my_issue_reviews']))
}

export function legacyIssueQueuePath(role) {
  return issueQueuePaths[role === 'station_manager' ? 'rectification' : 'review']
}
