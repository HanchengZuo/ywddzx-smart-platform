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
