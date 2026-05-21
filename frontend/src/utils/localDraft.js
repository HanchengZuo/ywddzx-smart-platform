const DRAFT_PREFIX = 'ywddzx_form_draft'
const DEFAULT_TTL_DAYS = 14
const DEFAULT_SAVE_DELAY = 650

const getDraftUserKey = () => {
    return localStorage.getItem('user_id') || localStorage.getItem('username') || 'anonymous'
}

export const getLocalDraftKey = (scope) => {
    return `${DRAFT_PREFIX}:${scope}:user:${getDraftUserKey()}`
}

const safeJsonParse = (value) => {
    try {
        return JSON.parse(value)
    } catch {
        return null
    }
}

export const loadLocalDraft = (scope, options = {}) => {
    const key = getLocalDraftKey(scope)
    const raw = localStorage.getItem(key)
    if (!raw) return null

    const payload = safeJsonParse(raw)
    const savedAt = Number(payload?.saved_at || 0)
    const ttlDays = Number.isFinite(options.ttlDays) ? options.ttlDays : DEFAULT_TTL_DAYS
    const expired = savedAt > 0 && Date.now() - savedAt > ttlDays * 24 * 60 * 60 * 1000

    if (!payload || expired) {
        localStorage.removeItem(key)
        return null
    }

    return payload
}

export const clearLocalDraft = (scope) => {
    localStorage.removeItem(getLocalDraftKey(scope))
}

export const createLocalDraftManager = (scope, options = {}) => {
    let saveTimer = null
    let paused = false

    const collect = options.collect
    const collectFallback = options.collectFallback
    const isEmpty = options.isEmpty || (() => false)
    const delay = Number.isFinite(options.delay) ? options.delay : DEFAULT_SAVE_DELAY

    const writeDraft = (data) => {
        if (!data || isEmpty(data)) {
            clearLocalDraft(scope)
            return true
        }

        const payload = {
            version: options.version || 1,
            saved_at: Date.now(),
            data
        }
        localStorage.setItem(getLocalDraftKey(scope), JSON.stringify(payload))
        return true
    }

    const flush = () => {
        if (paused || typeof collect !== 'function') return false
        const data = collect()

        try {
            return writeDraft(data)
        } catch (error) {
            if (typeof collectFallback === 'function') {
                try {
                    const fallbackData = collectFallback(data)
                    const saved = writeDraft(fallbackData)
                    options.onFallback?.(error)
                    return saved
                } catch (fallbackError) {
                    options.onError?.(fallbackError)
                    return false
                }
            }
            options.onError?.(error)
            return false
        }
    }

    const scheduleSave = () => {
        if (paused) return
        if (saveTimer) window.clearTimeout(saveTimer)
        saveTimer = window.setTimeout(() => {
            saveTimer = null
            flush()
        }, delay)
    }

    const clear = () => {
        if (saveTimer) {
            window.clearTimeout(saveTimer)
            saveTimer = null
        }
        clearLocalDraft(scope)
    }

    const pause = async (callback) => {
        paused = true
        try {
            return await callback?.()
        } finally {
            window.setTimeout(() => {
                paused = false
            }, 0)
        }
    }

    const destroy = () => {
        if (saveTimer) {
            window.clearTimeout(saveTimer)
            saveTimer = null
        }
    }

    return {
        flush,
        scheduleSave,
        clear,
        pause,
        destroy,
        load: () => loadLocalDraft(scope, options)
    }
}

export const fileToDraftAsset = (file) => {
    return new Promise((resolve, reject) => {
        if (!file) {
            resolve(null)
            return
        }

        const reader = new FileReader()
        reader.onload = () => {
            resolve({
                name: file.name || 'draft-image.jpg',
                type: file.type || 'image/jpeg',
                size: file.size || 0,
                last_modified: file.lastModified || Date.now(),
                data_url: String(reader.result || '')
            })
        }
        reader.onerror = () => reject(new Error('草稿图片读取失败。'))
        reader.readAsDataURL(file)
    })
}

export const draftAssetToFile = async (asset) => {
    if (!asset?.data_url) return null
    const response = await fetch(asset.data_url)
    const blob = await response.blob()
    return new File([blob], asset.name || 'draft-image.jpg', {
        type: asset.type || blob.type || 'image/jpeg',
        lastModified: asset.last_modified || Date.now()
    })
}
