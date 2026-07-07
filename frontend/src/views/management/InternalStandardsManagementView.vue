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
        <button class="btn btn-secondary" type="button" :disabled="loading || saving" @click="openTagDialog">
          标签群组
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

      <section class="card-surface usage-mode-card">
        <div>
          <div class="section-kicker">巡检登记规范来源</div>
          <h3>当前使用{{ usageModeLabel }}进行巡检登记</h3>
          <p>{{ usageModeDescription }}</p>
          <span v-if="usageMode.updated_at" class="usage-mode-meta">
            最近调整：{{ usageMode.updated_at }} · {{ usageMode.updated_by_name || usageMode.updated_by_username || '系统' }}
          </span>
        </div>
        <div class="usage-mode-options" role="radiogroup" aria-label="巡检登记规范来源">
          <button type="button" class="usage-mode-option" :class="{ active: usageMode.mode === 'internal' }"
            :disabled="savingUsageMode" @click="updateUsageMode('internal')">
            <strong>内部规范库</strong>
            <span>使用业务督导中心自建内部规范，提交后自动展开到挂载的外部规范。</span>
          </button>
          <button type="button" class="usage-mode-option" :class="{ active: usageMode.mode === 'external' }"
            :disabled="savingUsageMode" @click="updateUsageMode('external')">
            <strong>外部规范库</strong>
            <span>临时使用检查表原件库里的外部规范ID，适合内部规范整理期过渡。</span>
          </button>
        </div>
      </section>

      <section class="card-surface list-card">
        <div class="list-head">
          <div>
            <div class="section-kicker">内部规范清单</div>
            <h3>共 {{ filteredInternalStandards.length }} 条内部规范</h3>
          </div>
          <div class="list-search-wrap">
            <input v-model.trim="keyword" class="list-search" type="search" placeholder="搜索内部规范ID、规范内容、标签或外部规范ID" />
          </div>
        </div>

        <div v-if="filterableTagGroups.length" class="field-filter-panel">
          <label v-for="group in filterableTagGroups" :key="group.id || group.group_type" class="field-filter-item">
            <span>{{ group.group_name }}</span>
            <select v-model="tagFilters[getTagGroupFilterKey(group)]">
              <option value="">全部</option>
              <option v-for="tag in getTagFilterOptions(group)" :key="tag.tag_key || tag.id" :value="tag.tag_name">
                {{ tag.tag_name }}
              </option>
            </select>
          </label>
          <button class="btn btn-secondary btn-sm" type="button" @click="clearFilters">清空筛选</button>
        </div>

        <div class="schema-overview">
          <span>系统标签群组：外部规范ID、检查表；自定义标签群组 {{ customTagGroups.length }} 个。</span>
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

            <div class="internal-content-preview">{{ item.content || '-' }}</div>

            <div class="tag-chip-cloud">
              <span v-for="tag in item.tags || []" :key="`${item.id}-${tag.group_type}-${tag.tag_name}`" class="tag-chip"
                :style="{ '--tag-color': tag.color || '#2563eb' }">
                <em>{{ tag.group_name }}</em>{{ tag.tag_name }}
              </span>
              <span v-if="!(item.tags || []).length" class="empty-selected">暂无标签</span>
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
            暂无内部规范，可先配置标签群组，再点击“新增内部规范”开始维护。
          </div>
          <div v-if="loading" class="empty-block">正在加载巡检规范库数据...</div>
        </div>
      </section>
    </template>

    <div v-if="tagDialog.visible" class="modal-overlay">
      <div class="modal-panel field-modal card-surface" @click.stop>
        <div class="modal-head">
          <div>
            <div class="section-kicker">标签群组</div>
            <h3>内部规范标签体系</h3>
            <p>外部规范ID和检查表是系统标签；这里维护区域、环节、专业等自定义标签群组。</p>
          </div>
          <button class="modal-close" type="button" @click="closeTagDialog">×</button>
        </div>

        <div class="field-config-help">
          <span>每个标签群组可以配置多个标签，内部规范可在同一群组内选择一个或多个标签。</span>
          <span>颜色配置在标签群组上，同一群组内的所有标签会使用同一种颜色。</span>
        </div>

        <div class="field-config-list">
          <div v-for="(group, groupIndex) in tagDialog.groups" :key="group.local_id" class="tag-group-config-card"
            :style="{ '--group-color': group.color || '#2563EB' }">
            <div class="tag-group-card-head">
              <div class="tag-group-title-block">
                <span class="field-order">群组 {{ groupIndex + 1 }}</span>
                <span class="tag-group-color-dot"></span>
                <input v-model.trim="group.group_name" type="text" placeholder="标签群组名称，例如：区域、环节、专业" />
              </div>
              <div class="tag-group-tools">
                <label class="tag-group-color-field">
                  <span>群组颜色</span>
                  <input v-model="group.color" type="color" />
                </label>
                <label class="filter-switch">
                  <input v-model="group.is_filterable" type="checkbox" />
                  <span>可筛选</span>
                </label>
                <div class="field-row-actions">
                  <button class="btn btn-secondary btn-sm" type="button" :disabled="groupIndex === 0" @click="moveTagGroup(groupIndex, -1)">上移</button>
                  <button class="btn btn-secondary btn-sm" type="button" :disabled="groupIndex === tagDialog.groups.length - 1"
                    @click="moveTagGroup(groupIndex, 1)">下移</button>
                  <button class="btn btn-danger btn-sm" type="button" @click="removeTagGroup(groupIndex)">删除群组</button>
                </div>
              </div>
            </div>

            <div class="tag-group-meta-line">
              <span>已配置 {{ group.tags.length }} 个标签</span>
              <span v-if="group.keyword">当前筛选 {{ getVisibleTagRows(group).length }} 个</span>
            </div>

            <div class="tag-config-toolbar">
              <input v-model.trim="group.newTagName" type="text" placeholder="输入标签名称，回车添加"
                @keydown.enter.prevent="addTag(groupIndex)" />
              <button class="btn btn-secondary btn-sm" type="button" @click="addTag(groupIndex)">添加标签</button>
              <input v-model.trim="group.keyword" type="search" placeholder="搜索本群组标签" />
            </div>

            <div class="tag-config-list">
              <div v-for="row in getVisibleTagRows(group)" :key="row.tag.local_id" class="tag-config-row">
                <span class="tag-edit-color-mark"></span>
                <input v-model.trim="row.tag.tag_name" type="text" placeholder="标签名称，例如：加油区、卸油区" />
                <button class="tag-remove-icon-btn" type="button" title="删除标签" @click="removeTag(groupIndex, row.tagIndex)">×</button>
              </div>
              <div v-if="!getVisibleTagRows(group).length" class="empty-tag-inline">
                {{ group.tags.length ? '没有匹配的标签。' : '当前群组还没有标签。' }}
              </div>
            </div>
          </div>
          <div v-if="!tagDialog.groups.length" class="empty-schema-card">
            当前没有自定义标签群组。可以直接新增一个“区域”标签群组开始维护。
          </div>
        </div>
        <div v-if="tagDialog.error" class="dialog-message error">{{ tagDialog.error }}</div>

        <div class="modal-actions split-actions">
          <button class="btn btn-secondary" type="button" @click="addTagGroup">添加标签群组</button>
          <div>
            <button class="btn btn-secondary" type="button" @click="closeTagDialog">取消</button>
            <button class="btn btn-primary" type="button" :disabled="saving" @click="saveTagGroups">
              {{ saving ? '保存中...' : '保存标签群组' }}
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
            <p>填写内部规范内容，再为它绑定外部规范ID并选择标签。</p>
          </div>
          <button class="modal-close" type="button" @click="closeStandardDialog">×</button>
        </div>

        <div class="step-tabs">
          <button type="button" :class="{ active: standardDialog.step === 1 }" @click="standardDialog.step = 1">
            1. 规范内容
          </button>
          <button type="button" :class="{ active: standardDialog.step === 2 }" @click="standardDialog.step = 2">
            2. 标签与外部规范
          </button>
        </div>

        <div v-if="standardDialog.step === 1" class="standard-step">
          <label class="standard-field-item standard-content-editor">
            <span>规范内容<em>用于生成内部规范ID</em></span>
            <textarea v-model.trim="standardDialog.form.content" rows="8"
              placeholder="填写业务督导中心内部整理后的规范内容"></textarea>
          </label>
          <label class="switch-field">
            <input v-model="standardDialog.form.is_active" type="checkbox" />
            启用这条内部规范
          </label>
        </div>

        <div v-else class="standard-step">
          <div class="standard-tag-picker">
            <div class="section-kicker">自定义标签</div>
            <div v-if="customTagGroups.length" class="tag-picker-grid">
              <section v-for="group in customTagGroups" :key="group.id" class="tag-picker-group">
                <strong>{{ group.group_name }}</strong>
                <div class="tag-picker-options">
                  <button v-for="tag in group.tags" :key="tag.id" type="button" class="tag-select-chip"
                    :class="{ selected: isTagSelected(tag.id) }"
                    :style="{ '--tag-color': tag.color || '#2563eb' }"
                    @click="toggleTag(tag.id)">
                    {{ tag.tag_name }}
                  </button>
                </div>
              </section>
            </div>
            <div v-else class="empty-schema-card">暂无自定义标签群组，可先保存外部规范ID标签。</div>
          </div>

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
            <button v-if="standardDialog.step === 1" class="btn btn-primary" type="button"
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
const TAG_COLOR_PALETTE = [
  '#2563EB',
  '#0F766E',
  '#D97706',
  '#DC2626',
  '#7C3AED',
  '#0891B2',
  '#65A30D',
  '#DB2777',
  '#4F46E5',
  '#EA580C'
]
const loading = ref(false)
const saving = ref(false)
const savingUsageMode = ref(false)
const keyword = ref('')
const tagGroups = ref([])
const internalStandards = ref([])
const externalStandards = ref([])
const importFileInput = ref(null)
const tagFilters = reactive({})
const message = reactive({ text: '', type: 'info' })
const usageMode = reactive({
  mode: 'internal',
  mode_label: '内部规范库',
  updated_at: '',
  updated_by_username: '',
  updated_by_name: ''
})
let messageTimer = null

const createEmptyStandardForm = () => ({
  id: null,
  internal_standard_id: '',
  content: '',
  is_active: true,
  external_links: [],
  tag_ids: []
})

const tagDialog = reactive({
  visible: false,
  groups: [],
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

const customTagGroups = computed(() => tagGroups.value.filter((group) => group.group_type === 'custom' && !group.is_system))
const filterableTagGroups = computed(() => tagGroups.value.filter((group) => group.is_filterable))

const usageModeLabel = computed(() => usageMode.mode === 'external' ? '外部规范库' : '内部规范库')
const usageModeDescription = computed(() => usageMode.mode === 'external'
  ? '巡检登记会直接搜索和引用检查表原件库中的外部规范ID，问题仍会挂到对应检查表规范下。'
  : '巡检登记会搜索和引用内部规范ID，并按挂载关系自动写入对应外部规范问题。')

const filteredInternalStandards = computed(() => {
  const text = keyword.value.toLowerCase()
  return internalStandards.value.filter((item) => {
    const tagText = (item.tags || []).map((tag) => `${tag.group_name} ${tag.tag_name}`).join(' ')
    const externalText = (item.linked_externals || [])
      .map((link) => link.external_standard_id)
      .join(' ')
    const keywordMatched = !text || [
      item.internal_standard_id,
      item.content,
      tagText,
      externalText
    ].join(' ').toLowerCase().includes(text)
    if (!keywordMatched) return false

    return filterableTagGroups.value.every((group) => {
      const filterValue = String(tagFilters[getTagGroupFilterKey(group)] || '').trim()
      if (!filterValue) return true
      return (item.tags || []).some((tag) => {
        return tag.group_name === group.group_name && tag.tag_name === filterValue
      })
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

const getTagGroupFilterKey = (group) => String(group.id || group.group_type || group.group_name)

const getTagFilterOptions = (group) => {
  const values = []
  const seen = new Set()
  internalStandards.value.forEach((item) => {
    ;(item.tags || []).forEach((tag) => {
      if (tag.group_name !== group.group_name) return
      const key = tag.tag_key || tag.tag_name
      if (!key || seen.has(key)) return
      seen.add(key)
      values.push(tag)
    })
  })
  return values
}

const clearFilters = () => {
  Object.keys(tagFilters).forEach((key) => {
    tagFilters[key] = ''
  })
}

const createLocalId = (prefix) => `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`

const randomTagGroupColor = (seed = '') => {
  if (seed) {
    let hash = 0
    String(seed).split('').forEach((char) => {
      hash = ((hash << 5) - hash) + char.charCodeAt(0)
      hash |= 0
    })
    return TAG_COLOR_PALETTE[Math.abs(hash) % TAG_COLOR_PALETTE.length]
  }
  return TAG_COLOR_PALETTE[Math.floor(Math.random() * TAG_COLOR_PALETTE.length)]
}

const getVisibleTagRows = (group) => {
  const keywordText = String(group?.keyword || '').trim().toLowerCase()
  return (group?.tags || [])
    .map((tag, tagIndex) => ({ tag, tagIndex }))
    .filter(({ tag }) => !keywordText || String(tag.tag_name || '').toLowerCase().includes(keywordText))
}

const fetchInternalStandards = async () => {
  const response = await axios.get('/api/management/internal-standards', {
    params: { user_id: currentUserId, _ts: Date.now() }
  })
  tagGroups.value = response.data?.tag_groups || []
  internalStandards.value = response.data?.items || []
  Object.assign(usageMode, response.data?.usage_mode || {})
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

const updateUsageMode = async (mode) => {
  if (savingUsageMode.value || usageMode.mode === mode) return
  try {
    savingUsageMode.value = true
    const response = await axios.put('/api/management/internal-standards/usage-mode', {
      user_id: currentUserId,
      mode
    })
    Object.assign(usageMode, response.data?.usage_mode || {})
    setMessage(response.data?.message || '巡检登记规范来源已更新。', 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || '巡检登记规范来源更新失败。', 'error')
  } finally {
    savingUsageMode.value = false
  }
}

const openTagDialog = () => {
  tagDialog.groups = customTagGroups.value.map((group) => ({
    ...group,
    color: group.color || randomTagGroupColor(group.group_name),
    is_filterable: group.is_filterable ?? true,
    keyword: '',
    newTagName: '',
    local_id: group.id || createLocalId('group'),
    tags: (group.tags || []).map((tag) => ({
      ...tag,
      color: group.color || tag.color || randomTagGroupColor(group.group_name),
      local_id: tag.id || createLocalId('tag')
    }))
  }))
  tagDialog.error = ''
  tagDialog.visible = true
}

const closeTagDialog = () => {
  tagDialog.visible = false
}

const addTagGroup = () => {
  tagDialog.error = ''
  tagDialog.groups.push({
    local_id: createLocalId('group'),
    group_name: '',
    color: randomTagGroupColor(),
    is_filterable: true,
    keyword: '',
    newTagName: '',
    tags: []
  })
}

const removeTagGroup = (index) => {
  const group = tagDialog.groups[index]
  if (group?.tags?.some((tag) => internalStandards.value.some((item) => (item.custom_tag_ids || []).includes(tag.id)))) {
    const confirmed = window.confirm(`标签群组【${group.group_name}】已有内部规范使用。删除后这些标签绑定会同步移除，确定继续吗？`)
    if (!confirmed) return
  }
  tagDialog.groups.splice(index, 1)
}

const moveTagGroup = (index, offset) => {
  const targetIndex = index + offset
  if (targetIndex < 0 || targetIndex >= tagDialog.groups.length) return
  const [item] = tagDialog.groups.splice(index, 1)
  tagDialog.groups.splice(targetIndex, 0, item)
}

const addTag = (groupIndex) => {
  const group = tagDialog.groups[groupIndex]
  group.tags.push({
    local_id: createLocalId('tag'),
    tag_name: String(group.newTagName || '').trim(),
    color: group.color || randomTagGroupColor(group.group_name)
  })
  group.newTagName = ''
  group.keyword = ''
}

const removeTag = (groupIndex, tagIndex) => {
  tagDialog.groups[groupIndex].tags.splice(tagIndex, 1)
}

const saveTagGroups = async () => {
  try {
    saving.value = true
    tagDialog.error = ''
    const response = await axios.put('/api/management/internal-standards/tag-groups', {
      user_id: currentUserId,
      tag_groups: tagDialog.groups.map((group) => ({
        id: group.id,
        group_name: group.group_name,
        color: group.color,
        is_filterable: group.is_filterable,
        tags: (group.tags || []).map((tag) => ({
          id: tag.id,
          tag_name: tag.tag_name
        }))
      }))
    })
    tagGroups.value = response.data?.tag_groups || []
    setMessage(response.data?.message || '标签群组已保存。', 'success')
    tagDialog.visible = false
    await fetchAll()
  } catch (error) {
    tagDialog.error = error?.response?.data?.error || '标签群组保存失败。'
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
        content: item.content || '',
        is_active: Boolean(item.is_active),
        tag_ids: [...(item.custom_tag_ids || [])],
        external_links: (item.linked_externals || []).map((link) => ({
          external_standard_id: link.external_standard_id,
          external_inspection_table_id: link.external_inspection_table_id
        }))
      }
    : createEmptyStandardForm()
}

const closeStandardDialog = () => {
  standardDialog.visible = false
}

const isTagSelected = (tagId) => {
  return standardDialog.form.tag_ids.some((item) => String(item) === String(tagId))
}

const toggleTag = (tagId) => {
  const normalizedId = Number.parseInt(tagId, 10)
  if (!Number.isFinite(normalizedId)) return
  if (isTagSelected(normalizedId)) {
    standardDialog.form.tag_ids = standardDialog.form.tag_ids.filter((item) => String(item) !== String(normalizedId))
    return
  }
  standardDialog.form.tag_ids.push(normalizedId)
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
  if (!String(standardDialog.form.content || '').trim()) {
    standardDialog.error = '请填写内部规范内容。'
    standardDialog.step = 1
    return
  }
  if (!standardDialog.form.external_links.length) {
    standardDialog.error = '请至少绑定一个外部规范ID。'
    standardDialog.step = 2
    return
  }

  const payload = {
    user_id: currentUserId,
    content: standardDialog.form.content,
    is_active: standardDialog.form.is_active,
    external_links: standardDialog.form.external_links,
    tag_ids: standardDialog.form.tag_ids
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
  const confirmed = window.confirm('导入备份会覆盖当前全部内部巡检规范、标签群组和挂载关系，确定继续吗？')
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

.usage-mode-card {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(420px, 1.4fr);
  gap: 18px;
  align-items: stretch;
  padding: 22px;
  background:
    radial-gradient(circle at 92% 12%, rgba(20, 184, 166, 0.12), transparent 30%),
    rgba(255, 255, 255, 0.97);
}

.usage-mode-card h3 {
  margin: 0;
  color: #0f172a;
  font-size: 22px;
}

.usage-mode-card p {
  margin: 8px 0 10px;
  color: #64748b;
  line-height: 1.8;
}

.usage-mode-meta {
  display: inline-flex;
  padding: 6px 10px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
}

.usage-mode-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.usage-mode-option {
  min-height: 132px;
  padding: 18px;
  border: 1px solid #dbe4ee;
  border-radius: 20px;
  background: #fff;
  color: #334155;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;
}

.usage-mode-option:hover:not(:disabled),
.usage-mode-option.active {
  border-color: #0f766e;
  background: #f0fdfa;
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.13), 0 14px 28px rgba(15, 118, 110, 0.08);
}

.usage-mode-option strong {
  display: block;
  color: #0f172a;
  font-size: 17px;
  margin-bottom: 8px;
}

.usage-mode-option.active strong {
  color: #0f766e;
}

.usage-mode-option span {
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
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

.internal-content-preview {
  padding: 13px 14px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e5edf5;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-line;
  word-break: break-word;
}

.tag-chip-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 6px 9px;
  border: 1px solid color-mix(in srgb, var(--tag-color, #2563eb) 35%, #ffffff);
  border-radius: 999px;
  background: color-mix(in srgb, var(--tag-color, #2563eb) 10%, #ffffff);
  color: color-mix(in srgb, var(--tag-color, #2563eb) 72%, #0f172a);
  font-size: 12px;
  font-weight: 900;
  line-height: 1.25;
}

.tag-chip em {
  max-width: 92px;
  padding-right: 6px;
  border-right: 1px solid color-mix(in srgb, var(--tag-color, #2563eb) 28%, transparent);
  color: #64748b;
  font-style: normal;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  width: min(1080px, calc(100vw - 32px));
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
  gap: 16px;
}

.field-config-help {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.field-config-help span {
  padding: 11px 13px;
  border: 1px solid #ccfbf1;
  border-radius: 14px;
  background: #f0fdfa;
  color: #0f766e;
  font-size: 13px;
  font-weight: 850;
  line-height: 1.6;
}

.field-config-row {
  display: grid;
  grid-template-columns: 90px minmax(220px, 1fr) minmax(260px, 0.8fr) minmax(220px, auto);
  gap: 12px;
  align-items: center;
  padding: 16px;
  border: 1px solid #e5edf5;
  border-radius: 20px;
  background: linear-gradient(135deg, #ffffff, #f8fafc);
  box-sizing: border-box;
}

.tag-group-config-card {
  position: relative;
  padding: 16px;
  border: 1px solid color-mix(in srgb, var(--group-color, #2563eb) 22%, #e5edf5);
  border-radius: 22px;
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--group-color, #2563eb) 8%, transparent), transparent 46%),
    linear-gradient(135deg, #ffffff, #f8fafc);
  overflow: hidden;
}

.tag-group-config-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 6px;
  background: var(--group-color, #2563eb);
}

.tag-group-card-head {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding-left: 8px;
}

.tag-group-title-block {
  display: grid;
  grid-template-columns: auto auto minmax(220px, 1fr);
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.tag-group-title-block input,
.tag-config-toolbar input,
.tag-config-row input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  background: #fff;
  color: #0f172a;
  box-sizing: border-box;
}

.tag-group-color-dot,
.tag-edit-color-mark {
  width: 16px;
  height: 16px;
  border-radius: 999px;
  background: var(--group-color, #2563eb);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--group-color, #2563eb) 14%, transparent);
}

.tag-group-tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.tag-group-color-field {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  border: 1px solid #dbeafe;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
}

.tag-group-color-field input {
  width: 34px;
  height: 26px;
  padding: 2px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  cursor: pointer;
}

.tag-group-meta-line {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 12px 0 10px;
  padding-left: 8px;
}

.tag-group-meta-line span {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--group-color, #2563eb) 9%, #ffffff);
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.tag-config-toolbar {
  display: grid;
  grid-template-columns: minmax(200px, 1fr) auto minmax(180px, 0.8fr);
  gap: 10px;
  align-items: center;
  padding: 12px;
  border: 1px solid #e5edf5;
  border-radius: 18px 18px 0 0;
  background: #f8fafc;
}

.field-order {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  border-radius: 999px;
  background: #ecfeff;
  color: #64748b;
  font-size: 13px;
  font-weight: 900;
}

.field-flag-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.switch-field {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #475569;
  font-size: 13px;
  font-weight: 900;
}

.filter-switch {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 11px;
  border: 1px solid #dbeafe;
  border-radius: 999px;
  background: #f8fafc;
  color: #334155;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
  transition: all 0.18s ease;
}

.filter-switch:has(input:checked) {
  border-color: #5eead4;
  background: #ecfeff;
  color: #0f766e;
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.08);
}

.filter-switch input {
  width: 14px;
  height: 14px;
  accent-color: #0f766e;
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

.standard-field-item textarea {
  min-height: 88px;
  padding: 12px;
  resize: vertical;
  line-height: 1.7;
}

.standard-content-editor textarea {
  min-height: 210px;
  font-size: 15px;
  line-height: 1.8;
}

.switch-field {
  margin-top: 16px;
}

.tag-config-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
  max-height: 260px;
  overflow: auto;
  padding: 12px;
  border: 1px solid #e5edf5;
  border-top: 0;
  border-radius: 0 0 18px 18px;
  background: #ffffff;
}

.tag-config-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-width: 0;
  padding: 8px;
  border: 1px solid color-mix(in srgb, var(--group-color, #2563eb) 22%, #e5edf5);
  border-radius: 16px;
  background: color-mix(in srgb, var(--group-color, #2563eb) 6%, #ffffff);
}

.tag-config-row input {
  min-width: 0;
  height: 34px;
  border-color: transparent;
  background: rgba(255, 255, 255, 0.82);
}

.tag-remove-icon-btn {
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 999px;
  background: #fee2e2;
  color: #b91c1c;
  font-size: 18px;
  font-weight: 900;
  line-height: 1;
  cursor: pointer;
}

.empty-tag-inline {
  grid-column: 1 / -1;
  min-height: 82px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed #cbd5e1;
  border-radius: 16px;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 850;
}

.standard-tag-picker {
  padding: 14px;
  border: 1px solid #e5edf5;
  border-radius: 20px;
  background: #f8fafc;
  margin-bottom: 16px;
}

.tag-picker-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.tag-picker-group {
  padding: 14px;
  border: 1px solid #e5edf5;
  border-radius: 18px;
  background: #fff;
}

.tag-picker-group strong {
  display: block;
  color: #0f172a;
  font-size: 14px;
  margin-bottom: 10px;
}

.tag-picker-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-select-chip {
  min-height: 34px;
  padding: 0 11px;
  border: 1px solid color-mix(in srgb, var(--tag-color, #2563eb) 28%, #dbe4ee);
  border-radius: 999px;
  background: #fff;
  color: #334155;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
  transition: all 0.18s ease;
}

.tag-select-chip.selected {
  background: color-mix(in srgb, var(--tag-color, #2563eb) 14%, #ffffff);
  color: color-mix(in srgb, var(--tag-color, #2563eb) 78%, #0f172a);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--tag-color, #2563eb) 35%, transparent);
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
  .tag-picker-grid {
    grid-template-columns: 1fr;
  }

  .field-filter-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .usage-mode-card {
    grid-template-columns: 1fr;
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
  .field-config-row,
  .field-config-help,
  .external-toolbar,
  .usage-mode-options,
  .tag-group-card-head,
  .tag-group-title-block,
  .tag-config-toolbar,
  .tag-config-row {
    grid-template-columns: 1fr;
  }

  .tag-group-tools {
    justify-content: flex-start;
  }

  .tag-config-list {
    grid-template-columns: 1fr;
    max-height: 320px;
  }

  .usage-mode-card {
    padding: 18px;
    border-radius: 22px;
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
