import { canvasToBlob } from './imageUpload'

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))

const getOrientation = (photo) => {
  const width = Number(photo?.img?.width || 1)
  const height = Number(photo?.img?.height || 1)
  if (width / height > 1.08) return 'landscape'
  if (height / width > 1.08) return 'portrait'
  return 'square'
}

const createItem = (photo, cell) => ({
  photoId: photo.id,
  x: Math.round(cell.x),
  y: Math.round(cell.y),
  w: Math.round(cell.w),
  h: Math.round(cell.h),
  scale: 1,
  offsetX: 0,
  offsetY: 0
})

const normalizePhotoOrder = (photos = [], preferLandscape = false) => {
  if (!preferLandscape) return [...photos]
  return [...photos].sort((a, b) => {
    const score = (photo) => (getOrientation(photo) === 'landscape' ? 0 : 1)
    return score(a) - score(b)
  })
}

export const createAutoIssuePhotoComposition = (photos = []) => {
  const list = photos.slice(0, 3)
  const width = 1200
  const margin = 32
  const gap = 22
  const contentWidth = width - margin * 2

  if (list.length === 0) {
    return { width, height: 800, items: [], circles: [] }
  }

  if (list.length === 1) {
    const photo = list[0]
    const ratio = Number(photo?.img?.height || 1) / Number(photo?.img?.width || 1)
    const cellHeight = clamp(Math.round(contentWidth * ratio), 620, 1380)
    return {
      width,
      height: cellHeight + margin * 2,
      items: [createItem(photo, { x: margin, y: margin, w: contentWidth, h: cellHeight })],
      circles: []
    }
  }

  if (list.length === 2) {
    const orientations = list.map(getOrientation)
    const bothLandscape = orientations.every((item) => item === 'landscape')
    const bothPortrait = orientations.every((item) => item === 'portrait')

    if (bothLandscape) {
      const cellHeight = Math.round(contentWidth * 0.58)
      return {
        width,
        height: margin * 2 + cellHeight * 2 + gap,
        items: [
          createItem(list[0], { x: margin, y: margin, w: contentWidth, h: cellHeight }),
          createItem(list[1], { x: margin, y: margin + cellHeight + gap, w: contentWidth, h: cellHeight })
        ],
        circles: []
      }
    }

    const cellWidth = Math.round((contentWidth - gap) / 2)
    const cellHeight = bothPortrait ? 860 : 760
    return {
      width,
      height: margin * 2 + cellHeight,
      items: [
        createItem(list[0], { x: margin, y: margin, w: cellWidth, h: cellHeight }),
        createItem(list[1], { x: margin + cellWidth + gap, y: margin, w: contentWidth - cellWidth - gap, h: cellHeight })
      ],
      circles: []
    }
  }

  const landscapeCount = list.filter((photo) => getOrientation(photo) === 'landscape').length
  if (landscapeCount >= 2) {
    const ordered = normalizePhotoOrder(list, true)
    const topHeight = Math.round(contentWidth * 0.56)
    const bottomWidth = Math.round((contentWidth - gap) / 2)
    const bottomHeight = Math.round(bottomWidth * 0.72)
    return {
      width,
      height: margin * 2 + topHeight + gap + bottomHeight,
      items: [
        createItem(ordered[0], { x: margin, y: margin, w: contentWidth, h: topHeight }),
        createItem(ordered[1], { x: margin, y: margin + topHeight + gap, w: bottomWidth, h: bottomHeight }),
        createItem(ordered[2], { x: margin + bottomWidth + gap, y: margin + topHeight + gap, w: contentWidth - bottomWidth - gap, h: bottomHeight })
      ],
      circles: []
    }
  }

  const leftWidth = Math.round(contentWidth * 0.56)
  const rightWidth = contentWidth - leftWidth - gap
  const canvasHeight = 980
  const rightCellHeight = Math.round((canvasHeight - margin * 2 - gap) / 2)
  return {
    width,
    height: canvasHeight,
    items: [
      createItem(list[0], { x: margin, y: margin, w: leftWidth, h: canvasHeight - margin * 2 }),
      createItem(list[1], { x: margin + leftWidth + gap, y: margin, w: rightWidth, h: rightCellHeight }),
      createItem(list[2], { x: margin + leftWidth + gap, y: margin + rightCellHeight + gap, w: rightWidth, h: canvasHeight - margin * 2 - rightCellHeight - gap })
    ],
    circles: []
  }
}

export const clampCompositionItemOffset = (item, photo) => {
  if (!item || !photo?.img) return item
  const baseScale = Math.max(item.w / photo.img.width, item.h / photo.img.height)
  const scale = baseScale * clamp(Number(item.scale || 1), 1, 3)
  const renderedWidth = photo.img.width * scale
  const renderedHeight = photo.img.height * scale
  const maxOffsetX = Math.max(0, (renderedWidth - item.w) / 2)
  const maxOffsetY = Math.max(0, (renderedHeight - item.h) / 2)
  item.offsetX = clamp(Number(item.offsetX || 0), -maxOffsetX, maxOffsetX)
  item.offsetY = clamp(Number(item.offsetY || 0), -maxOffsetY, maxOffsetY)
  item.scale = clamp(Number(item.scale || 1), 1, 3)
  return item
}

export const renderIssuePhotoComposition = (canvas, photos = [], composition, options = {}) => {
  if (!canvas || !composition) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  canvas.width = composition.width
  canvas.height = composition.height
  const photoMap = new Map(photos.map((photo) => [photo.id, photo]))

  ctx.save()
  ctx.fillStyle = '#f8fafc'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  ;(composition.items || []).forEach((rawItem) => {
    const photo = photoMap.get(rawItem.photoId)
    const item = clampCompositionItemOffset(rawItem, photo)
    const isSelected = options.selectedPhotoId === item.photoId
    const isSwapSource = options.swapSourcePhotoId === item.photoId
    const isSwapTarget = options.swapTargetPhotoId === item.photoId && !isSwapSource
    ctx.save()
    ctx.shadowColor = 'rgba(15, 23, 42, 0.12)'
    ctx.shadowBlur = 18
    ctx.shadowOffsetY = 8
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(item.x, item.y, item.w, item.h)
    ctx.restore()

    ctx.save()
    ctx.beginPath()
    ctx.rect(item.x, item.y, item.w, item.h)
    ctx.clip()
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(item.x, item.y, item.w, item.h)

    if (photo?.img) {
      const baseScale = Math.max(item.w / photo.img.width, item.h / photo.img.height)
      const scale = baseScale * item.scale
      const drawWidth = photo.img.width * scale
      const drawHeight = photo.img.height * scale
      const drawX = item.x + item.w / 2 - drawWidth / 2 + item.offsetX
      const drawY = item.y + item.h / 2 - drawHeight / 2 + item.offsetY
      ctx.drawImage(photo.img, drawX, drawY, drawWidth, drawHeight)
    }
    ctx.restore()

    ctx.save()
    ctx.lineWidth = isSelected || isSwapSource || isSwapTarget ? 7 : 3
    ctx.strokeStyle = isSwapTarget
      ? '#f97316'
      : isSwapSource
        ? '#16a34a'
        : isSelected
          ? '#2563eb'
          : '#e2e8f0'
    ctx.strokeRect(item.x + 1, item.y + 1, item.w - 2, item.h - 2)
    ctx.restore()

    if (isSwapSource || isSwapTarget) {
      ctx.save()
      ctx.fillStyle = isSwapTarget ? 'rgba(249, 115, 22, 0.14)' : 'rgba(22, 163, 74, 0.12)'
      ctx.fillRect(item.x, item.y, item.w, item.h)
      ctx.fillStyle = isSwapTarget ? '#9a3412' : '#166534'
      ctx.font = '700 28px sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(isSwapTarget ? '放到这里' : '正在移动', item.x + item.w / 2, item.y + item.h / 2)
      ctx.restore()
    }
  })

  const circles = [...(composition.circles || [])]
  if (options.draftCircle) circles.push(options.draftCircle)
  circles.forEach((circle) => {
    if (!circle || !Number.isFinite(circle.r) || circle.r <= 2) return
    ctx.save()
    ctx.strokeStyle = circle.color || '#ef4444'
    ctx.lineWidth = circle.lineWidth || 8
    ctx.beginPath()
    ctx.arc(circle.x, circle.y, circle.r, 0, Math.PI * 2)
    ctx.stroke()
    ctx.restore()
  })

  ctx.restore()
}

export const exportIssuePhotoCompositionFile = async (photos, composition, filename = 'issue-photo-composite.jpg') => {
  const canvas = document.createElement('canvas')
  renderIssuePhotoComposition(canvas, photos, composition)
  const blob = await canvasToBlob(canvas, 0.86)
  return new File([blob], filename, { type: 'image/jpeg' })
}
