<template>
  <Teleport :to="teleportTarget">
    <div
      ref="overlay"
      class="issue-photo-preview-overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
      tabindex="-1"
      @click.self="emit('close')"
      @keydown.stop="handleKeydown"
      @wheel.prevent.stop="handleWheel"
    >
      <section class="issue-photo-preview-dialog">
        <header class="photo-preview-head">
          <strong>{{ title }}</strong>
          <button
            type="button"
            class="photo-preview-close"
            aria-label="关闭图片预览"
            @click="emit('close')"
          >
            ×
          </button>
        </header>
        <div
          ref="viewport"
          class="photo-preview-viewport"
          :class="{ dragging: pointers.size > 0, zoomed: transform.scale > 1 }"
          @pointerdown="startPointer"
          @pointermove="movePointer"
          @pointerup="endPointer"
          @pointercancel="endPointer"
          @lostpointercapture="endPointer"
          @dblclick.prevent="reset"
        >
          <img
            v-if="!failed"
            :key="url"
            :src="url"
            :alt="title"
            :style="imageStyle"
            draggable="false"
            @load="imageLoaded"
            @error="imageFailed"
          />
          <span v-if="failed" class="photo-preview-status" role="alert"
            >图片加载失败，请关闭后重试。</span
          >
          <span v-else-if="!loaded" class="photo-preview-status" role="status">正在加载图片…</span>
        </div>
        <footer class="photo-preview-tools">
          <div class="photo-preview-controls" role="group" aria-label="图片缩放">
            <button
              type="button"
              aria-label="缩小图片"
              :disabled="!loaded || transform.scale <= MIN_PHOTO_SCALE"
              @click="changeScale(transform.scale / 1.2)"
            >
              −
            </button>
            <output aria-label="当前缩放比例">{{ Math.round(transform.scale * 100) }}%</output>
            <button
              type="button"
              aria-label="放大图片"
              :disabled="!loaded || transform.scale >= MAX_PHOTO_SCALE"
              @click="changeScale(transform.scale * 1.2)"
            >
              ＋
            </button>
            <button type="button" class="photo-preview-reset" :disabled="!loaded" @click="reset">
              适应窗口
            </button>
          </div>
          <span class="photo-preview-hint">滚轮 / 双指缩放 · 拖动查看 · 双击复位</span>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  clampPhotoPosition,
  fitPhoto,
  lockPhotoPreviewScroll,
  MAX_PHOTO_SCALE,
  MIN_PHOTO_SCALE,
  zoomPhoto,
} from '@/utils/photoPreview'
const props = defineProps({
  url: { type: String, required: true },
  title: { type: String, default: '图片预览' },
})
const emit = defineEmits(['close'])
const overlay = ref(null),
  viewport = ref(null),
  teleportTarget = ref('body')
const loaded = ref(false),
  failed = ref(false)
const naturalSize = reactive({ width: 0, height: 0 }),
  viewportSize = reactive({ width: 0, height: 0 })
const transform = reactive({ scale: 1, x: 0, y: 0 }),
  pointers = reactive(new Map())
const imageSize = computed(() =>
  fitPhoto(naturalSize, {
    width: Math.max(0, viewportSize.width - 24),
    height: Math.max(0, viewportSize.height - 24),
  }),
)
const imageStyle = computed(() => ({
  width: `${imageSize.value.width}px`,
  height: `${imageSize.value.height}px`,
  visibility: loaded.value ? 'visible' : 'hidden',
  transform: `translate(-50%, -50%) translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
}))
let previousFocus
let releaseScroll
let resizeObserver
let disposed = false
function reset() {
  Object.assign(transform, { scale: 1, x: 0, y: 0 })
}
function imageLoaded(event) {
  if (event.target.getAttribute('src') !== props.url) return
  Object.assign(naturalSize, {
    width: event.target.naturalWidth,
    height: event.target.naturalHeight,
  })
  loaded.value = true
  failed.value = false
}
function imageFailed(event) {
  if (event.target.getAttribute('src') !== props.url) return
  failed.value = true
  loaded.value = false
}
function measureViewport() {
  if (!viewport.value) return
  Object.assign(viewportSize, {
    width: viewport.value.clientWidth,
    height: viewport.value.clientHeight,
  })
  Object.assign(
    transform,
    clampPhotoPosition(transform, transform.scale, imageSize.value, viewportSize),
  )
}
function anchorAt(point) {
  const rect = viewport.value.getBoundingClientRect()
  return { x: point.x - rect.left - rect.width / 2, y: point.y - rect.top - rect.height / 2 }
}
function changeScale(scale, anchor = { x: 0, y: 0 }) {
  if (loaded.value)
    Object.assign(transform, zoomPhoto(transform, scale, anchor, imageSize.value, viewportSize))
}
function handleWheel(event) {
  if (!viewport.value?.contains(event.target) || !event.deltaY) return
  const pixels =
    event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewportSize.height : 1)
  changeScale(
    transform.scale * Math.exp(-Math.max(-100, Math.min(100, pixels)) * 0.002),
    anchorAt({ x: event.clientX, y: event.clientY }),
  )
}
function startPointer(event) {
  if (!loaded.value || event.button !== 0) return
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  viewport.value.setPointerCapture(event.pointerId)
}
function movePointer(event) {
  if (!pointers.has(event.pointerId)) return
  const before = [...pointers.values()],
    previous = pointers.get(event.pointerId)
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  if (pointers.size === 2) {
    const after = [...pointers.values()]
    const distance = (points) => Math.hypot(points[1].x - points[0].x, points[1].y - points[0].y)
    const midpoint = (points) => ({
      x: (points[0].x + points[1].x) / 2,
      y: (points[0].y + points[1].y) / 2,
    })
    const oldDistance = distance(before)
    if (!oldDistance) return
    const oldCenter = midpoint(before),
      newCenter = midpoint(after)
    const next = zoomPhoto(
      transform,
      (transform.scale * distance(after)) / oldDistance,
      anchorAt(oldCenter),
      imageSize.value,
      viewportSize,
    )
    Object.assign(
      transform,
      next,
      clampPhotoPosition(
        { x: next.x + newCenter.x - oldCenter.x, y: next.y + newCenter.y - oldCenter.y },
        next.scale,
        imageSize.value,
        viewportSize,
      ),
    )
  } else if (pointers.size === 1) {
    Object.assign(
      transform,
      clampPhotoPosition(
        {
          x: transform.x + event.clientX - previous.x,
          y: transform.y + event.clientY - previous.y,
        },
        transform.scale,
        imageSize.value,
        viewportSize,
      ),
    )
  }
}
function endPointer(event) {
  pointers.delete(event.pointerId)
}
function handleKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
  } else if (event.key === 'Tab') {
    const buttons = [...overlay.value.querySelectorAll('button:not(:disabled)')]
    const index = buttons.indexOf(document.activeElement)
    event.preventDefault()
    const next =
      index < 0
        ? event.shiftKey
          ? buttons.length - 1
          : 0
        : (index + (event.shiftKey ? -1 : 1) + buttons.length) % buttons.length
    buttons[next]?.focus()
  } else if (['+', '=', '-', '0'].includes(event.key)) {
    event.preventDefault()
    if (event.key === '0') reset()
    else changeScale(transform.scale * (event.key === '-' ? 1 / 1.2 : 1.2))
  }
}
async function updateFullscreenTarget() {
  teleportTarget.value = document.fullscreenElement || 'body'
  await nextTick()
  if (disposed) return
  measureViewport()
  overlay.value?.focus()
}
watch(
  () => props.url,
  () => {
    loaded.value = false
    failed.value = false
    pointers.clear()
    reset()
  },
)
onMounted(async () => {
  previousFocus = document.activeElement
  releaseScroll = lockPhotoPreviewScroll(document.body)
  document.addEventListener('fullscreenchange', updateFullscreenTarget)
  window.addEventListener('resize', measureViewport)
  await updateFullscreenTarget()
  if (disposed) return
  resizeObserver = new ResizeObserver(measureViewport)
  if (viewport.value) resizeObserver.observe(viewport.value)
})
onBeforeUnmount(() => {
  disposed = true
  resizeObserver?.disconnect()
  document.removeEventListener('fullscreenchange', updateFullscreenTarget)
  window.removeEventListener('resize', measureViewport)
  releaseScroll?.()
  if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true })
})
</script>
<style scoped>
.issue-photo-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 100000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  box-sizing: border-box;
  background: rgba(15, 23, 42, 0.8);
  outline: none;
  pointer-events: auto;
  overscroll-behavior: contain;
}
.issue-photo-preview-dialog {
  display: flex;
  flex-direction: column;
  width: min(1200px, 100%);
  height: min(900px, 94dvh);
  max-height: 100%;
  min-height: 0;
  overflow: hidden;
  border: 1px solid #cbd5e1;
  border-radius: 18px;
  background: #f1f5f9;
  box-shadow: 0 24px 54px rgba(15, 23, 42, 0.32);
}
.photo-preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 18px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}
.photo-preview-head strong {
  color: #1e293b;
  font-size: 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.photo-preview-close {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: 1px solid #fecaca;
  border-radius: 10px;
  color: #b91c1c;
  background: #fff1f2;
  font-size: 24px;
  cursor: pointer;
}
.photo-preview-viewport {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  touch-action: none;
  cursor: zoom-in;
}
.photo-preview-viewport.zoomed {
  cursor: grab;
}
.photo-preview-viewport.dragging {
  cursor: grabbing;
}
.photo-preview-viewport img {
  position: absolute;
  left: 50%;
  top: 50%;
  display: block;
  max-width: none;
  max-height: none;
  padding: 0;
  margin: 0;
  border: 0;
  border-radius: 0;
  object-fit: contain;
  transform-origin: center;
  pointer-events: none;
  user-select: none;
  will-change: transform;
}
.photo-preview-status {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-size: 14px;
}
.photo-preview-tools {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 18px;
  background: #fff;
  border-top: 1px solid #e2e8f0;
}
.photo-preview-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}
.photo-preview-controls button {
  height: 36px;
  min-width: 36px;
  padding: 0 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #1e40af;
  cursor: pointer;
  font-size: 18px;
}
.photo-preview-controls button:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}
.photo-preview-controls .photo-preview-reset {
  font-size: 13px;
}
.photo-preview-controls output {
  width: 54px;
  text-align: center;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  color: #334155;
}
.photo-preview-hint {
  color: #64748b;
  font-size: 12px;
}
.issue-photo-preview-dialog button:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
@media (max-width: 640px) {
  .issue-photo-preview-overlay {
    padding: 8px;
  }
  .issue-photo-preview-dialog {
    height: 96dvh;
    border-radius: 12px;
  }
  .photo-preview-head,
  .photo-preview-tools {
    padding: 10px 12px;
  }
  .photo-preview-tools {
    justify-content: center;
  }
  .photo-preview-hint {
    width: 100%;
    text-align: center;
  }
}
</style>
