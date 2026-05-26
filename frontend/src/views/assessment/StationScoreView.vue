<template>
  <div class="station-score-page">
    <section class="score-hero">
      <div>
        <div class="page-kicker">考核系统</div>
        <h2>站点评分</h2>
        <p>按站点和月份读取可评分检查表，自动扣分并形成可导出的评分台账。</p>
      </div>
      <div class="hero-score-card">
        <span>{{ selectedMonthLabel }}</span>
        <strong>{{ formatScore(activeSummary.final_score) }}</strong>
        <small>当前总分 / {{ formatScore(activeSummary.max_score) }}</small>
      </div>
    </section>

    <section class="score-toolbar">
      <input v-model="filters.month" class="month-picker" type="month" aria-label="选择评分月份" @change="fetchScores" />

      <div ref="stationSelectRef" class="station-search-select">
        <input v-model.trim="stationSearch" type="search" placeholder="搜索并选择站点名称" aria-label="搜索并选择站点名称"
          @focus="openStationDropdown" @input="handleStationInput" />
        <div v-if="stationDropdownVisible" class="station-dropdown">
          <button v-for="station in filteredStations" :key="station.id" class="station-option" type="button"
            @click="selectStation(station)">
            <strong>{{ station.station_name }}</strong>
            <span>{{ station.region || '未设置片区' }}<template v-if="station.hos_station_code"> ｜ {{ station.hos_station_code }}</template></span>
          </button>
          <div v-if="!filteredStations.length" class="station-empty">无匹配站点</div>
        </div>
      </div>

      <div ref="checklistSelectRef" class="checklist-search-select">
        <input v-model.trim="checklistSearch" type="search" placeholder="搜索并选择检查表" aria-label="搜索并选择检查表"
          :disabled="!scoreData.tables.length" @focus="openChecklistDropdown" @input="handleChecklistInput" />
        <div v-if="checklistDropdownVisible" class="station-dropdown">
          <button v-for="table in filteredChecklists" :key="table.id" class="station-option" type="button"
            @click="selectChecklist(table)">
            <strong>{{ table.table_name }}</strong>
            <span>{{ table.checklist_mode_label || '未设置模式' }} ｜ {{ table.item_count || 0 }} 条规范</span>
          </button>
          <div v-if="!filteredChecklists.length" class="station-empty">无匹配检查表</div>
        </div>
      </div>

      <div class="export-actions">
        <button class="export-btn" type="button" :disabled="!canExportScores || !filters.stationId || !filters.inspectionTableId || !visibleScoreTables.length"
          @click="openScoreExportDialog('single')">
          导出Excel
        </button>
        <button class="export-btn secondary" type="button" :disabled="!canExportScores || !stations.length"
          @click="openScoreExportDialog('all')">
          一键导出全部站点
        </button>
      </div>
    </section>

    <div v-if="message.text" :class="['toast-message', message.type]">{{ message.text }}</div>
    <div v-if="error" class="message-card error">{{ error }}</div>

    <section class="summary-grid">
      <article v-for="card in summaryCards" :key="card.label" class="summary-card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.desc }}</small>
      </article>
    </section>

    <div v-if="loading" class="state-card">
      <div class="state-orb loading"></div>
      <h3>正在生成站点评分</h3>
      <p>系统正在读取检查表规范、挂载问题和人工调整记录。</p>
    </div>

    <div v-else-if="!filters.stationId" class="state-card">
      <div class="state-orb"></div>
      <h3>先选择一个站点</h3>
      <p>选择站点和月份后，系统会自动计算各检查表得分。</p>
    </div>

    <div v-else-if="!scoreData.tables.length" class="state-card">
      <div class="state-orb"></div>
      <h3>暂无可评分检查表</h3>
      <p>请先在检查表数据管理中，把需要参与评分的字段标记为“可评分”。</p>
    </div>

    <div v-else-if="!filters.inspectionTableId" class="state-card">
      <div class="state-orb"></div>
      <h3>请选择检查表</h3>
      <p>选择站点和检查表后，系统会展示该表的评分明细。</p>
    </div>

    <section v-else class="score-ledger-list">
      <article v-for="table in visibleScoreTables" :key="table.id" class="ledger-card">
        <div class="ledger-head">
          <div>
            <div class="table-title-line">
              <h3>{{ table.table_name }}</h3>
              <span :class="['mode-pill', table.checklist_mode]">{{ table.checklist_mode_label }}</span>
            </div>
            <p>
              {{ table.item_count }} 条规范，{{ table.issue_count }} 条问题，{{ table.deducted_item_count }} 项扣分。
            </p>
          </div>
          <div class="table-score-meter">
            <strong>{{ formatScore(table.final_score) }}</strong>
            <span>最终得分</span>
            <small>自动 {{ formatScore(table.auto_score) }} / 满分 {{ formatScore(table.max_score) }}</small>
          </div>
        </div>

        <div class="ledger-table-wrap">
          <table class="score-ledger-table">
            <thead>
              <tr>
                <th class="standard-id-col">外部规范ID</th>
                <th v-for="field in tableFieldHeaders(table)" :key="field.field_key">
                  {{ field.field_label }}
                </th>
                <th class="issue-desc-col tail-col">问题描述</th>
                <th class="issue-photo-col tail-col">问题照片</th>
                <th class="score-col tail-col">评分</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="standard in table.standards" :key="standard.standard_id"
                :class="{ deducted: standard.is_deducted, adjusted: standard.has_manual_adjustment }">
                <td class="standard-id-col">
                  <strong>{{ standard.standard_id }}</strong>
                </td>
                <td v-for="field in standard.all_fields" :key="field.field_key" class="standard-field-cell">
                  {{ field.value || '-' }}
                </td>
                <td class="issue-desc-col">
                  <div v-if="standard.issues.length" class="issue-desc-list">
                    <div v-for="issue in standard.issues" :key="issue.id" class="issue-desc-item">
                      <strong>#{{ issue.id }}</strong>
                      <span>{{ issue.description || '未填写问题描述' }}</span>
                      <em>{{ issue.inspection_date }} ｜ {{ issue.inspector_name || '未记录检查人' }}</em>
                    </div>
                  </div>
                  <span v-else class="muted-text">-</span>
                </td>
                <td class="issue-photo-col">
                  <div v-if="issuePhotos(standard).length" class="photo-strip">
                    <button v-for="photo in issuePhotos(standard)" :key="photo.url" class="photo-thumb-btn" type="button"
                      @click="previewImage(photo.url)">
                      <img :src="photo.url" alt="问题照片" />
                    </button>
                  </div>
                  <span v-else class="muted-text">-</span>
                </td>
                <td class="score-col">
                  <div class="score-cell">
                    <strong>{{ formatScore(standard.final_score) }}</strong>
                    <span>自动 {{ formatScore(standard.auto_score) }} / 满分 {{ formatScore(standard.max_score) }}</span>
                    <small v-if="standard.has_manual_adjustment">
                      {{ standard.adjusted_by_name || '未知人员' }}｜{{ standard.adjusted_at || '-' }}
                    </small>
                    <button v-if="scoreData.can_adjust" class="adjust-btn" type="button"
                      @click="openAdjustment(table, standard)">
                      调整
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    <div v-if="adjustDialog.visible" class="dialog-backdrop">
      <section class="adjust-dialog">
        <div class="dialog-head">
          <div>
            <div class="page-kicker">手动调整评分</div>
            <h3>{{ adjustDialog.tableName }}</h3>
            <p>外部规范ID {{ adjustDialog.standardId }}，本项满分 {{ formatScore(adjustDialog.maxScore) }}。</p>
          </div>
          <button class="dialog-close" type="button" @click="closeAdjustment">×</button>
        </div>

        <label class="score-input-field">
          <input v-model.number="adjustDialog.manualScore" type="number" min="0" :max="adjustDialog.maxScore"
            step="0.01" aria-label="调整后分值" />
        </label>

        <div class="dialog-actions">
          <button class="btn btn-secondary" type="button" @click="closeAdjustment">取消</button>
          <button class="btn btn-primary" type="button" :disabled="adjustDialog.saving" @click="saveAdjustment">
            {{ adjustDialog.saving ? '保存中...' : '保存调整' }}
          </button>
        </div>
      </section>
    </div>

    <div v-if="exportDialog.visible" class="dialog-backdrop">
      <section class="export-dialog">
        <div class="dialog-head">
          <div>
            <div class="page-kicker">后台导出任务</div>
            <h3>{{ exportDialog.mode === 'all' ? '一键导出全部站点评分' : '导出当前检查表评分' }}</h3>
            <p>导出任务会在后台生成文件，完成后可直接下载，服务器仅保留 7 天。</p>
          </div>
          <button class="dialog-close" type="button" @click="closeScoreExportDialog">×</button>
        </div>

        <div class="export-summary-grid">
          <div>
            <span>评分月份</span>
            <strong>{{ filters.month }}</strong>
          </div>
          <div>
            <span>导出范围</span>
            <strong>{{ exportDialog.mode === 'all' ? '全部站点' : selectedStationName }}</strong>
          </div>
          <div v-if="exportDialog.mode === 'single'">
            <span>检查表</span>
            <strong>{{ selectedChecklistName }}</strong>
          </div>
          <div>
            <span>{{ exportDialog.mode === 'all' ? '站点数量' : '规范数量' }}</span>
            <strong>{{ exportDialog.selectedCount }}</strong>
          </div>
          <div v-if="exportDialog.mode === 'all'">
            <span>检查表</span>
            <strong>{{ selectedExportChecklistCount }}</strong>
          </div>
        </div>

        <div v-if="exportDialog.mode === 'all'" class="export-checklist-panel">
          <div class="export-panel-head">
            <div>
              <strong>导出检查表</strong>
              <small>默认导出全部可评分检查表，也可以只选择一张或多张检查表。</small>
            </div>
            <div class="export-panel-actions">
              <button type="button" :disabled="isScoreExportLocked" @click="selectAllExportChecklists">全选</button>
              <button type="button" :disabled="isScoreExportLocked" @click="clearExportChecklists">清空</button>
            </div>
          </div>
          <input v-model.trim="exportDialog.checklistSearch" class="export-checklist-search" type="search"
            placeholder="搜索检查表名称" :disabled="isScoreExportLocked" />
          <div class="export-checklist-options">
            <label v-for="table in filteredExportChecklists" :key="table.id" class="export-checklist-option"
              :class="{ active: exportDialog.selectedTableIds.includes(String(table.id)), disabled: isScoreExportLocked }">
              <input type="checkbox" :checked="exportDialog.selectedTableIds.includes(String(table.id))"
                :disabled="isScoreExportLocked" @change="toggleExportChecklist(table.id)" />
              <span>
                <strong>{{ table.table_name }}</strong>
                <small>{{ table.checklist_mode_label || '未设置模式' }}</small>
              </span>
            </label>
            <div v-if="!filteredExportChecklists.length" class="export-checklist-empty">没有匹配的可评分检查表</div>
          </div>
        </div>

        <label class="photo-option-card">
          <input v-model="exportDialog.includePhotos.issue_photo" type="checkbox"
            :disabled="['pending', 'running'].includes(exportDialog.status)" />
          <span>
            <strong>导出问题照片</strong>
            <small>照片会嵌入 Excel 单元格，文件生成会更慢、体积也会更大。</small>
          </span>
        </label>

        <div v-if="exportDialog.taskId" class="export-task-panel">
          <div>
            <span class="task-status-label">{{ exportStatusLabel }}</span>
            <strong>{{ exportDialog.fileName || '正在准备文件名' }}</strong>
            <small v-if="exportDialog.fileSizeLabel">文件大小 {{ exportDialog.fileSizeLabel }}</small>
            <small v-if="exportDialog.expiresAt">保留至 {{ exportDialog.expiresAt }}</small>
          </div>
          <div class="task-progress-track">
            <span :style="{ width: exportProgressPercent + '%' }"></span>
          </div>
          <p v-if="exportDialog.error" class="export-error">{{ exportDialog.error }}</p>
        </div>
        <p v-if="exportDialog.error && !exportDialog.taskId" class="export-error standalone">{{ exportDialog.error }}</p>

        <div class="dialog-actions">
          <button class="btn btn-secondary" type="button" :disabled="exportDialog.submitting" @click="closeScoreExportDialog">
            关闭
          </button>
          <button v-if="exportDialog.status !== 'completed'" class="btn btn-primary" type="button"
            :disabled="exportDialog.submitting || ['pending', 'running'].includes(exportDialog.status)"
            @click="submitScoreExportTask">
            {{ exportDialog.submitting ? '提交中...' : '提交导出任务' }}
          </button>
          <button v-else class="btn btn-primary" type="button" :disabled="exportDialog.downloading"
            @click="downloadScoreExport">
            {{ exportDialog.downloading ? '下载中...' : '下载文件' }}
          </button>
        </div>
      </section>
    </div>

    <div v-if="imagePreview.visible" class="image-preview-backdrop" @click="closePreview">
      <img :src="imagePreview.url" alt="问题照片预览" @click.stop />
    </div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { pinyin } from 'pinyin-pro'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const getDefaultMonth = () => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

const filters = reactive({
  month: getDefaultMonth(),
  stationId: '',
  inspectionTableId: ''
})

const stationSearch = ref('')
const stationDropdownVisible = ref(false)
const stationSelectRef = ref(null)
const checklistSearch = ref('')
const checklistDropdownVisible = ref(false)
const checklistSelectRef = ref(null)
const stations = ref([])
const scorableChecklists = ref([])
const loading = ref(false)
const error = ref('')
const message = reactive({ text: '', type: 'info' })
let messageTimer = null
let exportPollTimer = null
const currentRole = localStorage.getItem('user_role') || localStorage.getItem('role') || ''
let parsedPermissions = {}
try {
  parsedPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch (error) {
  parsedPermissions = {}
}

const emptyScoreData = () => ({
  month: filters.month,
  station: null,
  can_adjust: false,
  summary: {
    table_count: 0,
    item_count: 0,
    issue_count: 0,
    deducted_item_count: 0,
    adjusted_item_count: 0,
    max_score: 0,
    auto_score: 0,
    final_score: 0
  },
  tables: []
})

const scoreData = ref(emptyScoreData())

const exportDialog = reactive({
  visible: false,
  mode: 'single',
  submitting: false,
  downloading: false,
  taskId: '',
  status: 'idle',
  error: '',
  selectedCount: 0,
  exportedCount: 0,
  fileName: '',
  fileSizeLabel: '',
  expiresAt: '',
  checklistSearch: '',
  selectedTableIds: [],
  includePhotos: {
    issue_photo: false
  }
})

const adjustDialog = reactive({
  visible: false,
  stationId: '',
  inspectionTableId: '',
  tableName: '',
  standardId: '',
  maxScore: 0,
  manualScore: 0,
  hasManualAdjustment: false,
  saving: false
})

const imagePreview = reactive({
  visible: false,
  url: ''
})

const selectedMonthLabel = computed(() => {
  const [year, month] = String(filters.month || '').split('-')
  return year && month ? `${year}年${Number(month)}月` : '当前月份'
})

const selectedStation = computed(() => {
  return stations.value.find((station) => String(station.id) === String(filters.stationId)) || null
})

const selectedStationName = computed(() => selectedStation.value?.station_name || '当前站点')

const visibleScoreTables = computed(() => {
  if (!filters.inspectionTableId) return []
  return (scoreData.value.tables || []).filter((table) => String(table.id) === String(filters.inspectionTableId))
})

const selectedChecklistName = computed(() => {
  return visibleScoreTables.value[0]?.table_name || '当前检查表'
})

const activeSummary = computed(() => {
  const table = visibleScoreTables.value[0]
  if (!table) return scoreData.value.summary
  return {
    table_count: 1,
    item_count: table.item_count || 0,
    issue_count: table.issue_count || 0,
    deducted_item_count: table.deducted_item_count || 0,
    adjusted_item_count: table.adjusted_item_count || 0,
    max_score: table.max_score || 0,
    auto_score: table.auto_score || 0,
    final_score: table.final_score || 0
  }
})

const filteredChecklists = computed(() => {
  return (scoreData.value.tables || []).filter((table) => {
    return matchesSmartSearch(
      [table.table_name, table.checklist_mode_label, table.table_code],
      checklistSearch.value
    )
  })
})

const filteredExportChecklists = computed(() => {
  return scorableChecklists.value.filter((table) => {
    return matchesSmartSearch(
      [table.table_name, table.checklist_mode_label, table.table_code],
      exportDialog.checklistSearch
    )
  })
})

const selectedExportChecklistCount = computed(() => exportDialog.selectedTableIds.length)

const isScoreExportLocked = computed(() => Boolean(exportDialog.taskId) || ['pending', 'running'].includes(exportDialog.status))

const canExportScores = computed(() => {
  return currentRole === 'root' || Boolean(parsedPermissions.adjust_station_scores) || Boolean(scoreData.value.can_adjust)
})

const exportStatusLabel = computed(() => {
  const statusMap = {
    idle: '待提交',
    pending: '等待处理',
    running: '正在生成',
    completed: '已完成',
    failed: '生成失败'
  }
  return statusMap[exportDialog.status] || '处理中'
})

const exportProgressPercent = computed(() => {
  if (exportDialog.status === 'completed') return 100
  if (exportDialog.status === 'failed') return 100
  if (exportDialog.status === 'running') {
    const selected = Math.max(Number(exportDialog.selectedCount || 0), 1)
    const exported = Math.max(Number(exportDialog.exportedCount || 0), 0)
    return Math.max(12, Math.min(92, Math.round((exported / selected) * 100)))
  }
  return exportDialog.status === 'pending' ? 16 : 0
})

const normalizeSearchToken = (value) => {
  return String(value || '')
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]+/gu, '')
}

const toPinyinText = (value, options = {}) => {
  const text = String(value || '').trim()
  if (!text) return ''
  try {
    return pinyin(text, {
      toneType: 'none',
      nonZh: 'consecutive',
      ...options
    })
  } catch (error) {
    return ''
  }
}

const buildSearchVariants = (value) => {
  const source = String(value || '').trim()
  if (!source) return []
  return [
    source,
    toPinyinText(source),
    toPinyinText(source, { pattern: 'first' })
  ].map(normalizeSearchToken).filter(Boolean)
}

const matchesSmartSearch = (values, keyword) => {
  const needle = normalizeSearchToken(keyword)
  if (!needle) return true
  return values.some((value) => buildSearchVariants(value).some((variant) => variant.includes(needle)))
}

const filteredStations = computed(() => {
  return stations.value.filter((station) => {
    return matchesSmartSearch(
      [station.station_name, station.region, station.station_usernames, station.hos_station_code],
      stationSearch.value
    )
  })
})

const summaryCards = computed(() => [
  {
    label: '最终得分',
    value: `${formatScore(activeSummary.value.final_score)} / ${formatScore(activeSummary.value.max_score)}`,
    desc: '包含人工调整后的全局结果'
  },
  {
    label: '自动扣分项',
    value: activeSummary.value.deducted_item_count,
    desc: `${activeSummary.value.issue_count} 条问题触发扣分`
  },
  {
    label: '可评分检查表',
    value: activeSummary.value.table_count,
    desc: `${activeSummary.value.item_count} 条规范参与评分`
  },
  {
    label: '人工调整',
    value: activeSummary.value.adjusted_item_count,
    desc: scoreData.value.can_adjust ? '你有调整权限' : '当前账号只读'
  }
])

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

const formatScore = (value) => {
  const number = Number(value || 0)
  return Number.isInteger(number) ? String(number) : number.toFixed(2)
}

const resolveImage = (path) => {
  if (!path) return ''
  if (String(path).startsWith('http')) return path
  const normalizedPath = String(path).startsWith('/') ? String(path).slice(1) : String(path)
  return `/storage/${normalizedPath}`
}

const issuePhotos = (standard) => {
  return (standard?.issues || [])
    .filter((issue) => issue.issue_photo)
    .map((issue) => ({
      id: issue.id,
      url: resolveImage(issue.issue_photo)
    }))
}

const tableFieldHeaders = (table) => {
  return table?.standards?.[0]?.all_fields || []
}

const openStationDropdown = () => {
  stationDropdownVisible.value = true
}

const handleStationInput = () => {
  stationDropdownVisible.value = true
  filters.stationId = ''
  filters.inspectionTableId = ''
  checklistSearch.value = ''
  scoreData.value = emptyScoreData()
}

const selectStation = async (station) => {
  stationSearch.value = station.station_name
  filters.stationId = String(station.id)
  filters.inspectionTableId = ''
  checklistSearch.value = ''
  stationDropdownVisible.value = false
  await fetchScores()
}

const closeStationDropdownOnOutsideClick = (event) => {
  if (stationSelectRef.value && !stationSelectRef.value.contains(event.target)) {
    stationDropdownVisible.value = false
  }
  if (checklistSelectRef.value && !checklistSelectRef.value.contains(event.target)) {
    checklistDropdownVisible.value = false
  }
}

const openChecklistDropdown = () => {
  if (!scoreData.value.tables.length) return
  checklistDropdownVisible.value = true
}

const handleChecklistInput = () => {
  checklistDropdownVisible.value = true
  filters.inspectionTableId = ''
}

const selectChecklist = (table) => {
  checklistSearch.value = table.table_name
  filters.inspectionTableId = String(table.id)
  checklistDropdownVisible.value = false
}

const syncSelectedChecklistAfterLoad = () => {
  const tables = scoreData.value.tables || []
  if (!tables.length) {
    filters.inspectionTableId = ''
    checklistSearch.value = ''
    return
  }
  const existing = tables.find((table) => String(table.id) === String(filters.inspectionTableId))
  const selected = existing || tables[0]
  filters.inspectionTableId = String(selected.id)
  checklistSearch.value = selected.table_name
}

const fetchStations = async () => {
  const response = await axios.get('/api/stations')
  stations.value = Array.isArray(response.data) ? response.data : []
}

const fetchScorableChecklists = async () => {
  const response = await axios.get('/api/assessment/station-scores/scorable-checklists', {
    params: { _ts: Date.now() }
  })
  scorableChecklists.value = Array.isArray(response.data?.checklists) ? response.data.checklists : []
}

const fetchScores = async () => {
  if (!filters.stationId) {
    scoreData.value = emptyScoreData()
    return
  }
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get('/api/assessment/station-scores', {
      params: {
        station_id: filters.stationId,
        month: filters.month
      }
    })
    scoreData.value = response.data
    syncSelectedChecklistAfterLoad()
  } catch (err) {
    error.value = err?.response?.data?.error || '站点评分加载失败。'
    scoreData.value = emptyScoreData()
    filters.inspectionTableId = ''
    checklistSearch.value = ''
  } finally {
    loading.value = false
  }
}

const resetExportDialog = (mode) => {
  stopScoreExportPolling()
  exportDialog.visible = true
  exportDialog.mode = mode
  exportDialog.submitting = false
  exportDialog.downloading = false
  exportDialog.taskId = ''
  exportDialog.status = 'idle'
  exportDialog.error = ''
  exportDialog.exportedCount = 0
  exportDialog.fileName = ''
  exportDialog.fileSizeLabel = ''
  exportDialog.expiresAt = ''
  exportDialog.checklistSearch = ''
  exportDialog.selectedTableIds = mode === 'all'
    ? scorableChecklists.value.map((table) => String(table.id))
    : []
  exportDialog.includePhotos = { issue_photo: false }
  exportDialog.selectedCount = mode === 'all'
    ? stations.value.length
    : Number(visibleScoreTables.value[0]?.item_count || 0)
}

const openScoreExportDialog = async (mode) => {
  if (!canExportScores.value) {
    setMessage('当前账号没有导出站点评分的权限。', 'error')
    return
  }
  if (mode === 'single' && (!filters.stationId || !filters.inspectionTableId || !visibleScoreTables.value.length)) {
    setMessage('请先选择站点和检查表。', 'error')
    return
  }
  if (mode === 'all' && !stations.value.length) {
    setMessage('暂无可导出的站点。', 'error')
    return
  }
  if (mode === 'all' && !scorableChecklists.value.length) {
    try {
      await fetchScorableChecklists()
    } catch (err) {
      setMessage(err?.response?.data?.error || '可评分检查表加载失败。', 'error')
      return
    }
  }
  if (mode === 'all' && !scorableChecklists.value.length) {
    setMessage('暂无可导出的可评分检查表。', 'error')
    return
  }
  resetExportDialog(mode)
}

const selectAllExportChecklists = () => {
  if (isScoreExportLocked.value) return
  exportDialog.selectedTableIds = scorableChecklists.value.map((table) => String(table.id))
}

const clearExportChecklists = () => {
  if (isScoreExportLocked.value) return
  exportDialog.selectedTableIds = []
}

const toggleExportChecklist = (tableId) => {
  if (isScoreExportLocked.value) return
  const normalizedId = String(tableId)
  if (exportDialog.selectedTableIds.includes(normalizedId)) {
    exportDialog.selectedTableIds = exportDialog.selectedTableIds.filter((item) => item !== normalizedId)
    return
  }
  exportDialog.selectedTableIds = [...exportDialog.selectedTableIds, normalizedId]
}

const closeScoreExportDialog = () => {
  if (exportDialog.submitting) return
  exportDialog.visible = false
  if (!['pending', 'running'].includes(exportDialog.status)) {
    stopScoreExportPolling()
  }
}

const stopScoreExportPolling = () => {
  if (exportPollTimer) {
    window.clearInterval(exportPollTimer)
    exportPollTimer = null
  }
}

const applyScoreExportTask = (task = {}) => {
  exportDialog.taskId = task.task_id || exportDialog.taskId
  exportDialog.status = task.status || exportDialog.status
  exportDialog.selectedCount = Number(task.selected_count ?? exportDialog.selectedCount) || 0
  exportDialog.exportedCount = Number(task.exported_count || 0)
  exportDialog.fileName = task.download_filename || exportDialog.fileName
  exportDialog.fileSizeLabel = task.file_size_label || ''
  exportDialog.expiresAt = task.expires_at || exportDialog.expiresAt
  exportDialog.error = task.error_message || ''
  const includePhotos = task.export_options?.include_photos
  if (includePhotos && typeof includePhotos === 'object') {
    exportDialog.includePhotos = {
      issue_photo: Boolean(includePhotos.issue_photo)
    }
  }
}

const pollScoreExportTask = async () => {
  if (!exportDialog.taskId) return
  try {
    const response = await axios.get(`/api/assessment/station-scores/export-tasks/${exportDialog.taskId}`, {
      params: { _ts: Date.now() }
    })
    applyScoreExportTask(response.data?.task || {})
    if (['completed', 'failed'].includes(exportDialog.status)) {
      stopScoreExportPolling()
      if (exportDialog.status === 'completed') {
        setMessage('站点评分导出文件已生成。', 'success')
      }
    }
  } catch (err) {
    stopScoreExportPolling()
    exportDialog.status = 'failed'
    exportDialog.error = err?.response?.data?.error || '导出任务状态查询失败。'
  }
}

const startScoreExportPolling = () => {
  stopScoreExportPolling()
  pollScoreExportTask()
  exportPollTimer = window.setInterval(pollScoreExportTask, 1600)
}

const submitScoreExportTask = async () => {
  try {
    exportDialog.submitting = true
    exportDialog.error = ''
    const payload = {
      mode: exportDialog.mode,
      month: filters.month,
      export_options: {
        include_photos: {
          issue_photo: Boolean(exportDialog.includePhotos.issue_photo)
        }
      }
    }
    if (exportDialog.mode === 'single') {
      payload.station_id = filters.stationId
      payload.inspection_table_id = filters.inspectionTableId
    } else {
      if (!exportDialog.selectedTableIds.length) {
        exportDialog.error = '请选择至少一张需要导出的检查表。'
        return
      }
      payload.inspection_table_ids = exportDialog.selectedTableIds
    }
    const response = await axios.post('/api/assessment/station-scores/export-tasks', payload)
    applyScoreExportTask(response.data?.task || {})
    startScoreExportPolling()
  } catch (err) {
    exportDialog.error = err?.response?.data?.error || '导出任务提交失败。'
    exportDialog.status = 'failed'
  } finally {
    exportDialog.submitting = false
  }
}

const downloadScoreExport = async () => {
  if (!exportDialog.taskId) return
  try {
    exportDialog.downloading = true
    const response = await axios.get(`/api/assessment/station-scores/export-tasks/${exportDialog.taskId}/download`, {
      responseType: 'blob'
    })
    const isZip = String(exportDialog.fileName || '').toLowerCase().endsWith('.zip')
    const blobUrl = window.URL.createObjectURL(new Blob([response.data], {
      type: isZip ? 'application/zip' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }))
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = exportDialog.fileName || (isZip ? `站点评分_${exportDialog.taskId.slice(0, 8)}.zip` : `站点评分_${exportDialog.taskId.slice(0, 8)}.xlsx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(blobUrl)
  } catch (err) {
    exportDialog.error = err?.response?.data?.error || '导出文件下载失败。'
  } finally {
    exportDialog.downloading = false
  }
}

const openAdjustment = (table, standard) => {
  adjustDialog.visible = true
  adjustDialog.stationId = filters.stationId
  adjustDialog.inspectionTableId = table.id
  adjustDialog.tableName = table.table_name
  adjustDialog.standardId = standard.standard_id
  adjustDialog.maxScore = Number(standard.max_score || 0)
  adjustDialog.manualScore = Number(standard.final_score || 0)
  adjustDialog.hasManualAdjustment = Boolean(standard.has_manual_adjustment)
}

const closeAdjustment = () => {
  if (adjustDialog.saving) return
  adjustDialog.visible = false
}

const saveAdjustment = async () => {
  adjustDialog.saving = true
  try {
    await axios.put('/api/assessment/station-scores/adjustment', {
      station_id: adjustDialog.stationId,
      inspection_table_id: adjustDialog.inspectionTableId,
      standard_id: adjustDialog.standardId,
      month: filters.month,
      manual_score: adjustDialog.manualScore
    })
    adjustDialog.visible = false
    setMessage('评分调整成功。', 'success')
    await fetchScores()
  } catch (err) {
    setMessage(err?.response?.data?.error || '评分调整保存失败。', 'error')
  } finally {
    adjustDialog.saving = false
  }
}

const previewImage = (url) => {
  imagePreview.url = url
  imagePreview.visible = true
}

const closePreview = () => {
  imagePreview.visible = false
  imagePreview.url = ''
}

onMounted(async () => {
  document.addEventListener('click', closeStationDropdownOnOutsideClick)
  try {
    await Promise.all([fetchStations(), fetchScorableChecklists()])
  } catch (err) {
    error.value = err?.response?.data?.error || '站点数据加载失败。'
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeStationDropdownOnOutsideClick)
  stopScoreExportPolling()
  if (messageTimer) window.clearTimeout(messageTimer)
})
</script>

<style scoped>
.station-score-page {
  display: grid;
  gap: 18px;
  color: #172033;
}

.score-hero,
.score-toolbar,
.summary-card,
.ledger-card,
.state-card,
.message-card,
.adjust-dialog,
.export-dialog {
  border: 1px solid rgba(80, 96, 125, 0.14);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 18px 45px rgba(31, 45, 72, 0.08);
}

.score-hero {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 24px;
  padding: 26px;
  border-radius: 28px;
  background:
    radial-gradient(circle at 12% 16%, rgba(47, 125, 95, 0.16), transparent 32%),
    linear-gradient(135deg, #f7fbf7 0%, #eef5ef 52%, #f8faf8 100%);
}

.page-kicker {
  color: #527260;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.16em;
}

.score-hero h2 {
  margin: 8px 0;
  font-size: clamp(28px, 4vw, 42px);
}

.score-hero p {
  margin: 0;
  color: #5c6678;
  line-height: 1.7;
}

.hero-score-card {
  min-width: 180px;
  display: grid;
  place-items: center;
  padding: 18px;
  border-radius: 24px;
  background: #173d2c;
  color: #fff;
}

.hero-score-card span,
.hero-score-card small {
  color: rgba(255, 255, 255, 0.72);
}

.hero-score-card strong {
  font-size: 40px;
  line-height: 1.1;
}

.score-toolbar {
  display: grid;
  grid-template-columns: 160px minmax(260px, 1fr) minmax(260px, 1fr) minmax(300px, auto);
  gap: 12px;
  align-items: center;
  padding: 14px;
  border-radius: 22px;
}

.month-picker,
.station-search-select input,
.checklist-search-select input,
.score-input-field input {
  width: 100%;
  min-height: 44px;
  border: 1px solid #d8dfd9;
  border-radius: 14px;
  background: #fff;
  color: #172033;
  font: inherit;
  padding: 10px 14px;
  outline: none;
}

.month-picker:focus,
.station-search-select input:focus,
.checklist-search-select input:focus,
.score-input-field input:focus {
  border-color: #2f7d5f;
  box-shadow: 0 0 0 4px rgba(47, 125, 95, 0.12);
}

.station-search-select,
.checklist-search-select {
  position: relative;
}

.station-dropdown {
  position: absolute;
  z-index: 30;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  max-height: 320px;
  overflow: auto;
  padding: 8px;
  border: 1px solid #dce5df;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 22px 55px rgba(31, 45, 72, 0.18);
}

.station-option {
  width: 100%;
  display: grid;
  gap: 4px;
  border: 0;
  border-radius: 14px;
  background: transparent;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
}

.station-option:hover {
  background: #eef7f1;
}

.station-option span,
.station-empty {
  color: #687386;
  font-size: 12px;
}

.station-empty {
  padding: 14px;
  text-align: center;
}

.export-btn,
.adjust-btn,
.btn {
  border: 0;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 800;
}

.export-btn {
  min-height: 44px;
  color: #fff;
  background: #2f7d5f;
}

.export-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.export-btn.secondary {
  background: #173d2c;
}

.export-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.export-actions .export-btn {
  min-width: 132px;
  padding: 0 16px;
}

.export-actions .export-btn.secondary {
  min-width: 178px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.summary-card {
  display: grid;
  gap: 6px;
  padding: 18px;
  border-radius: 22px;
}

.summary-card span,
.summary-card small,
.table-score-meter small,
.muted-text {
  color: #6a7282;
}

.summary-card strong {
  font-size: 28px;
  color: #173d2c;
}

.score-ledger-list {
  display: grid;
  gap: 18px;
}

.ledger-card {
  overflow: hidden;
  border-radius: 28px;
}

.ledger-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 190px;
  gap: 16px;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e5ece6;
  background: linear-gradient(135deg, #ffffff 0%, #f5f8f5 100%);
}

.table-title-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.table-title-line h3 {
  margin: 0;
  font-size: 22px;
}

.ledger-head p {
  margin: 8px 0 0;
  color: #677080;
}

.mode-pill {
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 800;
}

.mode-pill.online {
  color: #1d5d7f;
  background: #e8f6fc;
}

.mode-pill.offline {
  color: #7a4e16;
  background: #fff2d9;
}

.table-score-meter {
  display: grid;
  gap: 4px;
  justify-items: end;
}

.table-score-meter strong {
  color: #173d2c;
  font-size: 34px;
}

.ledger-table-wrap {
  overflow: auto;
  background: #fbfcfb;
}

.score-ledger-table {
  width: 100%;
  min-width: 1180px;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;
}

.score-ledger-table th,
.score-ledger-table td {
  max-width: 260px;
  border-right: 1px solid #dfe7e1;
  border-bottom: 1px solid #dfe7e1;
  padding: 10px;
  vertical-align: middle;
  text-align: center;
  white-space: pre-wrap;
  word-break: break-word;
}

.score-ledger-table th {
  position: sticky;
  top: 0;
  z-index: 2;
  color: #263548;
  background: #eaf2ec;
  font-weight: 900;
}

.score-ledger-table tbody tr {
  background: #fff;
}

.score-ledger-table tbody tr.deducted {
  background: #fff7f3;
}

.score-ledger-table tbody tr.adjusted {
  background: #f1fbf4;
}

.standard-id-col {
  width: 110px;
  color: #173d2c;
}

.standard-field-cell {
  text-align: left;
  line-height: 1.65;
}

.issue-desc-col {
  width: 300px;
  min-width: 300px;
}

.issue-photo-col {
  width: 170px;
  min-width: 170px;
}

.score-col {
  width: 180px;
  min-width: 180px;
}

.issue-desc-list {
  display: grid;
  gap: 8px;
  text-align: left;
}

.issue-desc-item {
  display: grid;
  gap: 3px;
  padding: 8px;
  border-radius: 12px;
  background: rgba(183, 77, 58, 0.08);
}

.issue-desc-item strong {
  color: #9d3f32;
}

.issue-desc-item em {
  color: #6a7282;
  font-size: 12px;
  font-style: normal;
}

.photo-strip {
  display: flex;
  justify-content: center;
  gap: 6px;
  flex-wrap: wrap;
}

.photo-thumb-btn {
  width: 58px;
  height: 58px;
  overflow: hidden;
  border: 1px solid #d4ded8;
  border-radius: 12px;
  background: #fff;
  cursor: zoom-in;
  padding: 0;
}

.photo-thumb-btn img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.score-cell {
  display: grid;
  justify-items: center;
  gap: 5px;
}

.score-cell strong {
  color: #173d2c;
  font-size: 24px;
}

.score-cell span,
.score-cell small {
  color: #667285;
  font-size: 12px;
}

.adjust-btn {
  padding: 7px 14px;
  color: #fff;
  background: #2f7d5f;
}

.btn {
  padding: 10px 16px;
}

.btn-primary {
  color: #fff;
  background: #2f7d5f;
}

.btn-secondary {
  color: #2f513f;
  background: #eef4ef;
}

.state-card,
.message-card {
  display: grid;
  place-items: center;
  gap: 8px;
  min-height: 180px;
  padding: 28px;
  border-radius: 26px;
  text-align: center;
}

.message-card.error {
  color: #9d3b2f;
  background: #fff5f2;
}

.state-card h3 {
  margin: 0;
}

.state-card p {
  margin: 0;
  color: #6a7282;
}

.state-orb {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #fff, #a6c979);
}

.state-orb.loading {
  animation: pulse 1.1s ease-in-out infinite alternate;
}

.toast-message {
  position: fixed;
  top: 24px;
  left: 50%;
  z-index: 90;
  transform: translateX(-50%);
  padding: 12px 20px;
  border-radius: 999px;
  color: #fff;
  background: #26384f;
  box-shadow: 0 18px 45px rgba(31, 45, 72, 0.22);
}

.toast-message.success {
  background: #2f7d5f;
}

.toast-message.error {
  background: #b44a3b;
}

.dialog-backdrop,
.image-preview-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(13, 22, 34, 0.48);
}

.image-preview-backdrop {
  z-index: 95;
  cursor: zoom-out;
}

.image-preview-backdrop img {
  max-width: min(92vw, 1200px);
  max-height: 88vh;
  border-radius: 16px;
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.35);
}

.adjust-dialog,
.export-dialog {
  width: min(480px, 100%);
  border-radius: 26px;
  padding: 22px;
}

.export-dialog {
  width: min(760px, 100%);
}

.dialog-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.dialog-head h3 {
  margin: 6px 0;
}

.dialog-head p {
  margin: 0;
  color: #657082;
}

.dialog-close {
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 50%;
  color: #516071;
  background: #f0f3f1;
  cursor: pointer;
  font-size: 22px;
}

.score-input-field {
  display: block;
  margin-top: 18px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.export-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.export-summary-grid > div {
  display: grid;
  gap: 5px;
  min-height: 78px;
  align-content: center;
  padding: 12px;
  border: 1px solid #dfe9e2;
  border-radius: 18px;
  background: #f8fbf8;
}

.export-summary-grid span,
.photo-option-card small,
.export-task-panel small {
  color: #697587;
  font-size: 12px;
}

.export-summary-grid strong {
  color: #173d2c;
  font-size: 15px;
}

.photo-option-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-top: 14px;
  padding: 14px;
  border: 1px dashed #bfd5c7;
  border-radius: 18px;
  background: #fbfdfb;
}

.photo-option-card input {
  width: 18px;
  height: 18px;
  margin-top: 2px;
  accent-color: #2f7d5f;
}

.photo-option-card span {
  display: grid;
  gap: 3px;
}

.export-checklist-panel {
  display: grid;
  gap: 12px;
  margin-top: 14px;
  padding: 14px;
  border: 1px solid #dfe9e2;
  border-radius: 18px;
  background: #f9fcfa;
}

.export-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.export-panel-head > div:first-child {
  display: grid;
  gap: 4px;
}

.export-panel-head small,
.export-checklist-option small,
.export-checklist-empty {
  color: #697587;
  font-size: 12px;
}

.export-panel-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.export-panel-actions button {
  border: 0;
  border-radius: 999px;
  padding: 7px 12px;
  color: #24533d;
  background: #eaf4ed;
  cursor: pointer;
  font-weight: 800;
}

.export-panel-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.export-checklist-search {
  width: 100%;
  min-height: 42px;
  border: 1px solid #d8dfd9;
  border-radius: 14px;
  padding: 9px 12px;
  font: inherit;
  outline: none;
}

.export-checklist-search:focus {
  border-color: #2f7d5f;
  box-shadow: 0 0 0 4px rgba(47, 125, 95, 0.12);
}

.export-checklist-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  max-height: 230px;
  overflow: auto;
  padding-right: 2px;
}

.export-checklist-option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-height: 62px;
  padding: 10px;
  border: 1px solid #dce7df;
  border-radius: 14px;
  background: #fff;
  cursor: pointer;
}

.export-checklist-option.active {
  border-color: #2f7d5f;
  background: #edf8f0;
}

.export-checklist-option.disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.export-checklist-option input {
  width: 17px;
  height: 17px;
  margin-top: 2px;
  accent-color: #2f7d5f;
}

.export-checklist-option span {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.export-checklist-option strong {
  color: #173d2c;
  line-height: 1.35;
}

.export-checklist-empty {
  grid-column: 1 / -1;
  padding: 16px;
  border-radius: 14px;
  background: #fff;
  text-align: center;
}

.export-task-panel {
  display: grid;
  gap: 10px;
  margin-top: 14px;
  padding: 14px;
  border-radius: 18px;
  background: #173d2c;
  color: #fff;
}

.export-task-panel > div:first-child {
  display: grid;
  gap: 5px;
}

.task-status-label {
  width: fit-content;
  border-radius: 999px;
  padding: 4px 10px;
  color: #173d2c;
  background: #dff0df;
  font-size: 12px;
  font-weight: 900;
}

.task-progress-track {
  height: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
}

.task-progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #bde08f, #ffffff);
  transition: width 0.25s ease;
}

.export-error {
  margin: 0;
  color: #ffd9d2;
}

.export-error.standalone {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 14px;
  color: #a23d31;
  background: #fff2ef;
}

@keyframes pulse {
  from {
    transform: scale(0.92);
    opacity: 0.72;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

@media (max-width: 980px) {
  .score-hero,
  .ledger-head {
    grid-template-columns: 1fr;
    display: grid;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .score-toolbar {
    grid-template-columns: 160px minmax(0, 1fr);
  }

  .export-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }

  .table-score-meter {
    justify-items: start;
  }
}

@media (max-width: 680px) {
  .score-hero,
  .score-toolbar,
  .ledger-head {
    border-radius: 20px;
    padding: 16px;
  }

  .summary-grid,
  .score-toolbar {
    grid-template-columns: 1fr;
  }

  .export-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .export-panel-head,
  .export-checklist-options {
    grid-template-columns: 1fr;
  }

  .export-panel-head {
    display: grid;
  }

  .export-actions,
  .export-actions .export-btn {
    width: 100%;
  }

  .hero-score-card {
    min-width: 0;
  }

  .score-ledger-table {
    min-width: 980px;
  }
}
</style>
