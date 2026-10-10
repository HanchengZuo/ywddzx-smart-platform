<template>
  <Teleport to="body">
    <div class="photo-editor-overlay" @keydown.esc.stop.prevent="close">
      <section
        class="photo-editor-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="photo-editor-title"
      >
        <header class="photo-editor-head">
          <div>
            <span>{{ title }}</span>
            <h3 id="photo-editor-title">裁剪、调换和图片标注</h3>
          </div>
          <button
            ref="closeButton"
            class="photo-editor-close"
            type="button"
            :disabled="saving"
            aria-label="关闭图片编辑"
            @click="close"
          >
            ×
          </button>
        </header>
        <div class="photo-editor-body">
          <aside class="photo-editor-side">
            <div class="editor-tool-group">
              <button
                v-for="entry in tools"
                :key="entry.key"
                type="button"
                :disabled="saving || (entry.key === 'swap' && photos.length < 2)"
                :class="{ active: tool === entry.key }"
                :aria-pressed="tool === entry.key"
                @click="changeTool(entry.key)"
              >
                {{ entry.label }}
              </button>
            </div>
            <p class="editor-tip">{{ tip }}</p>
            <div v-if="tool === 'annotation'" class="annotation-settings">
              <div class="editor-tool-group">
                <button
                  v-for="entry in shapes"
                  :key="entry.key"
                  type="button"
                  :class="{ active: shape === entry.key }"
                  :disabled="saving"
                  :aria-pressed="shape === entry.key"
                  @click="shape = entry.key"
                >
                  {{ entry.label }}
                </button>
              </div>
              <label class="editor-range"
                ><span>标注粗细：{{ lineWidth }}（默认6）</span>
                <input
                  v-model.number="lineWidth"
                  aria-label="标注粗细"
                  type="range"
                  min="2"
                  max="16"
                  step="1"
                  :disabled="saving"
                />
                <small>细 2 · 标准 6 · 粗 16</small>
              </label>
            </div>
            <div class="editor-source-list">
              <button
                v-for="photo in photos"
                :key="photo.id"
                type="button"
                :disabled="saving"
                :class="{ active: selectedPhotoId === photo.id }"
                @click="selectPhoto(photo.id)"
              >
                <img :src="photo.url" :alt="photo.name" /><span>{{ photo.name }}</span>
              </button>
            </div>
            <label v-if="tool === 'crop' && selectedItem" class="editor-range">
              <span>图片缩放 {{ Math.round(selectedItem.scale * 100) }}%</span>
              <input
                v-model.number="selectedItem.scale"
                aria-label="图片缩放"
                type="range"
                min="1"
                max="3"
                step="0.05"
                :disabled="saving"
                @input="scalePhoto"
              />
            </label>
            <div class="editor-actions-stack">
              <button type="button" :disabled="saving" @click="reset">自动重新拼接</button>
              <button type="button" :disabled="saving || !draft.annotations.length" @click="undo">
                撤销标注
              </button>
            </div>
            <p v-if="error" class="editor-error" role="alert">{{ error }}</p>
          </aside>
          <main class="photo-editor-canvas-wrap">
            <canvas
              ref="canvas"
              class="photo-editor-canvas"
              :class="{ marking: tool === 'annotation' }"
              aria-label="照片编辑画布"
              @pointerdown="pointerDown"
              @pointermove="pointerMove"
              @pointerup="pointerUp"
              @pointercancel="cancelPointer"
              @lostpointercapture="cancelPointer"
            ></canvas>
          </main>
        </div>
        <footer class="photo-editor-foot">
          <span>保存后应用到提交照片；取消会放弃本次编辑。</span>
          <button type="button" :disabled="saving" @click="close">取消</button>
          <button class="primary" type="button" :disabled="saving || !!pointer" @click="save">
            {{ saving ? '生成中…' : '保存照片' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  clampCompositionItemOffset,
  createAutoIssuePhotoComposition,
  createPhotoAnnotation,
  DEFAULT_ANNOTATION_LINE_WIDTH,
  exportIssuePhotoCompositionFile,
  renderIssuePhotoComposition,
} from '@/utils/imageComposer'

const props = defineProps({
  photos: { type: Array, required: true },
  composition: { type: Object, required: true },
  title: { type: String, default: '照片编辑' },
  savePhoto: { type: Function, required: true },
})
const emit = defineEmits(['close'])
const clone = (value) => JSON.parse(JSON.stringify(value))
const draft = ref(clone(props.composition))
draft.value.annotations = [...(draft.value.circles || []), ...(draft.value.annotations || [])]
draft.value.circles = []
const canvas = ref(null),
  closeButton = ref(null),
  tool = ref('crop'),
  shape = ref('circle')
const lineWidth = ref(DEFAULT_ANNOTATION_LINE_WIDTH),
  selectedPhotoId = ref(props.photos[0]?.id || '')
const pointer = ref(null),
  draftAnnotation = ref(null),
  swapTarget = ref(''),
  saving = ref(false),
  error = ref('')
const tools = [
  { key: 'crop', label: '裁剪调整' },
  { key: 'swap', label: '调换位置' },
  { key: 'annotation', label: '图片标注' },
]
const shapes = [
  { key: 'circle', label: '圆形标注' },
  { key: 'rectangle', label: '矩形标注' },
]
const tip = computed(() =>
  tool.value === 'crop'
    ? '选择图片后拖动调整裁剪位置，使用缩放条放大。'
    : tool.value === 'swap'
      ? '将一张照片拖到另一个框中调换位置。'
      : shape.value === 'circle'
        ? '从圆心向外拖动画圆，线宽可在下方调整。'
        : '从一个角拖到对角画矩形，支持任意拖动方向。',
)
const selectedItem = computed(() =>
  draft.value.items.find((item) => item.photoId === selectedPhotoId.value),
)
const photoById = (id) => props.photos.find((photo) => photo.id === id)
const redraw = () =>
  renderIssuePhotoComposition(canvas.value, props.photos, draft.value, {
    selectedPhotoId: tool.value === 'crop' ? selectedPhotoId.value : '',
    swapSourcePhotoId: pointer.value?.type === 'swap' ? pointer.value.photoId : '',
    swapTargetPhotoId: swapTarget.value,
    draftAnnotation: draftAnnotation.value,
  })
const pointFor = (event) => {
  const rect = canvas.value.getBoundingClientRect()
  return {
    x: Math.min(
      canvas.value.width,
      Math.max(0, ((event.clientX - rect.left) * canvas.value.width) / rect.width),
    ),
    y: Math.min(
      canvas.value.height,
      Math.max(0, ((event.clientY - rect.top) * canvas.value.height) / rect.height),
    ),
  }
}
const itemAt = (point) =>
  [...draft.value.items]
    .reverse()
    .find(
      (item) =>
        point.x >= item.x &&
        point.x <= item.x + item.w &&
        point.y >= item.y &&
        point.y <= item.y + item.h,
    )
function cancelPointer() {
  pointer.value = null
  draftAnnotation.value = null
  swapTarget.value = ''
  redraw()
}
function changeTool(value) {
  cancelPointer()
  tool.value = value
  redraw()
}
function selectPhoto(id) {
  selectedPhotoId.value = id
  changeTool('crop')
}
function scalePhoto() {
  clampCompositionItemOffset(selectedItem.value, photoById(selectedPhotoId.value))
  redraw()
}
function pointerDown(event) {
  if (saving.value || pointer.value || event.button !== 0) return
  const point = pointFor(event),
    item = itemAt(point)
  if (tool.value !== 'annotation' && !item) return
  canvas.value.setPointerCapture(event.pointerId)
  if (item) selectedPhotoId.value = item.photoId
  pointer.value = {
    id: event.pointerId,
    type: tool.value,
    start: point,
    photoId: item?.photoId,
    offsetX: item?.offsetX || 0,
    offsetY: item?.offsetY || 0,
    shape: shape.value,
    lineWidth: lineWidth.value,
  }
  redraw()
}
function pointerMove(event) {
  const gesture = pointer.value
  if (!gesture || gesture.id !== event.pointerId) return
  const point = pointFor(event)
  if (gesture.type === 'annotation')
    draftAnnotation.value = createPhotoAnnotation(
      gesture.shape,
      gesture.start,
      point,
      draft.value.width,
      draft.value.height,
      gesture.lineWidth,
    )
  else if (gesture.type === 'swap') swapTarget.value = itemAt(point)?.photoId || ''
  else {
    const item = draft.value.items.find((entry) => entry.photoId === gesture.photoId)
    item.offsetX = gesture.offsetX + point.x - gesture.start.x
    item.offsetY = gesture.offsetY + point.y - gesture.start.y
    clampCompositionItemOffset(item, photoById(gesture.photoId))
  }
  redraw()
}
function pointerUp(event) {
  if (!pointer.value || pointer.value.id !== event.pointerId) return
  pointerMove(event)
  const gesture = pointer.value,
    annotation = draftAnnotation.value
  if (
    annotation &&
    (annotation.type === 'rectangle' ? annotation.w > 8 && annotation.h > 8 : annotation.r > 8)
  )
    draft.value.annotations.push({ ...annotation })
  if (gesture.type === 'swap') {
    const a = draft.value.items.find((item) => item.photoId === gesture.photoId),
      b = draft.value.items.find((item) => item.photoId === swapTarget.value)
    if (a && b && a !== b) {
      ;[a.photoId, b.photoId] = [b.photoId, a.photoId]
      for (const item of [a, b]) {
        item.scale = 1
        item.offsetX = 0
        item.offsetY = 0
      }
    }
  }
  cancelPointer()
  if (canvas.value.hasPointerCapture(event.pointerId))
    canvas.value.releasePointerCapture(event.pointerId)
}
function reset() {
  cancelPointer()
  draft.value = createAutoIssuePhotoComposition(props.photos)
  draft.value.annotations = []
  redraw()
}
function undo() {
  draft.value.annotations.pop()
  redraw()
}
function close() {
  if (!saving.value) emit('close')
}
async function save() {
  if (saving.value || pointer.value) return
  saving.value = true
  error.value = ''
  try {
    const composition = clone(draft.value)
    const file = await exportIssuePhotoCompositionFile(
      props.photos,
      composition,
      `photo-edited-${Date.now()}.jpg`,
    )
    await props.savePhoto(file, composition)
    emit('close')
  } catch (err) {
    error.value = err?.message || '照片生成失败，请重试。'
  } finally {
    saving.value = false
  }
}
let previousFocus
onMounted(async () => {
  previousFocus = document.activeElement
  await nextTick()
  redraw()
  closeButton.value?.focus()
})
onBeforeUnmount(() => {
  previousFocus?.focus?.()
})
</script>

<style scoped>
.photo-editor-overlay {
  position: fixed;
  inset: 0;
  z-index: 13000;
  background: #0f172ac9;
  display: grid;
  place-items: center;
  padding: 20px;
}
.photo-editor-dialog {
  width: min(1160px, 96vw);
  max-height: 94dvh;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 22px;
  overflow: hidden;
  box-shadow: 0 30px 80px #0004;
  color: #172338;
}
.photo-editor-head,
.photo-editor-foot {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 24px;
  background: #f8fafc;
  flex-shrink: 0;
}
.photo-editor-head {
  justify-content: space-between;
  border-bottom: 1px solid #e2e8f0;
}
.photo-editor-head span {
  color: #64748b;
  font-size: 12px;
}
.photo-editor-head h3 {
  margin: 5px 0 0;
  font-size: 21px;
}
button {
  font: inherit;
  font-size: 13px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  color: #334155;
  padding: 10px 14px;
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
button:focus-visible,
input:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
.photo-editor-close {
  font-size: 24px;
  padding: 5px 12px;
}
.photo-editor-body {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: 0;
  overflow: auto;
}
.photo-editor-side {
  padding: 20px;
  overflow: auto;
  background: #fff;
  border-right: 1px solid #e2e8f0;
}
.editor-tool-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.editor-tool-group button {
  flex: 1 1 65px;
  padding: 10px 8px;
}
button.active {
  color: #1d4ed8;
  background: #eff6ff;
  border-color: #93c5fd;
}
.editor-tip {
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
}
.editor-source-list {
  display: grid;
  gap: 8px;
  margin: 16px 0;
}
.editor-source-list button {
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: left;
  min-width: 0;
}
.editor-source-list img {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
}
.editor-source-list span {
  overflow-wrap: anywhere;
  font-size: 12px;
}
.editor-range {
  display: grid;
  gap: 10px;
  margin: 14px 0;
  font-size: 13px;
}
.editor-range input {
  width: 100%;
  accent-color: #2563eb;
}
.editor-range small {
  color: #64748b;
}
.editor-actions-stack {
  display: grid;
  gap: 8px;
}
.photo-editor-canvas-wrap {
  min-width: 0;
  padding: 24px;
  overflow: auto;
  background: #e8edf3;
  display: grid;
  place-items: center;
}
.photo-editor-canvas {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 64dvh;
  touch-action: none;
  cursor: grab;
  display: block;
}
.photo-editor-canvas.marking {
  cursor: crosshair;
}
.photo-editor-foot {
  justify-content: flex-end;
  border-top: 1px solid #e2e8f0;
}
.photo-editor-foot span {
  margin-right: auto;
  font-size: 12px;
  color: #64748b;
}
button.primary {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}
.editor-error {
  color: #b91c1c;
  font-size: 13px;
}
@media (max-width: 768px) {
  .photo-editor-overlay {
    padding: 8px;
  }
  .photo-editor-dialog {
    width: 100%;
    max-height: 96dvh;
    border-radius: 16px;
  }
  .photo-editor-head,
  .photo-editor-foot {
    padding: 12px;
  }
  .photo-editor-head h3 {
    font-size: 17px;
  }
  .photo-editor-body {
    display: flex;
    flex-direction: column;
  }
  .photo-editor-side {
    padding: 12px;
    overflow: visible;
    border-right: 0;
  }
  .editor-source-list {
    display: flex;
    overflow-x: auto;
    margin: 10px 0;
  }
  .editor-source-list button {
    flex: 0 0 80px;
    padding: 6px;
  }
  .editor-source-list span {
    display: none;
  }
  .editor-actions-stack {
    grid-template-columns: 1fr 1fr;
  }
  .photo-editor-canvas-wrap {
    padding: 12px;
    overflow: visible;
  }
  .photo-editor-canvas {
    width: 100%;
    max-height: none;
  }
  .photo-editor-foot {
    flex-wrap: wrap;
  }
  .photo-editor-foot span {
    width: 100%;
  }
}
</style>
