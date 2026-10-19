<template>
  <div v-if="allowed" class="scheduling-page">
    <section class="coverage-console surface" aria-label="检查类型与统计周期">
      <header class="scheduling-header">
        <div class="heading-copy">
          <span class="page-kicker">运营系统 / 巡检覆盖</span>
          <h2>排班地图<span>把下一站，安排得更清楚</span></h2>
        </div>
        <div class="sync-status" :class="{ busy:loading, warning:error || !online }" role="status" aria-live="polite">
          <i aria-hidden="true"></i><strong>{{ syncText }}</strong>
          <small v-if="result" :title="updatedAt">核对于 {{ updatedTime }}</small>
          <small v-else>选择周期后自动更新</small>
        </div>
      </header>

      <div class="period-controls">
        <div class="mode-picker" role="group" aria-label="检查类型">
          <button type="button" :aria-pressed="draft.mode === 'offline'" :class="{ active:draft.mode === 'offline' }" @click="draft.mode = 'offline'"><strong>现场检查</strong><span>季度覆盖</span></button>
          <button type="button" :aria-pressed="draft.mode === 'online'" :class="{ active:draft.mode === 'online' }" @click="draft.mode = 'online'"><strong>视频检查</strong><span>月度覆盖</span></button>
        </div>
        <div class="period-fields">
          <label>年份<select v-model.number="draft.year"><option v-for="year in yearOptions" :key="year" :value="year">{{ year }} 年</option></select></label>
          <label v-if="draft.mode === 'offline'">季度<select v-model.number="draft.quarter"><option v-for="q in 4" :key="q" :value="q">第 {{ q }} 季度</option></select></label>
          <label v-else>月份<select v-model.number="draft.month"><option v-for="m in 12" :key="m" :value="m">{{ m }} 月</option></select></label>
        </div>
        <p class="period-note"><span class="automatic-tag">自动更新</span>任意一张{{ draft.mode === 'offline' ? '现场' : '视频' }}检查表有巡检记录，即视为该站本{{ draft.mode === 'offline' ? '季度' : '月' }}已检查。</p>
      </div>

      <section class="coverage-stats" aria-label="巡检覆盖统计" :aria-busy="loading">
        <article><span>可见站点</span><strong>{{ result ? summary.total : '—' }}<small>座</small></strong><p>{{ region || '全部可见片区' }}</p></article>
        <article class="checked"><span>已检查站点</span><strong>{{ result ? summary.checked : '—' }}<small>座</small></strong><p>已从地图销项</p></article>
        <article class="remaining"><span>待安排检查</span><strong>{{ result ? summary.remaining : '—' }}<small>座</small></strong><p>地图仅保留未检查站点</p></article>
        <article class="progress-card"><div><span>本周期覆盖率</span><strong>{{ result ? rate : '—' }}<small>%</small></strong><p>{{ result ? summary.checked + ' / ' + summary.total + ' 座' : '正在核对巡检记录' }}</p></div><i class="coverage-ring" :style="{ '--coverage':rate + '%' }" aria-hidden="true"></i></article>
      </section>
      <div v-if="loading" class="sync-line" aria-hidden="true"></div>
    </section>

    <p v-if="error" class="data-error" role="alert">{{ error }}<span v-if="result"> 当前保留 {{ result.period.label }} 的{{ result.period.mode === 'offline' ? '现场' : '视频' }}结果。</span></p>
    <p v-else-if="!online" class="offline-note" role="status">网络已断开，暂时保留上次结果；恢复连接后将自动核对。</p>

    <section v-if="result" class="coverage-workspace surface" :aria-busy="loading">
      <header class="workspace-header">
        <div><span class="result-label">待检查站点分布</span><h3>{{ result.period.mode === 'offline' ? '现场' : '视频' }} · {{ result.period.label }}</h3><p>{{ result.period.date_from }} — {{ result.period.date_to }}</p></div>
        <span class="scope-badge">按账号数据范围统计</span>
      </header>
      <p v-if="loading && pendingChange" class="sync-notice" role="status"><i aria-hidden="true"></i>正在切换至 {{ requestedLabel }}，下方暂时保留上一周期结果。</p>
      <p v-if="!result.has_tables" class="coverage-callout">当前账号可见范围内没有此类型的检查表，暂不判断站点覆盖情况。请联系管理员核对巡检记录的检查表范围。</p>
      <p v-else-if="!summary.total" class="coverage-callout">当前范围没有可见站点，请核对账号的巡检记录站点、片区范围。</p>
      <p v-else-if="summary.remaining === 0" class="coverage-callout complete">本周期当前范围内的站点均已有对应类型巡检记录，已全部从地图销项。</p>
      <p v-if="summary.missing_coordinates" class="coverage-callout">{{ summary.missing_coordinates }} 座待检查站点缺少有效坐标，未绘制图钉；仍计入待检查数量并保留在清单中。</p>

      <div class="workspace-filters">
        <label><span>站点所属地</span><select v-model="region"><option value="">全部可见片区</option><option v-for="item in result.regions" :key="item.region" :value="item.region">{{ item.region }}（待查 {{ item.remaining }}）</option></select></label>
        <label class="station-search"><span>快速查找站点</span><input v-model.trim="keyword" type="search" maxlength="120" placeholder="输入站名、片区或地址" /></label>
        <div class="filter-meta"><strong>{{ visibleStations.length }}<small>座待检查</small></strong><span>地图与清单同步筛选</span></div>
      </div>
      <div v-if="region || mapKeyword" class="scope-chips" aria-label="当前地图筛选"><span v-if="region">片区：{{ region }}</span><span v-if="mapKeyword">关键词：{{ mapKeyword }}</span></div>

      <div class="map-list-grid">
        <SchedulingMapCanvas ref="coverageMap" :stations="visibleStations" :viewport-key="viewportKey" :selected-id="selectedId" @select="selectedId = $event" />
        <aside class="station-list-panel" aria-label="待检查站点清单">
          <header><div><span class="list-kicker">下一站去哪里</span><h4>待检查清单</h4></div><span class="list-count">{{ visibleStations.length }}</span></header>
          <div class="station-list">
            <button v-for="(station,index) in visibleStations" :key="station.station_id" type="button" class="station-row" :class="{ selected:String(selectedId) === String(station.station_id) }" :aria-pressed="String(selectedId) === String(station.station_id)" @click="selectStation(station)">
              <span class="station-number">{{ String(index + 1).padStart(2,'0') }}</span>
              <span class="station-copy"><strong>{{ station.station_name }}<em v-if="station.status === '停业'">停业</em></strong><span>{{ station.region }}</span><small>{{ station.address || '未填写地址' }}</small><b>{{ stationCoordinates(station) ? '定位到地图 ↗' : '缺少坐标 · 请核对站点资料' }}</b></span>
            </button>
            <div v-if="!visibleStations.length" class="list-empty"><span aria-hidden="true">✓</span><strong>{{ mapKeyword ? '未找到匹配站点' : '当前范围暂无待检查站点' }}</strong><p>{{ mapKeyword ? '可尝试其他关键词。' : '已检查站点不会出现在清单和地图中。' }}</p></div>
          </div>
        </aside>
      </div>
      <p v-if="selectionNote" class="selection-note" role="status">{{ selectionNote }}</p>
    </section>
    <section v-else class="initial-loading surface" role="status" :aria-busy="loading">
      <div class="skeleton-title"></div><p>{{ loading ? '正在核对本周期的站点与巡检记录…' : '暂时无法显示覆盖数据，请检查网络或账号权限。' }}</p><div class="skeleton-map" aria-hidden="true"><div></div><aside><i></i><i></i><i></i></aside></div>
    </section>

    <details class="methodology surface">
      <summary><span>统计口径与数据说明</span><small>巡检记录为准 · 不受审核状态影响</small></summary>
      <p>数据以巡检记录的“巡检日期”为准，而非问题登记或审核日期。现场检查表按自然季度覆盖，视频检查表按自然月覆盖；类型取自检查表的现场/视频属性。</p>
      <p>同一站点在所选周期内，只要存在任意一张对应类型检查表的巡检记录即视为已检查，不要求完成所有检查表。不受问题有无、审核结果、检查完成确认或站经理签名状态影响，零问题记录同样计数。</p>
      <p>沿用当前账号巡检记录的站点、片区及检查表数据范围，但不隐藏未审核记录。所有可见站点均纳入，包含停业站点；缺少坐标不会被遗漏。覆盖率按站点去重，不能作为检查表逐表完成率、整改完成率或考核结论。</p>
      <p>更改检查类型、年份或季度／月份后自动更新；快速切换会合并请求，已查看周期在当前页面内短时缓存30秒。页面可见且联网时每分钟自动核对，后台或断网时暂停；失败后会延长重试间隔，恢复连接或返回页面时自动检查。数据以标注的核对时间为准。</p>
      <p>片区和关键词在本页即时筛选，不增加数据库查询；关键词不改变上方片区覆盖统计。更新内容不变时保持地图位置；本页面不绘制区域圈，只提供排班参考，不会自动派工、删除记录或修改巡检计划。</p>
    </details>
  </div>
  <div v-else class="surface denied">当前账号无权查看排班地图，请联系管理员授权。</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import SchedulingMapCanvas from '@/components/SchedulingMapCanvas.vue'
import { coverageQuery, currentCoveragePeriod, filterUncoveredStations, stationCoordinates } from '@/utils/schedulingCoverage'
import { createCoverageLoader, coverageKey } from '@/utils/schedulingCoverageLoader'
import { createAdaptivePolling } from '@/utils/adaptivePolling'

let permissions = {}
try { permissions = JSON.parse(localStorage.getItem('permissions') || '{}') } catch { /* Route guard verifies authorization again. */ }
const allowed = (localStorage.getItem('role') || localStorage.getItem('user_role')) === 'root' || Boolean(permissions.view_scheduling_map)
const draft = ref(currentCoveragePeriod())
const yearOptions = Array.from({ length:101 }, (_, index) => 2100 - index)
const result = ref(null)
const loading = ref(false)
const error = ref('')
const blocked = ref(false)
const online = ref(navigator.onLine)
const region = ref('')
const keyword = ref('')
const mapKeyword = ref('')
const selectedId = ref('')
const coverageMap = ref(null)
const selectionNote = ref('')
let keywordTimer = null
const summary = computed(() => result.value?.regions.find(item => item.region === region.value) || result.value?.summary || { total:0,checked:0,remaining:0,missing_coordinates:0 })
const rate = computed(() => summary.value.total ? Math.round(summary.value.checked / summary.value.total * 1000) / 10 : 0)
const visibleStations = computed(previous => {
  const rows = filterUncoveredStations(result.value?.stations || [], region.value, mapKeyword.value)
  return previous?.length === rows.length && rows.every((row, index) => row === previous[index]) ? previous : rows
})
const requestedKey = computed(() => {
  try { return coverageKey(draft.value) } catch { return '' }
})
const requestedLabel = computed(() => draft.value.mode === 'offline' ? draft.value.year + '年第' + draft.value.quarter + '季度的现场检查' : draft.value.year + '年' + draft.value.month + '月的视频检查')
const pendingChange = computed(() => result.value && requestedKey.value !== coverageKey(result.value.period))
const viewportKey = computed(() => JSON.stringify([result.value ? coverageKey(result.value.period) : '', region.value, mapKeyword.value]))
const updatedAt = computed(() => result.value?.generated_at ? new Date(result.value.generated_at).toLocaleString('zh-CN', { timeZone:'Asia/Shanghai',hour12:false }) : '—')
const updatedTime = computed(() => result.value?.generated_at ? new Date(result.value.generated_at).toLocaleTimeString('zh-CN', { timeZone:'Asia/Shanghai',hour12:false }) : '—')
const syncText = computed(() => blocked.value ? '访问权限已变化' : !online.value ? '离线保留结果' : loading.value ? (pendingChange.value ? '正在切换周期' : '正在核对数据') : error.value ? '等待自动重试' : '自动同步已开启')

const loader = createCoverageLoader({
  fetchCoverage: async (query, signal) => (await axios.get('/api/scheduling-map', { params:query,signal,timeout:15000 })).data,
  onChange(state) {
    const next = state.result
    if (next && next !== result.value) {
      const changed = !result.value || coverageKey(next.period) !== coverageKey(result.value.period)
      result.value = next
      if (region.value && !next.regions.some(item => item.region === region.value)) region.value = ''
      if (changed || (selectedId.value && !next.stations.some(item => String(item.station_id) === String(selectedId.value)))) {
        selectedId.value = ''
        selectionNote.value = ''
      }
    } else if (!next) result.value = null
    loading.value = state.loading
    error.value = state.error
    blocked.value = state.blocked
  },
})
const polling = createAdaptivePolling({
  task: async () => { if (!await loader.refresh()) throw new Error('Coverage refresh failed') },
  canRun: () => allowed && !document.hidden && navigator.onLine && !blocked.value,
})
function syncAutoRefresh() {
  online.value = navigator.onLine
  if (document.hidden || !online.value || blocked.value) polling.pause()
  else polling.start({ immediate:true })
}
function selectStation(station) {
  selectedId.value = station.station_id
  coverageMap.value?.focus(station)
  selectionNote.value = stationCoordinates(station) ? '已定位：' + station.station_name : station.station_name + ' 缺少有效坐标，请联系管理员在站点资料中补充。'
}
watch(requestedKey, () => { if (allowed) loader.select(draft.value) })
watch(keyword, () => {
  clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => { mapKeyword.value = keyword.value }, 120)
})
watch([region, keyword], () => { selectedId.value = ''; selectionNote.value = '' })
watch(blocked, value => { if (value) polling.pause() })
onMounted(() => {
  if (!allowed) return
  loader.select(coverageQuery(draft.value), { immediate:true })
  polling.start()
  document.addEventListener('visibilitychange', syncAutoRefresh)
  window.addEventListener('focus', syncAutoRefresh)
  window.addEventListener('online', syncAutoRefresh)
  window.addEventListener('offline', syncAutoRefresh)
})
onBeforeUnmount(() => {
  loader.dispose()
  polling.dispose()
  clearTimeout(keywordTimer)
  document.removeEventListener('visibilitychange', syncAutoRefresh)
  window.removeEventListener('focus', syncAutoRefresh)
  window.removeEventListener('online', syncAutoRefresh)
  window.removeEventListener('offline', syncAutoRefresh)
})
</script>

<style scoped>
.scheduling-page { display:grid; gap:16px; min-width:0; color:#203b50; }
.surface { border:1px solid #d9e5ee; border-radius:18px; background:#fff; box-shadow:0 8px 28px #14344c05; }
.coverage-console { position:relative; overflow:hidden; background:radial-gradient(ellipse at 100% 0%,#eaf5fb,transparent 48%),#fff; }
.scheduling-header { display:flex; align-items:center; justify-content:space-between; gap:18px; padding:21px 24px 17px; }
.page-kicker { color:#658ba2; font-size:10px; letter-spacing:1.5px; font-weight:700; }
.heading-copy h2 { display:flex; align-items:center; flex-wrap:wrap; gap:15px; margin:7px 0 0; color:#18374c; font-size:28px; line-height:1.3; }
.heading-copy h2 span { color:#859bab; font-size:12px; font-weight:400; letter-spacing:.5px; }
.sync-status { display:grid; grid-template-columns:7px auto; align-items:center; column-gap:8px; row-gap:4px; color:#358671; flex-shrink:0; }
.sync-status i { width:6px; height:6px; border-radius:50%; background:currentColor; box-shadow:0 0 0 4px #d7efe7; }
.sync-status strong { font-size:11px; font-weight:600; }.sync-status small { grid-column:2; color:#8b9dab; font-size:10px; }
.sync-status.busy { color:#2180ae; }.sync-status.busy i { box-shadow:0 0 0 4px #dceef8; }.sync-status.warning { color:#b17c27; }.sync-status.warning i { box-shadow:0 0 0 4px #f7edda; }
.period-controls { display:flex; flex-wrap:wrap; align-items:center; gap:16px 24px; padding:0 24px 18px; }
.mode-picker { display:flex; gap:4px; padding:4px; border:1px solid #dbe5ed; border-radius:11px; background:#f1f6f9; }
.mode-picker button { display:flex; flex-direction:column; align-items:center; gap:4px; min-width:108px; padding:9px 18px; border:1px solid transparent; border-radius:8px; background:none; color:#7890a1; cursor:pointer; font:inherit; }
.mode-picker button.active { border-color:#c4dce9; color:#17658c; background:#fff; box-shadow:0 2px 6px #1845690b; }
.mode-picker strong { font-size:13px; }.mode-picker span { font-size:10px; }
.period-fields { display:flex; gap:12px; }.period-fields label,.workspace-filters label { display:grid; gap:6px; color:#7691a3; font-size:11px; }
input,select { box-sizing:border-box; min-height:39px; padding:8px 11px; border:1px solid #d0dfe9; border-radius:8px; background:#fff; color:#294f68; font:inherit; font-size:13px; }
.period-fields select { min-width:115px; }.period-note { margin:0 0 0 auto; max-width:330px; color:#8a9eac; font-size:11px; line-height:1.9; }
.automatic-tag { display:inline-block; margin-right:7px; padding:0 6px; border-radius:4px; background:#eaf5fa; color:#4b86a0; font-size:10px; }
button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible { outline:2px solid #429aca; outline-offset:3px; }
.coverage-stats { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); border-top:1px solid #e5edf3; background:#ffffff90; }
.coverage-stats article { position:relative; padding:15px 24px; }.coverage-stats article+article::before { content:''; position:absolute; left:0; top:18px; bottom:18px; width:1px; background:#e5edf3; }
.coverage-stats article>span,.progress-card>div>span { color:#8094a4; font-size:11px; }.coverage-stats strong { display:block; margin:6px 0; color:#2a526d; font-size:28px; line-height:1; font-variant-numeric:tabular-nums; }.coverage-stats small { margin-left:6px; color:#8da1b0; font-size:11px; font-weight:400; }.coverage-stats p { margin:0; font-size:10px; color:#9aabb7; }.coverage-stats .checked strong { color:#2a8974; }.coverage-stats .remaining { background:linear-gradient(100deg,#fffcf5,transparent); }.coverage-stats .remaining strong { color:#bd8227; }
.progress-card { display:flex; align-items:center; justify-content:space-between; gap:12px; }.coverage-ring { position:relative; width:48px; height:48px; flex-shrink:0; border-radius:50%; background:conic-gradient(#38a48d var(--coverage),#e8f0f4 0); }.coverage-ring::after { content:''; position:absolute; inset:5px; border-radius:50%; background:#fff; }
.sync-line { position:absolute; bottom:0; left:0; right:0; height:2px; overflow:hidden; background:#e8f3f8; }.sync-line::after { content:''; display:block; width:30%; height:100%; background:#3599c3; animation:coverage-sync 1.4s ease-in-out infinite; }
.data-error,.offline-note,.sync-notice { margin:0; padding:12px 16px; border-radius:10px; font-size:12px; line-height:1.8; }.data-error { color:#a4473c; border:1px solid #f3d7d1; background:#fff8f6; }.offline-note { color:#8e702e; background:#fffaf0; border:1px solid #eee0bf; }.sync-notice { display:flex; align-items:center; gap:8px; margin-bottom:14px; color:#32718f; background:#eff8fc; border:1px solid #d6eaf4; }.sync-notice i { width:6px; height:6px; flex-shrink:0; border-radius:50%; background:#348cb2; }
.coverage-workspace { padding:18px; min-width:0; }.workspace-header { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; margin-bottom:16px; }.result-label { font-size:10px; letter-spacing:1.5px; color:#8aa2b3; }.workspace-header h3 { margin:5px 0; font-size:19px; color:#244a63; }.workspace-header p { margin:0; color:#8b9eac; font-size:11px; }.scope-badge { padding:6px 10px; border:1px solid #e0eaf1; border-radius:6px; background:#f8fbfd; color:#8ca0af; font-size:10px; }
.coverage-callout { margin:0 0 13px; padding:10px 13px; border:1px solid #f0dfbc; border-radius:8px; color:#926a24; background:#fffbf2; font-size:11px; line-height:1.8; }.coverage-callout.complete { color:#247764; background:#f1faf6; border-color:#c9e7db; }
.workspace-filters { display:flex; align-items:flex-end; gap:14px; margin-bottom:14px; }.workspace-filters select { min-width:210px; }.station-search { flex:1; min-width:0; }.station-search input { min-width:0; width:100%; }.filter-meta { min-width:115px; text-align:right; align-self:center; }.filter-meta strong { display:block; color:#b18036; font-size:22px; font-variant-numeric:tabular-nums; }.filter-meta small { margin-left:5px; color:#8094a5; font-size:10px; font-weight:400; }.filter-meta>span { color:#96a8b5; font-size:9px; }
.scope-chips { display:flex; gap:8px; flex-wrap:wrap; margin:0 0 12px; }.scope-chips span { max-width:100%; overflow-wrap:anywhere; padding:4px 8px; border:1px solid #d8e8f0; border-radius:5px; color:#518099; background:#f5fafc; font-size:10px; }
.map-list-grid { display:grid; grid-template-columns:minmax(0,1fr) 286px; gap:14px; height:clamp(580px,calc(100dvh - 270px),850px); }
.station-list-panel { display:flex; flex-direction:column; min-height:0; min-width:0; overflow:hidden; border:1px solid #d9e5ee; border-radius:14px; background:#f8fbfd; }.station-list-panel>header { display:flex; align-items:center; justify-content:space-between; padding:15px; border-bottom:1px solid #e1ebf2; background:linear-gradient(110deg,#fff,#f4f9fc); }.list-kicker { font-size:9px; color:#9badbb; letter-spacing:1px; }.station-list-panel h4 { margin:4px 0 0; font-size:14px; color:#345b73; }.list-count { display:grid; place-items:center; min-width:32px; height:29px; padding:0 7px; border:1px solid #e9dbba; border-radius:7px; color:#b17d27; background:#fffaf0; font-size:12px; font-weight:700; }
.station-list { min-height:0; overflow-y:auto; overscroll-behavior:contain; padding:7px; scrollbar-width:thin; scrollbar-color:#c7d8e4 transparent; }.station-row { display:flex; gap:10px; width:100%; padding:13px 8px; border:1px solid transparent; border-bottom-color:#e4edf3; border-radius:8px; background:none; text-align:left; cursor:pointer; }.station-row:hover,.station-row.selected { border-color:#c3deeb; background:#eaf5fa; }.station-number { display:grid; place-items:center; flex-shrink:0; width:24px; height:24px; border-radius:6px; color:#83a0b3; background:#edf3f7; font-size:10px; font-variant-numeric:tabular-nums; }.station-row.selected .station-number { color:#287799; background:#d7ebf6; }
.station-copy { display:grid; gap:5px; min-width:0; }.station-copy strong { color:#294e66; font-size:13px; line-height:1.5; }.station-copy>span { color:#7a95a7; font-size:10px; }.station-copy small { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; color:#9aadb9; font-size:10px; line-height:1.7; overflow-wrap:anywhere; }.station-copy b { margin-top:2px; color:#4f8ca8; font-size:10px; font-weight:500; }.station-copy em { display:inline-block; margin-left:7px; padding:0 4px; border-radius:3px; color:#a58650; background:#f4eddf; font-size:9px; font-weight:400; font-style:normal; }
.list-empty { display:grid; justify-items:center; gap:13px; padding:45px 16px; text-align:center; color:#8ca0ae; font-size:12px; }.list-empty>span { display:grid; place-items:center; width:38px; height:38px; border:1px solid #d5e8e1; border-radius:50%; color:#72a792; background:#f0f8f4; font-size:18px; }.list-empty p { margin:0; font-size:11px; line-height:1.8; }.selection-note { margin:12px 0 0; font-size:11px; color:#6e91a5; }
.methodology { padding:15px 18px; }.methodology summary { display:flex; align-items:center; gap:14px; cursor:pointer; color:#5b7e94; font-size:12px; font-weight:600; }.methodology summary::before { content:'›'; color:#92adbf; font-size:17px; transform:rotate(0deg); transition:transform .15s; }.methodology[open] summary::before { transform:rotate(90deg); }.methodology summary small { margin-left:auto; font-weight:400; color:#99abb8; font-size:10px; }.methodology p { margin-bottom:0; color:#8399aa; font-size:11px; line-height:1.9; }
.initial-loading { padding:22px; color:#859eaf; font-size:12px; }.skeleton-title { width:150px; height:18px; border-radius:5px; background:#eaf1f6; }.skeleton-map { display:grid; grid-template-columns:1fr 286px; gap:14px; height:580px; margin-top:20px; }.skeleton-map>div { border-radius:13px; background:linear-gradient(120deg,#eaf1f5,#f3f8fb,#eaf1f5); }.skeleton-map aside { padding:12px; border-radius:13px; background:#f5f9fc; }.skeleton-map i { display:block; height:80px; margin-bottom:12px; border-radius:9px; background:#eaf1f5; }.denied { padding:50px 20px; text-align:center; color:#7691a4; }
@keyframes coverage-sync { from { transform:translateX(-110%); } to { transform:translateX(440%); } }
@media(max-width:1150px) { .period-note { flex-basis:100%; max-width:none; margin-left:0; }.map-list-grid { grid-template-columns:minmax(0,1fr) 250px; }.progress-card { gap:6px; }.coverage-ring { width:38px; height:38px; } }
@media(max-width:900px) { .map-list-grid { grid-template-columns:1fr; height:auto; }.station-list-panel { max-height:420px; }.coverage-workspace { padding:14px; }.heading-copy h2 span { display:none; }.coverage-stats article { padding:14px 18px; }.coverage-ring { display:none; }.skeleton-map { grid-template-columns:1fr; height:520px; }.skeleton-map aside { display:none; } }
@media(max-width:600px) { .scheduling-page { gap:12px; }.scheduling-header { align-items:flex-start; padding:18px 16px 14px; }.heading-copy h2 { font-size:25px; }.page-kicker { font-size:9px; }.sync-status { margin-top:2px; }.sync-status strong { font-size:10px; }.sync-status small { font-size:9px; }.period-controls { padding:0 16px 16px; gap:12px; }.mode-picker { flex:1; }.mode-picker button { flex:1; min-width:0; padding:8px 12px; }.period-fields { width:100%; }.period-fields label { flex:1; min-width:0; }.period-fields select { width:100%; min-width:0; }.period-note { font-size:10px; }.coverage-stats { grid-template-columns:repeat(2,minmax(0,1fr)); }.coverage-stats article { padding:13px 16px; }.coverage-stats article:nth-child(3),.coverage-stats article:nth-child(4) { border-top:1px solid #e5edf3; }.coverage-stats article:nth-child(3)::before { display:none; }.coverage-stats strong { font-size:26px; }.workspace-header h3 { font-size:17px; }.scope-badge { display:none; }.workspace-filters { display:grid; grid-template-columns:1fr; gap:11px; }.workspace-filters select { width:100%; min-width:0; }.filter-meta { display:flex; align-items:center; justify-content:space-between; gap:10px; text-align:left; }.filter-meta strong { font-size:18px; }.filter-meta>span { font-size:10px; }.methodology summary small { display:none; }.initial-loading { padding:16px; } }
@media(max-width:600px) { input,select { min-height:44px; } }
@media(prefers-reduced-motion:reduce) { .sync-line::after { animation:none; }.methodology summary::before { transition:none; } }
</style>
