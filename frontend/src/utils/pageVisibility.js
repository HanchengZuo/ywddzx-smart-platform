import axios from 'axios'
import {
  PAGE_VISIBILITY_PAGE_BY_KEY,
  PAGE_VISIBILITY_PAGE_BY_PATH,
  PAGE_VISIBILITY_PAGES
} from '../config/pageVisibilityCatalog'
import { getStoredAuthToken, isUsableAuthToken } from './authSession'

export const PAGE_VISIBILITY_UPDATED_EVENT = 'page-visibility-updated'

const PAGE_VISIBILITY_CACHE_TTL_MS = 30 * 1000

let pageVisibilityInFlight = null
let pageVisibilityFetchedAt = 0
let pageVisibilitySettings = {}

const normalizeSettings = (rawSettings) => {
  const result = {}
  if (!rawSettings || typeof rawSettings !== 'object') return result

  Object.entries(rawSettings).forEach(([key, value]) => {
    if (PAGE_VISIBILITY_PAGE_BY_KEY[key]) {
      result[key] = Boolean(value)
    }
  })
  return result
}

export const getPageKeyForPath = (path) => PAGE_VISIBILITY_PAGE_BY_PATH[path]?.key || ''

export const getPageVisibilitySnapshot = () => ({ ...pageVisibilitySettings })

export const isPageVisibleInSnapshot = (pathOrKey, settings = pageVisibilitySettings) => {
  const key = PAGE_VISIBILITY_PAGE_BY_KEY[pathOrKey]
    ? pathOrKey
    : getPageKeyForPath(pathOrKey)
  if (!key) return true
  return settings[key] !== false
}

export const clearPageVisibilityCache = () => {
  pageVisibilityInFlight = null
  pageVisibilityFetchedAt = 0
  pageVisibilitySettings = {}
}

export const fetchPageVisibility = async ({ force = false } = {}) => {
  const token = getStoredAuthToken()
  if (!isUsableAuthToken(token)) {
    clearPageVisibilityCache()
    return {}
  }

  const now = Date.now()
  if (
    !force &&
    pageVisibilityFetchedAt &&
    now - pageVisibilityFetchedAt < PAGE_VISIBILITY_CACHE_TTL_MS
  ) {
    return getPageVisibilitySnapshot()
  }

  if (pageVisibilityInFlight) return pageVisibilityInFlight

  pageVisibilityInFlight = axios.get('/api/page-visibility')
    .then((response) => {
      if (!response.data?.success) throw new Error(response.data?.error || '页面显示配置读取失败。')
      pageVisibilitySettings = normalizeSettings(response.data.settings || {})
      pageVisibilityFetchedAt = Date.now()
      return getPageVisibilitySnapshot()
    })
    .catch((error) => {
      console.warn('页面显示配置读取失败，将暂时默认全部显示。', error)
      pageVisibilityFetchedAt = Date.now()
      pageVisibilitySettings = {}
      return {}
    })
    .finally(() => {
      pageVisibilityInFlight = null
    })

  return pageVisibilityInFlight
}

export const refreshPageVisibilityAndNotify = async () => {
  const settings = await fetchPageVisibility({ force: true })
  window.dispatchEvent(new CustomEvent(PAGE_VISIBILITY_UPDATED_EVENT, {
    detail: { settings }
  }))
  return settings
}

export const isKnownPagePath = (path) => Boolean(PAGE_VISIBILITY_PAGE_BY_PATH[path])

export const resolveFirstVisiblePath = (canAccessPath) => {
  const match = PAGE_VISIBILITY_PAGES.find((page) => (
    isPageVisibleInSnapshot(page.path) && (!canAccessPath || canAccessPath(page.path))
  ))
  return match?.path || '/feedback'
}
