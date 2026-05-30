<template>
  <div class="page-shell ai-usage-page">
    <div class="page-header card-surface ai-hero">
      <div>
        <div class="page-kicker">管理系统</div>
        <h2>AI调用统计</h2>
        <p>统计用户在系统中调用 DeepSeek AI 的位置、次数、字符量、估算 token 与费用，便于后续做成本和使用情况分析。</p>
      </div>
      <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchUsage">
        {{ loading ? '刷新中...' : '刷新数据' }}
      </button>
    </div>

    <div v-if="error" class="card-surface permission-card">
      <div class="permission-icon">!</div>
      <div class="permission-title">无法读取 AI 调用统计</div>
      <div class="permission-desc">{{ error }}</div>
    </div>

    <template v-else>
      <section class="summary-grid">
        <div class="card-surface summary-card primary">
          <span>功能触发次数</span>
          <strong>{{ formatNumber(summary.total_calls) }}</strong>
          <small>包含 AI 成功与本地回退记录</small>
        </div>
        <div class="card-surface summary-card">
          <span>实际请求 AI</span>
          <strong>{{ formatNumber(summary.ai_called) }}</strong>
          <small>成功 {{ formatNumber(summary.success) }} 次，回退 {{ formatNumber(summary.fallback) }} 次</small>
        </div>
        <div class="card-surface summary-card">
          <span>估算 Tokens</span>
          <strong>{{ formatNumber(summary.total_tokens_est, 2) }}</strong>
          <small>输入 {{ formatNumber(summary.input_tokens_est, 2) }} / 输出 {{ formatNumber(summary.output_tokens_est, 2) }}</small>
        </div>
        <div class="card-surface summary-card cost">
          <span>估算费用</span>
          <strong>{{ formatMoney(summary.total_cost_est) }}</strong>
          <small>按缓存未命中输入价粗略估算</small>
        </div>
      </section>

      <section class="card-surface filter-card">
        <div class="section-head">
          <div>
            <div class="section-kicker">筛选条件</div>
            <h3>按用户、位置、模型和时间查看</h3>
          </div>
          <div class="filter-actions">
            <button class="btn btn-secondary" type="button" @click="resetFilters">重置筛选</button>
            <button class="btn btn-primary" type="button" :disabled="loading" @click="fetchUsage">应用筛选</button>
          </div>
        </div>

        <div class="filter-grid">
          <label class="date-range-filter">
            <span>调用时间范围</span>
            <DateRangePicker
              v-model:date-from="filters.date_from"
              v-model:date-to="filters.date_to"
              placeholder="选择调用时间范围"
              aria-label="选择调用时间范围"
            />
          </label>
          <label>
            <span>使用位置</span>
            <select v-model="filters.usage_module">
              <option value="">全部位置</option>
              <option v-for="item in options.modules" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>
          <label>
            <span>模型</span>
            <select v-model="filters.model">
              <option value="">全部模型</option>
              <option v-for="item in options.models" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>
          <label>
            <span>状态</span>
            <select v-model="filters.status">
              <option v-for="item in options.status" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label>
            <span>用户/关键词</span>
            <input v-model.trim="filters.keyword" type="search" placeholder="姓名、账号、使用场景" @keyup.enter="fetchUsage" />
          </label>
        </div>
      </section>

      <section class="insight-grid">
        <div class="card-surface insight-card">
          <div class="section-head compact">
            <div>
              <div class="section-kicker">使用位置</div>
              <h3>功能调用分布</h3>
            </div>
          </div>
          <div class="rank-list">
            <div v-if="!byContext.length" class="empty-cell">暂无调用数据。</div>
            <div v-for="item in byContext" :key="item.key" class="rank-item">
              <div>
                <strong>{{ item.label }}</strong>
                <span>{{ formatNumber(item.total_chars) }} 字符 · {{ formatMoney(item.total_cost_est) }}</span>
              </div>
              <em>{{ item.calls }} 次</em>
            </div>
          </div>
        </div>

        <div class="card-surface insight-card">
          <div class="section-head compact">
            <div>
              <div class="section-kicker">用户排行</div>
              <h3>账号使用概览</h3>
            </div>
          </div>
          <div class="rank-list">
            <div v-if="!byUser.length" class="empty-cell">暂无用户调用数据。</div>
            <div v-for="item in byUser" :key="item.key" class="rank-item">
              <div>
                <strong>{{ item.label }}</strong>
                <span>{{ formatNumber(item.total_tokens_est, 2) }} tokens · {{ formatMoney(item.total_cost_est) }}</span>
              </div>
              <em>{{ item.calls }} 次</em>
            </div>
          </div>
        </div>

        <div class="card-surface pricing-card">
          <div class="section-kicker">估算规则</div>
          <h3>字符、Token 与价格</h3>
          <p>系统按“中文字符约 0.6 token、其他字符约 0.3 token”粗略估算。由于无法稳定获取缓存命中情况，费用默认按输入缓存未命中价格估算。</p>
          <div class="pricing-table">
            <div class="pricing-head">
              <span>模型</span>
              <span>输入/百万</span>
              <span>输出/百万</span>
            </div>
            <div v-for="item in options.pricing" :key="item.model" class="pricing-row">
              <span>{{ item.model }}</span>
              <span>¥{{ item.input_cache_miss }}</span>
              <span>¥{{ item.output }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="card-surface detail-card">
        <div class="section-head">
          <div>
            <div class="section-kicker">调用明细</div>
            <h3>最近 {{ filteredItems.length }} 条记录</h3>
            <p>后端最多返回 2000 条筛选结果，页面内做分页展示。</p>
          </div>
          <div class="detail-meta">总估算费用：{{ formatMoney(summary.total_cost_est) }}</div>
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>用户</th>
                <th>使用位置</th>
                <th>模型</th>
                <th>字符量</th>
                <th>估算 Token</th>
                <th>估算费用</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="8" class="empty-cell">正在加载 AI 调用统计...</td>
              </tr>
              <tr v-else-if="!paginatedItems.length">
                <td colspan="8" class="empty-cell">当前没有符合条件的 AI 调用记录。</td>
              </tr>
              <tr v-for="item in paginatedItems" :key="item.id">
                <td>
                  <strong>{{ item.created_at }}</strong>
                  <small>#{{ item.id }}</small>
                </td>
                <td>
                  <strong>{{ item.real_name || item.username || '-' }}</strong>
                  <small>{{ roleLabel(item.role) }} · {{ item.username || '-' }}</small>
                </td>
                <td>
                  <strong>{{ item.usage_module }} · {{ item.usage_action }}</strong>
                  <small>{{ item.request_summary || '-' }}</small>
                </td>
                <td>{{ item.model }}</td>
                <td>
                  <strong>{{ formatNumber(item.total_chars) }}</strong>
                  <small>输入 {{ formatNumber(item.prompt_chars) }} / 输出 {{ formatNumber(item.completion_chars) }}</small>
                </td>
                <td>{{ formatNumber(item.total_tokens_est, 2) }}</td>
                <td>{{ formatMoney(item.total_cost_est) }}</td>
                <td>
                  <span :class="['status-chip', statusClass(item)]">{{ statusLabel(item) }}</span>
                  <small>{{ item.message || '-' }}</small>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="filteredItems.length" class="pagination-bar">
          <div class="pagination-summary">共 {{ filteredItems.length }} 条</div>
          <div class="pagination-controls">
            <button class="btn btn-secondary pagination-btn" type="button" :disabled="page <= 1" @click="goToPage(1)">首页</button>
            <button class="btn btn-secondary pagination-btn" type="button" :disabled="page <= 1" @click="goToPage(page - 1)">上一页</button>
            <div class="pagination-page-list">
              <template v-for="item in visiblePageItems" :key="item.key">
                <span v-if="item.type === 'ellipsis'" class="pagination-ellipsis">...</span>
                <button v-else class="pagination-page-btn" :class="{ active: item.value === page }" type="button" @click="goToPage(item.value)">
                  {{ item.value }}
                </button>
              </template>
            </div>
            <button class="btn btn-secondary pagination-btn" type="button" :disabled="page >= totalPage" @click="goToPage(page + 1)">下一页</button>
            <button class="btn btn-secondary pagination-btn" type="button" :disabled="page >= totalPage" @click="goToPage(totalPage)">末页</button>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import axios from 'axios'
import DateRangePicker from '@/components/DateRangePicker.vue'

const loading = ref(false)
const error = ref('')
const items = ref([])
const byUser = ref([])
const byContext = ref([])
const summary = reactive({
  total_calls: 0,
  ai_called: 0,
  success: 0,
  fallback: 0,
  prompt_chars: 0,
  completion_chars: 0,
  total_chars: 0,
  input_tokens_est: 0,
  output_tokens_est: 0,
  total_tokens_est: 0,
  total_cost_est: 0
})
const options = reactive({
  modules: [],
  models: [],
  status: [{ value: '', label: '全部状态' }],
  pricing: []
})
const filters = reactive({
  date_from: '',
  date_to: '',
  usage_module: '',
  model: '',
  status: '',
  keyword: ''
})
const page = ref(1)
const pageSize = ref(20)

const userId = () => localStorage.getItem('user_id') || ''

const filteredItems = computed(() => items.value)
const totalPage = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / pageSize.value)))
const paginatedItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredItems.value.slice(start, start + pageSize.value)
})
const visiblePageItems = computed(() => {
  const total = totalPage.value
  const current = page.value
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => ({
      type: 'page',
      value: index + 1,
      key: `page-${index + 1}`
    }))
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
  const sorted = Array.from(pages).filter((value) => value >= 1 && value <= total).sort((a, b) => a - b)
  const result = []
  sorted.forEach((value, index) => {
    if (index > 0 && value - sorted[index - 1] > 1) {
      result.push({ type: 'ellipsis', key: `ellipsis-${sorted[index - 1]}-${value}` })
    }
    result.push({ type: 'page', value, key: `page-${value}` })
  })
  return result
})

const applySummary = (payload = {}) => {
  Object.keys(summary).forEach((key) => {
    summary[key] = Number(payload[key] || 0)
  })
}

const fetchUsage = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get('/api/management/ai-usage', {
      params: {
        user_id: userId(),
        ...filters
      }
    })
    if (!response.data?.success) throw new Error(response.data?.error || 'AI 调用统计读取失败。')
    applySummary(response.data.summary)
    items.value = response.data.items || []
    byUser.value = response.data.by_user || []
    byContext.value = response.data.by_context || []
    Object.assign(options, response.data.options || {})
    page.value = 1
  } catch (err) {
    error.value = err.response?.data?.error || err.message || 'AI 调用统计读取失败。'
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  Object.assign(filters, {
    date_from: '',
    date_to: '',
    usage_module: '',
    model: '',
    status: '',
    keyword: ''
  })
  fetchUsage()
}

const goToPage = (value) => {
  const next = Math.min(Math.max(Number(value) || 1, 1), totalPage.value)
  page.value = next
}

const formatNumber = (value, digits = 0) => {
  const number = Number(value || 0)
  return number.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })
}

const formatMoney = (value) => `¥${Number(value || 0).toFixed(6)}`

const roleLabel = (role) => {
  if (role === 'root') return '系统管理员'
  if (role === 'supervisor') return '督导组'
  if (role === 'station_manager') return '站点账号'
  if (role === 'quality_safety') return '质安部'
  if (role === 'development_plan') return '发展计划部'
  return role || '-'
}

const statusLabel = (item) => {
  if (item.success) return 'AI 成功'
  if (item.fallback_used) return item.ai_called ? 'AI失败回退' : '本地回退'
  if (item.ai_called) return '已请求'
  return '未请求'
}

const statusClass = (item) => {
  if (item.success) return 'success'
  if (item.fallback_used) return 'warning'
  return 'muted'
}

watch(totalPage, () => {
  if (page.value > totalPage.value) page.value = totalPage.value
})

onMounted(fetchUsage)
</script>

<style scoped>
.ai-usage-page {
  display: grid;
  gap: 18px;
}

.card-surface {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 24px;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
}

.ai-hero {
  background:
    radial-gradient(circle at 12% 20%, rgba(34, 197, 94, 0.16), transparent 34%),
    linear-gradient(135deg, rgba(240, 253, 244, 0.98), rgba(239, 246, 255, 0.98));
}

.page-header,
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.page-header {
  padding: 24px;
}

.page-kicker,
.section-kicker {
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.page-header h2,
.section-head h3,
.pricing-card h3 {
  margin: 6px 0 8px;
  color: #102033;
}

.page-header p,
.section-head p,
.pricing-card p {
  margin: 0;
  color: #64748b;
  line-height: 1.7;
}

.btn {
  border: 0;
  border-radius: 14px;
  padding: 10px 16px;
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.btn:not(:disabled):hover {
  transform: translateY(-1px);
}

.btn-primary {
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #fff;
  box-shadow: 0 12px 28px rgba(20, 184, 166, 0.24);
}

.btn-secondary {
  background: #eef6f5;
  color: #0f766e;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.summary-card {
  padding: 20px;
  display: grid;
  gap: 8px;
  overflow: hidden;
  position: relative;
}

.summary-card::after {
  content: "";
  position: absolute;
  right: -26px;
  top: -26px;
  width: 88px;
  height: 88px;
  border-radius: 999px;
  background: rgba(20, 184, 166, 0.12);
}

.summary-card span,
.summary-card small {
  color: #64748b;
}

.summary-card strong {
  color: #0f172a;
  font-size: 30px;
}

.summary-card.primary {
  background: linear-gradient(135deg, #123734, #0f766e);
}

.summary-card.primary span,
.summary-card.primary small,
.summary-card.primary strong {
  color: #fff;
}

.summary-card.cost strong {
  color: #b45309;
}

.filter-card,
.detail-card,
.insight-card,
.pricing-card {
  padding: 22px;
}

.filter-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
}

.filter-grid label {
  display: grid;
  gap: 8px;
  color: #475569;
  font-size: 13px;
  font-weight: 800;
}

.filter-grid .date-range-filter {
  grid-column: span 2;
}

.filter-grid input,
.filter-grid select {
  width: 100%;
  min-height: 42px;
  border: 1px solid #d8e3ea;
  border-radius: 14px;
  background: #f8fbfc;
  color: #0f172a;
  padding: 0 12px;
  font: inherit;
  outline: none;
}

.filter-grid input:focus,
.filter-grid select:focus {
  border-color: #14b8a6;
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.14);
}

.filter-grid :deep(.date-range-trigger) {
  min-height: 42px;
  border-radius: 14px;
  background: #f8fbfc;
  --date-range-border: #d8e3ea;
  --date-range-focus: #14b8a6;
  --date-range-focus-shadow: rgba(20, 184, 166, 0.14);
}

.insight-grid {
  display: grid;
  grid-template-columns: 1.1fr 1.1fr 0.9fr;
  gap: 14px;
}

.section-head.compact {
  margin-bottom: 14px;
}

.rank-list {
  display: grid;
  gap: 10px;
}

.rank-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 12px;
  background: #f8fafc;
}

.rank-item div {
  display: grid;
  gap: 4px;
}

.rank-item strong {
  color: #0f172a;
}

.rank-item span,
.rank-item em {
  color: #64748b;
  font-size: 12px;
}

.rank-item em {
  font-style: normal;
  font-weight: 900;
  color: #0f766e;
  white-space: nowrap;
}

.pricing-table {
  margin-top: 16px;
  display: grid;
  gap: 8px;
}

.pricing-head,
.pricing-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
  gap: 8px;
  align-items: center;
}

.pricing-head {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.pricing-row {
  padding: 10px;
  border-radius: 14px;
  background: #f8fafc;
  color: #334155;
  font-weight: 800;
}

.detail-meta {
  color: #b45309;
  font-weight: 900;
  white-space: nowrap;
}

.table-wrap {
  width: 100%;
  overflow-x: auto;
  margin-top: 16px;
}

table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0 10px;
}

th {
  color: #64748b;
  font-size: 12px;
  text-align: left;
  padding: 0 12px;
  white-space: nowrap;
}

td {
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
  color: #334155;
  padding: 13px 12px;
  vertical-align: top;
}

td:first-child {
  border-left: 1px solid #e2e8f0;
  border-radius: 16px 0 0 16px;
}

td:last-child {
  border-right: 1px solid #e2e8f0;
  border-radius: 0 16px 16px 0;
}

td strong,
td small {
  display: block;
}

td strong {
  color: #0f172a;
}

td small {
  margin-top: 4px;
  color: #64748b;
  line-height: 1.5;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
  font-weight: 900;
}

.status-chip.success {
  background: #dcfce7;
  color: #166534;
}

.status-chip.warning {
  background: #fef3c7;
  color: #92400e;
}

.status-chip.muted {
  background: #e2e8f0;
  color: #475569;
}

.empty-cell {
  color: #94a3b8;
  text-align: center;
  padding: 20px;
}

.permission-card {
  padding: 42px;
  text-align: center;
}

.permission-icon {
  width: 54px;
  height: 54px;
  margin: 0 auto 12px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 28px;
  font-weight: 900;
}

.permission-title {
  font-size: 20px;
  font-weight: 900;
  color: #0f172a;
}

.permission-desc {
  margin-top: 8px;
  color: #64748b;
}

.pagination-bar {
  margin-top: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.pagination-summary {
  color: #64748b;
  font-weight: 800;
}

.pagination-controls,
.pagination-page-list {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.pagination-btn,
.pagination-page-btn {
  min-height: 36px;
  padding: 8px 12px;
  border-radius: 12px;
}

.pagination-page-btn {
  border: 1px solid #d8e3ea;
  background: #fff;
  color: #475569;
  font-weight: 900;
  cursor: pointer;
}

.pagination-page-btn.active {
  border-color: #0f766e;
  background: #0f766e;
  color: #fff;
}

.pagination-ellipsis {
  color: #94a3b8;
  font-weight: 900;
}

@media (max-width: 1180px) {
  .summary-grid,
  .insight-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .filter-grid .date-range-filter {
    grid-column: span 2;
  }

  .pricing-card {
    grid-column: 1 / -1;
  }
}

@media (max-width: 720px) {
  .page-header,
  .section-head,
  .pagination-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .summary-grid,
  .insight-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .filter-grid .date-range-filter {
    grid-column: auto;
  }

  .page-header,
  .filter-card,
  .detail-card,
  .insight-card,
  .pricing-card {
    padding: 18px;
    border-radius: 20px;
  }

  .pagination-controls {
    justify-content: center;
  }
}
</style>
