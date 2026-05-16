<template>
  <div v-if="hasPermission" class="page-shell standards-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>巡检规范库</h2>
        <p class="page-desc">业务督导中心部门通过整理归纳外部规范库，从而自建形成的内部巡检规范库。</p>
      </div>
      <div class="header-badges">
        <span class="status-pill info">内部规范 {{ filteredStandards.length }}</span>
        <span class="status-pill success">已挂载 {{ linkedCount }}</span>
      </div>
    </div>

    <div class="filter-card card-surface">
      <label class="filter-item">
        <span>关键词搜索</span>
        <input v-model.trim="keyword" type="search" placeholder="搜索内部规范ID、字段内容或外部规范ID" />
      </label>
      <label v-for="field in filterableFields" :key="field.field_key" class="filter-item">
        <span>{{ field.field_label }}</span>
        <select v-model="fieldFilters[field.field_key]">
          <option value="">全部</option>
          <option v-for="value in getFieldFilterOptions(field.field_key)" :key="value" :value="value">
            {{ value }}
          </option>
        </select>
      </label>
      <button v-if="hasActiveFieldFilters" class="btn btn-light" type="button" @click="clearFieldFilters">
        清空筛选
      </button>
      <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchStandards">
        {{ loading ? '刷新中...' : '刷新数据' }}
      </button>
    </div>

    <div class="content-grid">
      <section class="list-card card-surface">
        <div class="list-toolbar">
          <div>
            <div class="list-count">共 {{ filteredStandards.length }} 条内部规范</div>
            <div class="list-page-info">第 {{ page }} / {{ totalPages }} 页</div>
          </div>
        </div>

        <div class="standard-list">
          <button v-for="item in paginatedStandards" :key="item.id" type="button" class="standard-card"
            :class="{ active: activeStandard?.id === item.id }" @click="selectStandard(item)">
            <div class="standard-card-top">
              <span class="internal-code">{{ item.internal_standard_id }}</span>
              <span :class="['status-pill', item.linked_externals?.length ? 'success' : 'neutral']">
                {{ item.linked_externals?.length ? `关联 ${item.linked_externals.length}` : '未关联外部规范' }}
              </span>
            </div>
            <div class="standard-card-fields">
              <span v-for="field in shortInternalFields" :key="field.field_key" class="standard-field-chip">
                <em>{{ field.field_label }}</em>
                <strong>{{ getFieldValue(item, field.field_key) || '-' }}</strong>
              </span>
            </div>
            <p v-if="getLongFieldPreview(item)" class="standard-long-preview">{{ getLongFieldPreview(item) }}</p>
            <p v-else-if="!shortInternalFields.length" class="standard-long-preview">暂无字段内容</p>
          </button>

          <div v-if="!loading && !filteredStandards.length" class="empty-block">
            暂无内部巡检规范。
          </div>
          <div v-if="loading" class="empty-block">正在加载内部巡检规范...</div>
        </div>

        <div v-if="filteredStandards.length" class="pagination-bar">
          <button class="btn btn-secondary btn-sm" type="button" :disabled="page <= 1" @click="goToPage(1)">首页</button>
          <button class="btn btn-secondary btn-sm" type="button" :disabled="page <= 1" @click="goToPage(page - 1)">上一页</button>
          <button v-for="item in visiblePageItems" :key="item.key" type="button" class="page-btn"
            :class="{ active: item.value === page }" :disabled="item.type === 'ellipsis'" @click="goToPage(item.value)">
            {{ item.type === 'ellipsis' ? '...' : item.value }}
          </button>
          <button class="btn btn-secondary btn-sm" type="button" :disabled="page >= totalPages" @click="goToPage(page + 1)">下一页</button>
          <button class="btn btn-secondary btn-sm" type="button" :disabled="page >= totalPages" @click="goToPage(totalPages)">末页</button>
        </div>
      </section>

      <section class="detail-card card-surface">
        <template v-if="activeStandard">
          <div class="detail-head">
            <div>
              <div class="section-kicker">内部规范详情</div>
              <h3>{{ activeStandard.internal_standard_id }}</h3>
              <p>{{ formatFieldSummary(activeStandard) }}</p>
            </div>
          </div>

          <div class="detail-block">
            <strong>内部规范字段</strong>
            <div class="internal-field-grid">
              <div v-for="field in internalFields" :key="field.field_key" class="internal-field-item"
                :class="{ long: field.is_long_text }">
                <span>{{ field.field_label }}</span>
                <strong>{{ getFieldValue(activeStandard, field.field_key) || '-' }}</strong>
              </div>
            </div>
          </div>

          <div class="detail-block">
            <strong>关联外部规范</strong>
            <div v-if="activeStandard.linked_externals?.length" class="external-link-list">
              <article v-for="link in activeStandard.linked_externals" :key="link.external_standard_id"
                class="external-link-card">
                <div>
                  <span>外部规范ID {{ link.external_standard_id }}</span>
                  <strong>{{ link.inspection_table_name || '未知检查表' }}</strong>
                </div>
                <p>{{ link.standard_detail_text || '暂无外部规范详情。' }}</p>
              </article>
            </div>
            <div v-else class="empty-inline">这条内部规范暂未挂载外部规范。</div>
          </div>
        </template>

        <div v-else class="empty-block detail-empty">
          请选择一条内部巡检规范查看详情。
        </div>
      </section>
    </div>

    <Teleport to="body">
      <div v-if="mobileDialogVisible && activeStandard" class="mobile-detail-modal" @click.self="mobileDialogVisible = false">
        <section class="mobile-detail-sheet card-surface">
          <div class="modal-handle"></div>
          <button class="modal-close" type="button" @click="mobileDialogVisible = false">×</button>
          <div class="section-kicker">内部规范详情</div>
          <h3>{{ activeStandard.internal_standard_id }}</h3>
          <p class="path-line">{{ formatFieldSummary(activeStandard) }}</p>
          <div class="detail-block">
            <strong>内部规范字段</strong>
            <div class="internal-field-grid">
              <div v-for="field in internalFields" :key="field.field_key" class="internal-field-item"
                :class="{ long: field.is_long_text }">
                <span>{{ field.field_label }}</span>
                <strong>{{ getFieldValue(activeStandard, field.field_key) || '-' }}</strong>
              </div>
            </div>
          </div>
          <div class="detail-block">
            <strong>关联外部规范</strong>
            <div v-if="activeStandard.linked_externals?.length" class="external-link-list">
              <article v-for="link in activeStandard.linked_externals" :key="link.external_standard_id"
                class="external-link-card">
                <span>外部规范ID {{ link.external_standard_id }}</span>
                <strong>{{ link.inspection_table_name || '未知检查表' }}</strong>
                <p>{{ link.standard_detail_text || '暂无外部规范详情。' }}</p>
              </article>
            </div>
            <div v-else class="empty-inline">这条内部规范暂未挂载外部规范。</div>
          </div>
        </section>
      </div>
    </Teleport>
  </div>

  <div v-else class="card-surface permission-card">
    <div class="permission-icon">!</div>
    <div class="permission-title">无权限访问</div>
    <div class="permission-desc">当前账号无权访问巡检规范库。</div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

const currentRole = localStorage.getItem('user_role') || ''
let localPermissions = {}
try {
  localPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch (error) {
  localPermissions = {}
}

const hasPermission = currentRole === 'root' || Boolean(localPermissions.view_inspection_standards)
const loading = ref(false)
const standards = ref([])
const internalFields = ref([])
const activeStandard = ref(null)
const keyword = ref('')
const page = ref(1)
const pageSize = 8
const mobileDialogVisible = ref(false)
const isMobile = ref(false)
const fieldFilters = reactive({})

const linkedCount = computed(() => standards.value.filter((item) => item.linked_externals?.length).length)
const filterableFields = computed(() => internalFields.value.filter((field) => field.is_filterable))
const shortInternalFields = computed(() => internalFields.value.filter((field) => !field.is_long_text))
const longInternalFields = computed(() => internalFields.value.filter((field) => field.is_long_text))
const hasActiveFieldFilters = computed(() => {
  return filterableFields.value.some((field) => String(fieldFilters[field.field_key] || '').trim())
})

const getFieldValue = (item, fieldKey) => {
  return String(item?.field_values?.[fieldKey] ?? '').trim()
}

const formatFieldSummary = (item) => {
  const values = internalFields.value
    .map((field) => getFieldValue(item, field.field_key))
    .filter(Boolean)
  return values.length ? values.join(' / ') : '未设置字段内容'
}

const getPrimaryFieldValue = (item) => {
  const firstField = internalFields.value[0]
  if (!firstField) return item?.content || ''
  return getFieldValue(item, firstField.field_key)
}

const getLongFieldPreview = (item) => {
  const values = longInternalFields.value
    .map((field) => {
      const value = getFieldValue(item, field.field_key)
      return value ? `${field.field_label}：${value}` : ''
    })
    .filter(Boolean)
  return values.join('\n')
}

const filteredStandards = computed(() => {
  const text = keyword.value.toLowerCase()
  return standards.value.filter((item) => {
    const keywordMatched = !text || [
      item.internal_standard_id,
      formatFieldSummary(item),
      ...internalFields.value.map((field) => getFieldValue(item, field.field_key)),
      ...(item.linked_externals || []).map((link) => `${link.external_standard_id} ${link.inspection_table_name} ${link.standard_detail_text}`)
    ].join(' ').toLowerCase().includes(text)
    if (!keywordMatched) return false

    return filterableFields.value.every((field) => {
      const filterValue = String(fieldFilters[field.field_key] || '').trim()
      return !filterValue || getFieldValue(item, field.field_key) === filterValue
    })
  })
})

const getFieldFilterOptions = (fieldKey) => {
  return [...new Set(
    standards.value
      .map((item) => getFieldValue(item, fieldKey))
      .filter(Boolean)
  )].sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
}

const clearFieldFilters = () => {
  Object.keys(fieldFilters).forEach((key) => {
    fieldFilters[key] = ''
  })
}

const totalPages = computed(() => Math.max(1, Math.ceil(filteredStandards.value.length / pageSize)))

const visiblePageItems = computed(() => {
  const total = totalPages.value
  const current = page.value
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => ({ type: 'page', value: index + 1, key: `p-${index + 1}` }))
  }
  const pages = new Set([1, total, current, current - 1, current + 1])
  const sorted = [...pages].filter((item) => item >= 1 && item <= total).sort((a, b) => a - b)
  const result = []
  sorted.forEach((value, index) => {
    const previous = sorted[index - 1]
    if (index > 0 && value - previous > 1) result.push({ type: 'ellipsis', key: `e-${previous}-${value}` })
    result.push({ type: 'page', value, key: `p-${value}` })
  })
  return result
})

const paginatedStandards = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredStandards.value.slice(start, start + pageSize)
})

const goToPage = (target) => {
  const next = Number.parseInt(target, 10)
  if (!Number.isFinite(next)) return
  page.value = Math.min(Math.max(next, 1), totalPages.value)
}

const selectStandard = (item) => {
  activeStandard.value = item
  if (isMobile.value) mobileDialogVisible.value = true
}

const syncViewport = () => {
  isMobile.value = window.matchMedia('(max-width: 768px)').matches
}

const fetchStandards = async () => {
  if (!hasPermission) return
  try {
    loading.value = true
    const response = await axios.get('/api/inspection-internal-standards', {
      params: { keyword: keyword.value, _ts: Date.now() }
    })
    internalFields.value = response.data?.fields || []
    standards.value = response.data?.items || []
    if (!activeStandard.value || !standards.value.some((item) => item.id === activeStandard.value.id)) {
      activeStandard.value = standards.value[0] || null
    }
  } finally {
    loading.value = false
  }
}

watch(keyword, () => {
  page.value = 1
})

watch(fieldFilters, () => {
  page.value = 1
}, { deep: true })

watch(filteredStandards, () => {
  if (page.value > totalPages.value) page.value = totalPages.value
})

onMounted(() => {
  syncViewport()
  window.addEventListener('resize', syncViewport)
  fetchStandards()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncViewport)
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

.page-header,
.filter-card,
.list-card,
.detail-card {
  padding: 22px;
}

.page-header {
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
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 900;
  margin-bottom: 12px;
}

.page-header h2,
.detail-head h3 {
  margin: 0;
  color: #0f172a;
}

.page-header h2 {
  font-size: 34px;
}

.page-desc,
.detail-head p,
.standard-card p,
.detail-block p,
.external-link-card p {
  color: #64748b;
  line-height: 1.8;
  white-space: pre-line;
}

.header-badges,
.pagination-bar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.list-card .pagination-bar {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid #e5edf5;
  align-items: center;
}

.filter-card {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
  align-items: end;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-item span,
.detail-block strong {
  color: #374151;
  font-size: 14px;
  font-weight: 900;
}

.filter-item input,
.filter-item select {
  height: 44px;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  padding: 0 14px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(320px, 430px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.list-toolbar {
  margin-bottom: 14px;
}

.list-count {
  color: #0f172a;
  font-weight: 900;
}

.list-page-info,
.path-line,
.empty-inline {
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.standard-list,
.external-link-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.standard-card {
  width: 100%;
  border: 1px solid #e5edf5;
  border-radius: 18px;
  background: #fff;
  padding: 15px;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;
}

.standard-card:hover,
.standard-card.active {
  border-color: #5eead4;
  background: #f0fdfa;
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.12);
}

.standard-card-top,
.detail-head,
.external-link-card div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.standard-card-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.standard-field-chip {
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid #e5edf5;
  border-radius: 13px;
  background: #f8fafc;
}

.standard-field-chip em {
  display: block;
  color: #64748b;
  font-size: 11px;
  font-style: normal;
  font-weight: 900;
  margin-bottom: 4px;
}

.standard-field-chip strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.45;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.standard-long-preview {
  margin: 12px 0 0;
  padding: 10px 12px;
  border-radius: 14px;
  background: #f8fafc;
  color: #475569;
  font-size: 13px;
  line-height: 1.75;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.internal-code {
  color: #0f766e;
  font-size: 16px;
  font-weight: 900;
}

.detail-block {
  padding: 16px;
  border: 1px solid #e5edf5;
  border-radius: 18px;
  background: #f8fafc;
  margin-top: 14px;
}

.detail-block > strong {
  display: block;
  margin-bottom: 13px;
}

.internal-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.internal-field-item {
  padding: 11px 12px;
  border: 1px solid #e5edf5;
  border-radius: 14px;
  background: #fff;
}

.internal-field-item.long {
  grid-column: 1 / -1;
}

.internal-field-item span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
  margin-bottom: 5px;
}

.internal-field-item strong {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-line;
  word-break: break-word;
}

.external-link-card {
  padding: 14px;
  border: 1px solid #dbe4ee;
  border-radius: 16px;
  background: #fff;
}

.external-link-list {
  gap: 14px;
}

.external-link-card span {
  color: #0f766e;
  font-weight: 900;
}

.external-link-card strong {
  color: #0f172a;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 900;
}

.status-pill.info {
  background: #ecfeff;
  color: #0f766e;
}

.status-pill.success {
  background: #ecfdf5;
  color: #15803d;
}

.status-pill.neutral {
  background: #f1f5f9;
  color: #475569;
}

.btn,
.page-btn {
  min-height: 40px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  font-weight: 800;
  cursor: pointer;
}

.btn-secondary:hover:not(:disabled),
.btn-light:hover:not(:disabled),
.page-btn:hover:not(:disabled),
.page-btn.active {
  border-color: #0f766e;
  background: #f0fdfa;
  color: #0f766e;
}

.btn-light {
  background: #f8fafc;
}

.btn-sm {
  min-height: 34px;
  padding: 0 11px;
  font-size: 12px;
}

.empty-block {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  text-align: center;
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
  background: #ecfeff;
  color: #0f766e;
  font-size: 28px;
  font-weight: 900;
  margin-bottom: 14px;
}

.permission-title {
  color: #0f172a;
  font-size: 22px;
  font-weight: 900;
}

.permission-desc {
  color: #64748b;
}

.mobile-detail-modal {
  position: fixed;
  inset: 0;
  z-index: 1800;
  display: none;
  align-items: center;
  justify-content: center;
  padding: 14px;
  background: rgba(15, 23, 42, 0.48);
  backdrop-filter: blur(10px);
}

.mobile-detail-sheet {
  position: relative;
  width: 100%;
  max-width: 560px;
  max-height: 86vh;
  overflow: auto;
  padding: 18px;
  border-radius: 26px;
}

.modal-handle {
  width: 44px;
  height: 5px;
  border-radius: 999px;
  margin: 0 auto 14px;
  background: #cbd5e1;
}

.modal-close {
  position: absolute;
  right: 16px;
  top: 14px;
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 14px;
  background: #f1f5f9;
  color: #334155;
  font-size: 26px;
}

@media (max-width: 1080px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .page-header,
  .filter-card,
  .standard-card-top,
  .detail-head,
  .external-link-card div {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: stretch;
  }

  .filter-card {
    display: flex;
    flex-direction: column;
  }

  .internal-field-grid {
    grid-template-columns: 1fr;
  }

  .standard-card-fields {
    grid-template-columns: 1fr;
  }

  .detail-card {
    display: none;
  }

  .mobile-detail-modal {
    display: flex;
  }

  .page-header h2 {
    font-size: 29px;
  }
}
</style>
