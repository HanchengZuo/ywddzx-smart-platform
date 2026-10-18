<template>
  <div class="help-page">
    <header class="page-header card">
      <div>
        <div class="eyebrow">公共功能 / HELP CENTER</div>
        <h2>帮助文档</h2>
        <p>按你要完成的任务查找操作说明，了解入口、步骤与注意事项。</p>
      </div>
      <div class="header-actions">
        <span class="reader-label">所有用户均可阅读</span
        ><button v-if="canEdit" class="button secondary" type="button" @click="toggleWorkspace">
          {{ workspace ? '返回用户阅读视图' : '文档维护' }}
        </button>
      </div>
    </header>
    <div v-if="message" class="page-message" role="status">{{ message }}</div>
    <div v-if="error" class="page-error" role="alert">
      {{ error }} <button type="button" @click="load">重试</button>
    </div>
    <div v-if="workspace" class="workspace-bar">
      <div>
        <strong>文档维护工作区</strong
        ><span>草稿仅编辑者可见，发布后才会更新所有用户看到的内容。</span>
      </div>
      <button class="button primary" type="button" @click="openEditor(null)">＋ 新增文档</button>
    </div>
    <section class="help-layout" :aria-busy="loading">
      <aside class="directory card" aria-label="帮助目录">
        <label class="search"
          ><span>搜索使用说明</span
          ><input v-model="keyword" type="search" placeholder="如：录入问题、整改、申诉"
        /></label>
        <div class="category-list" aria-label="按分类查阅">
          <button type="button" :class="{ active: !category }" @click="category = ''">
            全部文档 <small>{{ items.length }}</small></button
          ><button
            v-for="name in categories"
            :key="name"
            type="button"
            :class="{ active: category === name }"
            @click="category = name"
          >
            {{ name }}
            <small>{{ items.filter((item) => item.content.category === name).length }}</small>
          </button>
        </div>
        <nav aria-label="使用指南" class="article-list">
          <button
            v-for="item in filtered"
            :key="item.id"
            type="button"
            class="article-card"
            :class="{ active: selectedId === item.id }"
            :aria-current="selectedId === item.id ? 'page' : undefined"
            @click="select(item.id)"
          >
            <small
              >{{ item.content.category }}<em v-if="workspace">{{ helpStatus(item) }}</em></small
            ><strong>{{ item.content.title }}</strong>
            <p>{{ item.content.summary }}</p>
          </button>
        </nav>
        <p v-if="loading" class="empty" role="status">正在读取帮助内容…</p>
        <div v-else-if="!filtered.length" class="empty">
          <strong>没有找到相关文档</strong>
          <p>可更换关键词，或选择全部分类。</p>
          <button type="button" @click="clearFilters">清空筛选</button>
        </div>
        <div class="feedback-link">
          <strong>仍然没有解决？</strong>
          <p>提交操作步骤和截图，帮助我们改进系统与文档。</p>
          <RouterLink to="/feedback">前往系统反馈 →</RouterLink>
        </div>
      </aside>
      <section v-if="active" class="reader card" aria-labelledby="help-article-title">
        <header class="reader-head">
          <div>
            <small>{{ readingContent.category }}</small>
            <h3 id="help-article-title">{{ readingContent.title }}</h3>
            <p>{{ readingContent.summary }}</p>
          </div>
          <div v-if="workspace" class="edit-actions">
            <button class="button secondary" type="button" @click="openEditor(active)">
              编辑文档</button
            ><button
              v-if="active.published_at"
              class="button secondary"
              type="button"
              :disabled="changing"
              @click="setAvailability(active.archived ? 'restore' : 'archive')"
            >
              {{ active.archived ? '重新上架' : '下架文档' }}
            </button>
          </div>
        </header>
        <div class="article-meta">
          <span
            >{{ workspace ? '最后维护' : '最后发布' }}：{{ active.updated_by || '系统预置' }} ·
            {{ formatTime(active.updated_at) }}</span
          ><span v-if="workspace" class="status-chip">{{ helpStatus(active) }}</span>
        </div>
        <div v-if="workspace && active.has_draft" class="draft-notice">
          <span>{{
            showPublished
              ? '正在查看已发布内容，草稿尚未应用。'
              : '正在预览草稿，不会影响其他用户。'
          }}</span
          ><button
            v-if="active.published_content"
            type="button"
            @click="showPublished = !showPublished"
          >
            {{ showPublished ? '查看草稿' : '查看已发布版' }}
          </button>
        </div>
        <div v-if="workspace && active.archived" class="draft-notice">
          这篇文档已下架，普通用户看不到。重新发布或上架后恢复可见。
        </div>
        <div class="article-content">
          <HelpArticleBody
            :key="`${active.id}:${showPublished}`"
            :body="readingContent.body"
            :images="images"
          />
        </div>
        <details
          v-if="workspace"
          :key="`${active.id}:${active.revision}`"
          class="history"
          @toggle="loadHistory"
        >
          <summary>维护记录</summary>
          <p v-if="historyError" role="alert">{{ historyError }}</p>
          <p v-else-if="!history.length">暂无人工维护记录。</p>
          <ol v-else>
            <li v-for="(event, index) in history" :key="index">
              <strong>{{ actionNames[event.action] }}</strong> · 版本 {{ event.revision
              }}<span
                >{{ event.actor.real_name || event.actor.username }} ·
                {{ formatTime(event.created_at) }}</span
              >
            </li>
          </ol>
        </details>
      </section>
      <div v-else class="card reader-empty" role="status">
        {{ loading ? '正在准备帮助文档…' : '请选择一篇使用指南' }}
      </div>
    </section>
    <HelpDocumentEditor
      v-if="editing"
      :key="editorItem?.id || 'new'"
      :item="editorItem"
      :images="images"
      :categories="categories"
      @close="editing = false"
      @saved="saved"
    />
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import HelpArticleBody from '@/components/HelpArticleBody.vue'
import HelpDocumentEditor from '@/components/HelpDocumentEditor.vue'
import { createManualPreviewCache, HELP_IMAGE_CACHE } from '@/utils/manualLibrary'
import { filterHelpArticles, helpStatus } from '@/utils/helpContent'
const route = useRoute(),
  router = useRouter()
const items = ref([]),
  images = ref([]),
  selectedId = ref(''),
  keyword = ref(''),
  category = ref('')
const canEdit = ref(false),
  workspace = ref(false),
  loading = ref(true),
  error = ref(''),
  message = ref('')
const editing = ref(false),
  editorItem = ref(null),
  changing = ref(false),
  showPublished = ref(false)
const history = ref([]),
  historyError = ref('')
const active = computed(() => items.value.find((item) => item.id === selectedId.value))
const readingContent = computed(() =>
  showPublished.value && active.value?.published_content
    ? active.value.published_content
    : active.value?.content,
)
const categories = computed(() => [...new Set(items.value.map((item) => item.content.category))])
const filtered = computed(() => filterHelpArticles(items.value, keyword.value, category.value))
const actionNames = {
  draft: '保存草稿',
  publish: '发布文档',
  archive: '下架文档',
  restore: '重新上架',
}
function clearFilters() {
  keyword.value = ''
  category.value = ''
}
let disposed = false,
  requestVersion = 0,
  controller,
  historyController
const fetchBlob = async (url, { signal }) =>
  (await axios.get(url, { signal, responseType: 'blob' })).data
const cache = createManualPreviewCache(fetchBlob)
provide(HELP_IMAGE_CACHE, cache)
const formatTime = (value) =>
  value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : ''
async function load(preferred = '') {
  if (typeof preferred !== 'string') preferred = ''
  const version = ++requestVersion
  loading.value = true
  error.value = ''
  controller?.abort()
  controller = new AbortController()
  try {
    const { data } = await axios.get('/api/help-documents', {
      params: workspace.value ? { workspace: '1' } : {},
      signal: controller.signal,
    })
    if (disposed || version !== requestVersion) return
    resetReading()
    items.value = data.items
    images.value = data.attachments
    canEdit.value = data.can_edit
    const id = preferred || selectedId.value || route.query.document
    selectedId.value = data.items.some((item) => item.id === id) ? id : data.items[0]?.id || ''
    if (category.value && !categories.value.includes(category.value)) category.value = ''
  } catch (failure) {
    if (!disposed && version === requestVersion && !axios.isCancel(failure))
      error.value = failure.response?.data?.error || '帮助文档读取失败，请重试。'
  } finally {
    if (!disposed && version === requestVersion) loading.value = false
  }
}
function select(id) {
  selectedId.value = id
  router.replace({ query: { ...route.query, document: id } }).catch(() => {})
}
function toggleWorkspace() {
  workspace.value = !workspace.value
  message.value = ''
  load()
}
function openEditor(item) {
  if (canEdit.value) {
    editorItem.value = item
    editing.value = true
  }
}
async function saved(item, action) {
  editing.value = false
  message.value =
    action === 'publish'
      ? '已发布，所有用户现在可阅读最新内容。'
      : '草稿已保存，用户仍阅读上一次发布的内容。'
  await load(item.id)
}
async function setAvailability(action) {
  const item = active.value
  if (
    !item ||
    changing.value ||
    !window.confirm(
      action === 'archive'
        ? '下架后普通用户将无法查阅，确定下架这篇文档？'
        : '确定重新上架这篇文档的已发布内容？',
    )
  )
    return
  changing.value = true
  try {
    await axios.put(`/api/help-documents/${item.id}`, { action, revision: item.revision })
    if (!disposed) {
      message.value =
        action === 'archive' ? '文档已下架，内容与维护记录仍保留。' : '文档已重新上架。'
      await load(item.id)
    }
  } catch (failure) {
    if (!disposed) error.value = failure.response?.data?.error || '操作失败，请重试。'
  } finally {
    if (!disposed) changing.value = false
  }
}
function resetReading() {
  showPublished.value = false
  history.value = []
  historyError.value = ''
  historyController?.abort()
}
async function loadHistory(event) {
  if (!event.target.open || !active.value) return
  const id = active.value.id
  historyController?.abort()
  historyController = new AbortController()
  try {
    const { data } = await axios.get(`/api/help-documents/${id}/history`, {
      signal: historyController.signal,
    })
    if (!disposed && active.value?.id === id) history.value = data.items
  } catch (failure) {
    if (!disposed && active.value?.id === id && !axios.isCancel(failure))
      historyError.value = '维护记录加载失败，请关闭后重新打开。'
  }
}
watch(selectedId, resetReading)
watch(
  () => route.query.document,
  (id) => {
    if (items.value.some((item) => item.id === id)) selectedId.value = id
  },
)
onMounted(load)
onBeforeUnmount(() => {
  disposed = true
  requestVersion++
  controller?.abort()
  historyController?.abort()
  cache.dispose()
})
</script>
<style scoped>
.help-page {
  --blue: #2266a1;
  --ink: #17364f;
  --muted: #6b7f92;
  display: grid;
  gap: 18px;
  color: var(--ink);
}
.card {
  background: #fff;
  border: 1px solid #dce5ee;
  border-radius: 22px;
  min-width: 0;
  box-shadow: 0 12px 35px #17364f08;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 26px 28px;
  background: radial-gradient(ellipse at 100% 0, #e8f3fc, transparent 60%), #fff;
}
.eyebrow {
  font-size: 11px;
  color: var(--blue);
  letter-spacing: 0.1em;
  font-weight: 800;
}
h2 {
  font-size: 34px;
  margin: 10px 0;
}
.page-header p {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.8;
}
.header-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  flex-shrink: 0;
}
.reader-label {
  font-size: 12px;
  color: #42726e;
  background: #edf6f3;
  padding: 6px 11px;
  border-radius: 8px;
}
.button {
  padding: 10px 14px;
  border: 1px solid #d5e0eb;
  border-radius: 9px;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  background: #fff;
  color: var(--blue);
}
.button.primary {
  background: var(--blue);
  border-color: var(--blue);
  color: #fff;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.help-layout {
  display: grid;
  grid-template-columns: minmax(240px, 300px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.directory {
  padding: 20px 16px;
}
.search {
  display: grid;
  gap: 9px;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 17px;
}
.search input {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 12px;
  border: 1px solid #d6e2ec;
  border-radius: 10px;
  font: inherit;
  font-size: 13px;
  color: var(--ink);
  background: #f9fbfd;
}
.category-list {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.category-list button {
  background: #f4f7fa;
  color: #637e96;
  padding: 7px 9px;
  border: 1px solid transparent;
  border-radius: 8px;
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}
.category-list button.active {
  background: #eaf3fd;
  border-color: #c6def1;
  color: var(--blue);
}
.category-list small {
  margin-left: 5px;
  opacity: 0.65;
}
.article-list {
  display: grid;
  gap: 9px;
}
.article-card {
  width: 100%;
  font: inherit;
  color: inherit;
  background: #fff;
  border: 1px solid #e3eaf1;
  border-radius: 13px;
  padding: 15px;
  text-align: left;
  cursor: pointer;
}
.article-card.active {
  background: #f0f6fd;
  border-color: #9ebfdf;
  box-shadow: inset 3px 0 var(--blue);
}
.article-card:hover {
  border-color: #acc7e1;
}
.article-card small {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
  color: #6c8aa4;
  font-size: 11px;
  margin-bottom: 10px;
}
.article-card em {
  font-style: normal;
  color: #a07735;
}
.article-card strong {
  font-size: 14px;
  line-height: 1.6;
}
.article-card p {
  color: var(--muted);
  font-size: 12px;
  margin: 8px 0 0;
  line-height: 1.8;
}
.feedback-link {
  padding: 18px 4px 0;
  border-top: 1px solid #e6edf4;
  margin-top: 22px;
  font-size: 12px;
}
.feedback-link p {
  color: var(--muted);
  line-height: 1.8;
}
.feedback-link a {
  color: var(--blue);
  text-decoration: none;
}
.reader {
  padding: 26px 30px;
}
.reader-head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
}
.reader-head small {
  color: var(--blue);
  font-size: 12px;
}
.reader-head h3 {
  font-size: 26px;
  margin: 10px 0;
}
.reader-head p {
  font-size: 14px;
  color: var(--muted);
  line-height: 1.8;
  margin: 0;
}
.article-meta {
  font-size: 11px;
  color: #8191a1;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 16px 0 25px;
}
.status-chip {
  color: #a27a37;
}
.article-content {
  border-top: 1px solid #edf1f5;
  padding-top: 24px;
}
.workspace-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  background: #eef5fc;
  border: 1px solid #caddf0;
  padding: 15px 20px;
  border-radius: 12px;
}
.workspace-bar strong {
  display: block;
  font-size: 14px;
  margin-bottom: 5px;
}
.workspace-bar span {
  color: #6a8096;
  font-size: 12px;
}
.edit-actions {
  display: flex;
  gap: 8px;
}
.draft-notice {
  margin-bottom: 20px;
  background: #fffaec;
  color: #8d733e;
  padding: 12px;
  border-radius: 9px;
  font-size: 12px;
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.draft-notice button,
.page-error button,
.empty button {
  border: 0;
  background: transparent;
  font: inherit;
  color: var(--blue);
  cursor: pointer;
}
.history {
  margin-top: 25px;
  border-top: 1px solid #e7edf3;
  padding-top: 16px;
  font-size: 12px;
  color: var(--muted);
}
.history summary {
  cursor: pointer;
}
.history ol {
  padding-left: 20px;
}
.history li {
  margin: 13px 0;
}
.history li span {
  display: block;
  margin-top: 5px;
}
.page-error,
.page-message {
  padding: 13px 18px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.8;
}
.page-error {
  background: #fff0ec;
  color: #a64436;
}
.page-message {
  background: #eff8f4;
  color: #3a7865;
}
.empty {
  text-align: center;
  padding: 25px 8px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.8;
}
.reader-empty {
  min-height: 420px;
  display: grid;
  place-items: center;
  color: var(--muted);
}
:focus-visible {
  outline: 3px solid #7fb8e5;
  outline-offset: 3px;
}
@media (max-width: 900px) {
  .help-layout {
    grid-template-columns: 235px minmax(0, 1fr);
    gap: 14px;
  }
  .reader {
    padding: 24px 20px;
  }
}
@media (max-width: 760px) {
  .help-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .page-header {
    padding: 22px 20px;
    align-items: start;
    flex-wrap: wrap;
  }
  h2 {
    font-size: 28px;
  }
  .header-actions {
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
  }
  .directory {
    padding: 18px;
  }
  .article-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .article-card {
    padding: 12px;
  }
  .article-card p {
    display: none;
  }
  .reader-head h3 {
    font-size: 23px;
  }
  .feedback-link {
    display: none;
  }
  .reader {
    padding: 22px 18px;
  }
}
</style>
