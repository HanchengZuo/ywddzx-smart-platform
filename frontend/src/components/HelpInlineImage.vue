<template>
  <figure ref="figure" class="help-inline-figure" :style="{ '--figure-width': `${width}%` }">
    <p v-if="!asset" class="image-status" role="alert">此流程图暂不可用，请联系文档维护人。</p>
    <template v-else>
      <p v-if="error" class="image-status" role="alert">
        {{ error }} <button type="button" @click="retry">重新加载</button>
      </p>
      <p v-else-if="!ready" class="image-status" role="status">正在加载流程图…</p>
      <button
        v-if="url && !error"
        class="figure-image"
        type="button"
        :disabled="!ready"
        :aria-label="`放大查看${caption || asset.title}`"
        @click="zoom = true"
      >
        <img
          :key="url"
          :src="url"
          :alt="caption || asset.title"
          @load="imageLoaded"
          @error="imageFailed"
        />
      </button>
      <figcaption>
        <span>{{ caption || asset.title }}</span>
        <div class="figure-tools">
          <button type="button" :disabled="!ready || !!error" @click="zoom = true">放大查看</button
          ><button v-if="allowDownload" type="button" :disabled="downloading" @click="download">
            {{ downloading ? '下载中…' : asset.format === 'PDF' ? '下载原始PDF' : '下载原图' }}
          </button>
        </div>
      </figcaption>
      <p v-if="downloadError" class="image-status" role="alert">{{ downloadError }}</p>
    </template>
    <InspectionPhotoPreview
      v-if="zoom && ready && url"
      :url="url"
      :title="caption || asset?.title || '流程图'"
      :target="figure?.closest('dialog[open]') || null"
      @close="zoom = false"
    />
  </figure>
</template>
<script setup>
import { inject, onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
import InspectionPhotoPreview from './InspectionPhotoPreview.vue'
import { createManualPreviewCache, HELP_IMAGE_CACHE } from '@/utils/manualLibrary'
const props = defineProps({
  asset: { type: Object, default: null },
  caption: { type: String, default: '' },
  width: { type: Number, default: 100 },
  allowDownload: { type: Boolean, default: true },
})
const injectedCache = inject(HELP_IMAGE_CACHE, null)
const cache =
  injectedCache ||
  createManualPreviewCache(
    async (url, { signal }) => (await axios.get(url, { responseType: 'blob', signal })).data,
  )
const figure = ref(null),
  url = ref(''),
  ready = ref(false),
  error = ref(''),
  zoom = ref(false),
  downloading = ref(false),
  downloadError = ref('')
const downloadUrls = new Map()
let disposed = false,
  version = 0,
  controller
async function load() {
  const current = ++version,
    asset = props.asset
  url.value = ''
  ready.value = false
  error.value = ''
  zoom.value = false
  if (!asset) return
  try {
    const loaded = await cache.load(asset.id, asset.preview_url)
    if (!disposed && current === version) url.value = loaded
  } catch (failure) {
    if (!disposed && current === version && !axios.isCancel(failure))
      error.value = '流程图加载失败。'
  }
}
function retry() {
  if (props.asset) cache.invalidate(props.asset.id)
  load()
}
function imageLoaded(event) {
  if (event.target.getAttribute('src') === url.value) ready.value = true
}
function imageFailed(event) {
  if (event.target.getAttribute('src') === url.value) error.value = '图片读取失败。'
}
async function download() {
  if (downloading.value || !props.asset) return
  const asset = props.asset
  downloading.value = true
  downloadError.value = ''
  controller = new AbortController()
  try {
    const { data } = await axios.get(asset.download_url, {
      responseType: 'blob',
      signal: controller.signal,
    })
    if (disposed) return
    const address = URL.createObjectURL(data),
      timer = setTimeout(() => {
        URL.revokeObjectURL(address)
        downloadUrls.delete(address)
      }, 60000)
    downloadUrls.set(address, timer)
    const link = document.createElement('a')
    link.href = address
    link.download = asset.filename
    document.body.appendChild(link)
    link.click()
    link.remove()
  } catch (failure) {
    if (!disposed && !axios.isCancel(failure)) downloadError.value = '原图下载失败，请稍后重试。'
  } finally {
    if (!disposed) downloading.value = false
  }
}
watch(() => props.asset?.id, load, { immediate: true })
onBeforeUnmount(() => {
  disposed = true
  version++
  controller?.abort()
  if (!injectedCache) cache.dispose()
  for (const [address, timer] of downloadUrls) {
    clearTimeout(timer)
    URL.revokeObjectURL(address)
  }
})
</script>
<style scoped>
.help-inline-figure {
  width: var(--figure-width, 100%);
  max-width: 100%;
  margin: 24px auto;
}
.figure-image {
  width: 100%;
  display: block;
  padding: 0;
  background: #fff;
  border: 1px solid #e0e8ef;
  border-radius: 8px;
  cursor: zoom-in;
  overflow: hidden;
}
.figure-image img {
  display: block;
  width: 100%;
  height: auto;
  object-fit: contain;
}
figcaption {
  text-align: center;
  font-size: 12px;
  line-height: 1.8;
  color: #718499;
  padding: 8px 4px 0;
  overflow-wrap: anywhere;
}
.figure-tools {
  display: inline-flex;
  gap: 12px;
  margin-left: 12px;
  flex-wrap: wrap;
}
.figure-tools button,
.image-status button {
  font: inherit;
  border: 0;
  background: none;
  color: #3273aa;
  padding: 2px 0;
  cursor: pointer;
}
button:disabled {
  cursor: default;
  opacity: 0.5;
}
.image-status {
  font-size: 12px;
  color: #70869a;
  padding: 14px;
  text-align: center;
  background: #f4f7fb;
  border-radius: 8px;
}
button:focus-visible {
  outline: 3px solid #82b9e4;
  outline-offset: 3px;
}
@media (max-width: 760px) {
  .help-inline-figure {
    width: 100%;
  }
}
</style>
