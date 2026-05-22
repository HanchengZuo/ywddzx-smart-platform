<template>
  <div class="page-shell completion-management-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">管理系统</div>
        <h2>巡检封存管理</h2>
        <p>管理检查人完成确认、自动封存规则，以及同站点同检查表按自然周期唯一记录的执行情况。</p>
      </div>
      <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchData">
        {{ loading ? '刷新中...' : '刷新数据' }}
      </button>
    </div>

    <transition name="toast-fade">
      <div v-if="message.text" class="action-toast card-surface" :class="message.type">{{ message.text }}</div>
    </transition>

    <section class="config-grid">
      <div class="card-surface config-card">
        <div class="section-head">
          <div>
            <div class="section-kicker">自动规则</div>
            <h3>自动确认完成</h3>
          </div>
          <span :class="['status-chip', config.auto_complete_enabled ? 'success' : 'muted']">
            {{ config.auto_complete_enabled ? '已启用' : '已停用' }}
          </span>
        </div>

        <div class="config-form">
          <label class="switch-row">
            <input v-model="config.auto_complete_enabled" type="checkbox" />
            <span>超过设定天数仍未手动确认时，系统自动确认完成并封存</span>
          </label>
          <label class="field-row">
            <span>自动确认天数</span>
            <input v-model.number="config.auto_complete_days" type="number" min="1" max="31" />
            <small>默认 7 天；建议不超过一个巡检周。</small>
          </label>
          <label class="field-row">
            <span>同站同表唯一周期</span>
            <select v-model="config.record_uniqueness_period">
              <option value="week">自然周</option>
              <option value="month">自然月</option>
              <option value="quarter">自然季度</option>
              <option value="year">自然年</option>
            </select>
            <small>按真实日历周期判断，不按固定天数滚动计算。</small>
          </label>
        </div>

        <div class="config-actions">
          <button class="btn btn-primary" type="button" :disabled="savingConfig" @click="saveConfig">
            {{ savingConfig ? '保存中...' : '保存规则' }}
          </button>
          <span v-if="config.updated_at" class="config-updated">
            上次更新：{{ config.updated_at }}
          </span>
        </div>
      </div>

      <div class="card-surface rule-card">
        <div class="section-kicker">业务规则</div>
        <h3>当前执行逻辑</h3>
        <p>站经理签字确认、检查人完成确认或自动到期确认都会封存巡检记录，封存后禁止继续新增、编辑、删除该检查表问题。</p>
        <p>同一站点同一检查表在同一{{ recordPeriodLabel }}只保留一条巡检记录，未确认完成前跨天继续写入同一条记录。</p>
        <p>系统会读取提交当天所属的真实日历周期；例如设置为自然月时，月底录入后第二天跨月即可重新登记。</p>
      </div>

      <div class="card-surface stat-card">
        <span>最近记录</span>
        <strong>{{ records.length }}</strong>
        <small>本页最多展示最近 500 条</small>
      </div>
      <div class="card-surface stat-card">
        <span>未完成</span>
        <strong>{{ pendingCount }}</strong>
        <small>仍允许继续登记问题</small>
      </div>
      <div class="card-surface stat-card">
        <span>已封存</span>
        <strong>{{ completedCount }}</strong>
        <small>不能再增删改问题</small>
      </div>
    </section>

    <section class="card-surface list-card">
      <div class="list-head">
        <div>
          <div class="section-kicker">记录清单</div>
          <h3>巡检记录完成状态</h3>
        </div>
        <div class="filter-actions">
          <button class="btn btn-secondary" type="button" @click="resetFilters">重置筛选</button>
        </div>
      </div>

      <div class="filter-grid">
        <label>
          <span>完成状态</span>
          <select v-model="filters.completionStatus">
            <option value="">全部</option>
            <option value="pending">待检查人确认</option>
            <option value="completed">已确认完成</option>
          </select>
        </label>
        <label>
          <span>记录周期</span>
          <input v-model.trim="filters.period" type="text" placeholder="输入月份、周、季度或年份" />
        </label>
        <label>
          <span>站点</span>
          <input v-model.trim="filters.station" type="text" placeholder="输入站点名称" />
        </label>
        <label>
          <span>检查表</span>
          <input v-model.trim="filters.table" type="text" placeholder="输入检查表名称" />
        </label>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>记录周期</th>
              <th>站点</th>
              <th>检查表</th>
              <th>问题数</th>
              <th>检查人</th>
              <th>完成确认</th>
              <th>站经理签字</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in paginatedRecords" :key="record.id">
              <td>
                <strong>{{ record.inspection_period_label || record.inspection_month || '-' }}</strong>
                <small>{{ record.inspection_date || '-' }}</small>
              </td>
              <td>
                <strong>{{ record.station_name || '-' }}</strong>
                <small>{{ record.station_region || '-' }}</small>
              </td>
              <td>{{ record.inspection_table_name || '-' }}</td>
              <td>{{ record.issue_count || 0 }}</td>
              <td>{{ record.inspector_names || '-' }}</td>
              <td>
                <span :class="['status-chip', isCompleted(record) ? 'success' : 'warning']">
                  {{ completionStatusLabel(record) }}
                </span>
                <small v-if="isCompleted(record)" class="status-meta">
                  {{ completionMeta(record) }}
                </small>
              </td>
              <td>
                <span :class="['status-chip', record.sign_status === '已签名确认' ? 'success' : 'muted']">
                  {{ record.sign_status || '待签名确认' }}
                </span>
              </td>
              <td>
                <div class="table-actions">
                  <button v-if="!isCompleted(record)" class="btn btn-primary btn-sm" type="button"
                    :disabled="actingId === record.id" @click="confirmComplete(record)">
                    后台确认
                  </button>
                  <button v-else class="btn btn-secondary btn-sm" type="button"
                    :disabled="actingId === record.id || isSigned(record)"
                    :title="isSigned(record) ? '站经理已签字确认，不能恢复未完成' : ''" @click="reopenRecord(record)">
                    恢复未完成
                  </button>
                  <small v-if="isSigned(record)" class="action-hint">站经理已签字，不能恢复</small>
                </div>
              </td>
            </tr>
            <tr v-if="!loading && filteredRecords.length === 0">
              <td colspan="8" class="empty-cell">当前没有符合条件的巡检记录。</td>
            </tr>
            <tr v-if="loading">
              <td colspan="8" class="empty-cell">正在加载巡检记录...</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!loading && filteredRecords.length" class="pagination-bar">
        <div class="pagination-summary">共 {{ filteredRecords.length }} 条记录</div>
        <div class="pagination-controls">
          <div class="pagination-size-control">
            <label>每页显示</label>
            <select v-model.number="pageSize">
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
            </select>
          </div>
          <div class="pagination-nav-row">
            <button class="btn btn-secondary pagination-btn" type="button" :disabled="page <= 1"
              @click="goToPage(1)">首页</button>
            <button class="btn btn-secondary pagination-btn" type="button" :disabled="page <= 1"
              @click="prevPage">上一页</button>
          </div>
          <div class="pagination-page-list" aria-label="巡检封存管理页码">
            <template v-for="item in visiblePageItems" :key="item.key">
              <span v-if="item.type === 'ellipsis'" class="pagination-ellipsis">...</span>
              <button v-else class="pagination-page-btn" :class="{ active: item.value === page }" type="button"
                @click="goToPage(item.value)">
                {{ item.value }}
              </button>
            </template>
          </div>
          <div class="pagination-nav-row">
            <button class="btn btn-secondary pagination-btn" type="button" :disabled="page >= totalPage"
              @click="nextPage">下一页</button>
            <button class="btn btn-secondary pagination-btn" type="button" :disabled="page >= totalPage"
              @click="goToPage(totalPage)">末页</button>
          </div>
          <div class="pagination-jump">
            <span>跳至</span>
            <input v-model="pageJumpInput" type="number" min="1" :max="totalPage" :placeholder="`1-${totalPage}`"
              @keyup.enter="jumpToInputPage" />
            <button class="btn btn-primary pagination-jump-btn" type="button" @click="jumpToInputPage">跳转</button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import axios from 'axios'

const loading = ref(false)
const savingConfig = ref(false)
const actingId = ref(null)
const records = ref([])
const config = reactive({
  auto_complete_enabled: true,
  auto_complete_days: 7,
  record_uniqueness_period: 'month',
  record_uniqueness_period_label: '自然月',
  updated_at: ''
})
const filters = reactive({
  completionStatus: '',
  period: '',
  station: '',
  table: ''
})
const page = ref(1)
const pageSize = ref(10)
const pageJumpInput = ref('')
const message = reactive({
  text: '',
  type: 'info'
})
let messageTimer = null

const userId = () => localStorage.getItem('user_id') || ''

const showMessage = (text, type = 'info') => {
  if (messageTimer) {
    clearTimeout(messageTimer)
    messageTimer = null
  }
  message.text = text
  message.type = type
  if (!text) return
  messageTimer = setTimeout(() => {
    message.text = ''
    message.type = 'info'
    messageTimer = null
  }, 2600)
}

const isSigned = (record) => record?.sign_status === '已签名确认'
const isCompleted = (record) => record?.inspector_completion_status === '已确认完成' || isSigned(record)
const pendingCount = computed(() => records.value.filter((record) => !isCompleted(record)).length)
const completedCount = computed(() => records.value.filter(isCompleted).length)
const periodLabels = {
  week: '自然周',
  month: '自然月',
  quarter: '自然季度',
  year: '自然年'
}
const recordPeriodLabel = computed(() => {
  return config.record_uniqueness_period_label || periodLabels[config.record_uniqueness_period] || '自然月'
})

const normalize = (value) => String(value || '').trim().toLowerCase()
const filteredRecords = computed(() => records.value.filter((record) => {
  const status = isCompleted(record) ? 'completed' : 'pending'
  const matchedStatus = !filters.completionStatus || filters.completionStatus === status
  const periodText = `${record.inspection_period_label || ''} ${record.inspection_period_key || ''} ${record.inspection_month || ''}`
  const matchedPeriod = !filters.period || normalize(periodText).includes(normalize(filters.period))
  const matchedStation = !filters.station || normalize(record.station_name).includes(normalize(filters.station))
  const matchedTable = !filters.table || normalize(record.inspection_table_name).includes(normalize(filters.table))
  return matchedStatus && matchedPeriod && matchedStation && matchedTable
}))

const totalPage = computed(() => Math.max(1, Math.ceil(filteredRecords.value.length / pageSize.value)))

const visiblePageItems = computed(() => {
  const total = totalPage.value
  const current = page.value

  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => {
      const value = index + 1
      return { type: 'page', value, key: `page-${value}` }
    })
  }

  const pages = new Set([1, total, current, current - 1, current + 1])
  if (current <= 3) {
    pages.add(2)
    pages.add(3)
    pages.add(4)
  }
  if (current >= total - 2) {
    pages.add(total - 1)
    pages.add(total - 2)
    pages.add(total - 3)
  }

  const sortedPages = [...pages]
    .filter((value) => value >= 1 && value <= total)
    .sort((a, b) => a - b)

  const result = []
  sortedPages.forEach((value, index) => {
    const previous = sortedPages[index - 1]
    if (index > 0 && value - previous > 1) {
      result.push({ type: 'ellipsis', key: `ellipsis-${previous}-${value}` })
    }
    result.push({ type: 'page', value, key: `page-${value}` })
  })

  return result
})

const paginatedRecords = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRecords.value.slice(start, start + pageSize.value)
})

const completionMeta = (record) => {
  if (isSigned(record) && (
    !record.inspector_completion_source_label ||
    record.inspector_completion_source === 'signature'
  )) {
    const signedName = record.station_manager_signed_name || ''
    const signedAt = record.station_manager_signed_at || record.inspector_completed_at || ''
    return ['站经理签字确认', signedName, signedAt].filter(Boolean).join('｜') || '站经理签字确认'
  }
  const source = record.inspector_completion_source_label || ''
  const by = record.inspector_completed_by_name || record.inspector_completed_by_username || ''
  const at = record.inspector_completed_at || ''
  return [source, by, at].filter(Boolean).join('｜') || '已确认完成'
}

const completionStatusLabel = (record) => {
  return isCompleted(record) ? '已确认完成' : record?.inspector_completion_status || '待检查人确认'
}

const applyConfig = (nextConfig = {}) => {
  config.auto_complete_enabled = Boolean(nextConfig.auto_complete_enabled)
  config.auto_complete_days = Number(nextConfig.auto_complete_days || 7)
  config.record_uniqueness_period = nextConfig.record_uniqueness_period || 'month'
  config.record_uniqueness_period_label = nextConfig.record_uniqueness_period_label || periodLabels[config.record_uniqueness_period] || '自然月'
  config.updated_at = nextConfig.updated_at || ''
}

const fetchData = async () => {
  try {
    loading.value = true
    const response = await axios.get('/api/management/inspection-completion', {
      params: { user_id: userId(), _ts: Date.now() }
    })
    applyConfig(response.data?.config || {})
    records.value = response.data?.records || []
    if (response.data?.auto_completed_count > 0) {
      showMessage(`系统已自动确认 ${response.data.auto_completed_count} 条超期巡检记录。`, 'success')
    }
  } catch (error) {
    records.value = []
    showMessage(error?.response?.data?.error || '巡检封存数据加载失败。', 'error')
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  try {
    savingConfig.value = true
    const response = await axios.put('/api/management/inspection-completion/config', {
      user_id: userId(),
      auto_complete_enabled: config.auto_complete_enabled,
      auto_complete_days: config.auto_complete_days,
      record_uniqueness_period: config.record_uniqueness_period
    })
    applyConfig(response.data?.config || config)
    showMessage(response.data?.message || '规则已保存。', 'success')
  } catch (error) {
    showMessage(error?.response?.data?.error || '规则保存失败。', 'error')
  } finally {
    savingConfig.value = false
  }
}

const confirmComplete = async (record) => {
  if (!record?.id || actingId.value) return
  if (!window.confirm(`确认将【${record.station_name}｜${record.inspection_table_name}】封存为已完成吗？`)) return
  try {
    actingId.value = record.id
    const response = await axios.post(`/api/management/inspection-completion/${record.id}/complete`, {
      user_id: userId()
    })
    showMessage(response.data?.message || '已确认完成。', 'success')
    await fetchData()
  } catch (error) {
    showMessage(error?.response?.data?.error || '后台确认失败。', 'error')
  } finally {
    actingId.value = null
  }
}

const reopenRecord = async (record) => {
  if (!record?.id || actingId.value) return
  if (isSigned(record)) {
    showMessage('站经理已签字确认的巡检记录不能恢复为未完成。', 'error')
    return
  }
  if (!window.confirm(`确认将【${record.station_name}｜${record.inspection_table_name}】恢复为未完成吗？恢复后仍受当前自然周期唯一记录规则限制。`)) return
  try {
    actingId.value = record.id
    const response = await axios.post(`/api/management/inspection-completion/${record.id}/reopen`, {
      user_id: userId()
    })
    showMessage(response.data?.message || '已恢复为未完成。', 'success')
    await fetchData()
  } catch (error) {
    showMessage(error?.response?.data?.error || '恢复失败。', 'error')
  } finally {
    actingId.value = null
  }
}

const resetFilters = () => {
  filters.completionStatus = ''
  filters.period = ''
  filters.station = ''
  filters.table = ''
}

const goToPage = (targetPage) => {
  const normalizedPage = Number.parseInt(targetPage, 10)
  if (!Number.isFinite(normalizedPage)) return
  page.value = Math.min(Math.max(normalizedPage, 1), totalPage.value)
}

const prevPage = () => {
  goToPage(page.value - 1)
}

const nextPage = () => {
  goToPage(page.value + 1)
}

const jumpToInputPage = () => {
  goToPage(pageJumpInput.value)
  pageJumpInput.value = ''
}

watch([filters, pageSize], () => {
  page.value = 1
}, { deep: true })

watch(totalPage, (value) => {
  if (page.value > value) {
    page.value = value
  }
})

onMounted(fetchData)
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.card-surface {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dbe4ee;
  border-radius: 24px;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.07);
}

.page-header,
.section-head,
.list-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.page-header {
  padding: 26px 28px;
  background:
    radial-gradient(circle at 88% 8%, rgba(15, 118, 110, 0.15), transparent 30%),
    linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
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
}

.page-header h2,
.section-head h3,
.list-head h3,
.rule-card h3 {
  margin: 10px 0 0;
  color: #0f172a;
}

.page-header p,
.rule-card p,
.config-updated,
.stat-card small,
td small,
.status-meta,
.field-row small {
  color: #64748b;
  font-size: 12px;
  line-height: 1.7;
}

.config-grid {
  display: grid;
  grid-template-columns: minmax(360px, 1.5fr) minmax(300px, 1fr) repeat(3, minmax(150px, 0.55fr));
  gap: 16px;
  align-items: stretch;
}

.config-card,
.rule-card,
.stat-card,
.list-card {
  padding: 22px;
}

.config-card {
  grid-row: span 2;
}

.rule-card {
  grid-row: span 2;
}

.stat-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  min-height: 116px;
}

.stat-card span {
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.stat-card strong {
  color: #0f172a;
  font-size: 32px;
}

.config-form {
  display: grid;
  gap: 16px;
  margin-top: 18px;
}

.switch-row,
.field-row {
  display: grid;
  gap: 8px;
  color: #334155;
  font-size: 14px;
  font-weight: 800;
}

.switch-row {
  grid-template-columns: auto 1fr;
  align-items: center;
}

.field-row input,
.field-row select,
.filter-grid input,
.filter-grid select {
  width: 100%;
  height: 42px;
  padding: 0 12px;
  border: 1px solid #d1d5db;
  border-radius: 14px;
  box-sizing: border-box;
  color: #0f172a;
  background: #fff;
}

.config-actions,
.filter-actions,
.table-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.table-actions {
  flex-direction: column;
  align-items: flex-start;
}

.action-hint {
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.5;
}

.filter-grid {
  display: grid;
  grid-template-columns: 160px 180px repeat(2, minmax(220px, 1fr));
  gap: 14px;
  margin: 18px 0;
}

.filter-grid label {
  display: grid;
  gap: 7px;
  color: #334155;
  font-size: 13px;
  font-weight: 900;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1120px;
}

th,
td {
  padding: 13px 14px;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
  color: #0f172a;
  font-size: 13px;
  vertical-align: middle;
}

th {
  color: #475569;
  background: #f8fafc;
  font-weight: 900;
}

td strong,
td small {
  display: block;
}

tr:last-child td {
  border-bottom: none;
}

.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.pagination-summary {
  color: #475569;
  font-size: 14px;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.pagination-size-control,
.pagination-nav-row,
.pagination-page-list,
.pagination-jump {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.pagination-size-control label,
.pagination-jump span {
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
  white-space: nowrap;
}

.pagination-controls select,
.pagination-jump input {
  height: 40px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0 10px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
}

.pagination-jump input {
  width: 78px;
  text-align: center;
}

.pagination-btn,
.pagination-jump-btn {
  min-width: 72px;
}

.pagination-page-list {
  padding: 4px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
}

.pagination-page-btn {
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #475569;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
  transition: all 0.18s ease;
}

.pagination-page-btn:hover {
  background: #dbeafe;
  color: #1d4ed8;
}

.pagination-page-btn.active {
  background: #0f766e;
  color: #fff;
  box-shadow: 0 8px 16px rgba(15, 118, 110, 0.22);
}

.pagination-ellipsis {
  min-width: 28px;
  color: #94a3b8;
  font-weight: 900;
  line-height: 34px;
  text-align: center;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 5px 10px;
  border-radius: 999px;
  color: #475569;
  background: #f1f5f9;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
}

.status-chip.success {
  color: #166534;
  background: #dcfce7;
}

.status-chip.warning {
  color: #9a3412;
  background: #ffedd5;
}

.status-chip.muted {
  color: #64748b;
  background: #f1f5f9;
}

.empty-cell {
  padding: 28px;
  color: #64748b;
  text-align: center;
}

.action-toast {
  position: fixed;
  left: 50%;
  top: 84px;
  z-index: 3000;
  transform: translateX(-50%);
  min-width: min(420px, calc(100vw - 32px));
  padding: 14px 18px;
  text-align: center;
  font-size: 14px;
  font-weight: 900;
}

.action-toast.success {
  color: #166534;
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.action-toast.error {
  color: #991b1b;
  background: #fef2f2;
  border-color: #fecaca;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}

@media (max-width: 1180px) {
  .config-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .config-card,
  .rule-card {
    grid-row: auto;
  }

  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .pagination-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .pagination-controls {
    align-items: stretch;
    flex-direction: column;
  }

  .pagination-nav-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .pagination-page-list {
    justify-content: flex-start;
    overflow-x: auto;
  }

  .pagination-jump {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) 82px;
  }

  .pagination-jump input {
    width: 100%;
  }
}
</style>
