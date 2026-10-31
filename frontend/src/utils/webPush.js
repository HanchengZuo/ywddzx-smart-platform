import axios from 'axios'

export function pushCapability(env = window) {
  const ua = env.navigator?.userAgent || ''
  const ios =
    /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && env.navigator?.maxTouchPoints > 1)
  const standalone = !!(
    env.navigator?.standalone || env.matchMedia?.('(display-mode: standalone)').matches
  )
  if (!env.isSecureContext)
    return {
      code: 'insecure',
      hint: '需要 HTTPS 安全连接（本机 localhost 可测试），普通 HTTP 无法接收推送。',
    }
  if (ios && !standalone)
    return {
      code: 'ios_install_required',
      hint: 'iPhone / iPad 请升级至 iOS 16.4 及以上，在 Safari 中打开本网站，点“分享”→“添加到主屏幕”，再从主屏幕图标打开并开启通知。',
    }
  if (!env.navigator?.serviceWorker || !env.PushManager || !env.Notification)
    return {
      code: 'unsupported',
      hint: '当前浏览器未提供完整 Web Push 能力。微信、部分华为及其他品牌内置浏览器可能不支持，请尝试系统支持的 Chrome、Edge、Firefox 或 Safari。',
    }
  return {
    code: 'supported',
    hint: '浏览器具备 Web Push 能力，但是否实际收到仍受推送网络、系统通知权限、省电限制及浏览器后台运行设置影响。请发送测试通知验证。',
  }
}

export const newRequestId = () => {
  if (crypto.randomUUID) return crypto.randomUUID()
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  const value = [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${value.slice(0, 8)}-${value.slice(8, 12)}-${value.slice(12, 16)}-${value.slice(16, 20)}-${value.slice(20)}`
}
let deviceQueue = Promise.resolve()
function deviceOperation(operation) {
  const next = deviceQueue
    .catch(() => {})
    .then(() =>
      navigator.locks ? navigator.locks.request('ywddzx-push-device', operation) : operation(),
    )
  deviceQueue = next
  return next
}
export function currentDeviceKey() {
  let key = localStorage.getItem('web_push_device_key')
  if (!/^[A-Za-z0-9_-]{43}$/.test(key || '')) {
    key = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))))
      .replaceAll('+', '-')
      .replaceAll('/', '_')
      .replace(/=+$/, '')
    localStorage.setItem('web_push_device_key', key)
  }
  return key
}
export function publicKeyBytes(value) {
  const base = value.replaceAll('-', '+').replaceAll('_', '/')
  return Uint8Array.from(atob(base + '='.repeat((4 - (base.length % 4)) % 4)), (char) =>
    char.charCodeAt(0),
  )
}
export const pushRegistration = () =>
  navigator.serviceWorker.register('/push-sw.js', { scope: '/', updateViaCache: 'none' })
async function readyRegistration() {
  await pushRegistration()
  let timer
  try {
    return await Promise.race([
      navigator.serviceWorker.ready,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('通知服务启动超时，请刷新重试。')), 12000)
      }),
    ])
  } finally {
    clearTimeout(timer)
  }
}
let preparedRegistration = null
let preparation = null
export const isPushPrepared = () => Boolean(preparedRegistration)
export function preparePush() {
  if (pushCapability().code !== 'supported') return Promise.resolve(null)
  if (preparedRegistration) return Promise.resolve(preparedRegistration)
  if (!preparation)
    preparation = readyRegistration()
      .then((registration) => {
        preparedRegistration = registration
        return registration
      })
      .finally(() => {
        preparation = null
      })
  return preparation
}
export const syncDevice = (options = {}) => deviceOperation(() => syncDeviceUnlocked(options))
async function syncDeviceUnlocked({ active = true } = {}) {
  const capability = pushCapability()
  let subscription = null
  const registration = capability.code === 'supported' ? await preparePush() : null
  if (active && capability.code === 'supported' && Notification.permission === 'granted') {
    subscription = (await registration.pushManager.getSubscription())?.toJSON() || null
  }
  const { data } = await axios.post('/api/notifications/device', {
    device_key: currentDeviceKey(),
    capability: capability.code,
    permission: window.Notification?.permission || 'unavailable',
    subscription,
  })
  return data.device
}
export async function enableDevice(publicKey) {
  if (pushCapability().code !== 'supported') throw new Error(pushCapability().hint)
  if (!publicKey) throw new Error('管理员尚未配置 Web Push，暂不能授权订阅。')
  if (!preparedRegistration) throw new Error('设备通知服务尚在准备，请刷新状态后再次点击开启。')
  try {
    // Safari must enter the native subscribe call directly from the click handler:
    // no await, HTTP request, or navigator.locks queue may precede this call.
    await preparedRegistration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: publicKeyBytes(publicKey),
    })
  } catch (error) {
    if (error.name === 'InvalidStateError') {
      await (await preparedRegistration.pushManager.getSubscription())?.unsubscribe()
      throw new Error('已清理旧推送身份，请再次点击“开启”完成新的订阅。', { cause: error })
    }
    if (error.name === 'NotAllowedError' || Notification.permission === 'denied')
      throw new Error('尚未允许通知，请在此主屏幕应用或浏览器的系统通知设置中允许，再点击开启。', {
        cause: error,
      })
    throw new Error(
      '浏览器未能连接推送服务，请检查网络、系统通知和后台运行设置，或尝试其他受支持浏览器。',
      { cause: error },
    )
  }
  return deviceOperation(() => syncDeviceUnlocked())
}
export const disableDevice = () =>
  deviceOperation(async () => {
    await axios.delete('/api/notifications/device', { data: { device_key: currentDeviceKey() } })
    if (navigator.serviceWorker) {
      const registration = await navigator.serviceWorker.getRegistration('/push-sw.js')
      await (await registration?.pushManager.getSubscription())?.unsubscribe()
    }
  })
export const pushDeviceStatus = (device) =>
  !device
    ? '尚未登记'
    : device.active
      ? '已订阅'
      : device.permission === 'denied'
        ? '浏览器已拒绝'
        : { unsupported: '不支持', insecure: '非安全连接', ios_install_required: '需添加主屏幕' }[
            device.capability
          ] || '未订阅 / 需重新开启'
