<template>
  <div v-if="hasPermission" class="page-shell standards-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>巡检规范库</h2>
      </div>
    </div>

    <transition name="toast-fade">
      <div v-if="copyMessage" class="copy-toast" :class="copyMessageType">{{ copyMessage }}</div>
    </transition>

    <div class="filter-card card-surface">
      <div class="filter-grid">
        <div class="filter-item filter-item-keyword">
          <label>关键词搜索</label>
          <input v-model.trim="filters.keyword" type="text" placeholder="可搜索规范ID、规范详情或检查表相关内容" />
        </div>

        <div v-for="field in publicFilterFields" :key="field.field_key" class="filter-item filter-item-public"
          :class="{ 'filter-item-disabled': isFilterDisabled(field.field_key) }">
          <label>{{ field.field_label }}</label>
          <select v-if="isFieldSelect(field.field_key)" v-model="dynamicFilters[field.field_key]"
            :disabled="isFilterDisabled(field.field_key)">
            <option value="">{{ getFilterDefaultOption(field.field_key) }}</option>
            <option v-for="option in getFieldOptions(field.field_key)" :key="option" :value="option">
              {{ option }}
            </option>
          </select>
          <input v-else v-model.trim="dynamicFilters[field.field_key]" type="text"
            :disabled="isFilterDisabled(field.field_key)" :placeholder="`搜索${field.field_label}`" />
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

        <div v-for="field in localFilterFields" :key="field.field_key" class="filter-item"
          :class="{ 'filter-item-disabled': isFilterDisabled(field.field_key) }">
          <label>{{ field.field_label }}</label>
          <select v-if="isFieldSelect(field.field_key)" v-model="dynamicFilters[field.field_key]"
            :disabled="isFilterDisabled(field.field_key)">
            <option value="">{{ getFilterDefaultOption(field.field_key) }}</option>
            <option v-for="option in getFieldOptions(field.field_key)" :key="option" :value="option">
              {{ option }}
            </option>
          </select>
          <input v-else v-model.trim="dynamicFilters[field.field_key]" type="text"
            :disabled="isFilterDisabled(field.field_key)" :placeholder="`搜索${field.field_label}`" />
        </div>
      </div>

      <div class="filter-actions">
        <button class="btn btn-secondary" type="button" @click="resetFilters">重置筛选</button>
        <button class="btn btn-secondary" type="button" @click="fetchStandards" :disabled="loading">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
        <button class="btn btn-secondary btn-export-template" type="button" @click="openExportTemplateDialog">
          导出规范模板设定
        </button>
        <button class="btn btn-primary btn-export" type="button" @click="exportStandards"
          :disabled="loading || filteredList.length === 0">
          导出规范
        </button>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="exportTemplateDialog.visible" class="template-modal">
        <div class="template-modal-card card-surface">
          <div class="template-modal-header">
            <div>
              <div class="template-kicker">EXPORT TEMPLATE</div>
              <h3>导出规范模板设定</h3>
              <p>这是全系统共享模板。任何账号保存后，所有用户导出规范都会按这套字段口径生成A4文件。</p>
            </div>
            <button class="template-close-btn" type="button" @click="closeExportTemplateDialog">×</button>
          </div>

          <div class="template-modal-toolbar">
            <div class="template-stat">
              已选择 <strong>{{ exportTemplateSelectedTotal }}</strong> / {{ exportTemplateTotalFieldCount }} 个字段
            </div>
            <div class="template-toolbar-actions">
              <button class="btn btn-secondary" type="button" @click="selectAllExportFields()">全选全部</button>
              <button class="btn btn-secondary" type="button" @click="clearAllExportFields">清空全部</button>
              <button class="btn btn-secondary" type="button" @click="resetExportTemplateDraft">恢复默认</button>
            </div>
          </div>

          <div v-if="exportTemplateDialog.loading" class="template-loading">
            正在读取所有检查表字段...
          </div>

          <div v-else class="template-table-list">
            <section v-for="group in exportTemplateTableGroups" :key="group.table_id" class="template-table-card">
              <div class="template-table-head">
                <div>
                  <h4>{{ group.table_name }}</h4>
                  <span>{{ getExportTemplateSelectedCount(group.table_id) }} / {{ group.fields.length }} 个字段</span>
                </div>
                <div class="template-table-actions">
                  <button class="mini-btn" type="button" @click="selectAllExportFields(group.table_id)">全选</button>
                  <button class="mini-btn" type="button" @click="clearExportFields(group.table_id)">清空</button>
                </div>
              </div>

              <div v-if="group.fields.length" class="template-field-grid">
                <label v-for="field in group.fields" :key="`${group.table_id}-${field.field_key}`"
                  class="template-field-option">
                  <input type="checkbox" :checked="isExportFieldSelected(group.table_id, field.field_key)"
                    @change="toggleExportField(group.table_id, field.field_key, $event.target.checked)" />
                  <span>
                    <strong>{{ field.field_label }}</strong>
                    <em v-if="field.is_public">公共字段</em>
                  </span>
                </label>
              </div>

              <div v-else class="template-empty-fields">这张检查表暂未配置字段。</div>
            </section>
          </div>

          <div class="template-modal-footer">
            <button class="btn btn-secondary" type="button" @click="closeExportTemplateDialog">取消</button>
            <button class="btn btn-primary" type="button" :disabled="exportTemplateDialog.loading"
              @click="saveExportTemplateDialog">
              保存模板
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <div class="content-grid">
      <div class="list-card card-surface">
        <div class="list-toolbar">
          <div>
            <div class="list-count">共 {{ filteredList.length }} 条规范</div>
            <div class="list-table-name">{{ activeInspectionTableName || '全部检查表' }}</div>
          </div>
          <div class="list-page-info">第 {{ page }} / {{ totalPages }} 页</div>
        </div>

        <div class="list-wrap">
          <button v-for="item in paginatedList" :key="getStandardIdentity(item)" class="standard-item"
            :class="{ active: isActiveStandard(item) }" type="button"
            @click="selectStandard(item)">
            <div class="standard-item-top">
              <span class="standard-code">{{ item.standard_id }}</span>
              <span class="standard-process">{{ item.inspection_table_name || activeInspectionTableName || '未选择检查表'
                }}</span>
            </div>
            <div class="standard-check-item">{{ getStandardPrimaryTitle(item) }}</div>
            <div class="standard-card-meta" v-if="getStandardSummaryFields(item).length">
              <div v-for="entry in getStandardSummaryFields(item)" :key="`${getStandardIdentity(item)}-${entry.key}`"
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
              <h3>{{ activeStandardTitle }}</h3>
            </div>
            <div class="detail-actions">
              <button class="btn btn-secondary" type="button" @click="copyCode">复制规范ID</button>
              <button class="btn btn-primary" type="button" @click="copyStandard">复制整条规范</button>
            </div>
          </div>

          <div class="detail-meta-grid">
            <div class="meta-item">
              <div class="meta-label">检查表</div>
              <div class="meta-value">{{ activeStandardTableName }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">规范ID</div>
              <div class="meta-value">{{ activeStandard.standard_id }}</div>
            </div>
          </div>

          <div v-if="activeStandardDetailEntries.length" class="detail-detail-grid">
            <div v-for="entry in activeStandardDetailEntries" :key="`${activeStandardIdentity}-${entry.key}`"
              class="detail-field-card">
              <div class="detail-field-label">{{ entry.label }}</div>
              <div class="detail-field-value multiline-content">{{ formatMultiline(entry.value) || '暂无' }}</div>
            </div>
          </div>
          <div v-else class="empty-detail empty-detail-compact">
            <div class="empty-detail-title">暂无字段内容</div>
            <div class="empty-detail-desc">这条规范暂未维护可展示的字段内容。</div>
          </div>
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
const copyMessageType = ref('info')
let copyMessageTimer = null
const page = ref(1)
const pageSize = 5

const filters = ref({
  keyword: '',
  inspectionTableId: ''
})

const dynamicFilters = ref({})
const exportTemplateDialog = ref({
  visible: false,
  loading: false
})
const exportTemplateTableGroups = ref([])
const exportTemplateHasSaved = ref(false)
const exportTemplateSelection = ref({})
const exportTemplateDraft = ref({})

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

const FRIENDLY_FIELD_LABELS = {
  serial_no: '序号',
  business_process: '业务流程',
  check_item: '检查项目',
  check_content: '检查内容',
  project_name: '项目名称',
  check_category: '检查类别',
  check_method: '检查方法',
  issue_code: '问题代码',
  is_forbidden: '是否禁令'
}

const DETAIL_HIDDEN_FIELDS = [
  'id',
  'standard_id',
  'created_at',
  'standard_detail_text',
  'inspection_table_id',
  'inspection_table_name',
  'inspection_table_code'
]
const SELECT_OPTION_THRESHOLD = 12
const SELECT_MAX_OPTION_TEXT_LENGTH = 16
const INTERNAL_FIELD_KEY_PATTERN = /^(f_)?checklist_\d|^f_checklist_|^table_code$|^field_key$/
const TITLE_EXCLUDED_LABELS = new Set(['序号', '编号', '规范ID', '标准ID'])
const AREA_PRIMARY_LABEL = '一级区域'
const AREA_SECONDARY_LABEL = '二级区域'

const normalize = (value) => String(value || '').toLowerCase()
const normalizeFieldLabel = (value) => String(value || '').replace(/\s/g, '')
const formatMultiline = (value) => String(value || '').replace(/\\n/g, '\n')

const activeInspectionTable = computed(() => {
  return inspectionTables.value.find((item) => String(item.id) === String(filters.value.inspectionTableId)) || null
})

const activeInspectionTableName = computed(() => activeInspectionTable.value?.table_name || '')

const activeStandardIdentity = computed(() => getStandardIdentity(activeStandard.value))

const activeStandardTitle = computed(() => {
  return activeStandard.value ? getStandardPrimaryTitle(activeStandard.value) : ''
})

const activeStandardTableName = computed(() => {
  return getStandardTableName(activeStandard.value)
})

const getFieldLabel = (item, fieldKey) => {
  if (fieldKey === 'standard_id') return '规范ID'
  return fieldMap.value[fieldKey] || FRIENDLY_FIELD_LABELS[fieldKey] || ''
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
    if (isAreaSecondaryField(field)) {
      return
    }
    const values = standards.value
      .map((item) => String(item[field.field_key] || '').trim())
      .filter((value) => value && !value.includes('\n') && value.length <= SELECT_MAX_OPTION_TEXT_LENGTH)
    const uniqueValues = uniqueSortedOptions(values)
    map[field.field_key] = isAreaField(field)
      ? uniqueValues
      : uniqueValues.length > 0 && uniqueValues.length <= SELECT_OPTION_THRESHOLD ? uniqueValues : []
  })
  const secondaryKey = areaSecondaryField.value?.field_key
  const primaryKey = areaPrimaryField.value?.field_key
  const primaryValue = primaryKey ? String(dynamicFilters.value[primaryKey] || '').trim() : ''
  if (secondaryKey) {
    map[secondaryKey] = primaryValue
      ? uniqueSortedOptions(
        standards.value
          .filter((item) => String(item[primaryKey] || '').trim() === primaryValue)
          .map((item) => item[secondaryKey])
      )
      : []
  }
  return map
})

const uniqueSortedOptions = (values) => {
  return [...new Set(values.map((item) => String(item || '').trim()).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
}

const exportTemplateTotalFieldCount = computed(() => {
  return exportTemplateTableGroups.value.reduce((total, group) => total + group.fields.length, 0)
})

const exportTemplateSelectedTotal = computed(() => {
  return exportTemplateTableGroups.value.reduce((total, group) => {
    return total + getExportTemplateSelectedCount(group.table_id)
  }, 0)
})

const normalizeTemplateTableId = (tableId) => String(tableId || '')

const normalizeFieldKeyList = (list = []) => {
  return [...new Set((Array.isArray(list) ? list : []).map((item) => String(item || '').trim()).filter(Boolean))]
}

const buildAllSelectedExportTemplate = () => {
  return exportTemplateTableGroups.value.reduce((selection, group) => {
    selection[normalizeTemplateTableId(group.table_id)] = group.fields.map((field) => field.field_key)
    return selection
  }, {})
}

const normalizeExportTemplateSelection = (selection = {}) => {
  return exportTemplateTableGroups.value.reduce((normalized, group) => {
    const tableId = normalizeTemplateTableId(group.table_id)
    const availableKeys = new Set(group.fields.map((field) => String(field.field_key)))
    normalized[tableId] = normalizeFieldKeyList(selection[tableId]).filter((key) => availableKeys.has(key))
    return normalized
  }, {})
}

const getExportTemplateSelectedCount = (tableId) => {
  const selected = exportTemplateDraft.value[normalizeTemplateTableId(tableId)] || []
  return normalizeFieldKeyList(selected).length
}

const isExportFieldSelected = (tableId, fieldKey) => {
  const selected = exportTemplateDraft.value[normalizeTemplateTableId(tableId)] || []
  return selected.includes(fieldKey)
}

const toggleExportField = (tableId, fieldKey, checked) => {
  const tableKey = normalizeTemplateTableId(tableId)
  const selected = new Set(exportTemplateDraft.value[tableKey] || [])
  if (checked) {
    selected.add(fieldKey)
  } else {
    selected.delete(fieldKey)
  }
  exportTemplateDraft.value = {
    ...exportTemplateDraft.value,
    [tableKey]: [...selected]
  }
}

const selectAllExportFields = (tableId = null) => {
  if (tableId && typeof tableId === 'object') {
    tableId = null
  }
  if (tableId !== null) {
    const tableKey = normalizeTemplateTableId(tableId)
    const group = exportTemplateTableGroups.value.find((item) => normalizeTemplateTableId(item.table_id) === tableKey)
    if (!group) return
    exportTemplateDraft.value = {
      ...exportTemplateDraft.value,
      [tableKey]: group.fields.map((field) => field.field_key)
    }
    return
  }

  exportTemplateDraft.value = buildAllSelectedExportTemplate()
}

const clearExportFields = (tableId) => {
  const tableKey = normalizeTemplateTableId(tableId)
  exportTemplateDraft.value = {
    ...exportTemplateDraft.value,
    [tableKey]: []
  }
}

const clearAllExportFields = () => {
  exportTemplateDraft.value = exportTemplateTableGroups.value.reduce((selection, group) => {
    selection[normalizeTemplateTableId(group.table_id)] = []
    return selection
  }, {})
}

const resetExportTemplateDraft = () => {
  exportTemplateDraft.value = buildAllSelectedExportTemplate()
}

const isFieldWithLabel = (field, label) => normalizeFieldLabel(field?.field_label) === label

const isAreaPrimaryField = (field) => isFieldWithLabel(field, AREA_PRIMARY_LABEL)

const isAreaSecondaryField = (field) => isFieldWithLabel(field, AREA_SECONDARY_LABEL)

const isAreaField = (field) => isAreaPrimaryField(field) || isAreaSecondaryField(field)

const areaPrimaryField = computed(() => filterableFields.value.find(isAreaPrimaryField) || null)

const areaSecondaryField = computed(() => filterableFields.value.find(isAreaSecondaryField) || null)

const areaPrimaryFilterValue = computed(() => {
  const primaryKey = areaPrimaryField.value?.field_key
  return primaryKey ? String(dynamicFilters.value[primaryKey] || '').trim() : ''
})

const isAreaSecondaryFieldKey = (fieldKey) => String(fieldKey || '') === String(areaSecondaryField.value?.field_key || '')

const getStandardDetailEntries = (item) => {
  if (!item) return []
  const mappedEntries = Object.entries(item)
    .filter(([key, value]) => !DETAIL_HIDDEN_FIELDS.includes(key) && value !== null && String(value).trim())
    .filter(([key]) => shouldShowDetailKey(key))
    .map(([key, value]) => ({
      key,
      label: getFieldLabel(item, key),
      value: String(value)
    }))
    .filter((entry) => entry.label)
  const fallbackEntries = parseStandardDetailText(item.standard_detail_text)
  if (mappedEntries.length) {
    const mappedLabels = new Set(mappedEntries.map((entry) => entry.label))
    return [
      ...mappedEntries,
      ...fallbackEntries.filter((entry) => !mappedLabels.has(entry.label))
    ]
  }
  return fallbackEntries
}

const activeStandardDetailEntries = computed(() => {
  return getStandardDetailEntries(activeStandard.value)
})

const filterableFields = computed(() => {
  return inspectionTableFields.value.filter((item) => item.is_filterable)
})

const publicFilterFields = computed(() => {
  return filterableFields.value.filter((item) => item.is_public)
})

const localFilterFields = computed(() => {
  return filterableFields.value.filter((item) => !item.is_public)
})

const isFieldSelect = (fieldKey) => {
  const field = filterableFields.value.find((item) => item.field_key === fieldKey)
  return Boolean(isAreaField(field) || getFieldOptions(fieldKey).length > 0)
}

const getFieldOptions = (fieldKey) => {
  return fieldOptionsMap.value[fieldKey] || []
}

const isFilterDisabled = (fieldKey) => {
  if (!isAreaSecondaryFieldKey(fieldKey)) return false
  const primaryKey = areaPrimaryField.value?.field_key
  return !primaryKey || !String(dynamicFilters.value[primaryKey] || '').trim()
}

const getFilterDefaultOption = (fieldKey) => {
  return isFilterDisabled(fieldKey) ? '请先选择一级区域' : '全部'
}

const getStandardIdentity = (item) => {
  if (!item) return ''
  const tableId = item.inspection_table_id || filters.value.inspectionTableId || activeInspectionTable.value?.id || 'unknown'
  return `${tableId}:${item.standard_id || ''}`
}

const isActiveStandard = (item) => {
  return Boolean(activeStandard.value) && activeStandardIdentity.value === getStandardIdentity(item)
}

const getStandardTableName = (item) => {
  return item?.inspection_table_name || activeInspectionTableName.value || '未选择检查表'
}

const getStandardFallbackTitle = (item) => {
  const detailEntries = parseStandardDetailText(item?.standard_detail_text)
  const preferredEntry = detailEntries.find((entry) => {
    const label = String(entry.label || '').trim()
    return label && !TITLE_EXCLUDED_LABELS.has(label) && String(entry.value || '').trim()
  })
  if (preferredEntry) return preferredEntry.value

  const firstLine = String(item?.standard_detail_text || '')
    .replace(/\\n/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .find(Boolean)
  if (!firstLine) return ''
  const separatorIndex = firstLine.indexOf('：')
  return separatorIndex > -1 ? firstLine.slice(separatorIndex + 1).trim() : firstLine
}

const getStandardPrimaryTitle = (item) => {
  return item.check_content || item.check_item || item.project_name || getStandardFallbackTitle(item) || '未命名规范'
}

const shouldShowDetailKey = (key) => {
  if (fieldMap.value[key]) return true
  if (FRIENDLY_FIELD_LABELS[key]) return true
  return !INTERNAL_FIELD_KEY_PATTERN.test(String(key || ''))
}

const parseStandardDetailText = (text) => {
  return String(text || '')
    .replace(/\\n/g, '\n')
    .split('\n')
    .map((line, index) => {
      const trimmed = line.trim()
      if (!trimmed) return null
      const separatorIndex = trimmed.indexOf('：')
      if (separatorIndex < 0) {
        return {
          key: `detail_${index}`,
          label: '规范内容',
          value: trimmed
        }
      }
      return {
        key: `detail_${index}`,
        label: trimmed.slice(0, separatorIndex).trim() || '规范内容',
        value: trimmed.slice(separatorIndex + 1).trim()
      }
    })
    .filter((entry) => entry && entry.value)
}

const getStandardSummaryFields = (item) => {
  const preferredEntries = SUMMARY_FIELD_CANDIDATES
    .filter((key) => key in item)
    .map((key) => ({
      key,
      label: getFieldLabel(item, key),
      value: String(item[key] || '').trim()
    }))
    .filter((entry) => entry.label && entry.value && !entry.value.includes('\n') && entry.value.length <= 40)
    .slice(0, 3)
  if (preferredEntries.length) return preferredEntries
  const fieldEntries = inspectionTableFields.value
    .filter((field) => field.field_key in item)
    .map((field) => ({
      key: field.field_key,
      label: field.field_label,
      value: String(item[field.field_key] || '').trim()
    }))
    .filter((entry) => entry.value && !entry.value.includes('\n') && entry.value.length <= 40)
    .slice(0, 3)
  if (fieldEntries.length) return fieldEntries
  return parseStandardDetailText(item.standard_detail_text)
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
    .sort((a, b) => {
      if (!filters.value.inspectionTableId) {
        const tableCompare = String(a.inspection_table_name || '').localeCompare(
          String(b.inspection_table_name || ''),
          'zh-Hans-CN'
        )
        if (tableCompare) return tableCompare
      }
      return Number(a.standard_id || 0) - Number(b.standard_id || 0)
    })
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

    const stillExists = list.find((item) => isActiveStandard(item))
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
  const response = await axios.get('/api/inspection-table-fields', {
    params: filters.value.inspectionTableId
      ? { table_id: filters.value.inspectionTableId }
      : {}
  })
  inspectionTableFields.value = response.data || []
  syncDynamicFilters()
}

const ensureExportTemplateFieldsLoaded = async (force = false) => {
  if (!force && exportTemplateTableGroups.value.length) {
    exportTemplateDialog.value = {
      ...exportTemplateDialog.value,
      loading: false
    }
    return
  }
  if (!inspectionTables.value.length) {
    await fetchInspectionTables()
  }

  exportTemplateDialog.value = {
    ...exportTemplateDialog.value,
    loading: true
  }

  try {
    const responses = await Promise.all(
      inspectionTables.value.map((table) =>
        axios.get('/api/inspection-table-fields', {
          params: { table_id: table.id }
        })
      )
    )

    exportTemplateTableGroups.value = inspectionTables.value.map((table, index) => ({
      table_id: table.id,
      table_name: table.table_name,
      fields: (responses[index]?.data || []).map((field) => ({
        field_key: String(field.field_key || ''),
        field_label: field.field_label || field.field_key || '未命名字段',
        is_public: Boolean(field.is_public)
      })).filter((field) => field.field_key)
    }))
  } finally {
    exportTemplateDialog.value = {
      ...exportTemplateDialog.value,
      loading: false
    }
  }
}

const fetchExportTemplateSelection = async () => {
  const response = await axios.get('/api/inspection-standard-export-template')
  exportTemplateHasSaved.value = Boolean(response.data?.has_saved)
  exportTemplateSelection.value = response.data?.tables && typeof response.data.tables === 'object'
    ? response.data.tables
    : {}
}

const openExportTemplateDialog = async () => {
  exportTemplateDialog.value = {
    visible: true,
    loading: true
  }

  try {
    await ensureExportTemplateFieldsLoaded(true)
    await fetchExportTemplateSelection()
    exportTemplateDraft.value = exportTemplateHasSaved.value
      ? normalizeExportTemplateSelection(exportTemplateSelection.value)
      : buildAllSelectedExportTemplate()
  } catch (error) {
    showCopyToast('读取检查表字段失败，请稍后重试。', 'error')
    closeExportTemplateDialog()
  }
}

const closeExportTemplateDialog = () => {
  exportTemplateDialog.value = {
    visible: false,
    loading: false
  }
  exportTemplateDraft.value = {}
}

const saveExportTemplateDialog = () => {
  const normalized = normalizeExportTemplateSelection(exportTemplateDraft.value)
  exportTemplateDialog.value = {
    ...exportTemplateDialog.value,
    loading: true
  }
  axios.put('/api/inspection-standard-export-template', {
    tables: normalized
  }).then((response) => {
    exportTemplateSelection.value = response.data?.tables || normalized
    exportTemplateHasSaved.value = true
    closeExportTemplateDialog()
    showCopyToast('导出规范公共模板已保存。', 'success')
  }).catch((error) => {
    exportTemplateDialog.value = {
      ...exportTemplateDialog.value,
      loading: false
    }
    showCopyToast(error?.response?.data?.error || '保存导出规范公共模板失败。', 'error')
  })
}

const syncDynamicFilters = () => {
  const nextDynamicFilters = {}
  filterableFields.value.forEach((field) => {
    nextDynamicFilters[field.field_key] = dynamicFilters.value[field.field_key] || ''
  })
  dynamicFilters.value = nextDynamicFilters
}

const buildStandardQueryParams = (tableId) => {
  const params = {
    table_id: tableId
  }
  if (filters.value.keyword) {
    params.keyword = filters.value.keyword
  }
  Object.entries(dynamicFilters.value).forEach(([key, value]) => {
    if (String(value || '').trim()) {
      params[key] = value
    }
  })
  return params
}

const fetchStandards = async () => {
  try {
    loading.value = true
    copyMessage.value = ''

    if (!filters.value.inspectionTableId) {
      const responses = await Promise.all(
        inspectionTables.value.map((table) =>
          axios.get('/api/inspection-table-standards', {
            params: buildStandardQueryParams(table.id)
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

    const response = await axios.get('/api/inspection-table-standards', {
      params: buildStandardQueryParams(filters.value.inspectionTableId)
    })
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
  standards.value = []
  activeStandard.value = null
  copyMessage.value = ''
  page.value = 1
  await fetchInspectionTableFields()
  await fetchStandards()
}

const selectStandard = (item) => {
  activeStandard.value = item
  copyMessage.value = ''
}

const showCopyToast = (message, type = 'info') => {
  if (copyMessageTimer) {
    clearTimeout(copyMessageTimer)
    copyMessageTimer = null
  }

  copyMessageType.value = type
  copyMessage.value = message
  copyMessageTimer = setTimeout(() => {
    copyMessage.value = ''
    copyMessageTimer = null
  }, 2200)
}

const fallbackCopyText = (text) => {
  const textArea = document.createElement('textarea')
  textArea.value = text
  textArea.setAttribute('readonly', '')
  textArea.style.position = 'fixed'
  textArea.style.left = '-9999px'
  textArea.style.top = '0'
  textArea.style.opacity = '0'
  textArea.style.fontSize = '16px'
  document.body.appendChild(textArea)
  textArea.focus()
  textArea.select()
  textArea.setSelectionRange(0, textArea.value.length)

  let copied = false
  try {
    copied = document.execCommand('copy')
  } finally {
    document.body.removeChild(textArea)
  }

  if (!copied) {
    throw new Error('copy command failed')
  }
}

const copyText = async (text) => {
  const value = String(text || '')
  if (!value) throw new Error('empty copy text')

  if (window.isSecureContext && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value)
      return
    } catch (error) {
      fallbackCopyText(value)
      return
    }
  }

  fallbackCopyText(value)
}

const copyCode = async () => {
  if (!activeStandard.value) return
  try {
    await copyText(String(activeStandard.value.standard_id || ''))
    showCopyToast('规范ID已复制。', 'success')
  } catch (error) {
    showCopyToast('复制失败，请手动复制。', 'error')
  }
}

const copyStandard = async () => {
  if (!activeStandard.value) return
  const detailText = activeStandardDetailEntries.value.length
    ? activeStandardDetailEntries.value
      .map((entry) => `${entry.label}：${formatMultiline(entry.value)}`)
      .join('\n')
    : formatMultiline(activeStandard.value.standard_detail_text)
  const text = [
    `检查表：${getStandardTableName(activeStandard.value)}`,
    `规范ID：${activeStandard.value.standard_id || ''}`,
    detailText || ''
  ].join('\n')

  try {
    await copyText(text)
    showCopyToast('整条规范已复制。', 'success')
  } catch (error) {
    showCopyToast('复制失败，请手动复制。', 'error')
  }
}

const escapeHtml = (value) => String(value ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

const renderPrintMultiline = (value) => {
  return escapeHtml(formatMultiline(value) || '-').replace(/\n/g, '<br>')
}

const getPrintDateText = () => {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(new Date())
}

const getExportFilterTags = () => {
  const tags = [
    {
      label: '检查表',
      value: activeInspectionTableName.value || '全部检查表'
    }
  ]

  if (filters.value.keyword) {
    tags.push({
      label: '关键词',
      value: filters.value.keyword
    })
  }

  const fieldLabelMap = inspectionTableFields.value.reduce((map, field) => {
    map[field.field_key] = field.field_label
    return map
  }, {})

  Object.entries(dynamicFilters.value).forEach(([key, value]) => {
    const text = String(value || '').trim()
    if (!text) return
    tags.push({
      label: fieldLabelMap[key] || FRIENDLY_FIELD_LABELS[key] || key,
      value: text
    })
  })

  return tags
}

const getExportTableId = (item) => {
  return normalizeTemplateTableId(
    item?.inspection_table_id || filters.value.inspectionTableId || activeInspectionTable.value?.id || ''
  )
}

const getExportTemplateFieldSet = (tableId) => {
  const tableKey = normalizeTemplateTableId(tableId)
  if (!exportTemplateHasSaved.value || !Array.isArray(exportTemplateSelection.value[tableKey])) {
    return null
  }
  return new Set(normalizeFieldKeyList(exportTemplateSelection.value[tableKey]))
}

const getExportTableFields = (tableId) => {
  const tableKey = normalizeTemplateTableId(tableId)
  const group = exportTemplateTableGroups.value.find((item) => normalizeTemplateTableId(item.table_id) === tableKey)
  return group?.fields || []
}

const getExportStandardDetailEntries = (item) => {
  const tableId = getExportTableId(item)
  const fields = getExportTableFields(tableId)
  const selectedSet = getExportTemplateFieldSet(tableId)

  if (fields.length) {
    return fields
      .filter((field) => !selectedSet || selectedSet.has(field.field_key))
      .map((field) => ({
        key: field.field_key,
        label: field.field_label,
        value: String(item?.[field.field_key] ?? '').trim() || '-'
      }))
  }

  const entries = getStandardDetailEntries(item)
  if (!selectedSet) return entries
  return entries.filter((entry) => selectedSet.has(entry.key))
}

const buildStandardPrintCard = (item, index) => {
  const entries = getExportStandardDetailEntries(item)
  const detailHtml = entries.length
    ? entries.map((entry) => `
        <div class="field-row">
          <div class="field-label">${escapeHtml(entry.label)}</div>
          <div class="field-value">${renderPrintMultiline(entry.value)}</div>
        </div>
      `).join('')
    : `<div class="field-row field-row-full">
        <div class="field-label">导出字段</div>
        <div class="field-value">当前检查表未选择导出字段。</div>
      </div>`

  return `
    <article class="standard-card">
      <div class="standard-head">
        <div class="standard-index">${index + 1}</div>
        <div class="standard-title-block">
          <div class="standard-title">${escapeHtml(getStandardPrimaryTitle(item))}</div>
          <div class="standard-subtitle">${escapeHtml(getStandardTableName(item))}</div>
        </div>
        <div class="standard-code">规范ID ${escapeHtml(item.standard_id || '-')}</div>
      </div>
      <div class="field-grid">
        ${detailHtml}
      </div>
    </article>
  `
}

const buildStandardsPrintDocument = () => {
  const exportList = filteredList.value
  const filterTags = getExportFilterTags()
  const filterHtml = filterTags
    .map((tag) => `<span class="filter-tag">${escapeHtml(tag.label)}：${escapeHtml(tag.value)}</span>`)
    .join('')

  return `<!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <title>巡检规范导出</title>
        <style>
          @page {
            size: A4;
            margin: 12mm;
          }

          * {
            box-sizing: border-box;
          }

          body {
            margin: 0;
            background: #dbe4ee;
            color: #172033;
            font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }

          .print-toolbar {
            position: sticky;
            top: 0;
            z-index: 10;
            display: flex;
            justify-content: center;
            gap: 12px;
            padding: 14px;
            background: rgba(241, 245, 249, 0.92);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid #cbd5e1;
          }

          .print-toolbar button {
            height: 38px;
            padding: 0 16px;
            border-radius: 999px;
            border: 1px solid #2563eb;
            background: #2563eb;
            color: #ffffff;
            font-weight: 800;
            cursor: pointer;
          }

          .paper {
            width: 210mm;
            min-height: 297mm;
            margin: 18px auto;
            padding: 15mm 14mm;
            background:
              linear-gradient(135deg, rgba(37, 99, 235, 0.08), transparent 34%),
              #ffffff;
            box-shadow: 0 22px 50px rgba(15, 23, 42, 0.18);
          }

          .report-header {
            padding-bottom: 14px;
            border-bottom: 2px solid #172033;
            margin-bottom: 14px;
          }

          .report-kicker {
            font-size: 11px;
            letter-spacing: 0.18em;
            color: #2563eb;
            font-weight: 900;
            margin-bottom: 8px;
          }

          .report-title {
            margin: 0;
            font-size: 24px;
            line-height: 1.25;
            color: #0f172a;
          }

          .report-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 8px 14px;
            margin-top: 10px;
            color: #475569;
            font-size: 11px;
            font-weight: 700;
          }

          .filter-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 12px 0 18px;
          }

          .filter-tag {
            display: inline-flex;
            align-items: center;
            min-height: 24px;
            padding: 3px 9px;
            border-radius: 999px;
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            color: #1e3a8a;
            font-size: 10px;
            font-weight: 800;
          }

          .standard-card {
            break-inside: avoid;
            page-break-inside: avoid;
            margin-bottom: 12px;
            border: 1px solid #d8e2ee;
            border-radius: 12px;
            overflow: hidden;
            background: #ffffff;
          }

          .standard-head {
            display: grid;
            grid-template-columns: 32px minmax(0, 1fr) auto;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            background: #f8fafc;
            border-bottom: 1px solid #e5edf5;
          }

          .standard-index {
            width: 26px;
            height: 26px;
            border-radius: 999px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #172033;
            color: #ffffff;
            font-size: 11px;
            font-weight: 900;
          }

          .standard-title {
            font-size: 14px;
            line-height: 1.45;
            font-weight: 900;
            color: #0f172a;
          }

          .standard-subtitle {
            margin-top: 2px;
            color: #64748b;
            font-size: 10px;
            font-weight: 700;
          }

          .standard-code {
            padding: 5px 9px;
            border-radius: 999px;
            background: #dbeafe;
            color: #1d4ed8;
            font-size: 10px;
            font-weight: 900;
            white-space: nowrap;
          }

          .field-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0;
          }

          .field-row {
            display: grid;
            grid-template-columns: 84px minmax(0, 1fr);
            min-height: 34px;
            border-top: 1px solid #eef2f7;
          }

          .field-row:nth-child(1),
          .field-row:nth-child(2) {
            border-top: none;
          }

          .field-row-full {
            grid-column: 1 / -1;
          }

          .field-label {
            padding: 8px 9px;
            background: #f8fafc;
            border-right: 1px solid #eef2f7;
            color: #64748b;
            font-size: 10px;
            line-height: 1.55;
            font-weight: 900;
            word-break: break-word;
          }

          .field-value {
            padding: 8px 10px;
            color: #1f2937;
            font-size: 10.5px;
            line-height: 1.7;
            word-break: break-word;
          }

          .report-footer {
            margin-top: 16px;
            padding-top: 10px;
            border-top: 1px solid #d8e2ee;
            color: #94a3b8;
            font-size: 10px;
            text-align: center;
          }

          @media print {
            body {
              background: #ffffff;
            }

            .print-toolbar {
              display: none;
            }

            .paper {
              width: auto;
              min-height: auto;
              margin: 0;
              padding: 0;
              box-shadow: none;
              background: #ffffff;
            }

            .standard-card {
              margin-bottom: 9px;
            }
          }
        </style>
      </head>
      <body>
        <div class="print-toolbar">
          <button type="button" onclick="window.print()">打印 / 保存 PDF</button>
          <button type="button" onclick="window.close()">关闭</button>
        </div>
        <main class="paper">
          <header class="report-header">
            <div class="report-kicker">INSPECTION STANDARD EXPORT</div>
            <h1 class="report-title">巡检规范导出</h1>
            <div class="report-meta">
              <span>导出时间：${escapeHtml(getPrintDateText())}</span>
              <span>规范数量：${exportList.length} 条</span>
              <span>来源：业务督导中心数智管理平台</span>
            </div>
          </header>
          <section class="filter-tags">
            ${filterHtml || '<span class="filter-tag">全部规范</span>'}
          </section>
          <section class="standard-list">
            ${exportList.map((item, index) => buildStandardPrintCard(item, index)).join('')}
          </section>
          <footer class="report-footer">本文件按当前筛选条件生成，仅用于巡检规范查阅、打印与留存。</footer>
        </main>
      </body>
    </html>`
}

const exportStandards = async () => {
  if (!filteredList.value.length) {
    showCopyToast('当前没有可导出的规范。', 'error')
    return
  }

  try {
    await ensureExportTemplateFieldsLoaded(true)
    await fetchExportTemplateSelection()
  } catch (error) {
    showCopyToast('读取导出模板字段失败，请稍后重试。', 'error')
    return
  }

  const printWindow = window.open('', '_blank', 'width=1080,height=780')
  if (!printWindow) {
    showCopyToast('浏览器阻止了导出窗口，请允许弹窗后重试。', 'error')
    return
  }

  printWindow.document.open()
  printWindow.document.write(buildStandardsPrintDocument())
  printWindow.document.close()
  printWindow.focus()
  window.setTimeout(() => {
    printWindow.print()
  }, 300)
  showCopyToast('已生成A4导出页面，可在打印窗口保存为PDF。', 'success')
}

watch(
  () => filters.value.inspectionTableId,
  async (value) => {
    copyMessage.value = ''
    page.value = 1
    activeStandard.value = null
    standards.value = []

    try {
      await fetchInspectionTableFields()
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

watch(
  areaPrimaryFilterValue,
  () => {
    const secondaryKey = areaSecondaryField.value?.field_key
    if (!secondaryKey || !dynamicFilters.value[secondaryKey]) return
    dynamicFilters.value = {
      ...dynamicFilters.value,
      [secondaryKey]: ''
    }
  }
)

onMounted(async () => {
  if (!hasPermission) return
  try {
    await fetchInspectionTables()
    await fetchInspectionTableFields()
    await fetchStandards()
  } catch (error) {
    inspectionTables.value = []
    inspectionTableFields.value = []
    standards.value = []
  }
})

onBeforeUnmount(() => {
  if (copyMessageTimer) {
    clearTimeout(copyMessageTimer)
    copyMessageTimer = null
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

.filter-item-public label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.filter-item-public label::after {
  content: '公共';
  padding: 2px 7px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0e7490;
  font-size: 11px;
  font-weight: 800;
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

.filter-item-disabled label {
  color: #94a3b8;
}

.filter-item input:disabled,
.filter-item select:disabled {
  cursor: not-allowed;
  color: #94a3b8;
  background: #f1f5f9;
  border-color: #e2e8f0;
  box-shadow: none;
}

.filter-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.btn-export {
  min-width: 112px;
}

.btn-export-template {
  min-width: 164px;
}

.template-modal {
  position: fixed;
  inset: 0;
  z-index: 1800;
  padding: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(10px);
}

.template-modal-card {
  width: min(1080px, 100%);
  max-height: min(860px, calc(100vh - 48px));
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.template-modal-header {
  padding: 24px 26px 18px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  border-bottom: 1px solid #e7edf4;
  background:
    radial-gradient(circle at 8% 0%, rgba(37, 99, 235, 0.12), transparent 32%),
    #ffffff;
}

.template-kicker {
  color: #2563eb;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.14em;
  margin-bottom: 8px;
}

.template-modal-header h3 {
  margin: 0;
  color: #0f172a;
  font-size: 26px;
  line-height: 1.35;
}

.template-modal-header p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.7;
}

.template-close-btn {
  width: 38px;
  height: 38px;
  border-radius: 999px;
  border: 1px solid #d7e0ea;
  background: #ffffff;
  color: #64748b;
  font-size: 24px;
  cursor: pointer;
}

.template-close-btn:hover {
  color: #0f172a;
  background: #f8fafc;
}

.template-modal-toolbar {
  padding: 16px 26px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  border-bottom: 1px solid #e7edf4;
  background: #f8fafc;
  flex-wrap: wrap;
}

.template-stat {
  color: #64748b;
  font-size: 14px;
  font-weight: 800;
}

.template-stat strong {
  color: #2563eb;
  font-size: 20px;
}

.template-toolbar-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.template-loading,
.template-empty-fields {
  padding: 28px;
  color: #64748b;
  text-align: center;
  line-height: 1.8;
}

.template-table-list {
  padding: 18px 22px 22px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: #f8fafc;
}

.template-table-card {
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: #ffffff;
  overflow: hidden;
}

.template-table-head {
  padding: 16px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #eef2f7;
}

.template-table-head h4 {
  margin: 0 0 4px;
  color: #0f172a;
  font-size: 16px;
}

.template-table-head span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.template-table-actions {
  display: flex;
  gap: 8px;
}

.mini-btn {
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid #d7e0ea;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.mini-btn:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.template-field-grid {
  padding: 16px 18px 18px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.template-field-option {
  min-height: 48px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #ffffff;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.template-field-option:hover {
  border-color: #bfdbfe;
  background: #f8fbff;
}

.template-field-option input {
  margin-top: 3px;
  accent-color: #2563eb;
}

.template-field-option span {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.template-field-option strong {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.45;
  word-break: break-word;
}

.template-field-option em {
  width: fit-content;
  padding: 2px 7px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0e7490;
  font-style: normal;
  font-size: 11px;
  font-weight: 900;
}

.template-modal-footer {
  padding: 16px 26px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  border-top: 1px solid #e7edf4;
  background: #ffffff;
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

.copy-toast {
  position: fixed;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: min(calc(100vw - 32px), 420px);
  z-index: 1500;
  font-size: 14px;
  line-height: 1.7;
  color: #1d4ed8;
  background: rgba(239, 246, 255, 0.98);
  border: 1px solid #bfdbfe;
  border-radius: 14px;
  padding: 12px 14px;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.16);
  backdrop-filter: blur(8px);
  text-align: center;
  animation: copy-toast-pulse 1.2s ease-in-out infinite;
}

.copy-toast.success {
  color: #166534;
  background: rgba(236, 253, 245, 0.98);
  border-color: #bbf7d0;
}

.copy-toast.error {
  color: #b91c1c;
  background: rgba(254, 242, 242, 0.98);
  border-color: #fecaca;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, calc(-50% + 12px));
}

@keyframes copy-toast-pulse {
  0%,
  100% {
    box-shadow: 0 14px 28px rgba(15, 23, 42, 0.16);
  }

  50% {
    box-shadow: 0 18px 36px rgba(37, 99, 235, 0.24);
  }
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

.empty-detail-compact {
  min-height: 150px;
  border: 1px dashed #cbd5e1;
  border-radius: 16px;
  background: #f8fafc;
  margin-top: 4px;
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

  .template-field-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
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

  .template-modal {
    padding: 12px;
    align-items: stretch;
  }

  .template-modal-card {
    max-height: calc(100vh - 24px);
  }

  .template-modal-header,
  .template-modal-toolbar,
  .template-modal-footer {
    padding-left: 16px;
    padding-right: 16px;
  }

  .template-modal-header h3 {
    font-size: 22px;
  }

  .template-table-list {
    padding: 14px;
  }

  .template-table-head,
  .template-modal-toolbar,
  .template-modal-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .template-toolbar-actions,
  .template-table-actions,
  .template-modal-footer {
    width: 100%;
  }

  .template-toolbar-actions .btn,
  .template-modal-footer .btn {
    flex: 1;
  }

  .template-field-grid {
    grid-template-columns: 1fr;
  }
}
</style>
