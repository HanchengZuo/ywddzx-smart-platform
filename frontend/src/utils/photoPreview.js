export const MIN_PHOTO_SCALE = 0.5
export const MAX_PHOTO_SCALE = 5

export function fitPhoto(image, viewport) {
  if (!image.width || !image.height || !viewport.width || !viewport.height)
    return { width: 0, height: 0 }
  const ratio = Math.min(viewport.width / image.width, viewport.height / image.height, 1)
  return { width: image.width * ratio, height: image.height * ratio }
}

export function clampPhotoPosition(position, scale, image, viewport) {
  const limitX = Math.max(0, (image.width * scale - viewport.width) / 2)
  const limitY = Math.max(0, (image.height * scale - viewport.height) / 2)
  return {
    x: Math.min(limitX, Math.max(-limitX, position.x)) || 0,
    y: Math.min(limitY, Math.max(-limitY, position.y)) || 0,
  }
}

// Keep the point under the cursor (or pinch midpoint) stationary while zooming.
export function zoomPhoto(state, requestedScale, anchor, image, viewport) {
  const scale = Math.min(MAX_PHOTO_SCALE, Math.max(MIN_PHOTO_SCALE, requestedScale))
  const ratio = scale / state.scale
  const position = clampPhotoPosition(
    { x: anchor.x - (anchor.x - state.x) * ratio, y: anchor.y - (anchor.y - state.y) * ratio },
    scale,
    image,
    viewport,
  )
  return { scale, ...position }
}

const scrollLocks = new WeakMap()
export function lockPhotoPreviewScroll(body) {
  let lock = scrollLocks.get(body)
  if (!lock) {
    lock = { count: 0, overflow: body.style.overflow }
    scrollLocks.set(body, lock)
  }
  lock.count += 1
  body.style.overflow = 'hidden'
  let released = false
  return () => {
    if (released) return
    released = true
    lock.count -= 1
    if (!lock.count) {
      body.style.overflow = lock.overflow
      scrollLocks.delete(body)
    }
  }
}
