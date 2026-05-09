import axios from 'axios'

const AUTH_STORAGE_KEYS = [
  'auth_token',
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

export const getStoredAuthToken = () => localStorage.getItem('auth_token') || ''

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

export const clearAuthSession = () => {
  AUTH_STORAGE_KEYS.forEach((key) => localStorage.removeItem(key))
  syncAxiosAuthHeader()
}

export const storeAuthSession = (user, token) => {
  if (!token) {
    throw new Error('登录响应缺少服务端令牌。')
  }

  localStorage.setItem('auth_token', token)
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
  syncAxiosAuthHeader()
}

export const configureAxiosAuth = (router) => {
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
        clearAuthSession()
        if (router?.currentRoute?.value?.path !== '/login') {
          router?.push?.('/login')
        }
      }
      return Promise.reject(error)
    }
  )
}
