import axios from 'axios'
import { appVersion, formatAppVersion } from '../config/versionInfo'

const VERSION_EXPIRED_CODE = 'FRONTEND_VERSION_EXPIRED'
const VERSION_EXPIRED_MESSAGE = '系统已更新，正在刷新页面...'

let versionCheckInFlight = null
let upgradeReloading = false

const normalizeVersion = (value) => {
  const rawValue = String(value || '').trim().replace(/^v/i, '')
  return rawValue ? formatAppVersion(rawValue) : ''
}

export const isFrontendVersionExpiredResponse = (error) => (
  error?.response?.status === 426 &&
  error?.response?.data?.code === VERSION_EXPIRED_CODE
)

export const forceFrontendUpgradeReload = (message = VERSION_EXPIRED_MESSAGE) => {
  if (upgradeReloading) return
  upgradeReloading = true
  try {
    window.alert(message || VERSION_EXPIRED_MESSAGE)
  } finally {
    localStorage.clear()
    sessionStorage.clear()
    window.location.reload(true)
  }
}

export const checkFrontendVersion = async () => {
  if (versionCheckInFlight) return versionCheckInFlight

  versionCheckInFlight = axios.get('/api/version', {
    headers: {
      'Cache-Control': 'no-cache',
      Pragma: 'no-cache'
    }
  })
    .then((response) => {
      const serverVersion = normalizeVersion(response.data?.version)
      const currentVersion = normalizeVersion(appVersion)
      if (serverVersion && currentVersion && serverVersion !== currentVersion) {
        forceFrontendUpgradeReload()
        return false
      }
      return true
    })
    .catch((error) => {
      if (isFrontendVersionExpiredResponse(error)) {
        forceFrontendUpgradeReload(error.response?.data?.message || VERSION_EXPIRED_MESSAGE)
        return false
      }
      console.warn('前端版本校验失败，将继续加载当前页面。', error)
      return true
    })
    .finally(() => {
      versionCheckInFlight = null
    })

  return versionCheckInFlight
}
