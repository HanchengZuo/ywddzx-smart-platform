export function notificationMessageId(value) {
  return typeof value === 'string' &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
    ? value.toLowerCase()
    : ''
}

export function notificationTarget(value) {
  const id = notificationMessageId(value)
  return id ? { path: '/notifications', query: { message: id } } : null
}

export function businessNotificationPath(item) {
  if (item.kind !== 'business') return ''
  if (['quality_review_handoff', 'non_oil_review'].includes(item.source) &&
      ['/inspection/my-reviews', '/inspection/my-rectifications'].includes(item.action_path)) {
    const id = String(item.entity_id ?? '')
    return /^[1-9][0-9]{0,9}$/.test(id) ? { path: item.action_path, query: { issue_id: id } } : ''
  }
  return ['/inspection/appeals', '/inspection/records'].includes(item.action_path) ? item.action_path : ''
}
