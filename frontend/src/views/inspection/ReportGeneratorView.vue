<template>
  <div class="report-page">
    <section class="report-hero card-surface">
      <div>
        <div class="page-kicker">报告自动生成</div>
        <h2>月度监督检查报告</h2>
        <p>先以质量计量监督检查报告为样板，按月份汇总计量稽查现场与视频检查问题数据。</p>
      </div>
      <div class="report-month-control">
        <label>
          <span>报告月份</span>
          <input v-model="selectedMonth" type="month" @change="fetchReport" />
        </label>
        <button type="button" class="regenerate-report-btn" :disabled="loading" @click="fetchReport({ force: true })">
          重新生成
        </button>
      </div>
    </section>

    <div v-if="error" class="state-card error">{{ error }}</div>

    <section v-if="loading" class="state-card card-surface">
      <div class="state-orb loading"></div>
      <h3>正在生成报告</h3>
      <p>系统正在读取检查表、站点和问题数据，稍等一下就好。</p>
    </section>

    <section v-else class="report-document card-surface">
      <div class="report-document-head">
        <div>
          <span class="doc-eyebrow">{{ report.month_label || '-' }}</span>
          <h1>{{ report.title || '上海销售质量计量监督检查报告' }}</h1>
        </div>
        <div class="doc-meta">
          <span>数据来源</span>
          <strong>{{ targetTableText }}</strong>
          <small>上次生成：{{ reportGeneratedAt }}</small>
          <small v-if="reportSnapshot.cached" class="snapshot-hint">当前展示上次生成结果</small>
        </div>
      </div>

      <div class="summary-cards">
        <article v-for="card in summaryCards" :key="card.label" class="summary-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>

      <article class="chapter-card">
        <div class="chapter-banner">第一章　总体情况</div>
        <p class="chapter-lead">{{ report.overview_text || emptyOverviewText }}</p>

        <div class="report-table-wrap">
          <table class="report-table">
            <thead>
              <tr>
                <th rowspan="2">二级单位</th>
                <th rowspan="2">检查站点数量</th>
                <th colspan="2">发现问题数量</th>
                <th rowspan="2">单库、车、站问题数量</th>
              </tr>
              <tr>
                <th>一般性问题</th>
                <th>涉及禁止项问题</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!reportRows.length">
                <td colspan="5" class="empty-cell">当前月份暂无计量稽查问题数据。</td>
              </tr>
              <tr v-for="row in reportRows" :key="`${row.unit_type}-${row.unit_name}`">
                <td>
                  <div class="unit-cell">
                    <span :class="['unit-type-pill', row.unit_type]">{{ row.unit_type_label }}</span>
                    <strong>{{ row.unit_name }}</strong>
                  </div>
                </td>
                <td>{{ row.station_count }}</td>
                <td>{{ row.general_issue_count }}</td>
                <td>{{ row.prohibited_issue_count }}</td>
                <td>{{ row.total_issue_count }}</td>
              </tr>
              <tr class="total-row">
                <td>{{ totalRow.unit_name || '合计' }}</td>
                <td>{{ totalRow.station_count || 0 }}</td>
                <td>{{ totalRow.general_issue_count || 0 }}</td>
                <td>{{ totalRow.prohibited_issue_count || 0 }}</td>
                <td>{{ totalRow.total_issue_count || 0 }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="chapter-card">
        <div class="chapter-banner">第二章　检查发现-发现问题</div>
        <p class="chapter-lead">{{ chapterTwoText }}</p>
      </article>

      <article class="chapter-card">
        <div class="chapter-banner">第三章　检查发现-禁止项问题</div>
        <p class="chapter-note">
          系统从禁止项问题中优先按片区或控（参）股单位去重选取典型问题，最多展示 10 项。
        </p>
        <div class="report-table-wrap">
          <table class="report-table typical-table">
            <thead>
              <tr>
                <th>所属单位（片区/控参股单位）</th>
                <th>禁止项管理规定（具体问题描述）</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!prohibitedExamples.length">
                <td colspan="2" class="empty-cell">当前月份暂无可提取的禁止项典型问题。</td>
              </tr>
              <tr v-for="item in prohibitedExamples" :key="`prohibited-${item.issue_id}-${item.unit_name}`">
                <td>
                  <div class="unit-cell">
                    <span :class="['unit-type-pill', item.unit_type]">{{ item.unit_type_label }}</span>
                    <strong>{{ item.unit_name }}</strong>
                  </div>
                </td>
                <td class="text-cell">{{ item.description }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="chapter-card station-link-chapter">
        <div class="chapter-banner">第四章　检查发现-加油站环节</div>
        <p class="chapter-lead strong-lead">{{ stationLinkText }}</p>
        <h4 class="chart-title">分布条形图</h4>
        <div class="bar-chart" :style="{ '--chart-max': chartMax }">
          <div class="chart-grid">
            <span v-for="tick in chartTicks" :key="`tick-${tick}`" :style="{ bottom: `${(tick / chartMax) * 100}%` }">
              {{ tick }}
            </span>
          </div>
          <div class="chart-bars">
            <div v-for="item in businessFlowRows" :key="`flow-${item.name}`" class="chart-bar-item">
              <div class="bar-value">{{ item.count }}</div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ height: `${getBarHeight(item.count)}%` }"></div>
              </div>
              <div class="bar-label">{{ item.name }}</div>
              <div class="bar-percent">{{ formatPercent(item.percentage) }}</div>
            </div>
            <div v-if="!businessFlowRows.length" class="chart-empty">当前月份暂无业务流程分布数据。</div>
          </div>
        </div>
      </article>

      <article class="chapter-card">
        <div class="chapter-banner">第五章　各环节突出问题</div>
        <div class="analysis-source-pill" :class="{ ai: deepAnalysis.ai_generated }">
          {{ deepAnalysis.ai_generated ? 'AI已辅助筛选突出问题' : 'AI暂不可用，已使用本地规则筛选' }}
        </div>
        <section v-for="flow in flowHighlights" :key="`highlight-${flow.flow_name}`" class="flow-highlight-section">
          <div class="flow-highlight-head">
            <h4>{{ flow.flow_name }}</h4>
            <p>发现问题{{ flow.count || 0 }}项，突出问题{{ flow.highlight_count || 0 }}项：</p>
          </div>
          <p v-if="flow.summary" class="flow-highlight-summary">{{ flow.summary }}</p>
          <div v-if="flow.highlighted_issues?.length" class="highlight-issue-grid">
            <article v-for="issue in flow.highlighted_issues" :key="`highlight-issue-${flow.flow_name}-${issue.issue_id}`"
              class="highlight-issue-card">
              <div class="highlight-issue-text">
                <span>{{ issue.unit_name || '未设置单位' }}</span>
                <strong>{{ issue.station_name || '未命名站点' }}</strong>
                <p>{{ issue.description || '暂无问题描述' }}</p>
              </div>
              <button
                v-if="issue.issue_photo"
                type="button"
                class="highlight-photo is-clickable"
                @click="openImagePreview(issue.issue_photo, `${issue.station_name || '问题'}照片`)"
              >
                <img :src="resolveImage(issue.issue_photo)" alt="问题照片" />
              </button>
              <div v-else class="highlight-photo">
                <span>暂无照片</span>
              </div>
            </article>
          </div>
          <div v-else class="empty-highlight">当前环节暂无可展示的突出问题。</div>
        </section>
      </article>

      <article class="chapter-card trace-chapter">
        <div class="chapter-banner">第六章　管理追溯</div>
        <div v-if="managementTrace.typical_issue" class="trace-problem-card">
          <span>典型问题</span>
          <strong>{{ formatStationIssue(managementTrace.typical_issue) }}</strong>
        </div>
        <div v-else class="trace-problem-card muted">
          <span>典型问题</span>
          <strong>当前月份暂无可追溯的典型问题。</strong>
        </div>

        <div class="trace-analysis-grid">
          <article>
            <span>（1）执行层面</span>
            <p>{{ managementTrace.execution_analysis || '-' }}</p>
          </article>
          <article>
            <span>（2）监督层面</span>
            <p>{{ managementTrace.supervision_analysis || '-' }}</p>
          </article>
          <article>
            <span>（3）管理层面</span>
            <p>{{ managementTrace.management_analysis || '-' }}</p>
          </article>
        </div>

        <div class="trace-conclusion-card">
          <h4>典型问题分析</h4>
          <p>{{ managementTrace.conclusion || '综上所述：当前月份暂无可分析的典型问题。' }}</p>
          <h4>改进措施</h4>
          <ol v-if="managementTrace.improvement_measures?.length">
            <li v-for="item in managementTrace.improvement_measures" :key="`${item.level}-${item.content}`">
              <strong>{{ item.level }}：</strong>{{ item.content }}
            </li>
          </ol>
          <p v-else>暂无改进措施。</p>
        </div>
      </article>

      <article class="chapter-card">
        <div class="chapter-banner">第七章　工作计划</div>
        <div class="work-plan-list">
          <article v-for="(item, index) in workPlan" :key="`work-plan-${index}`" class="work-plan-card">
            <span>{{ index + 1 }}</span>
            <div>
              <h4>{{ item.title }}</h4>
              <p>{{ item.content }}</p>
            </div>
          </article>
        </div>
      </article>
    </section>

    <teleport to="body">
      <div v-if="imagePreview.visible" class="report-image-preview" @click.self="closeImagePreview">
        <img :src="imagePreview.src" :alt="imagePreview.title || '问题照片预览'" />
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'

const getDefaultReportMonth = () => {
  const now = new Date()
  const previousMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1)
  const year = previousMonth.getFullYear()
  const month = String(previousMonth.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

const selectedMonth = ref(getDefaultReportMonth())
const loading = ref(false)
const error = ref('')
const imagePreview = ref({
  visible: false,
  src: '',
  title: ''
})
const report = ref({
  month: '',
  month_label: '',
  title: '',
  target_tables: [],
  summary: {},
  overview_text: '',
  finding_summary: {},
  prohibited_examples: [],
  deep_analysis: {},
  rows: [],
  total_row: {}
})

const reportSnapshot = computed(() => report.value.snapshot || {})
const reportGeneratedAt = computed(() => (
  reportSnapshot.value.generated_at
  || report.value.summary?.generated_at
  || '-'
))
const reportRows = computed(() => Array.isArray(report.value.rows) ? report.value.rows : [])
const totalRow = computed(() => report.value.total_row || {})
const findingSummary = computed(() => report.value.finding_summary || {})
const businessFlowRows = computed(() => (
  Array.isArray(findingSummary.value.business_flow_distribution)
    ? findingSummary.value.business_flow_distribution
    : []
))
const prohibitedExamples = computed(() => (
  Array.isArray(report.value.prohibited_examples) ? report.value.prohibited_examples : []
))
const deepAnalysis = computed(() => report.value.deep_analysis || {})
const flowHighlights = computed(() => (
  Array.isArray(deepAnalysis.value.flow_highlights) ? deepAnalysis.value.flow_highlights : []
))
const managementTrace = computed(() => deepAnalysis.value.management_trace || {})
const workPlan = computed(() => (
  Array.isArray(deepAnalysis.value.work_plan) ? deepAnalysis.value.work_plan : []
))
const targetTableText = computed(() => {
  const tables = Array.isArray(report.value.target_tables) ? report.value.target_tables : []
  return tables.length ? tables.join('、') : '计量稽查检查表（现场）、计量稽查检查表（视频）'
})

const summaryCards = computed(() => {
  const summary = report.value.summary || {}
  return [
    {
      label: '管理片区',
      value: summary.region_count ?? 0,
      desc: '本月问题涉及片区'
    },
    {
      label: '控（参）股单位',
      value: summary.holding_unit_count ?? 0,
      desc: '按站点主数据识别'
    },
    {
      label: '检查站点',
      value: summary.station_count ?? 0,
      desc: '去重统计站点数'
    },
    {
      label: '发现问题',
      value: summary.total_issue_count ?? 0,
      desc: `禁止项 ${summary.prohibited_issue_count ?? 0} 项`
    }
  ]
})

const emptyOverviewText = computed(() => {
  const month = report.value.month_label || '当前月份'
  return `${month}暂无计量稽查现场与视频检查问题数据，暂不能形成总体情况统计。`
})

const joinChineseList = (items) => {
  const values = items.map((item) => String(item || '').trim()).filter(Boolean)
  if (!values.length) return ''
  if (values.length === 1) return values[0]
  if (values.length === 2) return values.join('和')
  return `${values.slice(0, -1).join('、')}和${values[values.length - 1]}`
}

const formatPercent = (value) => `${Number(value || 0).toFixed(1)}%`

const buildFlowText = (prefix, includePercent = false) => {
  const total = Number(findingSummary.value.total_issue_count ?? report.value.summary?.total_issue_count ?? 0)
  if (!total || !businessFlowRows.value.length) return `${prefix}0项。`
  const names = businessFlowRows.value.map((item) => item.name)
  const counts = businessFlowRows.value.map((item) => `${item.count}项`)
  const percentText = includePercent
    ? `，占比${joinChineseList(businessFlowRows.value.map((item) => formatPercent(item.percentage)))}`
    : ''
  return `${prefix}${total}项，涉及${joinChineseList(names)}问题，问题数量分别为${joinChineseList(counts)}${percentText}。`
}

const chapterTwoText = computed(() => buildFlowText('本次检查发现问题'))
const stationLinkText = computed(() => buildFlowText('检查发现加油站环节问题', true))

const chartMax = computed(() => {
  const max = Math.max(...businessFlowRows.value.map((item) => Number(item.count || 0)), 0)
  if (max <= 0) return 5
  return Math.ceil(max / chartTickStep.value) * chartTickStep.value
})

const chartTickStep = computed(() => {
  const max = Math.max(...businessFlowRows.value.map((item) => Number(item.count || 0)), 0)
  if (max <= 0) return 1
  const rawStep = max / 7
  const magnitude = 10 ** Math.floor(Math.log10(rawStep))
  const niceMultipliers = [1, 2, 5, 10]
  const multiplier = niceMultipliers.find((item) => item * magnitude >= rawStep) || 10
  return multiplier * magnitude
})

const chartTicks = computed(() => {
  const max = chartMax.value || 5
  const step = chartTickStep.value || 1
  const ticks = []
  for (let value = max; value >= 0; value -= step) {
    ticks.push(Math.round(value * 10) / 10)
  }
  if (ticks[ticks.length - 1] !== 0) ticks.push(0)
  return ticks
})

const getBarHeight = (count) => {
  const max = chartMax.value || 1
  return Math.max(2, Math.min(100, (Number(count || 0) / max) * 100))
}

const resolveImage = (path) => {
  if (!path) return ''
  const value = String(path || '').trim()
  if (!value) return ''
  if (value.startsWith('http://') || value.startsWith('https://') || value.startsWith('data:')) return value
  if (value.startsWith('/storage/')) return value
  if (value.startsWith('storage/')) return `/${value}`
  return `/storage/${value.replace(/^\/+/, '')}`
}

const formatStationIssue = (issue = {}) => {
  const station = String(issue.station_name || '').trim()
  const description = String(issue.description || '').trim()
  if (station && description) return `${station}${description}`
  return station || description || '暂无典型问题描述。'
}

const openImagePreview = (path, title = '问题照片预览') => {
  const src = resolveImage(path)
  if (!src) return
  imagePreview.value = {
    visible: true,
    src,
    title
  }
}

const closeImagePreview = () => {
  imagePreview.value = {
    visible: false,
    src: '',
    title: ''
  }
}

const fetchReport = async (options = {}) => {
  if (!selectedMonth.value) return
  const force = options?.force === true
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/quality-measurement-summary', {
      params: {
        user_id: localStorage.getItem('user_id') || '',
        month: selectedMonth.value,
        ...(force ? { force: 'true' } : {})
      }
    })
    if (!response.data?.success) {
      throw new Error(response.data?.error || '报告生成失败。')
    }
    report.value = response.data.report || report.value
  } catch (err) {
    error.value = err?.response?.data?.error || err?.message || '报告生成失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

onMounted(fetchReport)
</script>

<style scoped>
.report-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.card-surface {
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.22);
  box-shadow: 0 22px 54px rgba(15, 23, 42, 0.08);
}

.report-hero {
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: 24px;
  padding: 24px;
  border-radius: 24px;
  background:
    radial-gradient(circle at 8% 0%, rgba(14, 165, 233, 0.18), transparent 34%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(240, 249, 255, 0.94));
}

.page-kicker,
.doc-eyebrow {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.16em;
  color: #0284c7;
}

.report-hero h2,
.report-document h1 {
  margin: 8px 0;
  color: #0f172a;
}

.report-hero p {
  margin: 0;
  color: #64748b;
  line-height: 1.7;
}

.report-month-control {
  min-width: 230px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
  padding: 18px;
  border-radius: 20px;
  background: #0f172a;
  color: #e0f2fe;
}

.report-month-control label {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.report-month-control span {
  font-size: 13px;
  color: #bae6fd;
}

.report-month-control input {
  height: 44px;
  border: 0;
  border-radius: 14px;
  padding: 0 14px;
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}

.regenerate-report-btn {
  height: 42px;
  border: 1px solid rgba(186, 230, 253, 0.34);
  border-radius: 14px;
  color: #e0f2fe;
  background: rgba(14, 165, 233, 0.16);
  font-weight: 900;
  cursor: pointer;
  transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease;
}

.regenerate-report-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  background: rgba(14, 165, 233, 0.28);
  border-color: rgba(186, 230, 253, 0.62);
}

.regenerate-report-btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.state-card {
  min-height: 220px;
  border-radius: 24px;
  padding: 36px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748b;
}

.state-card.error {
  min-height: auto;
  padding: 16px 18px;
  color: #b91c1c;
  background: #fff1f2;
  border: 1px solid #fecdd3;
}

.state-orb {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0ea5e9, #22c55e);
  margin-bottom: 14px;
}

.state-orb.loading {
  animation: pulseOrb 1.2s ease-in-out infinite;
}

.report-document {
  border-radius: 28px;
  padding: 28px;
}

.report-document-head {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  padding-bottom: 22px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.25);
}

.doc-meta {
  min-width: 260px;
  max-width: 360px;
  padding: 16px;
  border-radius: 18px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #64748b;
}

.doc-meta strong {
  color: #0f172a;
  line-height: 1.5;
}

.snapshot-hint {
  display: inline-flex;
  width: fit-content;
  padding: 3px 8px;
  border-radius: 999px;
  color: #0369a1;
  background: #e0f2fe;
  font-weight: 800;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin: 22px 0 0;
}

.summary-card {
  padding: 18px;
  border-radius: 20px;
  background: linear-gradient(180deg, #f8fafc, #ffffff);
  border: 1px solid rgba(203, 213, 225, 0.75);
}

.summary-card span {
  color: #64748b;
  font-size: 13px;
}

.summary-card strong {
  display: block;
  margin: 6px 0;
  font-size: 30px;
  color: #0f172a;
}

.summary-card small {
  color: #94a3b8;
}

.chapter-card {
  padding: 28px;
  margin-top: 34px;
  border-radius: 24px;
  background: #ffffff;
  border: 1px solid rgba(203, 213, 225, 0.72);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.055);
}

.chapter-lead {
  margin: 0 0 24px;
  color: #334155;
  line-height: 2;
  text-indent: 2em;
}

.strong-lead {
  font-size: 24px;
  font-weight: 900;
  color: #020617;
  text-indent: 2em;
}

.chapter-note {
  margin: 0 0 22px;
  padding: 12px 14px;
  border-radius: 14px;
  color: #475569;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  line-height: 1.7;
}

.chapter-banner {
  position: relative;
  overflow: hidden;
  min-height: 64px;
  margin: -28px -28px 28px;
  padding: 16px 24px;
  border-radius: 23px 23px 0 0;
  background: linear-gradient(105deg, #0b6f9f 0%, #1686bd 58%, #2b9dca 100%);
  color: #ffffff;
  display: flex;
  align-items: center;
  font-size: 22px;
  font-weight: 900;
  line-height: 1.45;
  letter-spacing: 0.02em;
  box-shadow: inset 0 -1px 0 rgba(255, 255, 255, 0.18);
}

.chapter-banner::after {
  content: "";
  position: absolute;
  right: -24px;
  top: 50%;
  width: 132px;
  height: 132px;
  border: 24px solid rgba(255, 255, 255, 0.08);
  border-radius: 50%;
  transform: translateY(-50%);
  pointer-events: none;
}

.report-table-wrap {
  overflow-x: auto;
  border-radius: 18px;
  border: 1px solid #cbd5e1;
}

.report-table {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
  background: #ffffff;
}

.report-table th,
.report-table td {
  border: 1px solid #cbd5e1;
  padding: 13px 12px;
  text-align: center;
  vertical-align: middle;
  color: #0f172a;
}

.report-table th {
  background: #eff6ff;
  font-weight: 800;
}

.typical-table th:first-child {
  width: 260px;
}

.text-cell {
  text-align: left !important;
  line-height: 1.8;
}

.unit-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.unit-type-pill {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  color: #0369a1;
  background: #e0f2fe;
}

.unit-type-pill.holding {
  color: #92400e;
  background: #fef3c7;
}

.total-row td {
  font-weight: 900;
  background: #f8fafc;
}

.empty-cell {
  height: 96px;
  color: #94a3b8;
}

.chart-title {
  margin: 28px 0 8px 36px;
  font-size: 24px;
  color: #1f2937;
}

.bar-chart {
  position: relative;
  min-height: 360px;
  margin-top: 6px;
  padding: 18px 22px 12px 84px;
  overflow-x: auto;
}

.chart-grid {
  position: absolute;
  left: 18px;
  right: 22px;
  top: 18px;
  bottom: 66px;
  pointer-events: none;
}

.chart-grid::before {
  content: "";
  position: absolute;
  left: 62px;
  top: 0;
  width: 1px;
  bottom: 0;
  background: rgba(15, 23, 42, 0.38);
}

.chart-grid span {
  position: absolute;
  left: 0;
  transform: translateY(50%);
  min-width: 48px;
  text-align: right;
  font-size: 16px;
  color: #0f172a;
}

.chart-grid span::after {
  content: "";
  position: absolute;
  left: 62px;
  right: -100vw;
  top: 50%;
  height: 1px;
  background: rgba(148, 163, 184, 0.82);
}

.chart-bars {
  position: relative;
  z-index: 1;
  min-width: max(720px, 100%);
  height: 320px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 34px;
  padding-left: 52px;
}

.chart-bar-item {
  height: 100%;
  min-width: 104px;
  display: grid;
  grid-template-rows: 26px 1fr 36px 22px;
  justify-items: center;
  align-items: end;
}

.bar-value {
  font-size: 16px;
  color: #020617;
  align-self: end;
}

.bar-track {
  width: 54px;
  height: 100%;
  display: flex;
  align-items: flex-end;
}

.bar-fill {
  width: 100%;
  min-height: 4px;
  background: linear-gradient(180deg, #76b9ea, #4f9bd2);
  border-radius: 2px 2px 0 0;
}

.bar-label {
  align-self: start;
  padding-top: 10px;
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
  text-align: center;
  line-height: 1.25;
}

.bar-percent {
  align-self: start;
  color: #64748b;
  font-size: 13px;
}

.chart-empty {
  margin: auto;
  color: #94a3b8;
  font-weight: 700;
}

.analysis-source-pill {
  display: inline-flex;
  align-items: center;
  margin: 0 0 4px;
  padding: 7px 12px;
  border-radius: 999px;
  color: #92400e;
  background: #fef3c7;
  border: 1px solid #fde68a;
  font-size: 13px;
  font-weight: 800;
}

.analysis-source-pill.ai {
  color: #166534;
  background: #dcfce7;
  border-color: #bbf7d0;
}

.flow-highlight-section {
  margin-top: 18px;
  padding: 18px;
  border-radius: 20px;
  border: 1px solid #dbeafe;
  background: linear-gradient(180deg, #f8fbff, #ffffff);
}

.flow-highlight-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 12px;
}

.flow-highlight-head h4 {
  margin: 0;
  color: #0f172a;
  font-size: 22px;
}

.flow-highlight-head p {
  margin: 0;
  color: #0369a1;
  font-weight: 900;
}

.flow-highlight-summary {
  margin: 12px 0 0;
  color: #475569;
  line-height: 1.8;
}

.highlight-issue-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.highlight-issue-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 132px;
  gap: 14px;
  padding: 14px;
  border-radius: 18px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.06);
}

.highlight-issue-text span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.highlight-issue-text strong {
  display: block;
  margin: 4px 0 8px;
  color: #0f172a;
}

.highlight-issue-text p {
  margin: 0;
  color: #334155;
  line-height: 1.75;
}

.highlight-photo {
  width: 132px;
  height: 112px;
  border-radius: 14px;
  overflow: hidden;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 800;
}

.highlight-photo.is-clickable {
  border: 0;
  padding: 0;
  cursor: zoom-in;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.highlight-photo.is-clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 26px rgba(15, 23, 42, 0.18);
}

.highlight-photo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.report-image-preview {
  position: fixed;
  inset: 0;
  z-index: 90000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 26px;
  background: rgba(2, 6, 23, 0.82);
  backdrop-filter: blur(8px);
  cursor: zoom-out;
}

.report-image-preview img {
  max-width: min(1100px, 96vw);
  max-height: 92vh;
  object-fit: contain;
  border-radius: 18px;
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.42);
  cursor: default;
}

.empty-highlight {
  margin-top: 14px;
  padding: 18px;
  text-align: center;
  color: #94a3b8;
  background: #f8fafc;
  border-radius: 16px;
}

.trace-chapter {
  background:
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.12), transparent 35%),
    #ffffff;
}

.trace-problem-card {
  margin-top: 0;
  padding: 18px;
  border-radius: 20px;
  background: #0f172a;
  color: #e2e8f0;
}

.trace-problem-card.muted {
  background: #475569;
}

.trace-problem-card span {
  display: block;
  margin-bottom: 8px;
  color: #bae6fd;
  font-size: 13px;
  font-weight: 900;
}

.trace-problem-card strong {
  font-size: 20px;
  line-height: 1.7;
}

.trace-analysis-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.trace-analysis-grid article {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid #dbeafe;
  background: #f8fbff;
}

.trace-analysis-grid span {
  color: #0369a1;
  font-weight: 900;
}

.trace-analysis-grid p,
.trace-conclusion-card p,
.trace-conclusion-card li {
  color: #334155;
  line-height: 1.9;
}

.trace-conclusion-card {
  margin-top: 16px;
  padding: 18px;
  border-radius: 20px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.trace-conclusion-card h4 {
  margin: 0 0 10px;
  color: #0f172a;
}

.trace-conclusion-card ol {
  margin: 0;
  padding-left: 22px;
}

.work-plan-list {
  display: grid;
  gap: 14px;
  margin-top: 0;
}

.work-plan-card {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr);
  gap: 14px;
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, #f8fafc, #ffffff);
  border: 1px solid #e2e8f0;
}

.work-plan-card>span {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: #2488c7;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 900;
}

.work-plan-card h4 {
  margin: 0 0 8px;
  color: #0f172a;
}

.work-plan-card p {
  margin: 0;
  color: #475569;
  line-height: 1.9;
}

@keyframes pulseOrb {
  0%, 100% {
    transform: scale(0.94);
    opacity: 0.72;
  }
  50% {
    transform: scale(1.05);
    opacity: 1;
  }
}

@media (max-width: 900px) {
  .report-hero,
  .report-document-head {
    flex-direction: column;
  }

  .report-month-control,
  .doc-meta {
    width: 100%;
    max-width: none;
    min-width: 0;
    box-sizing: border-box;
  }

  .summary-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .report-document,
  .report-hero {
    padding: 18px;
    border-radius: 20px;
  }

  .chapter-card {
    padding: 20px;
    margin-top: 26px;
    border-radius: 20px;
  }

  .strong-lead {
    font-size: 20px;
  }

  .chapter-banner {
    min-height: 56px;
    margin: -20px -20px 22px;
    padding: 14px 18px;
    border-radius: 19px 19px 0 0;
    font-size: 19px;
  }

  .bar-chart {
    padding-left: 70px;
  }

  .chart-bars {
    gap: 22px;
  }

  .flow-highlight-head,
  .highlight-issue-card {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: flex-start;
  }

  .highlight-photo {
    width: 100%;
    height: 180px;
  }

  .trace-analysis-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .summary-cards {
    grid-template-columns: 1fr;
  }

  .report-document h1 {
    font-size: 24px;
    line-height: 1.35;
  }

  .chapter-card {
    margin-top: 24px;
  }

  .chapter-banner {
    font-size: 17px;
    letter-spacing: 0;
  }

  .chart-title {
    margin-left: 0;
    font-size: 20px;
  }

  .bar-chart {
    margin-left: -8px;
    margin-right: -8px;
  }
}
</style>
