<template>
  <section ref="uploadSection" class="inspection-photo-upload" :aria-busy="processing">
    <input :id="`${idPrefix}-upload`" ref="fileInput" class="photo-input" type="file" accept="image/*" multiple :disabled="disabled" @change="fileChanged" />
    <input :id="`${idPrefix}-camera`" ref="cameraInput" class="photo-input" type="file" accept="image/*" capture="environment" :disabled="disabled" @change="fileChanged" />
    <div class="photo-dropzone" :class="{ 'drag-active': dragActive, disabled }" role="button" :tabindex="disabled ? -1 : 0"
      :aria-label="`添加${label}，支持多图、粘贴和拖入`" :aria-disabled="disabled"
      @click="pick" @keydown.enter.self.prevent="pick" @keydown.space.self.prevent="pick"
      @dragenter.prevent="dragEnter" @dragover.prevent="dragOver" @dragleave.prevent="dragLeave"
      @drop.prevent="drop" @paste="paste">
      <span class="photo-upload-icon" aria-hidden="true">↑</span>
      <strong>{{ processing ? '正在处理照片…' : `选择或添加${label}` }}</strong>
      <p>最多3张，自动拼接为一张提交，默认完整保留画面。支持裁剪、调换位置、圆形/矩形标注和粗细调整。</p>
      <p>可复制后按 Ctrl+V / ⌘V 粘贴，或在电脑上拖入多张图片。</p>
      <div class="photo-actions">
        <button type="button" :disabled="disabled" @click.stop="cameraInput?.click()">拍照添加</button>
        <button type="button" class="primary" :disabled="disabled" @click.stop="pick">相册选择</button>
      </div>
    </div>
    <div v-if="previewUrl" class="photo-final-panel">
      <button type="button" class="photo-final-preview" :aria-label="`放大${label}`" @click="previewVisible = true">
        <img :src="previewUrl" :alt="`${label}最终提交预览`" />
      </button>
      <div class="photo-final-meta">
        <strong>最终提交照片</strong>
        <span>{{ photos.length > 1 ? `已由 ${photos.length} 张照片拼接生成` : finalFile?.name }}</span>
        <div class="photo-source-strip" aria-label="已添加的原始照片">
          <div v-for="(photo, index) in photos" :key="photo.id" class="photo-source">
            <img :src="photo.url" :alt="`第${index + 1}张：${photo.name}`" />
            <button type="button" :disabled="disabled || processing" :aria-label="`移除第${index + 1}张照片`" @click="remove(photo.id)">×</button>
          </div>
        </div>
        <div class="photo-actions">
          <button type="button" :disabled="disabled || processing" @click="editorVisible = true">图片编辑</button>
          <button type="button" :disabled="disabled || photos.length >= 3" @click="cameraInput?.click()">继续拍照</button>
          <button type="button" :disabled="disabled || photos.length >= 3" @click="pick">继续添加</button>
          <button type="button" :disabled="disabled" @click="clear()">清空图片</button>
        </div>
      </div>
    </div>
    <PhotoEditor v-if="editorVisible" :photos="photos" :composition="composition" :title="`${label}编辑`" :save-photo="saveEditor" @close="editorVisible = false" />
    <InspectionPhotoPreview v-if="previewVisible" :url="previewUrl" :title="label" @close="previewVisible = false" />
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import PhotoEditor from './PhotoEditor.vue'
import InspectionPhotoPreview from './InspectionPhotoPreview.vue'
import { getImageFilesFromClipboardEvent, getImageFilesFromDataTransfer, getImageFilesFromFileList,
  hasImageInDataTransfer, isDesktopImageDropEnabled, loadImageFromFile, prepareImageFile,
  prepareImagePreview, revokeObjectUrl, scrollImageUploadIntoView } from '@/utils/imageUpload'
import { createAutoIssuePhotoComposition, exportIssuePhotoCompositionFile } from '@/utils/imageComposer'

const props = defineProps({
  modelValue: { type: Object, default: null }, label: { type: String, default: '问题照片' },
  idPrefix: { type: String, required: true }, disabled: { type: Boolean, default: false },
  active: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue', 'notify', 'busy-change'])
const fileInput = ref(null), cameraInput = ref(null), uploadSection = ref(null)
const photos = ref([]), composition = ref(createAutoIssuePhotoComposition()), finalFile = ref(null), previewUrl = ref('')
const processing = ref(false), editorVisible = ref(false), previewVisible = ref(false), dragActive = ref(false)
const busy = computed(() => processing.value || editorVisible.value)
watch(busy, value => emit('busy-change', value), { flush: 'sync' })
let revision = 0, pending = 0, dragDepth = 0, alive = true, queue = Promise.resolve()
const valid = token => alive && token === revision && props.active && !props.disabled
const canReceive = () => props.active && !props.disabled && !editorVisible.value && !previewVisible.value
const release = list => list.forEach(photo => revokeObjectUrl(photo.url))
const notify = (message, type = 'info') => emit('notify', message, type)

// Serialize camera, picker, paste and drop operations; a reset invalidates all queued work.
function schedule(operation) {
  const token = revision
  pending++; processing.value = true
  const work = queue.then(() => valid(token) ? operation(token) : false)
  queue = work.catch(() => {})
  return work.catch(error => {
    if (valid(token)) notify(error?.message || '图片处理失败，请更换图片后重试。', 'error')
    return false
  }).finally(() => {
    if (token === revision) { pending--; processing.value = pending > 0 }
  })
}
async function publish(file, token) {
  const prepared = await prepareImagePreview(file)
  if (!valid(token)) { revokeObjectUrl(prepared.previewUrl); return false }
  revokeObjectUrl(previewUrl.value)
  previewUrl.value = prepared.previewUrl; finalFile.value = prepared.file
  emit('update:modelValue', prepared.file)
  return true
}
async function compose(list, token) {
  const layout = createAutoIssuePhotoComposition(list)
  const file = await exportIssuePhotoCompositionFile(list, layout, `${props.idPrefix}-${Date.now()}.jpg`)
  if (!await publish(file, token)) return false
  photos.value = list; composition.value = layout
  return true
}
function addFiles(files) {
  if (!canReceive()) return Promise.resolve(false)
  return schedule(async token => {
    const remaining = 3 - photos.value.length
    if (!remaining) { notify(`${props.label}最多只能添加3张。`, 'error'); return false }
    const added = []
    let committed = false
    try {
      for (const file of files.slice(0, remaining)) {
        const prepared = await prepareImageFile(file)
        const img = await loadImageFromFile(prepared)
        if (!valid(token)) return false
        added.push({ id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, file: prepared,
          img, url: URL.createObjectURL(prepared), name: prepared.name })
      }
      if (!added.length) return false
      committed = await compose([...photos.value, ...added], token)
      if (committed && files.length > remaining) notify('最多添加3张，已忽略超出的图片。')
      else if (committed && photos.value.length > 1) notify('照片已自动拼接，可进入图片编辑继续调整。', 'success')
      return committed
    } finally { if (!committed) release(added) }
  })
}
async function remove(id) {
  if (!canReceive() || processing.value) return
  const target = photos.value.find(photo => photo.id === id)
  const remaining = photos.value.filter(photo => photo.id !== id)
  if (!remaining.length) { clear(); return }
  await schedule(async token => {
    if (await compose(remaining, token)) release(target ? [target] : [])
  })
}
async function saveEditor(file, layout) {
  if (!await schedule(async token => {
    if (!await publish(file, token)) return false
    composition.value = layout
    notify('编辑照片已更新。', 'success')
    return true
  })) throw new Error('当前上传已关闭或照片处理失败，请重新打开。')
}
function clear(update = true) {
  revision++; pending = 0; processing.value = false
  editorVisible.value = false; previewVisible.value = false; dragActive.value = false; dragDepth = 0
  release(photos.value); photos.value = []; composition.value = createAutoIssuePhotoComposition()
  revokeObjectUrl(previewUrl.value); previewUrl.value = ''; finalFile.value = null
  if (fileInput.value) fileInput.value.value = ''
  if (cameraInput.value) cameraInput.value.value = ''
  if (update) emit('update:modelValue', null)
}
// Drafts contain the final JPEG, not its original sources; preserve its bytes on restore.
watch(() => props.modelValue, file => {
  if (file === finalFile.value) return
  clear(false)
  if (file) schedule(async token => {
    const img = await loadImageFromFile(file)
    if (!valid(token)) return false
    const photo = { id: `restored-${token}`, file, img, url: URL.createObjectURL(file), name: file.name }
    photos.value = [photo]; composition.value = createAutoIssuePhotoComposition([photo])
    previewUrl.value = URL.createObjectURL(file); finalFile.value = file
    return true
  })
}, { immediate: true })
function pick() { if (canReceive()) fileInput.value?.click() }
async function fileChanged(event) {
  const files = getImageFilesFromFileList(event.target.files)
  event.target.value = ''
  if (files.length) await addFiles(files)
}
async function paste(event) {
  if (event.defaultPrevented || !canReceive()) return
  const files = getImageFilesFromClipboardEvent(event)
  if (!files.length) return
  event.preventDefault(); dragDepth = 0; dragActive.value = false
  if (await addFiles(files)) { await nextTick(); scrollImageUploadIntoView(uploadSection.value) }
}
function dragEnter(event) {
  if (canReceive() && isDesktopImageDropEnabled() && hasImageInDataTransfer(event.dataTransfer)) { dragDepth++; dragActive.value = true }
}
function dragOver(event) {
  if (canReceive() && isDesktopImageDropEnabled() && hasImageInDataTransfer(event.dataTransfer)) { event.dataTransfer.dropEffect = 'copy'; dragActive.value = true }
}
function dragLeave() { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) dragActive.value = false }
function drop(event) {
  dragDepth = 0; dragActive.value = false
  if (!canReceive() || !isDesktopImageDropEnabled()) return
  const files = getImageFilesFromDataTransfer(event.dataTransfer)
  if (files.length) return addFiles(files)
  notify('请拖入图片文件。', 'error')
}
onMounted(() => window.addEventListener('paste', paste))
onBeforeUnmount(() => { alive = false; clear(false); window.removeEventListener('paste', paste) })
defineExpose({ clear })
</script>

<style scoped>
.inspection-photo-upload { min-width: 0; width: 100%; }
.photo-input { display: none; }
.photo-dropzone { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 22px 18px; border: 1px dashed #9bb8d1; border-radius: 16px; background: linear-gradient(180deg,#f1f7ff,#f8fafc); text-align: center; cursor: pointer; }
.photo-dropzone:hover,.photo-dropzone.drag-active { border-color: #2563eb; background: #eaf3ff; }
.photo-dropzone:focus-visible { outline: 2px solid #2563eb; outline-offset: 3px; }
.photo-dropzone.disabled { opacity: .65; cursor: default; }
.photo-dropzone strong { font-size: 16px; color: #173e5a; }
.photo-dropzone p { max-width: 580px; margin: 0; font-size: 13px; line-height: 1.7; color: #536b82; }
.photo-upload-icon { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; background: #e0edff; color: #2563eb; font-size: 24px; font-weight: 700; }
.photo-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.photo-actions button { min-height: 38px; padding: 8px 12px; border: 1px solid #b9cde2; border-radius: 10px; color: #294d70; background: white; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.photo-actions button.primary { background: #2563eb; border-color: #2563eb; color: white; }
button:disabled { opacity: .5; cursor: not-allowed; }
.photo-final-panel { display: flex; align-items: flex-start; gap: 16px; flex-wrap: wrap; padding: 14px; margin-top: 12px; border: 1px solid #dbe4ee; border-radius: 16px; background: white; }
.photo-final-preview { position: relative; display: block; overflow: hidden; flex: 0 0 148px; height: 140px; padding: 4px; border: 1px solid #dbe4ee; border-radius: 12px; background: #f8fafc; cursor: zoom-in; }
.photo-final-preview img,.photo-source img { display: block; width: 100%; height: 100%; object-fit: contain; }
.photo-final-preview img { position: absolute; inset: 4px; width: calc(100% - 8px); height: calc(100% - 8px); }
.photo-final-meta { display: flex; flex-direction: column; gap: 10px; flex: 1; min-width: 0; color: #244660; }
.photo-final-meta > span { overflow-wrap: anywhere; font-size: 13px; color: #64748b; }
.photo-source-strip { display: flex; flex-wrap: wrap; gap: 12px; padding-top: 4px; }
.photo-source { position: relative; width: 72px; height: 60px; border: 1px solid #dbe4ee; border-radius: 8px; background: #f8fafc; }
.photo-source button { position: absolute; right: -8px; top: -8px; width: 26px; height: 26px; border: 2px solid white; border-radius: 50%; background: #c73b43; color: white; cursor: pointer; }
@media(max-width:768px) { .photo-dropzone { padding: 18px 12px; } .photo-final-preview { flex-basis: 100%; width: 100%; height: 220px; } .photo-final-meta { flex-basis: 100%; } .photo-actions button { min-height: 44px; } }
</style>
