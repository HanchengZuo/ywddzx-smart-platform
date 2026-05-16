<template>
  <div v-if="hasPermission" class="page-shell originals-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">外部规范库</div>
        <h2>检查表原件库</h2>
        <p class="page-desc">集中查看上海公司事业部检查表 PDF 原件，并追溯由检查表拆解形成的外部规范列表。</p>
      </div>
      <div class="header-badges">
        <span class="status-pill info">检查表 {{ checklistItems.length }}</span>
        <span class="status-pill success">已上传 {{ uploadedCount }}</span>
        <span v-if="canManage && !isMobileView" class="status-pill manager">可维护原件</span>
      </div>
    </div>

    <div v-if="pageError" class="message-card error">{{ pageError }}</div>
    <div v-if="actionMessage" :class="['message-card', actionMessageType]">{{ actionMessage }}</div>

    <div class="content-grid">
      <section class="list-card card-surface">
        <div class="section-head">
          <div>
            <div class="section-kicker">检查表目录</div>
            <h3>共 {{ checklistItems.length }} 张检查表</h3>
          </div>
        </div>

        <div class="checklist-list">
          <article v-for="item in checklistItems" :key="item.inspection_table_id" class="checklist-card"
            :class="{ active: activeItem?.inspection_table_id === item.inspection_table_id }"
            @click="selectItem(item)">
            <div class="checklist-card-main">
              <div>
                <h4>{{ item.table_name }}</h4>
                <p>{{ item.description || '暂无检查表说明。' }}</p>
              </div>
              <span :class="['status-pill', item.has_pdf ? 'success' : 'neutral']">
                {{ item.has_pdf ? '已上传' : '待上传' }}
              </span>
            </div>

            <div class="card-meta-grid">
              <div>
                <span>最后更新</span>
                <strong>{{ item.updated_at || '暂未上传' }}</strong>
              </div>
              <div>
                <span>文件大小</span>
                <strong>{{ formatFileSize(item.file_size) }}</strong>
              </div>
              <div>
                <span>外部规范</span>
                <strong>{{ getExternalStandardsByTable(item.inspection_table_id).length }} 条</strong>
              </div>
            </div>

            <div class="checklist-card-footer">
              <button class="btn btn-secondary btn-compact" type="button" @click.stop="handlePreviewClick(item)">
                查看预览
              </button>
              <label v-if="canManage && !isMobileView" class="btn btn-primary btn-compact upload-label"
                :class="{ disabled: uploadingId === item.inspection_table_id }" @click.stop>
                <input type="file" accept="application/pdf,.pdf" :disabled="uploadingId === item.inspection_table_id"
                  @change="handlePdfChange(item, $event)" />
                {{ uploadingId === item.inspection_table_id ? '上传中...' : item.has_pdf ? '上传新版' : '上传PDF' }}
              </label>
            </div>

            <div v-if="isMobileView && activeItem?.inspection_table_id === item.inspection_table_id"
              class="mobile-external-section">
              <div class="external-section-head">
                <strong>外部规范列表</strong>
                <span>{{ getExternalStandardsByTable(item.inspection_table_id).length }} 条</span>
              </div>
              <article v-for="standard in getPaginatedExternalStandards(item.inspection_table_id)"
                :key="standard.external_standard_id" class="external-standard-card">
                <div class="external-standard-top">
                  <span>外部规范ID {{ standard.external_standard_id }}</span>
                  <em :class="{ linked: standard.linked_internal_standard_id }">
                    {{ standard.linked_internal_standard_id ? `内部 ${standard.linked_internal_standard_id}` : '未关联内部规范' }}
                  </em>
                </div>
                <p>{{ standard.standard_detail_text || '暂无外部规范详情。' }}</p>
              </article>
              <div v-if="getExternalTotalPage(item.inspection_table_id) > 1" class="pagination-bar mobile-standard-pager">
                <button class="btn btn-secondary pagination-btn" type="button"
                  :disabled="getStandardPage(item.inspection_table_id) <= 1"
                  @click.stop="setStandardPage(item.inspection_table_id, getStandardPage(item.inspection_table_id) - 1)">
                  上一页
                </button>
                <div class="pagination-page-list scrollable-pages" @click.stop>
                  <button v-for="pageNo in getAllPageNumbers(getExternalTotalPage(item.inspection_table_id))" :key="pageNo"
                    class="pagination-page-btn" :class="{ active: pageNo === getStandardPage(item.inspection_table_id) }"
                    type="button" @click="setStandardPage(item.inspection_table_id, pageNo)">
                    {{ pageNo }}
                  </button>
                </div>
                <button class="btn btn-secondary pagination-btn" type="button"
                  :disabled="getStandardPage(item.inspection_table_id) >= getExternalTotalPage(item.inspection_table_id)"
                  @click.stop="setStandardPage(item.inspection_table_id, getStandardPage(item.inspection_table_id) + 1)">
                  下一页
                </button>
              </div>
            </div>
          </article>

          <div v-if="!loading && checklistItems.length === 0" class="empty-block">
            暂无可展示的检查表。
          </div>
          <div v-if="loading" class="empty-block">正在加载检查表原件库...</div>
        </div>
      </section>

      <section v-if="!isMobileView" class="preview-card card-surface">
        <template v-if="activeItem">
          <div class="preview-header">
            <div>
              <div class="section-kicker">PDF 原件预览</div>
              <h3>{{ activeItem.table_name }}</h3>
              <p>{{ activeItem.original_filename || '当前检查表暂未上传 PDF 原件。' }}</p>
            </div>
            <div class="preview-actions">
              <a v-if="activeItem.has_pdf" class="btn btn-secondary" :href="activeItem.file_url" target="_blank"
                rel="noopener">
                新窗口打开
              </a>
            </div>
          </div>

          <div class="preview-meta-grid">
            <div class="meta-item">
              <span>最后更新日期</span>
              <strong>{{ activeItem.updated_at || '暂未上传' }}</strong>
            </div>
            <div class="meta-item">
              <span>上传人</span>
              <strong>{{ activeItem.uploaded_by_real_name || activeItem.uploaded_by_username || '-' }}</strong>
            </div>
            <div class="meta-item">
              <span>文件大小</span>
              <strong>{{ formatFileSize(activeItem.file_size) }}</strong>
            </div>
          </div>

          <div v-if="activeItem.has_pdf" class="pdf-preview-shell">
            <iframe :src="activeItem.file_url" title="检查表 PDF 原件预览"></iframe>
          </div>
          <div v-else class="empty-preview">
            <div class="empty-icon">PDF</div>
            <div class="empty-title">还没有上传原始 PDF</div>
            <p>上传后，所有用户都可以在这里查看该检查表原件；移动端也可以直接打开预览。</p>
          </div>

          <div class="external-section">
            <div class="external-section-head">
              <div>
                <div class="section-kicker">外部规范列表</div>
                <h3>由本检查表拆解得到的外部规范</h3>
              </div>
              <span class="status-pill info">{{ filteredActiveExternalStandards.length }} / {{ activeExternalStandards.length }} 条</span>
            </div>

            <div v-if="activeExternalStandards.length" class="external-filter-panel">
              <label class="external-filter-item external-filter-keyword">
                <span>关键词</span>
                <input v-model.trim="desktopStandardFilters.keyword" type="search" placeholder="搜索外部规范ID或规范内容"
                  @input="resetStandardPage(activeItem.inspection_table_id)" />
              </label>
              <label v-for="field in activeFilterFields" :key="field.field_key" class="external-filter-item">
                <span>{{ field.field_label }}</span>
                <select v-model="desktopStandardFilters.fieldValues[field.field_key]"
                  @change="resetStandardPage(activeItem.inspection_table_id)">
                  <option value="">全部</option>
                  <option v-for="value in getFieldOptionValues(field.field_key)" :key="value" :value="value">
                    {{ value }}
                  </option>
                </select>
              </label>
            </div>

            <div v-if="filteredActiveExternalStandards.length" class="external-standard-list">
              <article v-for="standard in paginatedActiveExternalStandards" :key="standard.external_standard_id"
                class="external-standard-card">
                <div class="external-standard-top">
                  <span>外部规范ID {{ standard.external_standard_id }}</span>
                  <em :class="{ linked: standard.linked_internal_standard_id }">
                    {{ standard.linked_internal_standard_id ? `已关联内部规范 ${standard.linked_internal_standard_id}` : '未关联内部规范' }}
                  </em>
                </div>
                <p>{{ standard.standard_detail_text || '暂无外部规范详情。' }}</p>
              </article>

              <div class="pagination-bar">
                <div class="pagination-summary">
                  共 {{ filteredActiveExternalStandards.length }} 条外部规范，第 {{ activeExternalPage }} / {{ activeExternalTotalPage }} 页
                </div>
                <div class="pagination-controls">
                  <button class="btn btn-secondary pagination-btn" type="button"
                    :disabled="activeExternalPage <= 1"
                    @click="setStandardPage(activeItem.inspection_table_id, activeExternalPage - 1)">
                    上一页
                  </button>
                  <div class="pagination-page-list scrollable-pages">
                    <button v-for="pageNo in getAllPageNumbers(activeExternalTotalPage)" :key="pageNo"
                      class="pagination-page-btn" :class="{ active: pageNo === activeExternalPage }"
                      type="button" @click="setStandardPage(activeItem.inspection_table_id, pageNo)">
                      {{ pageNo }}
                    </button>
                  </div>
                  <button class="btn btn-secondary pagination-btn" type="button"
                    :disabled="activeExternalPage >= activeExternalTotalPage"
                    @click="setStandardPage(activeItem.inspection_table_id, activeExternalPage + 1)">
                    下一页
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="empty-external">
              {{ activeExternalStandards.length ? '没有符合筛选条件的外部规范。' : '这张检查表暂未维护外部规范数据。' }}
            </div>
          </div>
        </template>

        <div v-else class="empty-preview">
          <div class="empty-icon">表</div>
          <div class="empty-title">暂无检查表</div>
          <p>请确认数据库中已配置并启用检查表。</p>
        </div>
      </section>
    </div>
  </div>
  <div v-else class="card-surface permission-card">
    <div class="permission-icon">!</div>
    <div class="permission-title">无权限访问</div>
    <div class="permission-desc">当前账号无权访问检查表原件库。</div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

const currentUserId = ref(localStorage.getItem('user_id') || '')
const currentUsername = ref(localStorage.getItem('username') || '')
const currentRole = localStorage.getItem('user_role') || ''
let localPermissions = {}
try {
  localPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch (error) {
  localPermissions = {}
}
const loading = ref(false)
const uploadingId = ref(null)
const pageError = ref('')
const actionMessage = ref('')
const actionMessageType = ref('info')
const hasPermission = currentRole === 'root' || Boolean(localPermissions.view_checklist_originals)
const canManage = ref(currentRole === 'root' || Boolean(localPermissions.manage_checklist_originals))
const checklistItems = ref([])
const externalStandards = ref([])
const activeTableId = ref('')
const fieldMap = ref({})
const standardPageByTable = ref({})
const STANDARD_PAGE_SIZE = 5
const desktopStandardFilters = reactive({
  keyword: '',
  fieldValues: {}
})
let actionMessageTimer = null

const detectMobileViewport = () => {
  const ua = navigator.userAgent || ''
  const mobileUa = /Android|iPhone|iPad|iPod|Mobile/i.test(ua)
  const coarsePointer = window.matchMedia ? window.matchMedia('(pointer: coarse)').matches : false
  return window.innerWidth <= 768 || (mobileUa && coarsePointer)
}

const isMobileView = ref(detectMobileViewport())

const uploadedCount = computed(() => checklistItems.value.filter((item) => item.has_pdf).length)

const activeItem = computed(() => {
  return checklistItems.value.find((item) => String(item.inspection_table_id) === String(activeTableId.value)) ||
    checklistItems.value[0] ||
    null
})

const activeExternalStandards = computed(() => getExternalStandardsByTable(activeItem.value?.inspection_table_id))

const activeFilterFields = computed(() => {
  return (fieldMap.value[String(activeItem.value?.inspection_table_id || '')] || [])
    .filter((field) => field.is_filterable)
})

const filteredActiveExternalStandards = computed(() => {
  const keyword = String(desktopStandardFilters.keyword || '').trim().toLowerCase()
  return activeExternalStandards.value.filter((item) => {
    const keywordMatched = !keyword || [
      item.external_standard_id,
      item.standard_detail_text,
      item.linked_internal_standard_id
    ].join(' ').toLowerCase().includes(keyword)
    if (!keywordMatched) return false

    return activeFilterFields.value.every((field) => {
      const filterValue = String(desktopStandardFilters.fieldValues[field.field_key] || '').trim()
      if (!filterValue) return true
      return String(item[field.field_key] ?? '').trim() === filterValue
    })
  })
})

const activeExternalTotalPage = computed(() => {
  return Math.max(1, Math.ceil(filteredActiveExternalStandards.value.length / STANDARD_PAGE_SIZE))
})

const activeExternalPage = computed(() => {
  return getStandardPage(activeItem.value?.inspection_table_id, activeExternalTotalPage.value)
})

const paginatedActiveExternalStandards = computed(() => {
  const tableId = activeItem.value?.inspection_table_id
  const start = (activeExternalPage.value - 1) * STANDARD_PAGE_SIZE
  return filteredActiveExternalStandards.value.slice(start, start + STANDARD_PAGE_SIZE)
})

const getExternalStandardsByTable = (inspectionTableId) => {
  return externalStandards.value.filter((item) => {
    return String(item.inspection_table_id) === String(inspectionTableId || '')
  })
}

const getStandardPage = (inspectionTableId, totalPage = null) => {
  const tableKey = String(inspectionTableId || '')
  const page = Number(standardPageByTable.value[tableKey] || 1)
  const maxPage = Number(totalPage || getExternalTotalPage(inspectionTableId) || 1)
  return Math.min(Math.max(page, 1), maxPage)
}

const setStandardPage = (inspectionTableId, pageValue) => {
  const tableKey = String(inspectionTableId || '')
  if (!tableKey) return
  const totalPage = getExternalTotalPage(inspectionTableId)
  standardPageByTable.value = {
    ...standardPageByTable.value,
    [tableKey]: Math.min(Math.max(Number(pageValue || 1), 1), totalPage)
  }
}

const resetStandardPage = (inspectionTableId) => {
  setStandardPage(inspectionTableId, 1)
}

const getExternalTotalPage = (inspectionTableId) => {
  const list = getExternalStandardsByTable(inspectionTableId)
  return Math.max(1, Math.ceil(list.length / STANDARD_PAGE_SIZE))
}

const getPaginatedExternalStandards = (inspectionTableId) => {
  const list = getExternalStandardsByTable(inspectionTableId)
  const page = getStandardPage(inspectionTableId)
  const start = (page - 1) * STANDARD_PAGE_SIZE
  return list.slice(start, start + STANDARD_PAGE_SIZE)
}

const getAllPageNumbers = (totalPage) => {
  return Array.from({ length: Math.max(1, Number(totalPage || 1)) }, (_, index) => index + 1)
}

const getFieldOptionValues = (fieldKey) => {
  return [...new Set(activeExternalStandards.value
    .map((item) => String(item[fieldKey] ?? '').trim())
    .filter(Boolean))]
}

const setActionMessage = (message, type = 'info') => {
  if (actionMessageTimer) {
    window.clearTimeout(actionMessageTimer)
    actionMessageTimer = null
  }

  actionMessage.value = message
  actionMessageType.value = type
  if (!message) return

  actionMessageTimer = window.setTimeout(() => {
    actionMessage.value = ''
    actionMessageTimer = null
  }, 2600)
}

const formatFileSize = (size) => {
  const bytes = Number(size || 0)
  if (!bytes) return '-'
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

const selectItem = (item) => {
  activeTableId.value = String(item.inspection_table_id)
  fetchFieldsForTable(item.inspection_table_id)
}

const handlePreviewClick = (item) => {
  if (isMobileView.value) {
    if (!item?.has_pdf || !item?.file_url) {
      setActionMessage('当前检查表暂未上传 PDF 原件。', 'error')
      return
    }
    window.open(item.file_url, '_blank', 'noopener')
    return
  }

  selectItem(item)
}

const fetchOriginals = async () => {
  if (!hasPermission) return

  if (!currentUserId.value) {
    pageError.value = '缺少当前用户信息，请重新登录。'
    return
  }

  try {
    loading.value = true
    pageError.value = ''
    const response = await axios.get('/api/inspection-table-originals', {
      params: {
        user_id: currentUserId.value,
        _ts: Date.now()
      }
    })
    checklistItems.value = response.data?.items || []
    canManage.value = Boolean(response.data?.can_manage)

    if (!checklistItems.value.some((item) => String(item.inspection_table_id) === String(activeTableId.value))) {
      activeTableId.value = checklistItems.value[0]?.inspection_table_id
        ? String(checklistItems.value[0].inspection_table_id)
        : ''
    }
  } catch (error) {
    pageError.value = error?.response?.data?.error || '检查表原件库加载失败，请稍后重试。'
    setActionMessage(pageError.value, 'error')
  } finally {
    loading.value = false
  }
}

const fetchExternalStandards = async () => {
  const response = await axios.get('/api/external-standards', {
    params: { _ts: Date.now() }
  })
  externalStandards.value = response.data?.items || []
}

const fetchFieldsForTable = async (inspectionTableId) => {
  const tableKey = String(inspectionTableId || '')
  if (!tableKey || fieldMap.value[tableKey]) return
  try {
    const response = await axios.get('/api/inspection-table-fields', {
      params: { table_id: tableKey, _ts: Date.now() }
    })
    fieldMap.value = {
      ...fieldMap.value,
      [tableKey]: response.data || []
    }
  } catch (error) {
    fieldMap.value = {
      ...fieldMap.value,
      [tableKey]: []
    }
  }
}

const handlePdfChange = async (item, event) => {
  const input = event.target
  const file = input.files?.[0]
  input.value = ''
  if (!file || !item?.inspection_table_id) return

  if (!file.name.toLowerCase().endsWith('.pdf')) {
    setActionMessage('只能上传 PDF 文件。', 'error')
    return
  }

  if (file.size > 50 * 1024 * 1024) {
    setActionMessage('PDF 文件不能超过 50MB。', 'error')
    return
  }

  try {
    uploadingId.value = item.inspection_table_id
    pageError.value = ''
    const formData = new FormData()
    formData.append('user_id', currentUserId.value)
    formData.append('pdf', file)
    const response = await axios.post(
      `/api/inspection-table-originals/${item.inspection_table_id}/pdf`,
      formData
    )
    setActionMessage(response.data?.message || '检查表原件 PDF 已更新。', 'success')
    await fetchOriginals()
    activeTableId.value = String(item.inspection_table_id)
  } catch (error) {
    const message = error?.response?.data?.error || 'PDF 上传失败，请稍后重试。'
    pageError.value = message
    setActionMessage(message, 'error')
  } finally {
    uploadingId.value = null
  }
}

const handleViewportResize = () => {
  isMobileView.value = detectMobileViewport()
}

onMounted(() => {
  window.addEventListener('resize', handleViewportResize)
  Promise.all([fetchOriginals(), fetchExternalStandards()]).catch((error) => {
    setActionMessage(error?.response?.data?.error || '外部规范库加载失败。', 'error')
  })
})

watch(activeItem, (item) => {
  if (item?.inspection_table_id) {
    fetchFieldsForTable(item.inspection_table_id)
    resetStandardPage(item.inspection_table_id)
  }
}, { immediate: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleViewportResize)
  if (actionMessageTimer) {
    window.clearTimeout(actionMessageTimer)
  }
})
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-surface {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dbe4ee;
  border-radius: 24px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
}

.page-header {
  padding: 26px 28px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.page-kicker,
.section-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 12px;
}

.page-header h2,
.preview-header h3,
.section-head h3 {
  margin: 0;
  color: #0f172a;
}

.page-header h2 {
  font-size: 34px;
}

.page-desc,
.preview-header p,
.checklist-card p,
.empty-preview p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
}

.header-badges {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  padding: 5px 11px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.status-pill.info {
  background: #eff6ff;
  color: #1d4ed8;
}

.status-pill.success {
  background: #ecfdf5;
  color: #15803d;
}

.status-pill.neutral {
  background: #f1f5f9;
  color: #475569;
}

.status-pill.manager {
  background: #fff7ed;
  color: #c2410c;
}

.message-card {
  padding: 13px 16px;
  border-radius: 16px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 14px;
  font-weight: 700;
}

.message-card.success {
  border-color: #bbf7d0;
  background: #ecfdf5;
  color: #15803d;
}

.message-card.error {
  border-color: #fecaca;
  background: #fef2f2;
  color: #dc2626;
}

.list-card,
.preview-card {
  padding: 20px;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(320px, 430px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.section-head h3 {
  font-size: 20px;
}

.checklist-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 760px;
  overflow: auto;
  padding-right: 4px;
}

.checklist-card {
  border: 1px solid #e5edf5;
  background: #fff;
  border-radius: 18px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.checklist-card:hover,
.checklist-card.active {
  border-color: #93c5fd;
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.08);
}

.checklist-card-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.table-code {
  color: #2563eb;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.04em;
}

.checklist-card h4 {
  margin: 6px 0 0;
  color: #0f172a;
  font-size: 16px;
  line-height: 1.45;
}

.card-meta-grid,
.preview-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.preview-meta-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.card-meta-grid div,
.meta-item {
  padding: 11px 12px;
  border-radius: 14px;
  border: 1px solid #e7edf4;
  background: #f8fafc;
  min-width: 0;
}

.card-meta-grid span,
.meta-item span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 5px;
}

.card-meta-grid strong,
.meta-item strong {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.checklist-card-footer {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.preview-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.preview-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.pdf-preview-shell {
  margin-top: 16px;
  height: min(74vh, 760px);
  min-height: 520px;
  border: 1px solid #dbe4ee;
  border-radius: 20px;
  overflow: hidden;
  background: #f8fafc;
}

.pdf-preview-shell iframe {
  width: 100%;
  height: 100%;
  border: 0;
  background: #fff;
}

.external-section {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid #e5edf5;
}

.external-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.external-filter-panel {
  display: grid;
  grid-template-columns: minmax(220px, 1.4fr) repeat(2, minmax(160px, 1fr));
  gap: 12px;
  padding: 14px;
  margin-bottom: 14px;
  border: 1px solid #e5edf5;
  border-radius: 18px;
  background: #f8fafc;
}

.external-filter-item {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}

.external-filter-item span {
  color: #475569;
  font-size: 12px;
  font-weight: 900;
}

.external-filter-item input,
.external-filter-item select {
  width: 100%;
  height: 40px;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  background: #fff;
  color: #0f172a;
  padding: 0 11px;
  box-sizing: border-box;
}

.external-standard-list,
.mobile-external-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-external-section {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #e5edf5;
}

.external-standard-card {
  padding: 14px;
  border: 1px solid #e5edf5;
  border-radius: 16px;
  background: #ffffff;
}

.external-standard-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.external-standard-top span {
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 900;
}

.external-standard-top em {
  flex: 0 0 auto;
  padding: 4px 9px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  font-weight: 900;
}

.external-standard-top em.linked {
  background: #ecfdf5;
  color: #15803d;
}

.external-standard-card p {
  margin: 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-line;
}

.empty-external {
  min-height: 110px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed #cbd5e1;
  border-radius: 16px;
  background: #f8fafc;
  color: #64748b;
}

.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.pagination-summary {
  color: #475569;
  font-size: 13px;
  font-weight: 800;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.pagination-btn {
  min-width: 72px;
}

.pagination-page-list {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: min(520px, 48vw);
  min-width: 0;
  padding: 4px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
  overflow-x: auto;
  overscroll-behavior-x: contain;
  scrollbar-width: thin;
}

.pagination-page-btn {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #475569;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
}

.pagination-page-btn.active {
  background: #2563eb;
  color: #fff;
  box-shadow: 0 8px 16px rgba(37, 99, 235, 0.22);
}

.pagination-page-btn:hover {
  background: #e0edff;
  color: #1d4ed8;
}

.pagination-page-btn.active:hover {
  background: #2563eb;
  color: #fff;
}

.mobile-standard-pager {
  gap: 10px;
  min-width: 0;
}

.empty-block,
.empty-preview {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748b;
  line-height: 1.8;
}

.empty-preview {
  min-height: 520px;
  border: 1px dashed #cbd5e1;
  border-radius: 20px;
  background: #f8fafc;
  margin-top: 16px;
  padding: 24px;
}

.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 18px;
  font-weight: 900;
  margin-bottom: 14px;
}

.empty-title {
  color: #0f172a;
  font-size: 20px;
  font-weight: 900;
}

.btn {
  min-height: 42px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.18s ease;
}

.btn-compact {
  min-height: 38px;
  font-size: 13px;
}

.btn-primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.btn-secondary:hover:not(:disabled) {
  background: #f8fafc;
}

.btn:disabled,
.upload-label.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.upload-label input {
  display: none;
}

.permission-card {
  min-height: 320px;
  margin: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 32px;
}

.permission-icon {
  width: 56px;
  height: 56px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 28px;
  font-weight: 900;
  margin-bottom: 14px;
}

.permission-title {
  font-size: 22px;
  font-weight: 900;
  color: #0f172a;
  margin-bottom: 8px;
}

.permission-desc {
  color: #64748b;
  font-size: 14px;
}

@media (max-width: 1200px) {
  .content-grid {
    grid-template-columns: 1fr;
  }

  .checklist-list {
    max-height: none;
  }
}

@media (max-width: 768px) {
  .page-header,
  .preview-header {
    flex-direction: column;
    align-items: stretch;
  }

  .page-header,
  .list-card,
  .preview-card {
    padding: 18px;
    border-radius: 22px;
  }

  .page-header h2 {
    font-size: 29px;
  }

  .header-badges,
  .preview-actions {
    justify-content: flex-start;
  }

  .card-meta-grid,
  .preview-meta-grid,
  .checklist-card-footer {
    grid-template-columns: 1fr;
  }

  .preview-actions .btn {
    width: 100%;
  }

  .checklist-card-main {
    flex-direction: column;
  }

  .external-section-head,
  .external-standard-top {
    flex-direction: column;
  }

  .external-filter-panel {
    grid-template-columns: 1fr;
  }

  .pagination-controls {
    width: 100%;
    justify-content: space-between;
    min-width: 0;
  }

  .mobile-standard-pager {
    width: 100%;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    min-width: 0;
  }

  .mobile-standard-pager .pagination-page-list {
    width: 100%;
    max-width: none;
    min-width: 0;
    justify-content: flex-start;
    white-space: nowrap;
  }

  .mobile-standard-pager .pagination-btn {
    min-width: 68px;
    padding-inline: 10px;
  }

  .pagination-controls .pagination-page-list {
    max-width: min(100%, 56vw);
  }

  .pdf-preview-shell {
    height: 68vh;
    min-height: 420px;
    border-radius: 18px;
  }

  .empty-preview {
    min-height: 360px;
  }
}
</style>
