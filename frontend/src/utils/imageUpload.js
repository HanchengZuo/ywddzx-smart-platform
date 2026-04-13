const MAX_UPLOAD_BYTES = 500 * 1024
const ACCEPTED_IMAGE_TYPES = [
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/webp',
    'image/heic',
    'image/heif'
]

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