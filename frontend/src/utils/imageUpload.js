const MAX_UPLOAD_BYTES = 500 * 1024
const ACCEPTED_IMAGE_TYPES = [
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/webp',
    'image/heic',
    'image/heif'
]

export const IMAGE_UPLOAD_TYPE_ERROR_MESSAGE = '仅支持上传 JPG、JPEG、PNG、WEBP、HEIC、HEIF 格式图片。'
export const IMAGE_UPLOAD_PROCESS_ERROR_MESSAGE = '图片处理失败，请更换图片后重试。'

export class ImageUploadError extends Error {
    constructor(message, code = 'IMAGE_UPLOAD_ERROR') {
        super(message)
        this.name = 'ImageUploadError'
        this.code = code
    }
}

export const getAcceptedImageTypes = () => [...ACCEPTED_IMAGE_TYPES]

export const loadImageFromFile = (file) => {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()

        reader.onload = () => {
            const img = new Image()
            img.onload = () => resolve(img)
            img.onerror = () => reject(new Error('图片读取失败。'))
            img.src = reader.result
        }

        reader.onerror = () => reject(new Error('图片读取失败。'))
        reader.readAsDataURL(file)
    })
}

export const canvasToBlob = (canvas, quality = 0.82) => {
    return new Promise((resolve, reject) => {
        canvas.toBlob((blob) => {
            if (!blob) {
                reject(new Error('图片压缩失败。'))
                return
            }
            resolve(blob)
        }, 'image/jpeg', quality)
    })
}

export const compressImageFile = async (file, options = {}) => {
    const maxUploadBytes = options.maxUploadBytes || MAX_UPLOAD_BYTES
    const maxWidth = options.maxWidth || 1600

    const img = await loadImageFromFile(file)

    let targetWidth = img.width
    let targetHeight = img.height

    if (img.width > maxWidth) {
        const ratio = maxWidth / img.width
        targetWidth = maxWidth
        targetHeight = Math.max(1, Math.round(img.height * ratio))
    }

    let canvas = document.createElement('canvas')
    canvas.width = targetWidth
    canvas.height = targetHeight

    let ctx = canvas.getContext('2d')
    if (!ctx) {
        throw new Error('浏览器不支持图片处理。')
    }

    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, targetWidth, targetHeight)
    ctx.drawImage(img, 0, 0, targetWidth, targetHeight)

    let quality = 0.82
    let blob = await canvasToBlob(canvas, quality)

    while (blob.size > maxUploadBytes && quality > 0.46) {
        quality -= 0.08
        blob = await canvasToBlob(canvas, quality)
    }

    while (blob.size > maxUploadBytes && canvas.width > 960) {
        const nextWidth = Math.max(960, Math.round(canvas.width * 0.9))
        const nextHeight = Math.max(1, Math.round(canvas.height * 0.9))

        const nextCanvas = document.createElement('canvas')
        nextCanvas.width = nextWidth
        nextCanvas.height = nextHeight

        const nextCtx = nextCanvas.getContext('2d')
        if (!nextCtx) {
            throw new Error('浏览器不支持图片处理。')
        }

        nextCtx.fillStyle = '#ffffff'
        nextCtx.fillRect(0, 0, nextWidth, nextHeight)
        nextCtx.drawImage(canvas, 0, 0, nextWidth, nextHeight)

        canvas = nextCanvas
        ctx = nextCtx
        blob = await canvasToBlob(canvas, 0.7)
    }

    const outputName = `${(file.name || 'upload').replace(/\.[^.]+$/, '') || 'upload'}.jpg`

    return new File([blob], outputName, {
        type: 'image/jpeg'
    })
}

export const validateImageType = (file) => {
    if (!file) return false
    if (!file.type) return true
    return ACCEPTED_IMAGE_TYPES.includes(file.type)
}

export const clearFileInput = (target) => {
    const input = target?.target || target
    if (input && typeof input.value !== 'undefined') {
        input.value = ''
    }
}

export const clearFileInputsById = (ids = []) => {
    ids.forEach((id) => {
        const input = document.getElementById(id)
        clearFileInput(input)
    })
}

export const revokeObjectUrl = (url) => {
    if (typeof url === 'string' && url.startsWith('blob:')) {
        URL.revokeObjectURL(url)
    }
}

export const revokePreviewList = (previews = [], urlKey = 'url') => {
    previews.forEach((item) => {
        const url = typeof item === 'string' ? item : item?.[urlKey]
        revokeObjectUrl(url)
    })
}

export const prepareImageFile = async (file, options = {}) => {
    if (!file) {
        throw new ImageUploadError('未选择图片。', 'EMPTY_FILE')
    }
    if (!validateImageType(file)) {
        throw new ImageUploadError(IMAGE_UPLOAD_TYPE_ERROR_MESSAGE, 'UNSUPPORTED_TYPE')
    }

    try {
        return await compressImageFile(file, options)
    } catch (error) {
        if (error instanceof ImageUploadError) {
            throw error
        }
        throw new ImageUploadError(error?.message || IMAGE_UPLOAD_PROCESS_ERROR_MESSAGE, 'PROCESS_FAILED')
    }
}

export const prepareImagePreview = async (file, options = {}) => {
    const preparedFile = await prepareImageFile(file, options)
    return {
        file: preparedFile,
        previewUrl: URL.createObjectURL(preparedFile)
    }
}

export const prepareImagePreviewList = async (files = [], options = {}) => {
    const list = Array.from(files || [])
    const limit = Number.isFinite(options.limit) ? options.limit : list.length
    const existingCount = Number.isFinite(options.existingCount) ? options.existingCount : 0
    const remainingCount = Math.max(0, limit - existingCount)
    const filesToProcess = list.slice(0, remainingCount)
    const preparedFiles = []
    const previews = []
    const errors = []

    if (remainingCount <= 0) {
        return {
            files: preparedFiles,
            previews,
            errors,
            failedCount: 0,
            truncated: list.length > 0,
            remainingCount,
            processedCount: 0
        }
    }

    for (const file of filesToProcess) {
        try {
            const prepared = await prepareImagePreview(file, options)
            preparedFiles.push(prepared.file)
            previews.push({
                file: prepared.file,
                url: prepared.previewUrl
            })
        } catch (error) {
            errors.push(error)
        }
    }

    return {
        files: preparedFiles,
        previews,
        errors,
        failedCount: errors.length,
        truncated: list.length > remainingCount,
        remainingCount,
        processedCount: filesToProcess.length
    }
}
