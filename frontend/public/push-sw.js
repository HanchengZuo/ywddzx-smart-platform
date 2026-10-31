/* Push only: never cache authenticated pages, API responses or user data. */
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()))
self.addEventListener('push', event => {
  let value = {}
  try { value = event.data?.json() || {} } catch { /* Display a generic visible notification. */ }
  const business = ['appeal_area', 'appeal_quality', 'inspection_signature', 'daily_schedule'].includes(value.scene)
  event.waitUntil(self.registration.showNotification('业务督导中心 · 新通知', {
    body: business && typeof value.hint === 'string' ? value.hint.slice(0, 240) : '你有一条系统消息，请登录通知中心查看。',
    icon: '/push-icon-192.png', badge: '/push-icon-192.png',
    tag: typeof value.tag === 'string' ? value.tag.slice(0, 100) : 'ywddzx-notification',
    data: { url: '/notifications' }
  }))
})
self.addEventListener('notificationclick', event => {
  event.notification.close()
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    const target = windows.find(client => new URL(client.url).origin === self.location.origin)
    if (target) {
      try { await target.navigate('/notifications'); return await target.focus() }
      catch { /* The old tab may have closed while the notification was clicked. */ }
    }
    return self.clients.openWindow('/notifications')
  })())
})
