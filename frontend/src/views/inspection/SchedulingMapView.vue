<template>
  <div v-if="allowed" class="scheduling-page">
    <section class="coverage-console surface" aria-label="检查类型与统计周期">
      <header class="scheduling-header">
        <div class="heading-copy">
          <span class="page-kicker">排班系统 / 巡检覆盖</span>
          <h2>排班地图</h2>
          <p>按巡检周期找出未检查站点，让下一步安排一目了然。</p>
        </div>
        <div class="sync-status" :class="{ busy:loading, warning:error || !online }" role="status" aria-live="polite">
          <i aria-hidden="true"></i><strong>{{ syncText }}</strong>
          <small v-if="result" :title="updatedAt">核对于 {{ updatedTime }}</small>
          <small v-else>选择周期后自动更新</small>
        </div>
      </header>

      <div class="period-section-heading"><strong><span aria-hidden="true">01</span>选择检查周期</strong><span>选好即更新，无需手动刷新</span></div>
      <div class="period-controls">
        <div class="mode-picker" role="group" aria-label="检查类型">
          <button type="button" :aria-pressed="draft.mode === 'offline'" :class="{ active:draft.mode === 'offline' }" @click="draft.mode = 'offline'"><strong>现场检查</strong><span>季度覆盖</span></button>
          <button type="button" :aria-pressed="draft.mode === 'online'" :class="{ active:draft.mode === 'online' }" @click="draft.mode = 'online'"><strong>视频检查</strong><span>月度覆盖</span></button>
        </div>
        <div class="period-fields">
          <label>年份<select v-model.number="draft.year" aria-label="年份"><option v-for="year in yearOptions" :key="year" :value="year">{{ year }} 年</option></select></label>
          <label v-if="draft.mode === 'offline'">季度<select v-model.number="draft.quarter" aria-label="季度"><option v-for="q in 4" :key="q" :value="q">第 {{ q }} 季度</option></select></label>
          <label v-else>月份<select v-model.number="draft.month" aria-label="月份"><option v-for="m in 12" :key="m" :value="m">{{ m }} 月</option></select></label>
        </div>
        <div class="period-note"><strong>{{ requestedLabel }}</strong><p><span class="automatic-tag">统计口径</span>任意一张对应类型检查表有巡检记录，即计为已检查，无需等待审核。</p></div>
      </div>

      <div class="stats-heading"><strong>本周期覆盖概览</strong><span v-if="result">{{ result.period.label }} · {{ result.period.mode === 'offline' ? '现场' : '视频' }} · {{ region || '全部可见片区' }}<b v-if="loading && pendingChange">暂为上一周期数据</b></span><span v-else>等待周期数据</span></div>
      <section class="coverage-stats" aria-label="巡检覆盖统计" :aria-busy="loading">
        <article><span>纳入覆盖站点</span><strong>{{ result ? summary.total : '—' }}<small>座</small></strong><p>已启用对应类型的巡检计划</p></article>
        <article class="checked"><span>已检查站点</span><strong>{{ result ? summary.checked : '—' }}<small>座</small></strong><p>已有记录，已从地图销项</p></article>
        <article class="remaining"><span>待安排检查</span><strong>{{ result ? summary.remaining : '—' }}<small>座</small></strong><p>仍需安排本周期检查</p></article>
        <article class="progress-card"><div><span>本周期覆盖率</span><strong>{{ result ? rate : '—' }}<small>%</small></strong><p>{{ result ? summary.checked + ' / ' + summary.total + ' 座' : '正在核对巡检记录' }}</p></div><i class="coverage-ring" :style="{ '--coverage':rate + '%' }" aria-hidden="true"></i></article>
      </section>
      <div v-if="loading" class="sync-line" aria-hidden="true"></div>
    </section>

    <p v-if="error" class="data-error" role="alert">{{ error }}<span v-if="result"> 当前保留 {{ result.period.label }} 的{{ result.period.mode === 'offline' ? '现场' : '视频' }}结果。</span></p>
    <p v-else-if="!online" class="offline-note" role="status">网络已断开，暂时保留上次结果；恢复连接后将自动核对。</p>

    <section v-if="result" class="coverage-workspace surface" :aria-busy="loading">
      <header class="workspace-header">
        <div><span class="result-label">02 / 待检查站点分布</span><h3>{{ result.period.mode === 'offline' ? '现场' : '视频' }} · {{ result.period.label }}</h3><p>{{ result.period.date_from }} — {{ result.period.date_to }}</p></div>
        <span class="scope-badge">按账号数据范围统计</span>
      </header>
      <p v-if="loading && pendingChange" class="sync-notice" role="status"><i aria-hidden="true"></i>正在切换至 {{ requestedLabel }}，下方暂时保留上一周期结果。</p>
      <p v-if="!result.has_tables" class="coverage-callout">当前账号可见范围内没有此类型的检查表，暂不判断站点覆盖情况。请联系管理员核对巡检记录的检查表范围。</p>
      <p v-else-if="!summary.total" class="coverage-callout">当前范围没有启用对应巡检计划的可见站点，请核对站点计划纳入设置及账号数据范围。</p>
      <p v-else-if="summary.remaining === 0" class="coverage-callout complete">本周期当前范围内的站点均已有对应类型巡检记录，已全部从地图销项。</p>
      <p v-if="summary.missing_coordinates" class="coverage-callout">{{ summary.missing_coordinates }} 座待检查站点缺少有效坐标，未绘制图钉；仍计入待检查数量并保留在清单中。</p>

      <div class="workspace-filters">
        <label><span>站点所属地</span><select v-model="region" aria-label="站点所属地"><option value="">全部可见片区</option><option v-for="item in result.regions" :key="item.region" :value="item.region">{{ item.region }}（待查 {{ item.remaining }}）</option></select></label>
        <label class="station-search"><span>快速查找站点</span><input v-model.trim="keyword" type="search" maxlength="120" placeholder="输入站名、片区或地址" /></label>
        <div class="filter-meta"><strong>{{ visibleStations.length }}<small>座待检查</small></strong><span>地图与清单同步筛选</span></div>
        <button v-if="region || keyword" type="button" class="clear-filters" @click="clearFilters">清空筛选</button>
      </div>
      <div class="filter-context"><div v-if="region || mapKeyword" class="scope-chips" aria-label="当前地图筛选"><button v-if="region" type="button" aria-label="清除片区筛选" @click="region = ''">片区：{{ region }}<span aria-hidden="true">×</span></button><button v-if="mapKeyword" type="button" aria-label="清除关键词筛选" @click="keyword = ''">关键词：{{ mapKeyword }}<span aria-hidden="true">×</span></button></div><small>关键词仅筛选地图和清单，不改变上方覆盖统计。</small></div>

      <div class="map-list-grid">
        <SchedulingMapCanvas ref="coverageMap" :stations="visibleStations" :viewport-key="viewportKey" :selected-id="selectedId" @select="selectedId = $event" />
        <aside class="station-list-panel" aria-label="待检查站点清单">
          <header><div><span class="list-kicker">点击清单，同步定位</span><h4>待检查站点</h4></div><span class="list-count">{{ visibleStations.length }}<small>座</small></span></header>
          <div class="station-list">
            <button v-for="(station,index) in visibleStations" :key="station.station_id" type="button" class="station-row" :class="{ selected:String(selectedId) === String(station.station_id), unlocated:!stationCoordinates(station) }" :aria-pressed="String(selectedId) === String(station.station_id)" @click="selectStation(station)">
              <span class="station-number">{{ String(index + 1).padStart(2,'0') }}</span>
              <span class="station-copy"><strong>{{ station.station_name }}<em v-if="station.status === '停业'">停业</em></strong><span>{{ station.region }}</span><small :title="station.address || '未填写地址'">{{ station.address || '未填写地址' }}</small><b>{{ stationCoordinates(station) ? '定位到地图 ↗' : '缺少坐标 · 保留在待检查清单' }}</b></span>
            </button>
            <div v-if="!visibleStations.length" class="list-empty" :class="{ complete:result.has_tables && summary.total > 0 && !mapKeyword }"><span aria-hidden="true">{{ mapKeyword ? '⌕' : result.has_tables && summary.total > 0 ? '✓' : '—' }}</span><strong>{{ !result.has_tables ? '暂无可核对的检查表' : !summary.total ? '当前范围暂无纳入计划的站点' : mapKeyword ? '未找到匹配站点' : '本周期当前范围已全部覆盖' }}</strong><p>{{ mapKeyword ? '可尝试其他关键词，或清空筛选。' : '已检查站点不会出现在清单和地图中。' }}</p></div>
          </div>
        </aside>
      </div>
      <p v-if="selectionNote" class="selection-note" role="status">{{ selectionNote }}</p>
    </section>
    <section v-else class="initial-loading surface" role="status" :aria-busy="loading">
      <div class="skeleton-title"></div><p>{{ loading ? '正在核对本周期的站点与巡检记录…' : '暂时无法显示覆盖数据，请检查网络或账号权限。' }}</p><div class="skeleton-map" aria-hidden="true"><div></div><aside><i></i><i></i><i></i></aside></div>
    </section>

    <details class="methodology surface">
      <summary><span>统计口径与数据说明</span><small>巡检记录为准 · 不受审核状态影响</small><b class="methodology-toggle" aria-hidden="true"></b></summary>
      <p>数据以巡检记录的“巡检日期”为准，而非问题登记或审核日期。现场检查表按自然季度覆盖，视频检查表按自然月覆盖；类型取自检查表的现场/视频属性。</p>
      <p>仅统计站点基础档案中已启用对应巡检计划的站点。关闭现场或视频计划纳入后，本站不再进入对应类型的覆盖总数、待检查清单和地图。</p>
      <p>同一站点在所选周期内，只要存在任意一张对应类型检查表的巡检记录即视为已检查，不要求完成所有检查表。不受问题有无、审核结果、检查完成确认或站经理签名状态影响，零问题记录同样计数。</p>
      <p>沿用当前账号巡检记录的站点、片区及检查表数据范围，但不隐藏未审核记录。在已启用对应巡检计划的可见站点中，包含停业站点；缺少坐标不会被遗漏。覆盖率按站点去重，不能作为检查表逐表完成率、整改完成率或考核结论。</p>
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
function clearFilters() {
  region.value = ''
  keyword.value = ''
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

<style scoped src="../../styles/schedulingMap.css"></style>
