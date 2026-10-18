<template>
  <div class="manual-page">
    <header class="manual-header card-surface">
      <div>
        <div class="page-kicker">公共功能 / HELP CENTER</div>
        <h2>系统说明书</h2>
        <p>从流程图开始，了解每一步由谁处理、如何流转，以及接下来该做什么。</p>
      </div>
      <div class="library-badge">
        <span>全员可阅</span><strong>{{ documents.length }} <small>份流程资料</small></strong>
      </div>
    </header>

    <div v-if="catalogError" class="manual-message error" role="alert">
      <span>{{ catalogError }}</span
      ><button type="button" @click="loadCatalog">重新加载</button>
    </div>
    <div v-if="downloadError" class="manual-message error" role="alert">{{ downloadError }}</div>

    <div class="manual-layout" :aria-busy="loadingCatalog">
      <aside class="manual-directory card-surface" aria-label="说明书目录">
        <div class="directory-heading">
          <h3>文档目录</h3>
          <span>{{ documents.length }} 份</span>
        </div>
        <label class="directory-search">
          <span class="sr-only">搜索说明书</span>
          <input v-model="keyword" type="search" placeholder="搜索标题、流程或关键词" />
        </label>
        <div v-if="loadingCatalog" class="directory-empty" role="status">正在读取说明书…</div>
        <div v-else-if="!filteredDocuments.length" class="directory-empty">
          <strong>没有找到相关资料</strong>
          <p>试试“审核”“整改”或“申诉”。</p>
          <button v-if="keyword" type="button" @click="keyword = ''">清空搜索</button>
        </div>
        <nav v-else class="document-list" aria-label="流程文档">
          <button
            v-for="item in filteredDocuments"
            :key="item.id"
            type="button"
            class="document-card"
            :class="{ active: selectedId === item.id }"
            :aria-current="selectedId === item.id ? 'page' : undefined"
            @click="selectDocument(item.id)"
          >
            <div class="document-card-top">
              <span :class="['file-mark', item.format.toLowerCase()]">{{ item.format }}</span
              ><span>{{ item.category }}</span>
            </div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.description }}</p>
            <div class="document-card-meta">
              <span>{{ item.pages }} 页 · {{ formatManualSize(item.file_size) }}</span
              ><span>{{ selectedId === item.id ? '正在阅读' : '查看文档 →' }}</span>
            </div>
          </button>
        </nav>
        <div class="directory-note">
          <strong>阅读提示</strong>
          <p>
            点击流程图可放大。大图支持滚轮缩放、拖动和双指操作；需要打印或留存时，可下载原始文件。
          </p>
        </div>
      </aside>

      <section
        v-if="activeDocument"
        class="manual-reader card-surface"
        aria-labelledby="reader-title"
      >
        <header class="reader-heading">
          <div>
            <div class="reader-category">{{ activeDocument.category }}</div>
            <h3 id="reader-title">{{ activeDocument.title }}</h3>
            <p>{{ activeDocument.filename }} · {{ formatManualSize(activeDocument.file_size) }}</p>
          </div>
          <div class="reader-actions">
            <button
              class="manual-button secondary"
              type="button"
              :disabled="!previewReady || !!previewError"
              @click="showZoom = true"
            >
              放大阅读
            </button>
            <button
              class="manual-button primary"
              type="button"
              :disabled="downloading"
              @click="downloadOriginal"
            >
              {{ downloading ? '正在下载…' : '下载原件' }}
            </button>
          </div>
        </header>
        <div class="document-context">
          <span v-for="tag in activeDocument.tags" :key="tag">{{ tag }}</span>
        </div>
        <p class="reader-notice">
          原件按上传内容保留；办理时限、照片要求及操作权限如有更新，请以系统当前配置和实际页面为准。
        </p>
        <div
          ref="readingArea"
          class="reading-area"
          :aria-busy="loadingPreview || (!previewReady && !previewError)"
        >
          <div
            v-if="loadingPreview || (!previewReady && !previewError)"
            class="preview-status"
            role="status"
          >
            <span class="loading-line"></span>正在加载高清预览…
          </div>
          <div v-if="previewError" class="preview-status error" role="alert">
            <strong>{{ previewError }}</strong>
            <p>也可以下载原件查看完整内容。</p>
            <button class="manual-button secondary" type="button" @click="retryPreview">
              重试预览
            </button>
          </div>
          <button
            v-if="previewUrl && !previewError"
            class="document-paper"
            :class="{ ready: previewReady }"
            type="button"
            :disabled="!previewReady"
            :aria-label="`放大阅读${activeDocument.title}`"
            @click="showZoom = true"
          >
            <img
              :key="previewUrl"
              :src="previewUrl"
              :alt="activeDocument.title"
              @load="previewLoaded"
              @error="previewFailed"
            />
          </button>
        </div>
        <footer class="reader-footer">
          <span>{{
            activeDocument.format === 'PDF'
              ? 'PDF 高清流程图预览，下载保留 PDF 原件'
              : '原始图片预览，完整展示不裁切'
          }}</span
          ><button type="button" @click="readingArea?.scrollTo({ top: 0, behavior: 'smooth' })">
            回到顶部 ↑
          </button>
        </footer>
      </section>
      <section v-else class="reader-placeholder card-surface" role="status">
        {{ loadingCatalog ? '准备阅读资料…' : '请从目录选择一份说明书' }}
      </section>
    </div>
    <InspectionPhotoPreview
      v-if="showZoom && previewReady && previewUrl"
      :url="previewUrl"
      :title="activeDocument?.title || '系统说明书'"
      @close="showZoom = false"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import InspectionPhotoPreview from '@/components/InspectionPhotoPreview.vue'
import {
  createManualPreviewCache,
  filterManualDocuments,
  formatManualSize,
} from '@/utils/manualLibrary'

const route = useRoute(),
  router = useRouter()
const documents = ref([]),
  selectedId = ref(''),
  keyword = ref('')
const loadingCatalog = ref(true),
  catalogError = ref(''),
  downloadError = ref('')
const loadingPreview = ref(false),
  previewReady = ref(false),
  previewError = ref(''),
  previewUrl = ref('')
const downloading = ref(false),
  showZoom = ref(false),
  readingArea = ref(null)
const activeDocument = computed(() => documents.value.find((item) => item.id === selectedId.value))
const filteredDocuments = computed(() => filterManualDocuments(documents.value, keyword.value))
let disposed = false,
  previewVersion = 0,
  catalogController,
  downloadController
const downloadUrls = new Map()
const fetchPreviewBlob = async (url, { signal }) =>
  (await axios.get(url, { signal, responseType: 'blob' })).data
let previewCache = createManualPreviewCache(fetchPreviewBlob)

async function loadCatalog() {
  loadingCatalog.value = true
  catalogError.value = ''
  catalogController?.abort()
  catalogController = new AbortController()
  try {
    const response = await axios.get('/api/system-manual/documents', {
      signal: catalogController.signal,
    })
    if (disposed) return
    if (!response.data?.success) throw new Error('Catalog unavailable')
    documents.value = response.data.items
    const requested = route.query.document
    selectedId.value = documents.value.some((item) => item.id === requested)
      ? requested
      : documents.value[0]?.id || ''
  } catch (error) {
    if (!disposed && !axios.isCancel(error)) catalogError.value = '说明书目录加载失败，请重试。'
  } finally {
    if (!disposed) loadingCatalog.value = false
  }
}

function selectDocument(id) {
  if (!documents.value.some((item) => item.id === id)) return
  selectedId.value = id
  router.replace({ query: { ...route.query, document: id } }).catch(() => {})
}

async function loadPreview() {
  const document = activeDocument.value
  const version = ++previewVersion
  showZoom.value = false
  previewUrl.value = ''
  previewReady.value = false
  previewError.value = ''
  loadingPreview.value = true
  if (!document) {
    loadingPreview.value = false
    return
  }
  await nextTick()
  readingArea.value?.scrollTo({ top: 0 })
  try {
    const url = await previewCache.load(document.id, document.preview_url)
    if (!disposed && version === previewVersion) previewUrl.value = url
  } catch (error) {
    if (!disposed && version === previewVersion && !axios.isCancel(error))
      previewError.value = '预览暂时无法加载。'
  } finally {
    if (!disposed && version === previewVersion) loadingPreview.value = false
  }
}

function previewLoaded(event) {
  if (event.target.getAttribute('src') === previewUrl.value) previewReady.value = true
}
function previewFailed(event) {
  if (event.target.getAttribute('src') === previewUrl.value)
    previewError.value = '预览图片读取失败。'
}
function retryPreview() {
  previewCache.dispose()
  previewCache = createManualPreviewCache(fetchPreviewBlob)
  loadPreview()
}

async function downloadOriginal() {
  const document = activeDocument.value
  if (!document || downloading.value) return
  downloading.value = true
  downloadError.value = ''
  downloadController = new AbortController()
  try {
    const { data } = await axios.get(document.download_url, {
      responseType: 'blob',
      signal: downloadController.signal,
    })
    if (disposed) return
    const url = URL.createObjectURL(data)
    const timer = window.setTimeout(() => {
      URL.revokeObjectURL(url)
      downloadUrls.delete(url)
    }, 60000)
    downloadUrls.set(url, timer)
    const link = window.document.createElement('a')
    link.href = url
    link.download = document.filename
    window.document.body.appendChild(link)
    link.click()
    link.remove()
  } catch (error) {
    if (!disposed && !axios.isCancel(error)) downloadError.value = '原件下载失败，请稍后重试。'
  } finally {
    if (!disposed) downloading.value = false
  }
}

watch(selectedId, loadPreview)
watch(
  () => route.query.document,
  (id) => {
    if (documents.value.some((item) => item.id === id)) selectedId.value = id
  },
)
onMounted(loadCatalog)
onBeforeUnmount(() => {
  disposed = true
  previewVersion++
  catalogController?.abort()
  downloadController?.abort()
  previewCache.dispose()
  for (const [url, timer] of downloadUrls) {
    window.clearTimeout(timer)
    URL.revokeObjectURL(url)
  }
  downloadUrls.clear()
})
</script>

<style scoped>
.manual-page {
  --manual-blue: #1d63a8;
  --manual-ink: #132f49;
  --manual-muted: #657c91;
  display: grid;
  gap: 20px;
  color: var(--manual-ink);
}
.card-surface {
  background: #fff;
  border: 1px solid #dbe4ee;
  border-radius: 24px;
  box-shadow: 0 18px 42px rgb(15 23 42 / 5%);
  min-width: 0;
}
.manual-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  padding: 26px 28px;
  background:
    radial-gradient(ellipse at 90% 0, #e4f1fc 0, transparent 50%),
    linear-gradient(120deg, #fff, #f8fbfe);
}
.page-kicker {
  color: var(--manual-blue);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.1em;
  margin-bottom: 10px;
}
.manual-header h2 {
  margin: 0;
  font-size: 34px;
  color: #0f172a;
}
.manual-header p {
  color: var(--manual-muted);
  font-size: 14px;
  line-height: 1.8;
  margin: 10px 0 0;
}
.library-badge {
  flex: 0 0 auto;
  padding: 12px 22px;
  border-left: 1px solid #cddfec;
  display: grid;
  gap: 6px;
}
.library-badge > span {
  font-size: 12px;
  color: var(--manual-blue);
}
.library-badge strong {
  font-size: 28px;
}
.library-badge small {
  font-size: 12px;
  color: var(--manual-muted);
  font-weight: 400;
}
.manual-layout {
  display: grid;
  grid-template-columns: minmax(250px, 310px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.manual-directory {
  padding: 22px 18px;
}
.directory-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.directory-heading h3 {
  margin: 0;
  font-size: 17px;
}
.directory-heading > span {
  color: var(--manual-muted);
  font-size: 12px;
}
.directory-search {
  display: block;
  margin-bottom: 18px;
}
.directory-search input {
  width: 100%;
  box-sizing: border-box;
  padding: 12px;
  min-height: 44px;
  border: 1px solid #d9e4ed;
  border-radius: 12px;
  color: var(--manual-ink);
  background: #f8fafc;
  font: inherit;
  font-size: 13px;
}
.document-list {
  display: grid;
  gap: 12px;
}
.document-card {
  text-align: left;
  font: inherit;
  color: inherit;
  width: 100%;
  padding: 17px;
  border: 1px solid #e2eaf1;
  background: #fff;
  border-radius: 16px;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s;
}
.document-card:hover {
  background: #f6faff;
  border-color: #92b8dd;
}
.document-card.active {
  background: #edf5fe;
  border-color: #8fb6dc;
  box-shadow: inset 3px 0 0 var(--manual-blue);
}
.document-card-top {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 12px;
  color: var(--manual-muted);
  font-size: 12px;
}
.file-mark {
  font-size: 10px;
  letter-spacing: 0.04em;
  background: #e5eef7;
  color: #315a7c;
  border: 1px solid #d0deec;
  padding: 5px 7px;
  border-radius: 6px;
  font-weight: 800;
}
.file-mark.png {
  background: #e9f5f0;
  color: #2b7361;
  border-color: #cce5d8;
}
.document-card > strong {
  font-size: 16px;
}
.document-card p {
  color: var(--manual-muted);
  font-size: 12px;
  line-height: 1.9;
  margin: 9px 0 16px;
}
.document-card-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: var(--manual-muted);
}
.document-card-meta span:last-child {
  color: var(--manual-blue);
}
.directory-note {
  margin-top: 22px;
  padding: 16px 4px 0;
  border-top: 1px solid #e7edf2;
  font-size: 12px;
}
.directory-note p {
  color: var(--manual-muted);
  line-height: 1.9;
  margin-bottom: 0;
}
.manual-reader {
  overflow: hidden;
}
.reader-heading {
  padding: 22px 24px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}
.reader-category {
  font-size: 11px;
  color: var(--manual-blue);
  margin-bottom: 6px;
}
.reader-heading h3 {
  font-size: 22px;
  margin: 0;
}
.reader-heading p {
  margin: 8px 0 0;
  color: var(--manual-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.reader-actions {
  display: flex;
  gap: 8px;
}
.manual-button {
  font: inherit;
  font-size: 13px;
  border-radius: 10px;
  padding: 10px 14px;
  min-height: 42px;
  cursor: pointer;
  font-weight: 700;
}
.manual-button.primary {
  background: var(--manual-blue);
  color: #fff;
  border: 1px solid var(--manual-blue);
}
.manual-button.secondary {
  background: #fff;
  color: var(--manual-blue);
  border: 1px solid #ceddeb;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
button:focus-visible,
input:focus-visible {
  outline: 3px solid #72b5e5;
  outline-offset: 3px;
}
.document-context {
  padding: 0 24px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.document-context span {
  background: #f2f6fa;
  color: #5a7185;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 11px;
}
.reader-notice {
  margin: 16px 24px;
  color: #7b6a46;
  background: #fffbf0;
  border-left: 3px solid #d9b56a;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.8;
}
.reading-area {
  height: clamp(460px, 76vh, 1080px);
  overflow: auto;
  background: #edf1f5;
  border-top: 1px solid #dfe7ef;
  padding: 22px;
  position: relative;
  box-sizing: border-box;
  scrollbar-gutter: stable;
}
.document-paper {
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  background: #fff;
  box-shadow: 0 6px 22px rgb(29 49 67 / 10%);
  cursor: zoom-in;
  opacity: 0;
}
.document-paper.ready {
  opacity: 1;
}
.document-paper img {
  display: block;
  width: 100%;
  height: auto;
  object-fit: contain;
}
.preview-status {
  display: flex;
  min-height: 270px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 14px;
  font-size: 13px;
  color: var(--manual-muted);
  text-align: center;
}
.preview-status p {
  margin: 0;
}
.preview-status.error {
  color: #a94332;
}
.loading-line {
  width: 80px;
  height: 3px;
  border-radius: 2px;
  background: linear-gradient(90deg, #dbe6f0, #3685c0, #dbe6f0);
  background-size: 200%;
  animation: reading-load 1.2s linear infinite;
}
.reader-footer {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding: 14px 24px;
  color: var(--manual-muted);
  font-size: 11px;
}
.reader-footer button,
.directory-empty button,
.manual-message button {
  border: 0;
  background: transparent;
  color: var(--manual-blue);
  font: inherit;
  cursor: pointer;
  min-height: 36px;
}
.directory-empty {
  padding: 25px 10px;
  font-size: 13px;
  color: var(--manual-muted);
  text-align: center;
  line-height: 1.8;
}
.directory-empty strong {
  color: var(--manual-ink);
}
.reader-placeholder {
  display: grid;
  place-items: center;
  min-height: 450px;
  color: var(--manual-muted);
}
.manual-message {
  border: 1px solid #efcfc9;
  border-radius: 12px;
  padding: 12px 16px;
  background: #fff3f0;
  color: #a94332;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
  white-space: nowrap;
}
@keyframes reading-load {
  to {
    background-position: -200%;
  }
}
@media (prefers-reduced-motion: reduce) {
  .loading-line {
    animation: none;
  }
  .document-card {
    transition: none;
  }
}
@media (max-width: 1050px) {
  .manual-layout {
    grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
    gap: 14px;
  }
  .reader-heading {
    padding: 20px;
  }
}
@media (max-width: 760px) {
  .manual-page {
    gap: 14px;
  }
  .manual-header {
    padding: 22px 20px;
    align-items: flex-start;
  }
  .manual-header h2 {
    font-size: 28px;
  }
  .library-badge {
    padding: 4px 0 4px 14px;
  }
  .library-badge strong {
    font-size: 23px;
  }
  .library-badge small {
    display: block;
    font-size: 10px;
  }
  .manual-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .manual-directory {
    padding: 18px;
  }
  .directory-heading {
    margin-bottom: 12px;
  }
  .directory-search {
    margin-bottom: 12px;
  }
  .document-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .document-card {
    padding: 12px;
  }
  .document-card > strong {
    font-size: 14px;
  }
  .document-card p,
  .document-card-meta span:first-child,
  .directory-note {
    display: none;
  }
  .document-card-meta {
    margin-top: 12px;
  }
  .document-card-top {
    font-size: 10px;
  }
  .reader-heading h3 {
    font-size: 20px;
  }
  .reader-actions {
    width: 100%;
  }
  .reader-actions button {
    flex: 1;
  }
  .document-context {
    padding: 0 20px;
  }
  .reader-notice {
    margin: 14px 20px;
  }
  .reading-area {
    padding: 10px;
    height: 66vh;
    min-height: 390px;
  }
  .reader-footer {
    padding: 12px 18px;
  }
  .page-kicker {
    font-size: 10px;
  }
}
</style>
