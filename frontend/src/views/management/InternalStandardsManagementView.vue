<template>
  <div class="page-shell internal-standard-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">管理系统</div>
        <h2>巡检规范库数据管理</h2>
        <p class="page-desc">维护业务督导中心自建内部规范，并建立内部规范与事业部外部规范的双向追溯关系。</p>
      </div>
      <div class="header-actions">
        <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchAll">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
        <button class="btn btn-secondary" type="button" :disabled="loading || saving" @click="exportBackup">
          导出备份
        </button>
        <button class="btn btn-secondary" type="button" :disabled="loading || saving" @click="triggerImportBackup">
          导入备份
        </button>
        <input ref="importFileInput" class="visually-hidden-file" type="file" accept="application/json,.json"
          :disabled="loading || saving" @change="handleImportBackup" />
        <button class="btn btn-secondary" type="button" :disabled="loading || saving" @click="openFieldDialog">
          字段配置
        </button>
        <button class="btn btn-primary" type="button" :disabled="loading || saving" @click="openStandardDialog()">
          新增内部规范
        </button>
      </div>
    </div>

    <div v-if="!hasPermission" class="card-surface permission-card">
      <div class="permission-icon">!</div>
      <div class="permission-title">无权限访问</div>
      <div class="permission-desc">当前账号无权访问巡检规范库数据管理页面。</div>
    </div>

    <template v-else>
      <div v-if="message.text" class="message-card" :class="message.type">{{ message.text }}</div>

      <section class="card-surface list-card">
        <div class="list-head">
          <div>
            <div class="section-kicker">内部规范清单</div>
            <h3>共 {{ filteredInternalStandards.length }} 条内部规范</h3>
          </div>
          <div class="list-search-wrap">
            <input v-model.trim="keyword" class="list-search" type="search" placeholder="搜索内部规范ID、字段内容或外部规范ID" />
          </div>
        </div>

        <div v-if="filterableFields.length" class="field-filter-panel">
          <label v-for="field in filterableFields" :key="field.field_key" class="field-filter-item">
            <span>{{ field.field_label }}</span>
            <select v-model="fieldFilters[field.field_key]">
              <option value="">全部</option>
              <option v-for="value in getInternalFieldOptions(field.field_key)" :key="value" :value="value">
                {{ value }}
              </option>
            </select>
          </label>
          <button class="btn btn-secondary btn-sm" type="button" @click="clearFilters">清空筛选</button>
        </div>

        <div class="schema-overview">
          <span v-if="internalFields.length">当前字段：{{ internalFields.map((field) => field.field_label).join('、') }}</span>
          <span v-else>当前还没有配置内部规范字段，请先点击“字段配置”。</span>
        </div>

        <div class="internal-list">
          <article v-for="item in filteredInternalStandards" :key="item.id" class="internal-card">
            <div class="internal-card-top">
              <div>
                <strong>{{ item.internal_standard_id }}</strong>
                <span :class="['status-pill', item.is_active ? 'success' : 'neutral']">
                  {{ item.is_active ? '启用' : '停用' }}
                </span>
              </div>
              <div class="card-actions">
                <button class="btn btn-secondary btn-sm" type="button" @click="openStandardDialog(item)">编辑</button>
                <button class="btn btn-danger btn-sm" type="button" :disabled="saving" @click="deleteStandard(item)">删除</button>
              </div>
            </div>

            <div class="field-value-grid">
              <div v-for="field in internalFields" :key="field.field_key" class="field-value-item">
                <span>{{ field.field_label }}</span>
                <strong>{{ getFieldValue(item, field.field_key) || '-' }}</strong>
              </div>
              <div v-if="!internalFields.length" class="field-value-item empty-schema">
                <span>字段配置</span>
                <strong>未配置</strong>
              </div>
            </div>

            <div class="link-summary">
              <span>挂载外部规范 {{ item.linked_externals?.length || 0 }} 条</span>
              <em v-if="item.linked_externals?.length">
                {{ item.linked_externals.slice(0, 3).map((link) => link.external_standard_id).join('、') }}
              </em>
              <em v-else>尚未挂载外部规范</em>
            </div>
          </article>

          <div v-if="!loading && !filteredInternalStandards.length" class="empty-block">
            暂无内部规范，可先配置字段，再点击“新增内部规范”开始维护。
          </div>
          <div v-if="loading" class="empty-block">正在加载巡检规范库数据...</div>
        </div>
      </section>
    </template>

    <div v-if="fieldDialog.visible" class="modal-overlay">
      <div class="modal-panel field-modal card-surface" @click.stop>
        <div class="modal-head">
          <div>
            <div class="section-kicker">字段配置</div>
            <h3>内部规范通用字段</h3>
            <p>这些字段会应用到所有内部规范，字段顺序决定新增规范时的填写顺序。</p>
          </div>
          <button class="modal-close" type="button" @click="closeFieldDialog">×</button>
        </div>

        <div class="field-config-list">
          <div v-for="(field, index) in fieldDialog.fields" :key="field.local_id" class="field-config-row">
            <span class="field-order">字段 {{ index + 1 }}</span>
            <input v-model.trim="field.field_label" type="text" placeholder="字段名称，例如：区域、环节、规范事项" />
            <label class="filter-switch">
              <input v-model="field.is_filterable" type="checkbox" />
              可筛选
            </label>
            <label class="filter-switch">
              <input v-model="field.is_long_text" type="checkbox" />
              长内容
            </label>
            <div class="field-row-actions">
              <button class="btn btn-secondary btn-sm" type="button" :disabled="index === 0" @click="moveField(index, -1)">上移</button>
              <button class="btn btn-secondary btn-sm" type="button" :disabled="index === fieldDialog.fields.length - 1"
                @click="moveField(index, 1)">下移</button>
              <button class="btn btn-danger btn-sm" type="button" @click="removeField(index)">删除</button>
            </div>
          </div>
          <div v-if="!fieldDialog.fields.length" class="empty-schema-card">
            当前没有字段。新增内部规范前，请先添加至少一个字段。
          </div>
        </div>
        <div v-if="fieldDialog.error" class="dialog-message error">{{ fieldDialog.error }}</div>

        <div class="modal-actions split-actions">
          <button class="btn btn-secondary" type="button" @click="addField">添加字段</button>
          <div>
            <button class="btn btn-secondary" type="button" @click="closeFieldDialog">取消</button>
            <button class="btn btn-primary" type="button" :disabled="saving" @click="saveFields">
              {{ saving ? '保存中...' : '保存字段配置' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="standardDialog.visible" class="modal-overlay">
      <div class="modal-panel standard-modal card-surface" @click.stop>
        <div class="modal-head">
          <div>
            <div class="section-kicker">{{ standardDialog.form.id ? '编辑内部规范' : '新增内部规范' }}</div>
            <h3>{{ standardDialog.form.id ? standardDialog.form.internal_standard_id : '系统自动生成内部规范ID' }}</h3>
            <p>先填写内部规范字段，再选择需要挂载的外部规范。</p>
          </div>
          <button class="modal-close" type="button" @click="closeStandardDialog">×</button>
        </div>

        <div class="step-tabs">
          <button type="button" :class="{ active: standardDialog.step === 1 }" @click="standardDialog.step = 1">
            1. 填写字段
          </button>
          <button type="button" :class="{ active: standardDialog.step === 2 }" @click="standardDialog.step = 2">
            2. 挂载外部规范
          </button>
        </div>

        <div v-if="standardDialog.step === 1" class="standard-step">
          <div v-if="!internalFields.length" class="empty-schema-card">
            当前还没有配置字段。请先关闭本弹窗，点击页面右上角“字段配置”。
          </div>
          <div v-else class="standard-field-grid">
            <label v-for="(field, index) in internalFields" :key="field.field_key" class="standard-field-item">
              <span>{{ field.field_label }}<em v-if="index === 0">用于生成内部规范ID</em></span>
              <textarea v-model.trim="standardDialog.form.field_values[field.field_key]"
                :rows="field.is_long_text ? 6 : 2"
                :class="{ 'long-text-input': field.is_long_text }"
                :placeholder="index === 0 ? '例如：配电间' : '填写字段内容，空值会显示为 -'"></textarea>
            </label>
          </div>
          <label class="switch-field">
            <input v-model="standardDialog.form.is_active" type="checkbox" />
            启用这条内部规范
          </label>
        </div>

        <div v-else class="standard-step">
          <div class="external-toolbar">
            <label>
              <span>按检查表筛选</span>
              <select v-model="standardDialog.externalTableId">
                <option value="">全部检查表</option>
                <option v-for="table in externalTableOptions" :key="table.id" :value="String(table.id)">
                  {{ table.name }}
                </option>
              </select>
            </label>
            <label>
              <span>搜索外部规范</span>
              <input v-model.trim="standardDialog.externalKeyword" type="search" placeholder="搜索外部规范ID、检查表名称或规范内容" />
            </label>
          </div>

          <div class="selected-links">
            <span v-for="link in standardDialog.form.external_links" :key="link.external_standard_id" class="selected-link">
              外部规范ID {{ link.external_standard_id }}
              <button type="button" @click="removeExternalLink(link.external_standard_id)">×</button>
            </span>
            <span v-if="!standardDialog.form.external_links.length" class="empty-selected">尚未挂载外部规范。</span>
          </div>

          <div class="external-list">
            <button v-for="item in filteredExternalStandards" :key="item.external_standard_id" type="button"
              class="external-card" :class="{ selected: isExternalSelected(item), disabled: isExternalLocked(item) }"
              :disabled="isExternalLocked(item)" @click="toggleExternal(item)">
              <div>
                <strong>外部规范ID {{ item.external_standard_id }}</strong>
                <span>{{ item.inspection_table_name }}</span>
              </div>
              <p>{{ item.standard_detail_text || '暂无外部规范详情。' }}</p>
              <em v-if="item.linked_internal_standard_id">
                已关联内部规范 {{ item.linked_internal_standard_id }}
              </em>
              <em v-else>未关联内部规范</em>
            </button>
            <div v-if="!filteredExternalStandards.length" class="empty-schema-card">没有匹配的外部规范。</div>
          </div>
        </div>
        <div v-if="standardDialog.error" class="dialog-message error">{{ standardDialog.error }}</div>

        <div class="modal-actions split-actions">
          <button class="btn btn-secondary" type="button" :disabled="standardDialog.step === 1" @click="standardDialog.step = 1">
            上一步
          </button>
          <div>
            <button class="btn btn-secondary" type="button" @click="closeStandardDialog">取消</button>
            <button v-if="standardDialog.step === 1" class="btn btn-primary" type="button" :disabled="!internalFields.length"
              @click="standardDialog.step = 2">
              下一步
            </button>
            <button v-else class="btn btn-primary" type="button" :disabled="saving" @click="saveStandard">
              {{ saving ? '保存中...' : standardDialog.form.id ? '保存修改' : '创建内部规范' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onMounted, reactive, ref } from 'vue'

const currentUserId = localStorage.getItem('user_id') || ''
const currentRole = localStorage.getItem('user_role') || ''
let localPermissions = {}
try {
  localPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch (error) {
  localPermissions = {}
}

const hasPermission = currentRole === 'root' || Boolean(localPermissions.manage_internal_standards)
const loading = ref(false)
const saving = ref(false)
const keyword = ref('')
const internalFields = ref([])
const internalStandards = ref([])
const externalStandards = ref([])
const importFileInput = ref(null)
const fieldFilters = reactive({})
const message = reactive({ text: '', type: 'info' })
let messageTimer = null

const createEmptyStandardForm = () => ({
  id: null,
  internal_standard_id: '',
  field_values: {},
  is_active: true,
  external_links: []
})

const fieldDialog = reactive({
  visible: false,
  fields: [],
  error: ''
})

const standardDialog = reactive({
  visible: false,
  step: 1,
  externalKeyword: '',
  externalTableId: '',
  form: createEmptyStandardForm(),
  error: ''
})

const setMessage = (text, type = 'info') => {
  if (messageTimer) window.clearTimeout(messageTimer)
  message.text = text
  message.type = type
  if (text) {
    messageTimer = window.setTimeout(() => {
      message.text = ''
      messageTimer = null
    }, 2600)
  }
}

const getFieldValue = (item, fieldKey) => {
  return String(item?.field_values?.[fieldKey] ?? '').trim()
}

const filterableFields = computed(() => internalFields.value.filter((field) => field.is_filterable))

const filteredInternalStandards = computed(() => {
  const text = keyword.value.toLowerCase()
  return internalStandards.value.filter((item) => {
    const fieldText = internalFields.value
      .map((field) => getFieldValue(item, field.field_key))
      .join(' ')
    const externalText = (item.linked_externals || [])
      .map((link) => link.external_standard_id)
      .join(' ')
    const keywordMatched = !text || [
      item.internal_standard_id,
      fieldText,
      externalText
    ].join(' ').toLowerCase().includes(text)
    if (!keywordMatched) return false

    return filterableFields.value.every((field) => {
      const filterValue = String(fieldFilters[field.field_key] || '').trim()
      if (!filterValue) return true
      return getFieldValue(item, field.field_key) === filterValue
    })
  })
})

const externalTableOptions = computed(() => {
  const map = new Map()
  externalStandards.value.forEach((item) => {
    if (!item.inspection_table_id) return
    map.set(String(item.inspection_table_id), {
      id: String(item.inspection_table_id),
      name: item.inspection_table_name || `检查表 ${item.inspection_table_id}`
    })
  })
  return [...map.values()]
})

const filteredExternalStandards = computed(() => {
  const keywordText = standardDialog.externalKeyword.toLowerCase()
  const tableId = String(standardDialog.externalTableId || '')
  return externalStandards.value.filter((item) => {
    if (tableId && String(item.inspection_table_id) !== tableId) return false
    if (!keywordText) return true
    return [
      item.external_standard_id,
      item.inspection_table_name,
      item.standard_detail_text,
      item.linked_internal_standard_id
    ].join(' ').toLowerCase().includes(keywordText)
  }).slice(0, 100)
})

const getInternalFieldOptions = (fieldKey) => {
  return [...new Set(internalStandards.value
    .map((item) => getFieldValue(item, fieldKey))
    .filter(Boolean))]
}

const clearFilters = () => {
  Object.keys(fieldFilters).forEach((key) => {
    fieldFilters[key] = ''
  })
}

const hydrateStandardFieldValues = (item = {}) => {
  const values = {}
  internalFields.value.forEach((field) => {
    values[field.field_key] = String(item.field_values?.[field.field_key] ?? '').trim()
  })
  return values
}

const fetchInternalStandards = async () => {
  const response = await axios.get('/api/management/internal-standards', {
    params: { user_id: currentUserId, _ts: Date.now() }
  })
  internalFields.value = response.data?.fields || []
  internalStandards.value = response.data?.items || []
}

const fetchExternalStandards = async () => {
  const response = await axios.get('/api/external-standards', {
    params: { _ts: Date.now() }
  })
  externalStandards.value = response.data?.items || []
}

const fetchAll = async () => {
  if (!hasPermission) return
  try {
    loading.value = true
    const [internalResult, externalResult] = await Promise.allSettled([
      fetchInternalStandards(),
      fetchExternalStandards()
    ])
    if (internalResult.status === 'rejected') {
      throw internalResult.reason
    }
    if (externalResult.status === 'rejected') {
      setMessage(externalResult.reason?.response?.data?.error || '外部规范数据加载失败，内部规范清单已刷新。', 'error')
    }
  } catch (error) {
    setMessage(error?.response?.data?.error || '规范数据加载失败。', 'error')
  } finally {
    loading.value = false
  }
}

const openFieldDialog = () => {
  fieldDialog.fields = internalFields.value.map((field) => ({
    ...field,
    local_id: field.field_key || `field_${Date.now()}_${Math.random().toString(16).slice(2)}`
  }))
  fieldDialog.error = ''
  fieldDialog.visible = true
}

const closeFieldDialog = () => {
  fieldDialog.visible = false
}

const addField = () => {
  fieldDialog.error = ''
  fieldDialog.fields.push({
    local_id: `field_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    field_key: '',
    field_label: '',
    is_filterable: true,
    is_long_text: false
  })
}

const hasFieldContent = (fieldKey) => {
  return internalStandards.value.some((item) => String(item.field_values?.[fieldKey] || '').trim())
}

const removeField = (index) => {
  const field = fieldDialog.fields[index]
  if (field?.field_key && hasFieldContent(field.field_key)) {
    const confirmed = window.confirm(`字段【${field.field_label}】已经有内部规范数据。删除后这些内容会永久丢失，确定继续吗？`)
    if (!confirmed) return
  }
  fieldDialog.fields.splice(index, 1)
}

const moveField = (index, offset) => {
  const targetIndex = index + offset
  if (targetIndex < 0 || targetIndex >= fieldDialog.fields.length) return
  const [item] = fieldDialog.fields.splice(index, 1)
  fieldDialog.fields.splice(targetIndex, 0, item)
}

const saveFields = async () => {
  try {
    saving.value = true
    fieldDialog.error = ''
    const response = await axios.put('/api/management/internal-standards/fields', {
      user_id: currentUserId,
      fields: fieldDialog.fields.map((field) => ({
        field_key: field.field_key,
        field_label: field.field_label,
        is_filterable: field.is_filterable,
        is_long_text: field.is_long_text
      }))
    })
    internalFields.value = response.data?.fields || []
    setMessage(response.data?.message || '字段配置已保存。', 'success')
    fieldDialog.visible = false
    await fetchAll()
  } catch (error) {
    fieldDialog.error = error?.response?.data?.error || '字段配置保存失败。'
  } finally {
    saving.value = false
  }
}

const openStandardDialog = (item = null) => {
  standardDialog.visible = true
  standardDialog.step = 1
  standardDialog.externalKeyword = ''
  standardDialog.externalTableId = ''
  standardDialog.error = ''
  standardDialog.form = item
    ? {
        id: item.id,
        internal_standard_id: item.internal_standard_id,
        field_values: hydrateStandardFieldValues(item),
        is_active: Boolean(item.is_active),
        external_links: (item.linked_externals || []).map((link) => ({
          external_standard_id: link.external_standard_id,
          external_inspection_table_id: link.external_inspection_table_id
        }))
      }
    : {
        ...createEmptyStandardForm(),
        field_values: hydrateStandardFieldValues()
      }
}

const closeStandardDialog = () => {
  standardDialog.visible = false
}

const isExternalSelected = (item) => {
  return standardDialog.form.external_links.some((link) => {
    return String(link.external_standard_id) === String(item.external_standard_id)
  })
}

const isExternalLocked = (item) => {
  return Boolean(item.linked_internal_standard_id) &&
    item.linked_internal_standard_id !== standardDialog.form.internal_standard_id
}

const toggleExternal = (item) => {
  if (isExternalLocked(item)) return
  standardDialog.error = ''
  if (isExternalSelected(item)) {
    removeExternalLink(item.external_standard_id)
    return
  }
  standardDialog.form.external_links.push({
    external_standard_id: item.external_standard_id,
    external_inspection_table_id: item.inspection_table_id
  })
}

const removeExternalLink = (externalStandardId) => {
  standardDialog.form.external_links = standardDialog.form.external_links.filter((link) => {
    return String(link.external_standard_id) !== String(externalStandardId)
  })
}

const saveStandard = async () => {
  if (!internalFields.value.length) {
    standardDialog.error = '请先配置内部规范字段。'
    return
  }
  const firstField = internalFields.value[0]
  if (!String(standardDialog.form.field_values[firstField.field_key] || '').trim()) {
    standardDialog.error = `请填写首个字段【${firstField.field_label}】。`
    standardDialog.step = 1
    return
  }

  const payload = {
    user_id: currentUserId,
    field_values: standardDialog.form.field_values,
    is_active: standardDialog.form.is_active,
    external_links: standardDialog.form.external_links
  }

  try {
    saving.value = true
    standardDialog.error = ''
    const response = standardDialog.form.id
      ? await axios.put(`/api/management/internal-standards/${standardDialog.form.id}`, payload)
      : await axios.post('/api/management/internal-standards', payload)
    setMessage(response.data?.message || '内部规范已保存。', 'success')
    standardDialog.visible = false
    await fetchAll()
  } catch (error) {
    standardDialog.error = error?.response?.data?.error || '保存内部规范失败。'
  } finally {
    saving.value = false
  }
}

const deleteStandard = async (item) => {
  if (!item?.id) return
  const confirmed = window.confirm(`确定删除内部规范【${item.internal_standard_id}】吗？相关外部规范挂载关系也会解除。`)
  if (!confirmed) return
  try {
    saving.value = true
    const response = await axios.delete(`/api/management/internal-standards/${item.id}`, {
      params: { user_id: currentUserId }
    })
    setMessage(response.data?.message || '内部规范已删除。', 'success')
    await fetchAll()
  } catch (error) {
    setMessage(error?.response?.data?.error || '删除内部规范失败。', 'error')
  } finally {
    saving.value = false
  }
}

const exportBackup = async () => {
  try {
    loading.value = true
    const response = await axios.get('/api/management/internal-standards/export', {
      params: { user_id: currentUserId, _ts: Date.now() },
      responseType: 'blob'
    })
    const disposition = response.headers?.['content-disposition'] || ''
    const match = disposition.match(/filename=([^;]+)/i)
    const filename = match?.[1]?.replace(/"/g, '') || `ywddzx_internal_standards_backup_${Date.now()}.json`
    const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    setMessage('巡检规范库备份已导出。', 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || '导出备份失败。', 'error')
  } finally {
    loading.value = false
  }
}

const handleImportBackup = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  const confirmed = window.confirm('导入备份会覆盖当前全部内部巡检规范、字段配置和挂载关系，确定继续吗？')
  if (!confirmed) {
    event.target.value = ''
    return
  }

  try {
    saving.value = true
    const formData = new FormData()
    formData.append('user_id', currentUserId)
    formData.append('file', file)
    const response = await axios.post('/api/management/internal-standards/import', formData)
    await fetchAll()
    setMessage(response.data?.message || '巡检规范库备份已导入。', 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || '导入备份失败。', 'error')
  } finally {
    saving.value = false
    if (importFileInput.value) importFileInput.value.value = ''
  }
}

const triggerImportBackup = () => {
  if (loading.value || saving.value) return
  importFileInput.value?.click()
}

onMounted(fetchAll)
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-surface {
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid #dbe4ee;
  border-radius: 24px;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.07);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 26px 28px;
  background:
    radial-gradient(circle at 92% 8%, rgba(20, 184, 166, 0.13), transparent 28%),
    rgba(255, 255, 255, 0.97);
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
.list-head h3,
.modal-head h3 {
  margin: 0;
  color: #0f172a;
}

.page-header h2 {
  font-size: 34px;
}

.page-desc,
.modal-head p {
  margin: 8px 0 0;
  color: #64748b;
  line-height: 1.8;
}

.header-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
  max-width: 560px;
}

.btn {
  min-height: 42px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
  font-weight: 850;
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.18s ease;
}

.btn-sm {
  min-height: 34px;
  padding: 0 11px;
  font-size: 12px;
}

.btn-primary {
  border-color: #0f766e;
  background: #0f766e;
  color: #fff;
}

.btn-danger {
  border-color: #fecaca;
  background: #fff5f5;
  color: #b91c1c;
}

.btn-secondary:hover:not(:disabled) {
  background: #f8fafc;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.visually-hidden-file {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  border: 0;
  opacity: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}

.message-card {
  padding: 13px 16px;
  border-radius: 16px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 14px;
  font-weight: 800;
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

.dialog-message {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 13px;
  font-weight: 850;
  line-height: 1.6;
}

.dialog-message.error {
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #b91c1c;
}

.list-card {
  padding: 22px;
}

.list-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.list-search-wrap {
  min-width: min(420px, 42vw);
}

.list-search,
.field-filter-item select,
.field-config-row input,
.standard-field-item textarea,
.external-toolbar input,
.external-toolbar select {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
  box-sizing: border-box;
}

.list-search,
.field-filter-item select,
.field-config-row input,
.external-toolbar input,
.external-toolbar select {
  height: 42px;
  padding: 0 13px;
}

.field-filter-panel {
  display: grid;
  grid-template-columns: repeat(4, minmax(160px, 1fr)) auto;
  gap: 12px;
  align-items: end;
  padding: 14px;
  border: 1px solid #e5edf5;
  border-radius: 18px;
  background: #f8fafc;
  margin-bottom: 14px;
}

.field-filter-item,
.standard-field-item,
.external-toolbar label {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.field-filter-item span,
.standard-field-item span,
.external-toolbar span {
  color: #475569;
  font-size: 12px;
  font-weight: 900;
}

.standard-field-item em {
  margin-left: 8px;
  color: #0f766e;
  font-style: normal;
  font-size: 12px;
}

.schema-overview {
  padding: 12px 14px;
  border-radius: 16px;
  background: linear-gradient(90deg, #ecfeff, #f8fafc);
  color: #475569;
  font-size: 13px;
  font-weight: 800;
  margin-bottom: 14px;
}

.internal-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.internal-card {
  border: 1px solid #e5edf5;
  border-radius: 20px;
  background: #fff;
  padding: 16px;
}

.internal-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.internal-card-top strong {
  color: #0f766e;
  font-size: 18px;
  margin-right: 8px;
}

.card-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.status-pill {
  display: inline-flex;
  min-height: 28px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 900;
}

.status-pill.success {
  background: #ecfdf5;
  color: #15803d;
}

.status-pill.neutral {
  background: #f1f5f9;
  color: #64748b;
}

.field-value-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.field-value-item {
  padding: 10px 12px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #e5edf5;
}

.field-value-item span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
  margin-bottom: 5px;
}

.field-value-item strong {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-line;
  word-break: break-word;
}

.link-summary {
  margin-top: 12px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.link-summary em {
  color: #0f766e;
  font-style: normal;
  text-align: right;
}

.empty-block,
.empty-schema-card {
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 20px;
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: #f8fafc;
  color: #64748b;
  line-height: 1.8;
  grid-column: 1 / -1;
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
  font-size: 22px;
  font-weight: 900;
  color: #0f172a;
  margin-bottom: 8px;
}

.permission-desc {
  color: #64748b;
  font-size: 14px;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(8px);
}

.modal-panel {
  width: min(1120px, calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  overflow: auto;
  padding: 24px;
  box-sizing: border-box;
  background:
    radial-gradient(circle at 0 0, rgba(20, 184, 166, 0.1), transparent 30%),
    rgba(255, 255, 255, 0.98);
}

.field-modal {
  width: min(980px, calc(100vw - 32px));
}

.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.modal-close {
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 999px;
  background: #f1f5f9;
  color: #0f172a;
  font-size: 24px;
  cursor: pointer;
}

.field-config-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-config-row {
  display: grid;
  grid-template-columns: 86px minmax(220px, 1fr) 92px 92px minmax(220px, auto);
  gap: 12px;
  align-items: center;
  padding: 14px;
  border: 1px solid #e5edf5;
  border-radius: 18px;
  background: #f8fafc;
  box-sizing: border-box;
}

.field-order {
  color: #64748b;
  font-size: 13px;
  font-weight: 900;
}

.filter-switch,
.switch-field {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #475569;
  font-size: 13px;
  font-weight: 900;
}

.field-row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.modal-actions {
  margin-top: 18px;
}

.split-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.split-actions > div {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.step-tabs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  padding: 6px;
  border-radius: 18px;
  background: #f1f5f9;
  margin-bottom: 18px;
}

.step-tabs button {
  min-height: 44px;
  border: 0;
  border-radius: 14px;
  background: transparent;
  color: #64748b;
  font-weight: 900;
  cursor: pointer;
}

.step-tabs button.active {
  background: #fff;
  color: #0f766e;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.standard-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.standard-field-item textarea {
  min-height: 88px;
  padding: 12px;
  resize: vertical;
  line-height: 1.7;
}

.standard-field-item textarea.long-text-input {
  min-height: 150px;
}

.switch-field {
  margin-top: 16px;
}

.external-toolbar {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.selected-links {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e5edf5;
  margin-bottom: 14px;
}

.selected-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 900;
}

.selected-link button {
  border: 0;
  background: transparent;
  color: #0f766e;
  cursor: pointer;
  font-weight: 900;
}

.empty-selected {
  color: #64748b;
  font-size: 13px;
}

.external-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  max-height: 460px;
  overflow: auto;
  padding-right: 4px;
  align-items: stretch;
}

.external-card {
  width: 100%;
  height: 100%;
  border: 1px solid #e5edf5;
  border-radius: 18px;
  background: #fff;
  padding: 14px;
  text-align: left;
  cursor: pointer;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  min-height: 178px;
}

.external-card.selected {
  border-color: #2dd4bf;
  background: #f0fdfa;
}

.external-card.disabled {
  cursor: not-allowed;
  opacity: 0.6;
  background: #f8fafc;
}

.external-card div {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
  min-height: 36px;
}

.external-card strong {
  color: #0f766e;
  min-width: 0;
  word-break: break-word;
}

.external-card span,
.external-card em {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
  word-break: break-word;
}

.external-card p {
  margin: 8px 0;
  color: #334155;
  line-height: 1.75;
  white-space: pre-line;
  flex: 1;
}

@media (max-width: 1100px) {
  .internal-list,
  .external-list,
  .standard-field-grid {
    grid-template-columns: 1fr;
  }

  .field-filter-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .page-header,
  .list-head,
  .modal-head,
  .internal-card-top {
    flex-direction: column;
    align-items: stretch;
  }

  .page-header,
  .list-card,
  .modal-panel {
    padding: 18px;
    border-radius: 22px;
  }

  .page-header h2 {
    font-size: 29px;
  }

  .header-actions,
  .card-actions {
    justify-content: flex-start;
  }

  .list-search-wrap {
    min-width: 0;
    width: 100%;
  }

  .field-filter-panel,
  .field-value-grid,
  .field-config-row,
  .external-toolbar {
    grid-template-columns: 1fr;
  }

  .field-row-actions,
  .split-actions,
  .split-actions > div {
    justify-content: stretch;
  }

  .split-actions .btn,
  .field-row-actions .btn,
  .header-actions .btn {
    width: 100%;
  }

  .modal-overlay {
    align-items: flex-end;
    padding: 12px;
  }

  .modal-panel {
    width: 100%;
    max-height: 92vh;
  }
}
</style>
