<template>
  <div v-if="hasPermission" class="page-shell standards-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>巡检规范库</h2>
      </div>
    </div>

    <div class="filter-card card-surface">
      <div class="filter-grid">
        <div class="filter-item filter-item-keyword">
          <label>关键词搜索</label>
          <input v-model.trim="filters.keyword" type="text" placeholder="可搜索规范ID、规范详情或检查表相关内容" />
        </div>

        <div class="filter-item">
          <label>检查表</label>
          <select v-model="filters.inspectionTableId">
            <option value="">全部检查表</option>
            <option v-for="table in inspectionTables" :key="table.id" :value="String(table.id)">
              {{ table.table_name }}
            </option>
          </select>
        </div>

        <div v-for="field in filterableFields" :key="field.field_key" class="filter-item">
          <label>{{ field.field_label }}</label>
          <select v-if="isFieldSelect(field.field_key)" v-model="dynamicFilters[field.field_key]">
            <option value="">全部</option>
            <option v-for="option in getFieldOptions(field.field_key)" :key="option" :value="option">
              {{ option }}
            </option>
          </select>
          <input v-else v-model.trim="dynamicFilters[field.field_key]" type="text"
            :placeholder="`搜索${field.field_label}`" />
        </div>
      </div>

      <div class="filter-actions">
        <button class="btn btn-secondary" type="button" @click="resetFilters">重置筛选</button>
        <button class="btn btn-secondary" type="button" @click="fetchStandards"
          :disabled="loading || !filters.inspectionTableId">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
      </div>
    </div>

    <div class="content-grid">
      <div class="list-card card-surface">
        <div class="list-toolbar">
          <div>
            <div class="list-count">共 {{ filteredList.length }} 条规范</div>
            <div class="list-table-name">{{ activeInspectionTableName }}</div>
          </div>
          <div class="list-page-info">第 {{ page }} / {{ totalPages }} 页</div>
        </div>

        <div class="list-wrap">
          <button v-for="item in paginatedList" :key="item.standard_id" class="standard-item"
            :class="{ active: activeStandard && activeStandard.standard_id === item.standard_id }" type="button"
            @click="selectStandard(item)">
            <div class="standard-item-top">
              <span class="standard-code">{{ item.standard_id }}</span>
              <span class="standard-process">{{ item.inspection_table_name || activeInspectionTableName || '未选择检查表'
                }}</span>
            </div>
            <div class="standard-check-item">{{ getStandardPrimaryTitle(item) }}</div>
            <div class="standard-card-meta" v-if="getStandardSummaryFields(item).length">
              <div v-for="entry in getStandardSummaryFields(item)" :key="`${item.standard_id}-${entry.key}`"
                class="standard-meta-line">
                <span class="standard-meta-label">{{ entry.label }}</span>
                <span class="standard-meta-value">{{ entry.value }}</span>
              </div>
            </div>
          </button>

          <div v-if="!loading && filteredList.length === 0" class="empty-block">
            未查询到符合条件的规范。
          </div>

          <div v-if="loading" class="empty-block">
            正在加载规范数据...
          </div>
        </div>
        <div v-if="filteredList.length > 0" class="list-pagination">
          <button class="btn btn-secondary" type="button" @click="prevPage" :disabled="page <= 1">上一页</button>
          <div class="list-pagination-summary">每页 {{ pageSize }} 条</div>
          <button class="btn btn-secondary" type="button" @click="nextPage" :disabled="page >= totalPages">下一页</button>
        </div>
      </div>

      <div class="detail-card card-surface">
        <template v-if="activeStandard">
          <div class="detail-header">
            <div>
              <div class="detail-kicker">规范详情</div>
              <h3>{{ activeStandard.standard_id }}｜{{ activeStandard.check_content || activeStandard.check_item ||
                activeStandard.project_name || '未命名规范' }}</h3>
            </div>
            <div class="detail-actions">
              <button class="btn btn-secondary" type="button" @click="copyCode">复制规范ID</button>
              <button class="btn btn-primary" type="button" @click="copyStandard">复制整条规范</button>
            </div>
          </div>

          <div class="detail-meta-grid">
            <div class="meta-item">
              <div class="meta-label">检查表</div>
              <div class="meta-value">{{ activeStandard?.inspection_table_name || activeInspectionTableName || '未选择检查表'
                }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">规范ID</div>
              <div class="meta-value">{{ activeStandard.standard_id }}</div>
            </div>
          </div>

          <div class="detail-detail-grid">
            <div v-for="entry in activeStandardDetailEntries" :key="`${activeStandard.standard_id}-${entry.key}`"
              class="detail-field-card">
              <div class="detail-field-label">{{ entry.label }}</div>
              <div class="detail-field-value multiline-content">{{ formatMultiline(entry.value) || '暂无' }}</div>
            </div>
          </div>

          <div v-if="copyMessage" class="copy-message">{{ copyMessage }}</div>
        </template>

        <div v-else class="empty-detail">
          <div class="empty-detail-icon">书</div>
          <div class="empty-detail-title">请选择一条巡检规范</div>
          <div class="empty-detail-desc">请先选择检查表，再按关键词或该检查表专属字段进行筛选，点击左侧规范后查看完整规范内容。</div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="card-surface permission-card">
    <div class="permission-icon">!</div>
    <div class="permission-title">无权限访问</div>
    <div class="permission-desc">当前账号无权访问巡检规范库。</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import axios from 'axios'

const loading = ref(false)
const currentRole = localStorage.getItem('user_role') || ''
let localPermissions = {}
try {
  localPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch (error) {
  localPermissions = {}
}
const hasPermission = currentRole === 'root' || Boolean(localPermissions.view_inspection_standards)
const inspectionTables = ref([])
const inspectionTableFields = ref([])
const standards = ref([])
const activeStandard = ref(null)
const copyMessage = ref('')
const page = ref(1)
const pageSize = 5

const filters = ref({
  keyword: '',
  inspectionTableId: ''
})

const dynamicFilters = ref({})

const SUMMARY_FIELD_CANDIDATES = [
  'serial_no',
  'business_process',
  'check_item',
  'check_content',
  'project_name',
  'check_category',
  'check_method',
  'issue_code',
  'is_forbidden'
]

const DETAIL_HIDDEN_FIELDS = [
  'id',
  'created_at',
  'standard_detail_text',
  'inspection_table_id',
  'inspection_table_name',
  'inspection_table_code'
]
const SELECT_OPTION_THRESHOLD = 12
const SELECT_MAX_OPTION_TEXT_LENGTH = 16

const CHECKLIST_LABEL_MAP = {
  quality_check: {
    standard_id: '规范ID',
    serial_no: '序号',
    business_process: '业务流程',
    check_item: '检查项目',
    check_content: '检查内容',
    requirement: '规范要求',
    check_method: '检查方法',
    issue_code: '问题编号',
    common_issue: '常见问题',
    inspection_path: '检查路径',
    is_forbidden: '是否禁止项'
  },
  service_hygiene_check: {
    standard_id: '规范ID',
    project_name: '项目',
    check_category: '检查类别',
    check_content: '检查内容',
    evaluation_standard: '检查评比标准',
    check_method: '检查方式'
  }
}

const normalize = (value) => String(value || '').toLowerCase()
const formatMultiline = (value) => String(value || '').replace(/\\n/g, '\n')

const activeInspectionTable = computed(() => {
  return inspectionTables.value.find((item) => String(item.id) === String(filters.value.inspectionTableId)) || null
})

const activeInspectionTableName = computed(() => activeInspectionTable.value?.table_name || '')

const getChecklistLabelMap = (item) => {
  const inspectionTableCode = item?.inspection_table_code || ''
  return CHECKLIST_LABEL_MAP[inspectionTableCode] || {}
}

const getFieldLabel = (item, fieldKey) => {
  const tableLabelMap = getChecklistLabelMap(item)
  return tableLabelMap[fieldKey] || fieldMap.value[fieldKey] || fieldKey
}

const fieldMap = computed(() => {
  const map = {}
  inspectionTableFields.value.forEach((field) => {
    map[field.field_key] = field.field_label
  })
  return map
})

const fieldOptionsMap = computed(() => {
  const map = {}
  filterableFields.value.forEach((field) => {
    const values = standards.value
      .map((item) => String(item[field.field_key] || '').trim())
      .filter((value) => value && !value.includes('\n') && value.length <= SELECT_MAX_OPTION_TEXT_LENGTH)
    const uniqueValues = [...new Set(values)]
    map[field.field_key] = uniqueValues.length > 0 && uniqueValues.length <= SELECT_OPTION_THRESHOLD ? uniqueValues : []
  })
  return map
})

const activeStandardDetailEntries = computed(() => {
  if (!activeStandard.value) return []
  return Object.entries(activeStandard.value)
    .filter(([key, value]) => !DETAIL_HIDDEN_FIELDS.includes(key) && value !== null && String(value).trim())
    .map(([key, value]) => ({
      key,
      label: getFieldLabel(activeStandard.value, key),
      value: String(value)
    }))
})

const filterableFields = computed(() => {
  return inspectionTableFields.value.filter((item) => item.is_filterable)
})

const isFieldSelect = (fieldKey) => {
  return getFieldOptions(fieldKey).length > 0
}

const getFieldOptions = (fieldKey) => {
  return fieldOptionsMap.value[fieldKey] || []
}

const getStandardPrimaryTitle = (item) => {
  return item.check_content || item.check_item || item.project_name || '未命名规范'
}

const getStandardSummaryFields = (item) => {
  return SUMMARY_FIELD_CANDIDATES
    .filter((key) => key in item)
    .map((key) => ({
      key,
      label: getFieldLabel(item, key),
      value: String(item[key] || '').trim()
    }))
    .filter((entry) => entry.value && !entry.value.includes('\n') && entry.value.length <= 40)
    .slice(0, 3)
}

const filteredList = computed(() => {
  return [...standards.value]
    .filter((item) => {
      const keywordSource = [
        item.standard_id,
        item.standard_detail_text,
        item.check_content,
        item.check_item,
        item.project_name,
        item.inspection_table_name
      ].join(' ')

      const matchedKeyword = !filters.value.keyword || normalize(keywordSource).includes(normalize(filters.value.keyword))

      const matchedDynamic = filterableFields.value.every((field) => {
        const keyword = dynamicFilters.value[field.field_key] || ''
        if (!keyword) return true
        return normalize(item[field.field_key]).includes(normalize(keyword))
      })

      return matchedKeyword && matchedDynamic
    })
    .sort((a, b) => Number(a.standard_id || 0) - Number(b.standard_id || 0))
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredList.value.length / pageSize)))

const paginatedList = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredList.value.slice(start, start + pageSize)
})

const prevPage = () => {
  if (page.value > 1) page.value -= 1
}

const nextPage = () => {
  if (page.value < totalPages.value) page.value += 1
}

watch(
  filteredList,
  (list) => {
    if (page.value > totalPages.value) {
      page.value = totalPages.value
    }

    if (!list.length) {
      activeStandard.value = null
      return
    }

    const stillExists = list.find((item) => activeStandard.value && item.standard_id === activeStandard.value.standard_id)
    if (!stillExists) {
      activeStandard.value = list[0]
    }
  },
  { immediate: true }
)

const fetchInspectionTables = async () => {
  const response = await axios.get('/api/inspection-tables')
  inspectionTables.value = response.data || []
}

const fetchInspectionTableFields = async () => {
  if (!filters.value.inspectionTableId) {
    inspectionTableFields.value = []
    return
  }
  const response = await axios.get('/api/inspection-table-fields', {
    params: {
      table_id: filters.value.inspectionTableId
    }
  })
  inspectionTableFields.value = response.data || []
}

const fetchStandards = async () => {
  try {
    loading.value = true
    copyMessage.value = ''

    if (!filters.value.inspectionTableId) {
      const responses = await Promise.all(
        inspectionTables.value.map((table) =>
          axios.get('/api/inspection-table-standards', {
            params: {
              table_id: table.id,
              ...(filters.value.keyword ? { keyword: filters.value.keyword } : {})
            }
          })
        )
      )

      standards.value = responses.flatMap((response, index) => {
        const table = inspectionTables.value[index]
        return (response.data || []).map((item) => ({
          ...item,
          inspection_table_id: table.id,
          inspection_table_name: table.table_name,
          inspection_table_code: table.table_code
        }))
      })
      return
    }

    const params = {
      table_id: filters.value.inspectionTableId
    }

    if (filters.value.keyword) {
      params.keyword = filters.value.keyword
    }

    Object.entries(dynamicFilters.value).forEach(([key, value]) => {
      if (String(value || '').trim()) {
        params[key] = value
      }
    })

    const response = await axios.get('/api/inspection-table-standards', { params })
    standards.value = (response.data || []).map((item) => ({
      ...item,
      inspection_table_id: activeInspectionTable.value?.id,
      inspection_table_name: activeInspectionTable.value?.table_name || '',
      inspection_table_code: activeInspectionTable.value?.table_code || ''
    }))
  } catch (error) {
    standards.value = []
  } finally {
    loading.value = false
  }
}

const resetFilters = async () => {
  filters.value = {
    keyword: '',
    inspectionTableId: ''
  }
  dynamicFilters.value = {}
  inspectionTableFields.value = []
  standards.value = []
  activeStandard.value = null
  copyMessage.value = ''
  page.value = 1
}

const selectStandard = (item) => {
  activeStandard.value = item
  copyMessage.value = ''
}

const copyCode = async () => {
  if (!activeStandard.value) return
  try {
    await navigator.clipboard.writeText(String(activeStandard.value.standard_id || ''))
    copyMessage.value = '规范ID已复制。'
  } catch (error) {
    copyMessage.value = '复制失败，请手动复制。'
  }
}

const copyStandard = async () => {
  if (!activeStandard.value) return
  const text = [
    `检查表：${activeInspectionTableName.value || ''}`,
    `规范ID：${activeStandard.value.standard_id || ''}`,
    `${formatMultiline(activeStandard.value.standard_detail_text) || ''}`
  ].join('\n')

  try {
    await navigator.clipboard.writeText(text)
    copyMessage.value = '整条规范已复制。'
  } catch (error) {
    copyMessage.value = '复制失败，请手动复制。'
  }
}

watch(
  () => filters.value.inspectionTableId,
  async (value) => {
    copyMessage.value = ''
    page.value = 1
    activeStandard.value = null
    standards.value = []
    dynamicFilters.value = {}

    if (!value) {
      inspectionTableFields.value = []
      await fetchStandards()
      return
    }

    try {
      await fetchInspectionTableFields()
      const nextDynamicFilters = {}
      filterableFields.value.forEach((field) => {
        nextDynamicFilters[field.field_key] = ''
      })
      dynamicFilters.value = nextDynamicFilters
      await fetchStandards()
    } catch (error) {
      inspectionTableFields.value = []
      standards.value = []
    }
  }
)

watch(
  () => filters.value.keyword,
  () => {
    page.value = 1
    copyMessage.value = ''
  }
)

watch(
  dynamicFilters,
  () => {
    page.value = 1
    copyMessage.value = ''
  },
  { deep: true }
)

onMounted(async () => {
  if (!hasPermission) return
  try {
    await fetchInspectionTables()
    await fetchStandards()
  } catch (error) {
    inspectionTables.value = []
    standards.value = []
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
  border-radius: 22px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
}

.page-header {
  padding: 24px 28px;
}

.page-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 14px;
}

.page-header h2 {
  margin: 0;
  font-size: 34px;
  color: #0f172a;
}

.filter-card {
  padding: 22px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(220px, 1fr));
  gap: 16px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-item-keyword {
  grid-column: span 2;
}

.filter-item label {
  font-size: 14px;
  font-weight: 700;
  color: #334155;
}

.filter-item input {
  height: 46px;
  border: 1px solid #d7e0ea;
  border-radius: 14px;
  padding: 0 14px;
  font-size: 14px;
  color: #0f172a;
  transition: all 0.18s ease;
}

.filter-item input:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.4);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.08);
}

.filter-item select {
  height: 46px;
  border: 1px solid #d7e0ea;
  border-radius: 14px;
  padding: 0 14px;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
  transition: all 0.18s ease;
}

.filter-item select:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.4);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.08);
}

.filter-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(340px, 420px) minmax(0, 1fr);
  gap: 20px;
  min-height: 620px;
}

.list-card,
.detail-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  min-height: 620px;
}

.list-toolbar {
  margin-bottom: 14px;
}

.list-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.list-page-info {
  font-size: 12px;
  color: #64748b;
  font-weight: 700;
  white-space: nowrap;
  padding-top: 2px;
}

.list-count {
  font-size: 14px;
  color: #64748b;
  font-weight: 700;
}

.list-table-name {
  font-size: 13px;
  color: #2563eb;
  font-weight: 700;
}

.list-wrap {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.list-pagination {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #e7edf4;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.list-pagination-summary {
  font-size: 13px;
  color: #64748b;
  font-weight: 700;
  text-align: center;
}

.standard-item {
  width: 100%;
  text-align: left;
  border: 1px solid #e5edf5;
  background: #fff;
  border-radius: 16px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.standard-item:hover {
  background: #f8fbff;
  border-color: #bfdbfe;
}

.standard-item.active {
  background: #eff6ff;
  border-color: #93c5fd;
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.08);
}

.standard-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.standard-code {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
}

.standard-process {
  font-size: 12px;
  color: #64748b;
  font-weight: 700;
}

.standard-check-item {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 6px;
}

.standard-card-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.standard-meta-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  line-height: 1.6;
}

.standard-meta-label {
  flex-shrink: 0;
  color: #64748b;
  font-weight: 700;
}

.standard-meta-value {
  color: #334155;
}

.standard-check-content {
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
}

.detail-card {
  overflow: auto;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.detail-kicker {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 8px;
}

.detail-header h3 {
  margin: 0;
  font-size: 26px;
  color: #0f172a;
  line-height: 1.4;
}

.detail-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.detail-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.meta-item {
  padding: 14px 16px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e7edf4;
}

.meta-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 8px;
}

.meta-value {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.6;
}

.detail-block {
  margin-bottom: 18px;
}

.detail-block-title {
  font-size: 15px;
  font-weight: 800;
  color: #334155;
  margin-bottom: 10px;
}

.detail-block-content {
  padding: 16px 18px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e7edf4;
  color: #334155;
  line-height: 1.9;
  white-space: pre-wrap;
}

.detail-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(240px, 1fr));
  gap: 14px;
}

.detail-field-card {
  padding: 16px 18px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e7edf4;
  min-width: 0;
}

.detail-field-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 8px;
}

.detail-field-value {
  font-size: 14px;
  line-height: 1.9;
  color: #334155;
}

.multiline-content {
  white-space: pre-line;
}

.copy-message {
  margin-top: 8px;
  font-size: 14px;
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 14px;
  padding: 12px 14px;
}

.empty-block,
.empty-detail {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748b;
  line-height: 1.8;
}

.empty-detail-icon {
  width: 60px;
  height: 60px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 26px;
  font-weight: 800;
  margin-bottom: 14px;
}

.empty-detail-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 8px;
}

.empty-detail-desc {
  max-width: 440px;
  font-size: 14px;
}

.btn {
  height: 42px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  cursor: pointer;
  transition: all 0.18s ease;
}

.btn-primary {
  background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
  border-color: #2563eb;
  color: #fff;
  box-shadow: 0 12px 22px rgba(37, 99, 235, 0.16);
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%);
}

.btn-secondary:hover:not(:disabled) {
  background: #f8fafc;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
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
  .filter-grid {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }

  .filter-item-keyword {
    grid-column: span 2;
  }

  .content-grid {
    grid-template-columns: 1fr;
  }

  .list-card,
  .detail-card {
    min-height: auto;
  }
}

@media (max-width: 768px) {

  .filter-grid,
  .detail-meta-grid {
    grid-template-columns: 1fr;
  }

  .filter-item-keyword {
    grid-column: span 1;
  }

  .page-header h2 {
    font-size: 30px;
  }

  .detail-header h3 {
    font-size: 22px;
  }

  .detail-detail-grid {
    grid-template-columns: 1fr;
  }

  .list-toolbar,
  .list-pagination {
    flex-direction: column;
    align-items: stretch;
  }

  .list-page-info,
  .list-pagination-summary {
    text-align: center;
  }
}
</style>
