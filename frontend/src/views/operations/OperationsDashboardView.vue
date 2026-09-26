<template>
  <div ref="cockpit" class="operations-cockpit" :class="{ 'screen-mode': expanded }">
    <header class="cockpit-header">
      <div class="brand-mark">
        <span class="brand-glyph" aria-hidden="true">◈</span>
        <div>业务督导中心<small>OPERATIONS COMMAND</small></div>
      </div>
      <div class="cockpit-title">
        <p>巡检 · 整改 · 洞察</p>
        <h1>运营数据驾驶舱</h1>
        <div class="title-beam" aria-hidden="true"></div>
      </div>
      <div class="header-actions">
        <span class="data-status"><i></i> 按权限汇总 · 非实时推送</span
        ><button class="screen-button" :aria-pressed="expanded" @click="toggleScreen">
          {{ expanded ? '退出大屏' : '全屏驾驶舱' }}
          <span aria-hidden="true">{{ expanded ? '↙' : '↗' }}</span>
        </button>
      </div>
    </header>

    <form class="command-bar" @submit.prevent="load">
      <span class="command-label">数据窗口 <small>TIME WINDOW</small></span>
      <label
        ><span class="sr-only">开始日期</span
        ><input v-model="draft.date_from" type="date" required /></label
      ><span class="range-dash">—</span>
      <label
        ><span class="sr-only">结束日期</span><input v-model="draft.date_to" type="date" required
      /></label>
      <label class="region-select"
        ><span class="sr-only">站点所属地</span
        ><select v-model="draft.region">
          <option value="">全部可见片区</option>
          <option v-for="region in regionOptions" :key="region">{{ region }}</option>
        </select></label
      >
      <button type="button" class="console-button" @click="reset">本月</button
      ><button class="console-button primary" :disabled="loading">
        {{ loading ? '汇总中…' : '开始分析' }}
      </button>
      <span class="snapshot-time">{{
        data ? '数据更新 ' + formatTime(data.generated_at) : '等待业务数据'
      }}</span>
    </form>
    <p v-if="dirty" class="cockpit-notice">
      筛选尚未应用。点击“开始分析”后更新，当前图表仍使用上次分析范围。
    </p>
    <p v-if="error" class="cockpit-notice error" role="alert">
      {{ error }} <button class="console-button" @click="load">重试</button>
    </p>
    <div v-if="loading" class="cockpit-loading" role="status">
      <div class="loading-orbit" aria-hidden="true"></div>
      <strong>正在汇总运营数据</strong><span>服务端聚合 · 不加载问题全库</span>
    </div>

    <main v-else-if="data" class="cockpit-main">
      <div class="scope-line">
        <span
          >{{ applied.date_from }} — {{ applied.date_to }} <b>/</b>
          {{ applied.region || '全部可见片区' }}</span
        ><span>点击图表条目可查看关联问题</span>
      </div>
      <section class="kpi-strip" aria-label="核心运营指标">
        <article
          v-for="(metric, index) in metrics"
          :key="metric.label"
          class="kpi"
          :class="metric.tone"
        >
          <span class="kpi-index">0{{ index + 1 }}</span>
          <div class="kpi-label">{{ metric.label }}</div>
          <div class="kpi-value">
            {{ metric.value }}<small>{{ metric.unit }}</small>
          </div>
          <p>{{ metric.hint }}</p>
          <div class="kpi-rule" aria-hidden="true"></div>
        </article>
      </section>

      <section class="command-grid">
        <div class="wing left-wing">
          <article class="instrument trend-instrument">
            <div class="instrument-title">
              <h2>巡检发现趋势</h2>
              <span>DAILY SIGNAL</span>
            </div>
            <div class="panel-caption">
              <span>有效问题 / 按登记日</span
              ><strong>{{ data.summary.valid }}<small> 项</small></strong>
            </div>
            <svg
              v-if="trend.length"
              class="trend-chart"
              viewBox="0 0 420 190"
              role="img"
              aria-label="所选期间有效问题登记趋势"
            >
              <defs>
                <linearGradient id="cockpit-trend-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stop-color="#32d8f2" stop-opacity=".35" />
                  <stop offset="1" stop-color="#32d8f2" stop-opacity="0" />
                </linearGradient>
              </defs>
              <g v-for="tick in [0, 1, 2, 3]" :key="tick">
                <line
                  x1="32"
                  x2="407"
                  :y1="150 - tick * 40"
                  :y2="150 - tick * 40"
                  stroke="#24495e"
                  stroke-dasharray="3 5"
                />
                <text x="25" :y="154 - tick * 40" text-anchor="end">
                  {{ Math.round((trendMax * tick) / 3) }}
                </text>
              </g>
              <path :d="trendArea" fill="url(#cockpit-trend-fill)" />
              <path :d="trendPath" fill="none" stroke="#48dff2" stroke-width="2" />
              <circle
                v-for="(point, index) in trend"
                :key="point.day"
                :cx="trendX(index)"
                :cy="trendY(point.valid)"
                r="2.2"
                fill="#a6f6ff"
              >
                <title>
                  {{ point.day }}：{{ point.valid }}项有效问题 / 登记{{ point.registered }}项
                </title>
              </circle>
              <text x="32" y="178">{{ applied.date_from }}</text>
              <text x="407" y="178" text-anchor="end">{{ applied.date_to }}</text>
            </svg>
            <p v-else class="empty-state">所选期间暂无问题登记</p>
            <div class="signal-footer">
              <span
                >全部登记 <b>{{ data.summary.total }}</b></span
              ><button @click="showDetails('待审核', { phase: '待审核' })">
                待审核 <b>{{ data.summary.pending_audit }}</b> ›
              </button>
            </div>
          </article>
          <article class="instrument aging-instrument">
            <div class="instrument-title">
              <h2>待处理账龄</h2>
              <span>AGING WATCH</span>
            </div>
            <div class="age-alert">
              <span>登记已满30天</span><strong>{{ data.summary.aged }}<small>项</small></strong
              ><i aria-hidden="true"></i>
            </div>
            <div v-if="data.ages.length" class="age-bars">
              <div v-for="row in data.ages" :key="row.label">
                <span>{{ row.label }}</span>
                <div class="segmented-track">
                  <i
                    :class="{ amber: row.rank === 3 }"
                    :style="{ width: barWidth(row.count, data.ages) }"
                  ></i>
                </div>
                <b>{{ row.count }}</b>
              </div>
            </div>
            <p v-else class="empty-state">暂无待处理事项</p>
            <p class="instrument-note">按登记日起的自然日计算，不作为流程超时认定。</p>
          </article>
        </div>

        <article class="instrument command-core">
          <div class="instrument-title">
            <h2>整改闭环中枢</h2>
            <span>WORKFLOW CONTROL</span>
          </div>
          <div class="core-visual">
            <div class="core-readout left-readout">
              <span>已闭环</span><strong>{{ data.summary.closed }}</strong
              ><small>项有效问题</small>
            </div>
            <div class="orbital-gauge">
              <svg viewBox="0 0 300 300" role="img" :aria-label="'有效问题闭环率 ' + closureLabel">
                <circle
                  class="orbit-slow"
                  cx="150"
                  cy="150"
                  r="141"
                  fill="none"
                  stroke="#28758c"
                  stroke-width="1"
                  stroke-dasharray="55 18 5 18"
                />
                <circle
                  cx="150"
                  cy="150"
                  r="129"
                  fill="none"
                  stroke="#224857"
                  stroke-width="5"
                  stroke-dasharray="1 8"
                />
                <circle cx="150" cy="150" r="111" fill="none" stroke="#153e50" stroke-width="10" />
                <circle
                  cx="150"
                  cy="150"
                  r="111"
                  fill="none"
                  stroke="#4bdedc"
                  stroke-width="10"
                  pathLength="100"
                  :stroke-dasharray="closurePercent + ' 100'"
                  transform="rotate(-90 150 150)"
                  stroke-linecap="butt"
                />
                <circle
                  cx="150"
                  cy="150"
                  r="91"
                  fill="#092437"
                  fill-opacity=".85"
                  stroke="#28647a"
                />
                <path
                  d="M 143 48 h 14 M 143 252 h 14 M 48 143 v 14 M 252 143 v 14"
                  stroke="#93eff4"
                  stroke-width="2"
                />
              </svg>
              <div class="gauge-label">
                <span>有效问题闭环率</span
                ><strong
                  >{{ data.summary.valid ? closurePercent.toFixed(1) : '—'
                  }}<small v-if="data.summary.valid">%</small></strong
                ><em>CLOSED LOOP</em>
              </div>
            </div>
            <div class="core-readout right-readout">
              <span>待处理</span><strong>{{ data.summary.open }}</strong
              ><small>项待继续流转</small>
            </div>
          </div>
          <div class="flow-controls">
            <button
              v-for="(phase, index) in openPhases"
              :key="phase"
              @click="showDetails(phase, { phase })"
            >
              <small>0{{ index + 1 }}</small
              ><span>{{ phase }}</span
              ><strong>{{ phaseCount(phase) }}</strong>
            </button>
          </div>
          <div class="core-meta">
            <button @click="showDetails('站级无法整改', { phase: '站级无法整改' })">
              站级无法整改 <b>{{ data.summary.unable }}</b></button
            ><button @click="showDetails('已销毁', { phase: '已销毁' })">
              已销毁 <b>{{ data.summary.destroyed }}</b></button
            ><span>当前状态分布，非流量漏斗</span>
          </div>
          <div class="region-head">
            <h3>片区运行矩阵</h3>
            <span>有效问题 / 闭环率</span>
          </div>
          <div v-if="data.units.length" class="region-matrix">
            <button v-for="row in data.units" :key="row.region" @click="openRegion(row.region)">
              <span :title="row.region">{{ row.region }}</span>
              <div>
                <strong>{{ row.valid }}<small> 项</small></strong
                ><em>{{ row.valid ? percent(row.closed, row.valid) + '%' : '—' }}</em>
              </div>
              <div class="matrix-track">
                <i :style="{ width: percent(row.closed, row.valid) + '%' }"></i>
              </div>
            </button>
          </div>
          <p v-else class="empty-state">暂无片区问题数据</p>
        </article>

        <div class="wing right-wing">
          <article class="instrument mix-instrument">
            <div class="instrument-title">
              <h2>检查表问题构成</h2>
              <span>BUSINESS MIX</span>
            </div>
            <div v-if="data.tables.length" class="table-signals panel-scroll">
              <button
                v-for="row in data.tables"
                :key="row.inspection_table_id"
                @click="
                  showDetails(row.table_name + '（' + row.mode + '）', {
                    table_id: row.inspection_table_id,
                    valid: '1',
                  })
                "
              >
                <div>
                  <span
                    >{{ row.table_name }}<small> / {{ row.mode }}</small></span
                  ><b>{{ row.count }}</b>
                </div>
                <div class="signal-track">
                  <i :style="{ width: barWidth(row.count, data.tables) }"></i>
                </div>
                <small
                  >{{ row.stations }}座站 · 占比{{ percent(row.count, data.summary.valid) }}%</small
                >
              </button>
            </div>
            <p v-else class="empty-state">暂无有效问题</p>
          </article>
          <article class="instrument standards-instrument">
            <div class="instrument-title">
              <h2>高频规范排行</h2>
              <span>TOP 15</span>
            </div>
            <div v-if="data.standards.length" class="standards-list panel-scroll">
              <button
                v-for="(row, index) in data.standards"
                :key="row.standard_key"
                @click="
                  showDetails('规范 ' + row.standard_key, {
                    standard_key: row.standard_key,
                    valid: '1',
                  })
                "
              >
                <span class="rank" :class="{ lead: index < 3 }">{{
                  String(index + 1).padStart(2, '0')
                }}</span
                ><span class="standard-copy"
                  ><strong>{{ row.standard_key }}</strong
                  ><span :title="row.detail">{{ row.detail || '暂无规范描述' }}</span
                  ><small>涉及{{ row.stations }}座站</small></span
                ><b>{{ row.count }}<small>次 ›</small></b>
              </button>
            </div>
            <p v-else class="empty-state">暂无规范引用</p>
          </article>
        </div>
      </section>

      <section class="action-deck">
        <article class="instrument regional-detail">
          <div class="instrument-title">
            <h2>片区协同明细</h2>
            <span>REGIONAL PERFORMANCE · 非绩效排名</span>
          </div>
          <RegionTable :rows="data.units" @open="openRegion" />
        </article>
        <article class="instrument station-instrument">
          <div class="instrument-title">
            <h2>优先跟进站点</h2>
            <span>待处理数量 TOP 12</span>
          </div>
          <div v-if="data.stations.length" class="station-list panel-scroll">
            <button
              v-for="(row, index) in data.stations"
              :key="row.station_id"
              @click="
                showDetails(row.station_name + ' · 待处理', {
                  station_id: row.station_id,
                  open: '1',
                })
              "
            >
              <span class="rank">{{ String(index + 1).padStart(2, '0') }}</span
              ><span
                ><strong>{{ row.station_name }}</strong
                ><small>{{ row.region }} · 最长账龄{{ row.oldest }}天</small></span
              ><b>{{ row.count }}<small>项 ›</small></b>
            </button>
          </div>
          <p v-else class="empty-state">暂无待跟进站点</p>
        </article>
      </section>
      <details class="methodology">
        <summary>统计口径与数据说明 <span>DATA DEFINITIONS</span></summary>
        <p>
          问题按登记日期筛选，展示查询时的最新状态，不是历史时点快照。有效问题仅含审核通过且未销毁的问题；闭环率
          = 已闭环有效问题 ÷
          全部有效问题。待处理含待验收、待整改、待复核、申诉中；站级无法整改独立统计，不计入闭环。
        </p>
        <p>
          巡检触达按巡检日期对站点去重，含零问题站点；底层巡检记录按站点与检查表计数。问题、亮点、巡检分别沿用原业务数据范围。有问题站均只统计有问题站点，不是全部受检站点平均。账龄按登记日至今天的自然日计算，不等同于流程超时，不作为考核结论。
        </p>
        <p>
          单次分析最多366天；数据只在打开页面或点击开始分析时读取，不自动轮询。图形装饰不代表额外业务指标。未使用证照、站点评分数据，不调用AI。
        </p>
      </details>
    </main>
    <dialog
      ref="detailDialog"
      class="cockpit-dialog"
      aria-labelledby="operations-detail-title"
      @click="closeOnBackdrop"
      @close="closeDetails"
    >
      <div class="operations-dialog-head">
        <div>
          <span class="eyebrow">关联问题 / EVIDENCE</span>
          <h3 id="operations-detail-title">{{ detailTitle }}</h3>
          <p>{{ applied.date_from }} 至 {{ applied.date_to }} · 共{{ detail.total }}项</p>
        </div>
        <button class="console-button" aria-label="关闭问题明细" @click="detailDialog.close()">
          关闭
        </button>
      </div>
      <div class="dialog-body" :aria-busy="detailLoading">
        <p v-if="detailLoading" class="empty-state" role="status">正在加载当前页…</p>
        <p v-else-if="detailError" class="error" role="alert">
          {{ detailError }}
          <button class="console-button" @click="loadDetails(detail.page)">重试</button>
        </p>
        <div v-else-if="detail.rows.length" class="detail-items">
          <article v-for="row in detail.rows" :key="row.id">
            <header>
              <strong>#{{ row.id }} · {{ row.station_name }}</strong
              ><span>{{ row.phase }}</span>
            </header>
            <small
              >{{ row.region }} · {{ row.table_name }}（{{ row.mode }}） ·
              {{ row.created_at }}</small
            >
            <p>{{ row.description }}</p>
          </article>
        </div>
        <p v-else class="empty-state">没有符合条件的问题</p>
      </div>
      <footer class="dialog-footer">
        <span
          >每页20项 · 第{{ detail.page }} / {{ Math.max(1, Math.ceil(detail.total / 20)) }}页</span
        >
        <div>
          <button
            class="console-button"
            :disabled="detailLoading || detail.page <= 1"
            @click="loadDetails(detail.page - 1)"
          >
            上一页</button
          ><button
            class="console-button primary"
            :disabled="detailLoading || detail.page * 20 >= detail.total"
            @click="loadDetails(detail.page + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import axios from 'axios'
import RegionTable from './RegionTable.vue'

const cockpit = ref(null),
  expanded = ref(false)
let nativeScreen = false
async function toggleScreen() {
  if (expanded.value) {
    if (document.fullscreenElement === cockpit.value) await document.exitFullscreen()
    expanded.value = false
    nativeScreen = false
    return
  }
  expanded.value = true
  if (cockpit.value?.requestFullscreen) {
    try {
      await cockpit.value.requestFullscreen()
      nativeScreen = true
    } catch {
      nativeScreen = false
    }
  }
}
function syncScreen() {
  if (nativeScreen && document.fullscreenElement !== cockpit.value) {
    expanded.value = false
    nativeScreen = false
  }
}
function escapeScreen(event) {
  if (event.key === 'Escape' && !document.fullscreenElement && !detailDialog.value?.open)
    expanded.value = false
}
const localDate = (date) =>
  String(date.getFullYear()) +
  '-' +
  String(date.getMonth() + 1).padStart(2, '0') +
  '-' +
  String(date.getDate()).padStart(2, '0')
const defaults = () => {
  const now = new Date()
  return {
    date_from: localDate(new Date(now.getFullYear(), now.getMonth(), 1)),
    date_to: localDate(now),
    region: '',
  }
}
const draft = ref(defaults()),
  applied = ref(defaults()),
  data = ref(null),
  regionOptions = ref([])
const loading = ref(false),
  error = ref('')
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(applied.value))
const openPhases = ['待验收', '待整改', '待复核', '申诉中']
const percent = (value, total) => (total ? ((value / total) * 100).toFixed(1) : '0.0')
const phaseCount = (phase) => data.value?.phases.find((row) => row.phase === phase)?.count || 0
const barWidth = (value, rows) =>
  String((value / Math.max(1, ...rows.map((row) => Number(row.count)))) * 100) + '%'
const formatTime = (value) => new Date(value).toLocaleString('zh-CN', { hour12: false })
const closurePercent = computed(() =>
  data.value?.summary.valid ? (data.value.summary.closed / data.value.summary.valid) * 100 : 0,
)
const closureLabel = computed(() =>
  data.value?.summary.valid ? closurePercent.value.toFixed(1) + '%' : '暂无有效问题',
)
const metrics = computed(() => {
  if (!data.value) return []
  const s = data.value.summary,
    r = data.value.records
  return [
    {
      label: '巡检触达站点',
      value: r ? r.stations : '—',
      unit: '座',
      hint: r ? '底层巡检记录 ' + r.records + ' 条' : '无巡检记录查看权限',
      tone: 'cyan',
    },
    {
      label: '已审核有效问题',
      value: s.valid,
      unit: '项',
      hint: '涉及 ' + s.stations + ' 座站点',
      tone: 'cyan',
    },
    {
      label: '待处理事项',
      value: s.open,
      unit: '项',
      hint: '验收 / 整改 / 复核 / 申诉',
      tone: 'amber',
    },
    {
      label: '账龄30天及以上',
      value: s.aged,
      unit: '项',
      hint: '自然日账龄 · 非超时认定',
      tone: 'amber',
    },
    {
      label: '确认亮点',
      value: data.value.highlights,
      unit: '项',
      hint: '所选期间已审核通过',
      tone: 'mint',
    },
    {
      label: '站级无法整改',
      value: s.unable,
      unit: '项',
      hint: '经复核确认 · 不计入闭环',
      tone: 'slate',
    },
  ]
})
const trend = computed(() => {
  if (!data.value?.trend?.length) return []
  const byDay = new Map(data.value.trend.map((row) => [row.day, row]))
  const rows = [],
    day = new Date(applied.value.date_from + 'T12:00:00'),
    end = new Date(applied.value.date_to + 'T12:00:00')
  while (day <= end) {
    const key = localDate(day)
    rows.push(byDay.get(key) || { day: key, valid: 0, registered: 0 })
    day.setDate(day.getDate() + 1)
  }
  return rows
})
const trendMax = computed(() => Math.max(3, ...trend.value.map((row) => row.valid)))
const trendX = (index) =>
  trend.value.length === 1 ? 220 : 32 + (index / Math.max(1, trend.value.length - 1)) * 375
const trendY = (value) => 150 - (value / trendMax.value) * 120
const trendPath = computed(() =>
  trend.value
    .map((row, index) => (index ? 'L' : 'M') + ' ' + trendX(index) + ' ' + trendY(row.valid))
    .join(' '),
)
const trendArea = computed(
  () => trendPath.value + ' L ' + trendX(trend.value.length - 1) + ' 150 L ' + trendX(0) + ' 150 Z',
)
let requestController, detailController
async function load() {
  requestController?.abort()
  const controller = new AbortController()
  requestController = controller
  loading.value = true
  error.value = ''
  detailDialog.value?.close()
  const filters = { ...draft.value }
  try {
    const response = await axios.get('/api/operations/overview', {
      params: filters,
      signal: controller.signal,
    })
    if (controller.signal.aborted) return
    data.value = response.data
    applied.value = filters
    regionOptions.value = response.data.regions
  } catch (err) {
    if (!axios.isCancel(err)) {
      error.value = err.response?.data?.error || '驾驶舱数据加载失败，请重试。'
      data.value = null
    }
  } finally {
    if (requestController === controller) loading.value = false
  }
}
function reset() {
  draft.value = defaults()
}
const detailDialog = ref(null),
  detailTitle = ref(''),
  detail = ref({ rows: [], total: 0, page: 1 }),
  detailLoading = ref(false),
  detailError = ref('')
let detailFilters = {}
function showDetails(title, filters) {
  detailTitle.value = title
  detailFilters = { ...filters }
  detail.value = { rows: [], total: 0, page: 1 }
  detailDialog.value.showModal()
  loadDetails(1)
}
function openRegion(region) {
  showDetails(region + ' · 有效问题', { region, valid: '1' })
}
function closeOnBackdrop(event) {
  if (event.target === detailDialog.value) detailDialog.value.close()
}
function closeDetails() {
  detailController?.abort()
}
async function loadDetails(pageNumber) {
  detailController?.abort()
  const controller = new AbortController()
  detailController = controller
  detailLoading.value = true
  detailError.value = ''
  try {
    const response = await axios.get('/api/operations/overview/issues', {
      params: { ...applied.value, ...detailFilters, page: pageNumber },
      signal: controller.signal,
    })
    if (!controller.signal.aborted) detail.value = response.data
  } catch (err) {
    if (!axios.isCancel(err)) detailError.value = err.response?.data?.error || '明细加载失败。'
  } finally {
    if (detailController === controller) detailLoading.value = false
  }
}
onMounted(() => {
  load()
  document.addEventListener('fullscreenchange', syncScreen)
  document.addEventListener('keydown', escapeScreen)
})
onBeforeUnmount(() => {
  requestController?.abort()
  detailController?.abort()
  detailDialog.value?.close()
  document.removeEventListener('fullscreenchange', syncScreen)
  document.removeEventListener('keydown', escapeScreen)
  if (document.fullscreenElement === cockpit.value) document.exitFullscreen().catch(() => {})
})
</script>

<style scoped>
.operations-cockpit {
  --c-bg: #061421;
  --c-panel: #0b2031;
  --c-line: #234759;
  --c-text: #d7ebf5;
  --c-muted: #8cabbf;
  --c-cyan: #50e3f2;
  --c-amber: #f4bb68;
  color: var(--c-text);
  font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
  position: relative;
  min-width: 0;
  padding: 22px;
  border: 1px solid #1e4156;
  border-radius: 10px;
  background:
    radial-gradient(ellipse at 50% 20%, #0d344745, transparent 60%),
    linear-gradient(#16354728 1px, transparent 1px),
    linear-gradient(90deg, #16354728 1px, transparent 1px), var(--c-bg);
  background-size:
    auto,
    40px 40px,
    40px 40px,
    auto;
  isolation: isolate;
}
.operations-cockpit.screen-mode {
  position: fixed;
  inset: 0;
  z-index: 8000;
  border-radius: 0;
  overflow: auto;
  padding: 22px 28px;
}
.operations-cockpit:fullscreen {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
}
.cockpit-header {
  display: grid;
  grid-template-columns: 1fr 1.3fr 1fr;
  align-items: center;
  gap: 20px;
  margin-bottom: 19px;
  min-height: 76px;
}
.brand-mark {
  display: flex;
  align-items: center;
  gap: 11px;
  font-size: 15px;
  letter-spacing: 2px;
  color: #bbdae9;
}
.brand-mark small {
  display: block;
  font-size: 9px;
  letter-spacing: 1.8px;
  margin-top: 7px;
  color: #648da5;
}
.brand-glyph {
  font-size: 38px;
  color: var(--c-cyan);
  text-shadow: 0 0 20px #29a4bc;
}
.cockpit-title {
  text-align: center;
  position: relative;
  padding: 0 12px 14px;
}
.cockpit-title p {
  color: #81abbe;
  font-size: 11px;
  letter-spacing: 8px;
  margin: 0 0 8px;
}
.cockpit-title h1 {
  font-size: clamp(23px, 2.2vw, 38px);
  font-weight: 600;
  letter-spacing: 6px;
  margin: 0;
  color: #e3faff;
  text-shadow: 0 0 24px #59cfe048;
}
.title-beam {
  position: absolute;
  bottom: 0;
  left: 8%;
  right: 8%;
  height: 2px;
  background: linear-gradient(90deg, transparent, #48cbdf, transparent);
}
.title-beam:before,
.title-beam:after {
  content: '';
  position: absolute;
  width: 28px;
  height: 5px;
  background: #4dd9ea;
  top: -1px;
  transform: skewX(-35deg);
}
.title-beam:before {
  left: 10%;
}
.title-beam:after {
  right: 10%;
}
.header-actions {
  display: grid;
  gap: 12px;
  justify-items: end;
}
.data-status {
  font-size: 10px;
  letter-spacing: 1px;
  color: var(--c-muted);
}
.data-status i {
  display: inline-block;
  width: 5px;
  height: 5px;
  background: #58e8c9;
  margin-right: 6px;
  box-shadow: 0 0 8px #58e8c9;
}
.screen-button,
.console-button {
  font: inherit;
  font-size: 12px;
  border: 1px solid #326074;
  background: #0f2e41;
  color: #caeaf5;
  border-radius: 3px;
  padding: 9px 14px;
  cursor: pointer;
  white-space: nowrap;
}
.screen-button {
  background: linear-gradient(110deg, #17455c, #092335);
  border-color: #347089;
}
.screen-button span {
  color: var(--c-cyan);
  margin-left: 12px;
}
.console-button.primary {
  background: #14617d;
  border-color: #4dc3dd;
  color: #effcff;
}
.console-button:disabled {
  opacity: 0.5;
  cursor: default;
}
button:focus-visible,
select:focus-visible,
input:focus-visible,
summary:focus-visible {
  outline: 2px solid #aaf5ff;
  outline-offset: 3px;
}
button:hover:not(:disabled) {
  filter: brightness(1.18);
}
.command-bar {
  border-block: 1px solid #234757;
  background: #0c2433c9;
  padding: 11px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.command-label {
  font-size: 12px;
  letter-spacing: 2px;
  margin-right: 10px;
  display: grid;
  gap: 4px;
}
.command-label small {
  font-size: 8px;
  color: #6f98ad;
  letter-spacing: 1px;
}
.command-bar input,
.command-bar select {
  color-scheme: dark;
  background: #091c2a;
  color: #c9e6f3;
  border: 1px solid #315366;
  border-radius: 3px;
  height: 34px;
  padding: 5px 8px;
  font: inherit;
  font-size: 12px;
  max-width: 100%;
}
.command-bar select {
  min-width: 150px;
}
.command-bar label {
  min-width: 0;
}
.range-dash {
  font-size: 11px;
  color: #7491a2;
}
.snapshot-time {
  margin-left: auto;
  color: #7fa4b7;
  font-size: 10px;
}
.cockpit-notice {
  border-left: 2px solid var(--c-amber);
  padding: 10px 15px;
  background: #65441b33;
  font-size: 12px;
  color: #f4cb8a;
}
.error {
  color: #ffb3a3;
}
.cockpit-loading {
  min-height: 480px;
  display: flex;
  flex-direction: column;
  gap: 17px;
  align-items: center;
  justify-content: center;
  color: var(--c-cyan);
}
.cockpit-loading > span {
  font-size: 12px;
  color: var(--c-muted);
}
.loading-orbit {
  width: 60px;
  height: 60px;
  border: 1px solid #245970;
  border-top: 2px solid #65eaf5;
  border-radius: 50%;
  animation: orbit 1.8s linear infinite;
}
.cockpit-main {
  display: grid;
  gap: 14px;
}
.scope-line {
  font-size: 10px;
  color: #8cb0c4;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 13px;
}
.scope-line b {
  margin: 0 10px;
  color: #427085;
}
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  border: 1px solid #285168;
  background: linear-gradient(180deg, #103046aa, #09233399);
}
.kpi {
  position: relative;
  padding: 17px 18px 13px;
  border-right: 1px solid #285168;
  min-width: 0;
}
.kpi:last-child {
  border-right: 0;
}
.kpi-index {
  position: absolute;
  right: 12px;
  top: 12px;
  color: #55798c;
  font:
    10px 'Consolas',
    monospace;
}
.kpi-label {
  color: #a3c3d4;
  font-size: 12px;
  padding-right: 15px;
}
.kpi-value {
  font-family: 'Bahnschrift', 'DIN Alternate', 'Consolas', sans-serif;
  font-size: clamp(27px, 2.6vw, 43px);
  font-variant-numeric: tabular-nums;
  color: #68e7f1;
  margin-top: 8px;
  line-height: 1.15;
  letter-spacing: 1px;
  text-shadow: 0 0 20px #46d3dd33;
}
.kpi-value small {
  font-family: 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  color: #8fb5c8;
  margin-left: 6px;
}
.kpi.amber .kpi-value {
  color: #f4c27d;
  text-shadow: 0 0 20px #deaa4c30;
}
.kpi.mint .kpi-value {
  color: #6aedc7;
}
.kpi.slate .kpi-value {
  color: #b7c9eb;
}
.kpi p {
  font-size: 9px;
  line-height: 1.6;
  color: #8ba9bb;
  margin: 9px 0;
}
.kpi-rule {
  height: 2px;
  width: 28px;
  background: #4aafc0;
  box-shadow:
    8px 0 0 #286075,
    16px 0 0 #133c51;
}
.command-grid {
  display: grid;
  grid-template-columns: minmax(235px, 1fr) minmax(390px, 1.55fr) minmax(240px, 1fr);
  gap: 14px;
  align-items: stretch;
}
.wing {
  display: grid;
  grid-template-rows: 1fr 1fr;
  gap: 14px;
  min-width: 0;
}
.instrument {
  position: relative;
  border: 1px solid #285168;
  background: linear-gradient(120deg, #0b2335eb, #081b2bea);
  min-width: 0;
  padding: 16px;
  box-shadow: inset 0 0 30px #0a233933;
}
.instrument:before,
.instrument:after {
  content: '';
  position: absolute;
  width: 14px;
  height: 14px;
  pointer-events: none;
}
.instrument:before {
  left: -1px;
  top: -1px;
  border-left: 2px solid #58c5d8;
  border-top: 2px solid #58c5d8;
}
.instrument:after {
  right: -1px;
  bottom: -1px;
  border-right: 2px solid #326c83;
  border-bottom: 2px solid #326c83;
}
.instrument-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid #26465a;
  padding-bottom: 11px;
  margin-bottom: 12px;
}
.instrument-title h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 1.5px;
  color: #d5edf7;
  position: relative;
  padding-left: 10px;
}
.instrument-title h2:before {
  content: '';
  position: absolute;
  left: 0;
  top: 3px;
  width: 3px;
  height: 12px;
  background: #4bcedd;
}
.instrument-title > span {
  font-size: 8px;
  letter-spacing: 1.1px;
  color: #749bad;
  text-align: right;
}
.panel-caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 10px;
  color: #85acbf;
}
.panel-caption strong {
  font-size: 18px;
  color: #62ddee;
  font-family: 'Consolas', monospace;
}
.panel-caption small {
  font-size: 10px;
  font-weight: 400;
}
.trend-chart {
  display: block;
  width: 100%;
  height: 170px;
}
.trend-chart text {
  font-size: 10px;
  fill: #88aabd;
}
.signal-footer {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  border-top: 1px solid #203d50;
  padding-top: 10px;
  color: #8cafc2;
}
.signal-footer button {
  border: 0;
  background: none;
  color: inherit;
  cursor: pointer;
  font: inherit;
}
.signal-footer b {
  font-family: 'Consolas', monospace;
  font-size: 16px;
  color: #c9edf5;
  margin-left: 6px;
}
.age-alert {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 9px 12px;
  background: linear-gradient(90deg, #8a622324, transparent);
  border-left: 2px solid #c69b57;
}
.age-alert > span {
  font-size: 11px;
  color: #e4be81;
}
.age-alert strong {
  font-family: 'Consolas', monospace;
  font-size: 25px;
  font-weight: 400;
  color: #f9cb83;
}
.age-alert small {
  font-size: 10px;
  margin-left: 5px;
}
.age-alert i {
  margin-left: auto;
  width: 6px;
  height: 6px;
  transform: rotate(45deg);
  background: #e5bb78;
  box-shadow: 0 0 12px #e5bb7850;
}
.age-bars {
  display: grid;
  gap: 17px;
  margin: 20px 0;
}
.age-bars > div {
  display: grid;
  grid-template-columns: 78px 1fr 25px;
  align-items: center;
  gap: 9px;
  font-size: 11px;
}
.age-bars b {
  color: #c5e8f1;
  font-family: 'Consolas', monospace;
  text-align: right;
}
.segmented-track {
  height: 7px;
  background: #143446;
}
.segmented-track i {
  display: block;
  height: 100%;
  background: repeating-linear-gradient(90deg, #39b9cf 0, #39b9cf 5px, #0b263b 5px, #0b263b 7px);
}
.segmented-track i.amber {
  background: repeating-linear-gradient(90deg, #e8b776 0, #e8b776 5px, #0b263b 5px, #0b263b 7px);
}
.instrument-note {
  font-size: 9px;
  line-height: 1.8;
  color: #7ca0b5;
  margin: 12px 0 0;
}
.panel-scroll {
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: #2d6278 transparent;
}
.command-core {
  background:
    radial-gradient(ellipse at 50% 25%, #12415765, transparent 60%),
    linear-gradient(180deg, #0b2539e8, #081b2ae8);
  display: flex;
  flex-direction: column;
}
.core-visual {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  min-height: 240px;
}
.core-visual:after {
  content: '';
  position: absolute;
  left: 15%;
  right: 15%;
  bottom: 4px;
  height: 22px;
  border: 1px solid #35728a55;
  border-radius: 50%;
  box-shadow: 0 5px 20px #16b6c719;
  pointer-events: none;
}
.orbital-gauge {
  width: clamp(210px, 20vw, 290px);
  position: relative;
  flex-shrink: 1;
  min-width: 180px;
}
.orbital-gauge svg {
  display: block;
  width: 100%;
  filter: drop-shadow(0 0 12px #44c3d323);
}
.orbit-slow {
  transform-origin: 150px 150px;
  animation: orbit 70s linear infinite;
}
.gauge-label {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  pointer-events: none;
}
.gauge-label > span {
  font-size: 11px;
  color: #aed1df;
}
.gauge-label strong {
  font-family: 'Bahnschrift', 'DIN Alternate', 'Consolas', sans-serif;
  font-weight: 400;
  font-size: clamp(28px, 3.6vw, 52px);
  color: #c8fbff;
  margin: 7px 0;
  letter-spacing: -1px;
}
.gauge-label strong small {
  font-size: 16px;
  letter-spacing: 0;
}
.gauge-label em {
  font-style: normal;
  font-size: 8px;
  letter-spacing: 3px;
  color: #5ea0b6;
}
.core-readout {
  display: grid;
  gap: 6px;
  font-size: 10px;
  color: #8ab7cb;
  min-width: 55px;
}
.core-readout strong {
  font-family: 'Consolas', monospace;
  font-size: 25px;
  font-weight: 400;
  color: #70e6d9;
}
.core-readout small {
  font-size: 8px;
  color: #739aaf;
}
.right-readout {
  text-align: right;
}
.right-readout strong {
  color: #f2c98a;
}
.flow-controls {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 8px;
}
.flow-controls button {
  position: relative;
  border: 1px solid #2c6074;
  background: linear-gradient(130deg, #15425470, #0a253455);
  color: #b9dce9;
  padding: 12px 5px 9px;
  display: grid;
  gap: 5px;
  cursor: pointer;
  text-align: center;
  min-width: 0;
}
.flow-controls small {
  font-size: 8px;
  color: #497e95;
  position: absolute;
  top: 3px;
  left: 4px;
}
.flow-controls span {
  font-size: 11px;
}
.flow-controls strong {
  font-size: 23px;
  font-weight: 400;
  font-family: 'Consolas', monospace;
  color: #7ee4f1;
}
.core-meta {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  padding: 11px 0;
  font-size: 9px;
  border-bottom: 1px solid #214357;
  color: #86a8bd;
}
.core-meta button {
  border: 0;
  background: none;
  color: #95bacd;
  font: inherit;
  cursor: pointer;
  padding: 0;
}
.core-meta b {
  margin-left: 5px;
  color: #d0e9f3;
}
.core-meta > span {
  margin-left: auto;
  color: #7296ab;
}
.region-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 14px 0 10px;
}
.region-head h3 {
  font-size: 12px;
  font-weight: 400;
  letter-spacing: 2px;
  margin: 0;
}
.region-head > span {
  font-size: 9px;
  color: #82a9bc;
}
.region-matrix {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  max-height: 188px;
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: #2d6278 transparent;
}
.region-matrix button {
  padding: 9px;
  border: 1px solid #234c60;
  background: #0b2a3d99;
  color: #a7ccdd;
  cursor: pointer;
  text-align: left;
  min-width: 0;
}
.region-matrix button > span {
  display: block;
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.region-matrix button > div:not(.matrix-track) {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-top: 6px;
  gap: 5px;
}
.region-matrix strong {
  color: #c4eff8;
  font-size: 18px;
  font-weight: 400;
  font-family: 'Consolas', monospace;
}
.region-matrix strong small {
  font-size: 8px;
  color: #7facc0;
}
.region-matrix em {
  font-size: 9px;
  font-style: normal;
  color: #61d9bd;
}
.matrix-track {
  margin-top: 7px;
  height: 2px;
  background: #184055;
}
.matrix-track i {
  display: block;
  height: 100%;
  background: #54cdb7;
}
.table-signals {
  max-height: 235px;
  display: grid;
  gap: 14px;
  padding-right: 5px;
}
.table-signals button {
  background: none;
  border: 0;
  padding: 0;
  text-align: left;
  cursor: pointer;
  color: #abcddb;
}
.table-signals button > div:first-child {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
}
.table-signals button span small {
  font-size: 9px;
  color: #7da0b5;
}
.table-signals b {
  font:
    16px 'Consolas',
    monospace;
  color: #7dd7ee;
}
.signal-track {
  height: 5px;
  background: #183747;
  margin: 7px 0 5px;
}
.signal-track i {
  height: 100%;
  display: block;
  background: linear-gradient(90deg, #216b99, #5bd5e9);
}
.table-signals button > small {
  font-size: 9px;
  color: #7197ac;
}
.standards-list {
  max-height: 235px;
}
.standards-list button,
.station-list button {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 10px;
  padding: 11px 1px;
  border: 0;
  border-bottom: 1px solid #214256;
  background: transparent;
  text-align: left;
  color: var(--c-text);
  cursor: pointer;
}
.rank {
  font-family: 'Consolas', monospace;
  font-size: 12px;
  color: #658a9f;
  min-width: 20px;
}
.rank.lead {
  color: #f0c18a;
}
.standard-copy {
  display: grid;
  gap: 5px;
  flex: 1;
  min-width: 0;
}
.standard-copy strong {
  font-size: 12px;
  color: #b9e9f4;
  font-weight: 500;
}
.standard-copy > span {
  font-size: 10px;
  color: #97b6c9;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.standard-copy small {
  font-size: 9px;
  color: #7499ae;
}
.standards-list b,
.station-list b {
  font:
    18px 'Consolas',
    monospace;
  color: #70d2e7;
  white-space: nowrap;
}
.standards-list b small,
.station-list b small {
  font:
    9px 'Microsoft YaHei',
    sans-serif;
  color: #7da6bd;
  margin-left: 4px;
}
.action-deck {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 14px;
}
.regional-detail :deep(.region-table) {
  max-height: 240px;
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: #2d6278 transparent;
}
.regional-detail :deep(table) {
  color: #b0d0e0;
  font-size: 11px;
}
.regional-detail :deep(th) {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #102e40;
  color: #8cb3c8;
  font-size: 10px;
}
.regional-detail :deep(td) {
  border-color: #1d3b4d;
  padding: 12px 13px;
}
.regional-detail :deep(td:first-child) {
  color: #bfdbe7;
  font-weight: 400;
}
.regional-detail :deep(.progress) {
  background: #183d4e;
}
.regional-detail :deep(.progress i) {
  background: #54cbb3;
}
.regional-detail :deep(small) {
  color: #8ebdcf;
}
.regional-detail :deep(button) {
  background: #15415a;
  color: #84dcef;
  border-radius: 2px;
}
.regional-detail :deep(.pending) {
  color: #f1c28b;
}
.regional-detail :deep(.empty) {
  color: #80a6b9;
}
.station-list {
  max-height: 240px;
}
.station-list button > span:nth-child(2) {
  flex: 1;
  display: grid;
  gap: 5px;
}
.station-list strong {
  font-size: 11px;
  font-weight: 400;
}
.station-list small {
  font-size: 9px;
  color: #7da2b7;
}
.methodology {
  font-size: 11px;
  color: #85a9bd;
  line-height: 1.9;
  border-top: 1px solid #26495d;
  padding-top: 10px;
}
.methodology summary {
  cursor: pointer;
  color: #99bdcd;
  font-size: 10px;
}
.methodology summary span {
  font-size: 8px;
  margin-left: 10px;
  letter-spacing: 1px;
  color: #537f96;
}
.empty-state {
  text-align: center;
  padding: 25px 5px;
  font-size: 12px;
  line-height: 1.8;
  color: #8ab0c3;
}
.cockpit-dialog {
  padding: 0;
  width: min(850px, 94vw);
  max-height: 88dvh;
  border: 1px solid #42809a;
  border-radius: 6px;
  background: #0b2031;
  color: #d2e9f4;
  box-shadow: 0 0 60px #2a8dac22;
}
.cockpit-dialog::backdrop {
  background: #010b17bb;
}
.operations-dialog-head {
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
  border-bottom: 1px solid #285168;
}
.operations-dialog-head h3 {
  font-size: 18px;
  margin: 7px 0;
}
.eyebrow {
  font-size: 9px;
  letter-spacing: 2px;
  color: #63c7db;
}
.operations-dialog-head p {
  font-size: 11px;
  color: #91b3c8;
  margin: 0;
}
.dialog-body {
  padding: 0 20px;
  max-height: 58dvh;
  overflow: auto;
}
.detail-items article {
  padding: 17px 0;
  border-bottom: 1px solid #26495d;
}
.detail-items header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  font-size: 13px;
}
.detail-items header > span {
  font-size: 10px;
  white-space: nowrap;
  color: #8cdae8;
  border: 1px solid #2e6378;
  padding: 4px 8px;
}
.detail-items small {
  display: block;
  margin-top: 9px;
  font-size: 10px;
  color: #8db3c8;
}
.detail-items p {
  font-size: 13px;
  line-height: 1.9;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  gap: 10px;
  color: #91b3c8;
  font-size: 11px;
}
.dialog-footer > div {
  display: flex;
  gap: 7px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}
@keyframes orbit {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .orbit-slow,
  .loading-orbit {
    animation: none;
  }
}
/* Keep the main instruments in one screen; long lists scroll inside their panels. */
@media (min-width: 1500px) and (min-height: 900px) {
  .operations-cockpit.screen-mode {
    display: flex;
    flex-direction: column;
    height: 100dvh;
    box-sizing: border-box;
    padding: 14px 22px;
  }
  .screen-mode .cockpit-header {
    min-height: 68px;
    margin-bottom: 10px;
    flex-shrink: 0;
  }
  .screen-mode .command-bar {
    flex-shrink: 0;
    padding-block: 8px;
  }
  .screen-mode .cockpit-main {
    flex: 1;
    min-height: 0;
    grid-template-rows: auto auto minmax(440px, 1fr) 172px auto;
    gap: 10px;
  }
  .screen-mode .kpi {
    padding: 10px 16px;
  }
  .screen-mode .kpi-value {
    font-size: 34px;
    margin-top: 5px;
  }
  .screen-mode .kpi p {
    margin: 5px 0;
  }
  .screen-mode .command-grid,
  .screen-mode .wing,
  .screen-mode .action-deck {
    min-height: 0;
    gap: 10px;
  }
  .screen-mode .wing {
    grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
  }
  .screen-mode .instrument {
    display: flex;
    flex-direction: column;
    min-height: 0;
    padding: 12px;
  }
  .screen-mode .instrument-title {
    flex-shrink: 0;
    margin-bottom: 8px;
    padding-bottom: 8px;
  }
  .screen-mode .panel-scroll,
  .screen-mode .region-matrix,
  .screen-mode .regional-detail :deep(.region-table) {
    flex: 1;
    min-height: 0;
    max-height: none;
    overflow: auto;
  }
  .screen-mode .core-visual {
    min-height: 180px;
    flex: 1;
  }
  .screen-mode .orbital-gauge {
    width: clamp(180px, 21vh, 240px);
  }
  .screen-mode .gauge-label strong {
    font-size: 38px;
  }
  .screen-mode .region-matrix {
    flex: 0 1 132px;
  }
  .screen-mode .region-matrix button {
    padding: 7px 9px;
  }
  .screen-mode .trend-chart {
    flex: 1;
    min-height: 0;
    max-height: 165px;
  }
  .screen-mode .age-alert {
    margin-block: 4px;
    padding-block: 5px;
  }
  .screen-mode .age-bars {
    gap: 9px;
  }
  .screen-mode .instrument-note {
    margin-bottom: 0;
  }
  .screen-mode .methodology {
    padding-top: 5px;
  }
}
@media (max-width: 1200px) {
  .command-grid {
    grid-template-columns: minmax(215px, 1fr) minmax(330px, 1.5fr);
  }
  .right-wing {
    grid-column: 1/-1;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto;
  }
  .kpi {
    padding: 15px 12px;
  }
  .kpi-label {
    font-size: 10px;
  }
  .kpi p {
    font-size: 9px;
  }
  .kpi-value {
    font-size: 30px;
  }
  .brand-mark {
    font-size: 12px;
  }
  .brand-mark small {
    font-size: 8px;
  }
  .cockpit-title h1 {
    font-size: 25px;
    letter-spacing: 3px;
  }
  .cockpit-title p {
    letter-spacing: 4px;
  }
  .brand-glyph {
    font-size: 30px;
  }
  .action-deck {
    grid-template-columns: 1.4fr 1fr;
  }
}
@media (max-width: 850px) {
  .operations-cockpit {
    padding: 16px;
  }
  .cockpit-header {
    grid-template-columns: 1fr auto;
    gap: 15px;
  }
  .brand-mark {
    display: none;
  }
  .cockpit-title {
    text-align: left;
    padding-left: 0;
  }
  .cockpit-title p {
    font-size: 9px;
  }
  .cockpit-title h1 {
    font-size: 23px;
  }
  .header-actions .data-status {
    display: none;
  }
  .kpi-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .kpi:nth-child(3) {
    border-right: 0;
  }
  .kpi:nth-child(-n + 3) {
    border-bottom: 1px solid #285168;
  }
  .command-grid {
    grid-template-columns: 1fr;
  }
  .command-core {
    grid-row: 1;
  }
  .left-wing,
  .right-wing {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto;
  }
  .action-deck {
    grid-template-columns: 1fr;
  }
  .core-visual {
    min-height: 240px;
  }
  .orbital-gauge {
    width: 245px;
  }
  .gauge-label strong {
    font-size: 43px;
  }
  .core-readout {
    min-width: 70px;
  }
  .region-matrix {
    max-height: 200px;
  }
  .snapshot-time {
    width: 100%;
    margin-left: 0;
  }
  .scope-line {
    flex-wrap: wrap;
  }
  .instrument-title h2 {
    font-size: 13px;
  }
}
@media (max-width: 520px) {
  .operations-cockpit {
    padding: 12px;
    border-radius: 5px;
  }
  .operations-cockpit.screen-mode {
    padding: 12px;
  }
  .cockpit-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 13px;
    gap: 8px;
  }
  .cockpit-title h1 {
    font-size: 19px;
    letter-spacing: 2px;
  }
  .cockpit-title p {
    font-size: 8px;
    letter-spacing: 3px;
  }
  .header-actions {
    gap: 0;
  }
  .screen-button {
    font-size: 10px;
    padding: 8px;
  }
  .screen-button span {
    margin-left: 2px;
  }
  .command-bar {
    padding: 10px;
    gap: 8px;
  }
  .command-label {
    width: 100%;
    display: flex;
    align-items: center;
    margin-bottom: 3px;
  }
  .command-bar label {
    flex: 1 1 40%;
  }
  .command-bar input {
    width: 100%;
    font-size: 11px;
    padding: 4px;
  }
  .command-bar .region-select {
    flex-basis: 50%;
  }
  .command-bar select {
    width: 100%;
    min-width: 0;
    font-size: 11px;
  }
  .command-bar .console-button {
    padding: 8px;
    font-size: 11px;
  }
  .snapshot-time {
    font-size: 9px;
    line-height: 1.8;
  }
  .kpi {
    padding: 13px 9px;
  }
  .kpi-index {
    display: none;
  }
  .kpi-label {
    font-size: 10px;
    padding-right: 0;
  }
  .kpi-value {
    font-size: 27px;
  }
  .kpi-value small {
    font-size: 9px;
    margin-left: 3px;
  }
  .kpi p {
    font-size: 8px;
    min-height: 26px;
  }
  .left-wing,
  .right-wing {
    grid-template-columns: 1fr;
  }
  .instrument {
    padding: 13px;
  }
  .core-visual {
    min-height: 200px;
  }
  .orbital-gauge {
    width: 195px;
    min-width: 150px;
  }
  .core-readout {
    min-width: 45px;
    font-size: 9px;
  }
  .core-readout strong {
    font-size: 21px;
  }
  .core-readout small {
    font-size: 7px;
  }
  .gauge-label > span {
    font-size: 9px;
  }
  .gauge-label strong {
    font-size: 32px;
  }
  .gauge-label em {
    font-size: 7px;
    letter-spacing: 1px;
  }
  .flow-controls {
    gap: 6px;
  }
  .flow-controls strong {
    font-size: 21px;
  }
  .flow-controls span {
    font-size: 10px;
  }
  .region-matrix {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    max-height: 245px;
  }
  .core-meta {
    font-size: 8px;
    gap: 9px;
  }
  .core-meta > span {
    width: 100%;
    margin: 0;
  }
  .instrument-title > span {
    font-size: 7px;
  }
  .scope-line {
    font-size: 9px;
    line-height: 1.7;
  }
  .table-signals,
  .standards-list {
    max-height: 290px;
  }
  .dialog-footer {
    flex-wrap: wrap;
  }
  .cockpit-dialog {
    width: 96vw;
  }
  .operations-dialog-head {
    padding: 15px;
  }
  .dialog-body {
    padding: 0 15px;
  }
  .operations-dialog-head h3 {
    font-size: 16px;
  }
}
</style>
