import axios from 'axios'

const AUTH_STORAGE_KEYS = [
  'auth_token',
  'auth_expires_at',
  'user_id',
  'username',
  'real_name',
  'user_role',
  'role',
  'phone',
  'station_id',
  'station_name',
  'region',
  'address',
  'permissions',
  'must_change_password'
]

const AUTH_MESSAGE_KEY = 'auth_session_message'
const DEFAULT_EXPIRED_MESSAGE = '登录已过期，请重新登录。'
export const AUTH_SESSION_EXPIRED_EVENT = 'auth-session-expired'

export const getStoredAuthToken = () => localStorage.getItem('auth_token') || ''

export const getStoredAuthExpiresAt = () => {
  const value = Number.parseInt(localStorage.getItem('auth_expires_at') || '0', 10)
  return Number.isFinite(value) ? value : 0
}

export const getStoredAuthSecondsRemaining = () => {
  const expiresAt = getStoredAuthExpiresAt()
  if (!expiresAt) return 0
  return Math.max(0, Math.floor((expiresAt - Date.now()) / 1000))
}

export const isUsableAuthToken = (token = getStoredAuthToken()) => {
  const value = String(token || '').trim()
  return Boolean(value) && !value.startsWith('backend-login-')
}

export const syncAxiosAuthHeader = () => {
  const token = getStoredAuthToken()
  if (isUsableAuthToken(token)) {
    axios.defaults.headers.common.Authorization = `Bearer ${token}`
    return
  }
  delete axios.defaults.headers.common.Authorization
}

export const getAuthSessionMessage = () => localStorage.getItem(AUTH_MESSAGE_KEY) || ''

export const consumeAuthSessionMessage = () => {
  const message = getAuthSessionMessage()
  localStorage.removeItem(AUTH_MESSAGE_KEY)
  return message
}

export const clearAuthSession = (message = '') => {
  AUTH_STORAGE_KEYS.forEach((key) => localStorage.removeItem(key))
  if (message) {
    localStorage.setItem(AUTH_MESSAGE_KEY, message)
  }
  syncAxiosAuthHeader()
}

export const notifyAuthSessionExpired = (message = DEFAULT_EXPIRED_MESSAGE) => {
  clearAuthSession(message || DEFAULT_EXPIRED_MESSAGE)
  window.dispatchEvent(new CustomEvent(AUTH_SESSION_EXPIRED_EVENT, {
    detail: {
      message: message || DEFAULT_EXPIRED_MESSAGE
    }
  }))
}

export const storeAuthSession = (user, token, expiresInSeconds = null) => {
  if (!token) {
    throw new Error('登录响应缺少服务端令牌。')
  }

  localStorage.setItem('auth_token', token)
  const ttl = Number(expiresInSeconds)
  if (Number.isFinite(ttl) && ttl > 0) {
    localStorage.setItem('auth_expires_at', String(Date.now() + ttl * 1000))
  } else {
    localStorage.removeItem('auth_expires_at')
  }
  localStorage.setItem('user_id', user?.id ?? '')
  localStorage.setItem('username', user?.username || '')
  localStorage.setItem('real_name', user?.real_name || '')
  localStorage.setItem('user_role', user?.role || '')
  localStorage.setItem('role', user?.role || '')
  localStorage.setItem('phone', user?.phone || '')
  localStorage.setItem('station_id', user?.station_id ?? '')
  localStorage.setItem('station_name', user?.station_name || '')
  localStorage.setItem('region', user?.region || '')
  localStorage.setItem('address', user?.address || '')
  localStorage.setItem('permissions', JSON.stringify(user?.permissions || {}))
  localStorage.setItem('must_change_password', user?.must_change_password ? 'true' : 'false')
  localStorage.removeItem(AUTH_MESSAGE_KEY)
  syncAxiosAuthHeader()
}

export const configureAxiosAuth = () => {
  syncAxiosAuthHeader()

  axios.interceptors.request.use((config) => {
    const token = getStoredAuthToken()
    config.headers = config.headers || {}
    if (isUsableAuthToken(token)) {
      config.headers.Authorization = `Bearer ${token}`
    } else {
      delete config.headers.Authorization
    }
    return config
  })

  axios.interceptors.response.use(
    (response) => response,
    (error) => {
      const status = error?.response?.status
      const url = String(error?.config?.url || '')
      if (status === 401 && !url.includes('/api/login')) {
        notifyAuthSessionExpired(error?.response?.data?.error || DEFAULT_EXPIRED_MESSAGE)
      }
      return Promise.reject(error)
    }
  )
}
