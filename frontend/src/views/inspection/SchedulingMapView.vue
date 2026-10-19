<template>
  <div v-if="allowed" class="scheduling-page">
    <header class="scheduling-header surface">
      <div><span class="page-kicker">运营系统 / 巡检覆盖</span><h2>排班地图</h2><p>让尚未检查的站点一目了然，为下一次巡检安排提供依据。</p></div>
      <span class="read-only-tag">只读覆盖查询</span>
    </header>

    <section class="period-panel surface" aria-label="检查类型与统计周期">
      <div class="mode-picker" role="group" aria-label="检查类型">
        <button type="button" :aria-pressed="draft.mode === 'offline'" :class="{ active:draft.mode === 'offline' }" @click="draft.mode = 'offline'"><strong>现场检查</strong><span>按季度覆盖</span></button>
        <button type="button" :aria-pressed="draft.mode === 'online'" :class="{ active:draft.mode === 'online' }" @click="draft.mode = 'online'"><strong>视频检查</strong><span>按月覆盖</span></button>
      </div>
      <form class="period-fields" @submit.prevent="loadCoverage">
        <label>年份<input v-model.number="draft.year" type="number" min="2000" max="2100" step="1" required /></label>
        <label v-if="draft.mode === 'offline'">季度<select v-model.number="draft.quarter"><option v-for="q in 4" :key="q" :value="q">第 {{ q }} 季度</option></select></label>
        <label v-else>月份<select v-model.number="draft.month"><option v-for="m in 12" :key="m" :value="m">{{ m }} 月</option></select></label>
        <button class="query-button" type="submit" :disabled="loading">{{ loading ? '正在查询…' : '查看未检查站点' }}</button>
      </form>
      <p class="period-note">{{ draft.mode === 'offline' ? '本季度内任意一张现场检查表有巡检记录，即视为该站点已检查。' : '本月内任意一张视频检查表有巡检记录，即视为该站点已检查。' }}<span v-if="dirty">设置已更改，请点击查询应用。</span></p>
    </section>

    <p v-if="error" class="data-error" role="alert">{{ error }}<span v-if="result"> 下方保留上次查询结果。</span></p>
    <template v-if="result">
      <section class="coverage-stats" aria-label="巡检覆盖统计">
        <article class="surface"><span>当前范围站点</span><strong>{{ summary.total }}<small>座</small></strong><p>{{ region || '全部可见片区' }}</p></article>
        <article class="surface checked"><span>已有对应记录</span><strong>{{ summary.checked }}<small>座</small></strong><p>已从地图销项</p></article>
        <article class="surface remaining"><span>尚未检查</span><strong>{{ summary.remaining }}<small>座</small></strong><p>本周期待安排巡检</p></article>
        <article class="surface progress-card"><span>本周期覆盖率</span><strong>{{ rate }}<small>%</small></strong><div class="coverage-track"><i :style="{ width:rate + '%' }"></i></div></article>
      </section>

      <section class="coverage-workspace surface" :aria-busy="loading">
        <header class="workspace-header">
          <div><span class="result-label">当前查询结果</span><h3>{{ result.period.mode === 'offline' ? '现场' : '视频' }} · {{ result.period.label }}</h3><p>{{ result.period.date_from }} — {{ result.period.date_to }}<span>更新于 {{ updatedAt }}</span></p></div>
          <button class="light-button" type="button" :disabled="loading" @click="reloadApplied">更新当前周期覆盖</button>
        </header>
        <p v-if="!result.has_tables" class="coverage-callout">当前账号可见范围内没有此类型的检查表，暂不判断站点覆盖情况。请联系管理员核对巡检记录的检查表范围。</p>
        <p v-else-if="!summary.total" class="coverage-callout">当前范围没有可见站点，请核对账号的巡检记录站点、片区范围。</p>
        <p v-else-if="summary.remaining === 0" class="coverage-callout complete">本周期当前范围内的站点均已有对应类型巡检记录，已全部从地图销项。</p>
        <p v-if="summary.missing_coordinates" class="coverage-callout">{{ summary.missing_coordinates }} 座待检查站点缺少有效坐标，未绘制图钉；仍计入待检查数量并保留在清单中。</p>
        <div class="workspace-filters">
          <label><span>站点所属地</span><select v-model="region"><option value="">全部可见片区</option><option v-for="item in result.regions" :key="item.region" :value="item.region">{{ item.region }}（待查 {{ item.remaining }}）</option></select></label>
          <label class="station-search"><span>清单与地图同步筛选</span><input v-model.trim="keyword" type="search" placeholder="搜索站名、片区或地址" /></label>
          <span>匹配 {{ visibleStations.length }} 座待检查站点</span>
        </div>
        <div class="map-list-grid">
          <SchedulingMapCanvas ref="coverageMap" :stations="visibleStations" :region-points="visibleRegionPoints" :selected-id="selectedId" @select="selectedId = $event" />
          <aside class="station-list-panel" aria-label="待检查站点清单">
            <header><h4>待检查清单</h4><span>{{ visibleStations.length }} 座</span></header>
            <div class="station-list">
              <button v-for="(station,index) in visibleStations" :key="station.station_id" type="button" class="station-row" :class="{ selected:String(selectedId) === String(station.station_id) }" :aria-pressed="String(selectedId) === String(station.station_id)" @click="selectStation(station)">
                <span class="station-number">{{ String(index + 1).padStart(2,'0') }}</span>
                <span class="station-copy"><strong>{{ station.station_name }}</strong><span>{{ station.region }}<em v-if="station.status === '停业'">停业</em></span><small>{{ station.address || '未填写地址' }}</small><b>{{ stationCoordinates(station) ? '定位站点 ↗' : '缺少坐标 · 请核对站点资料' }}</b></span>
              </button>
              <div v-if="!visibleStations.length" class="list-empty"><strong>暂无待检查站点</strong><p>{{ keyword ? '可尝试其他关键词。' : '已检查站点不会出现在清单和地图中。' }}</p></div>
            </div>
          </aside>
        </div>
        <p v-if="selectionNote" class="selection-note" role="status">{{ selectionNote }}</p>
        <div v-if="loading" class="refresh-indicator" role="status">正在核对新的巡检记录，请稍候…</div>
      </section>
    </template>
    <div v-else-if="loading" class="initial-loading surface" role="status">正在核对本周期的站点与巡检记录…</div>

    <details class="methodology surface">
      <summary>统计口径与数据说明</summary>
      <p>数据以巡检记录的“巡检日期”为准，而非问题登记或审核日期。现场检查表按自然季度覆盖，视频检查表按自然月覆盖；类型取自检查表的现场/视频属性。</p>
      <p>同一站点在所选周期内，只要存在任意一张对应类型检查表的巡检记录即视为已检查，不要求完成所有检查表。不受问题有无、审核结果、检查完成确认或站经理签名状态影响，零问题记录同样计数；记录被删除后会在下次查询中重新判断。</p>
      <p>沿用当前账号巡检记录的站点、片区及检查表数据范围，但不隐藏未审核记录。所有可见站点均纳入，包含停业站点；缺少坐标不会被遗漏。覆盖率按站点去重，不能作为检查表逐表完成率、整改完成率或考核结论。</p>
      <p>蓝色片区区划根据该片区所有可见站点的有效坐标生成包围范围，边缘适当留白，仅为业务片区站点分布示意，不是高德行政边界；不同片区的范围可能重叠。已检查站点不显示图钉，但仍用于保持片区范围稳定。未设置片区或无有效坐标时不生成区划；可使用“片区区划”开关隐藏区域。</p>
      <p>数据按查询时刻读取；新增记录后可点击“更新当前周期覆盖”。关键词只筛选待检查清单与图钉，不改变上方的片区覆盖统计。本页面只提供排班参考，不会自动派工、删除记录或修改巡检计划。</p>
    </details>
  </div>
  <div v-else class="surface denied">当前账号无权查看排班地图，请联系管理员授权。</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import SchedulingMapCanvas from '@/components/SchedulingMapCanvas.vue'
import { coverageQuery, currentCoveragePeriod, filterUncoveredStations, stationCoordinates } from '@/utils/schedulingCoverage'

let permissions = {}
try { permissions = JSON.parse(localStorage.getItem('permissions') || '{}') } catch { /* Route guard verifies authorization again. */ }
const allowed = (localStorage.getItem('role') || localStorage.getItem('user_role')) === 'root' || Boolean(permissions.view_scheduling_map)
const draft = ref(currentCoveragePeriod())
const result = ref(null)
const loading = ref(false)
const error = ref('')
const region = ref('')
const keyword = ref('')
const selectedId = ref('')
const coverageMap = ref(null)
const selectionNote = ref('')
let controller = null
let sequence = 0
const summary = computed(() => result.value?.regions.find(item => item.region === region.value) || result.value?.summary || { total:0,checked:0,remaining:0,missing_coordinates:0 })
const rate = computed(() => summary.value.total ? Math.round(summary.value.checked / summary.value.total * 1000) / 10 : 0)
const visibleStations = computed(() => filterUncoveredStations(result.value?.stations || [], region.value, keyword.value))
const visibleRegionPoints = computed(() => (result.value?.region_points || []).filter(item => !region.value || item.region === region.value))
const dirty = computed(() => {
  if (!result.value) return false
  try { return JSON.stringify(coverageQuery(draft.value)) !== JSON.stringify(coverageQuery(result.value.period)) } catch { return true }
})
const updatedAt = computed(() => result.value?.generated_at ? new Date(result.value.generated_at).toLocaleString('zh-CN', { timeZone:'Asia/Shanghai',hour12:false }) : '—')

function selectStation(station) {
  selectedId.value = station.station_id
  coverageMap.value?.focus(station)
  selectionNote.value = stationCoordinates(station) ? `已定位：${station.station_name}` : `${station.station_name} 缺少有效坐标，请联系管理员在站点资料中补充。`
}
async function loadCoverage(source) {
  let query
  try { query = coverageQuery(source?.mode ? source : draft.value) } catch (cause) { error.value = cause.message; return }
  const token = ++sequence
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get('/api/scheduling-map', { params:query, signal:controller.signal })
    if (token !== sequence) return
    result.value = response.data
    if (region.value && !result.value.regions.some(item => item.region === region.value)) region.value = ''
    selectedId.value = ''
    selectionNote.value = ''
  } catch (cause) {
    if (token === sequence && cause.code !== 'ERR_CANCELED') error.value = cause.response?.data?.error || '覆盖数据读取失败，请稍后重试。'
  } finally { if (token === sequence) loading.value = false }
}
function reloadApplied() { if (result.value) loadCoverage(result.value.period) }
watch([region, keyword], () => { selectedId.value = ''; selectionNote.value = '' })
onMounted(() => { if (allowed) loadCoverage() })
onBeforeUnmount(() => { sequence++; controller?.abort() })
</script>

<style scoped>
.scheduling-page { display:grid; gap:20px; color:#203b50; }
.surface { border:1px solid #dbe4ee; border-radius:22px; background:#fff; box-shadow:0 12px 32px #14344c06; }
.scheduling-header { display:flex; align-items:center; justify-content:space-between; gap:20px; padding:24px 28px; background:radial-gradient(ellipse at 95% 0%,#e7f3f9,transparent 55%),#fff; }
.page-kicker { color:#387395; font-size:12px; font-weight:700; letter-spacing:1px; }
.scheduling-header h2 { margin:12px 0 7px; font-size:34px; color:#0f172a; }
.scheduling-header p { margin:0; color:#73869a; font-size:13px; line-height:1.8; }
.read-only-tag { flex-shrink:0; padding:8px 12px; border:1px solid #d5e6ee; border-radius:8px; background:#f4f9fb; color:#527b90; font-size:12px; }
.period-panel { display:flex; align-items:flex-start; flex-wrap:wrap; gap:20px; padding:22px; }
.mode-picker { display:flex; gap:5px; padding:5px; border:1px solid #dce6ef; border-radius:13px; background:#f4f7fa; }
.mode-picker button { display:grid; gap:4px; min-width:128px; padding:11px 18px; border:1px solid transparent; border-radius:9px; background:none; color:#657f93; cursor:pointer; }
.mode-picker button.active { color:#17658c; background:#fff; border-color:#c6deeb; box-shadow:0 3px 9px #1845690c; }
.mode-picker strong { font-size:14px; }.mode-picker span { font-size:11px; }
.period-fields { display:flex; align-items:flex-end; flex-wrap:wrap; gap:14px; margin-left:auto; }
.period-fields label,.workspace-filters label { display:grid; gap:8px; color:#658196; font-size:12px; }
input,select { box-sizing:border-box; min-height:42px; padding:8px 12px; border:1px solid #cfdde8; border-radius:9px; background:#fff; color:#264c65; font:inherit; font-size:14px; }
.period-fields input { width:110px; }.period-fields select { min-width:130px; }
.query-button,.light-button { min-height:42px; padding:10px 18px; border:1px solid #18749e; border-radius:9px; background:#18749e; color:#fff; font:inherit; font-size:13px; font-weight:700; cursor:pointer; }
button:disabled { opacity:.55; cursor:wait; }button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible { outline:2px solid #3b9ccc; outline-offset:3px; }
.light-button { border-color:#d2e2ec; color:#42758d; background:#f5fafc; }
.period-note { flex-basis:100%; margin:0; font-size:12px; line-height:1.8; color:#7890a3; }.period-note span { margin-left:12px; color:#b16d12; font-weight:700; }
.data-error { margin:0; padding:15px 18px; border:1px solid #fecaca; border-radius:12px; color:#a13434; background:#fff5f5; font-size:13px; line-height:1.8; }
.coverage-stats { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; }
.coverage-stats article { padding:20px 22px; }.coverage-stats article>span { color:#6d8296; font-size:12px; }
.coverage-stats strong { display:block; margin:12px 0 8px; color:#204c6a; font-size:32px; line-height:1; font-variant-numeric:tabular-nums; }.coverage-stats small { margin-left:7px; color:#91a2b2; font-size:12px; font-weight:400; }
.coverage-stats p { margin:0; color:#90a0af; font-size:11px; }.coverage-stats .checked strong { color:#258371; }.coverage-stats .remaining { border-top:3px solid #d99a38; }.coverage-stats .remaining strong { color:#bb7b15; }
.coverage-track { height:5px; overflow:hidden; border-radius:5px; background:#e9f0f5; margin-top:17px; }.coverage-track i { display:block; height:100%; background:linear-gradient(90deg,#2b97b8,#37a992); }
.coverage-workspace { position:relative; padding:20px; min-width:0; }.workspace-header { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:18px; margin-bottom:18px; }
.result-label { color:#6990a4; font-size:11px; letter-spacing:1px; }.workspace-header h3 { margin:7px 0; color:#1d465f; font-size:21px; }.workspace-header p { margin:0; color:#8194a4; font-size:12px; line-height:1.8; }.workspace-header p span { margin-left:18px; }
.coverage-callout { margin:0 0 14px; padding:12px 15px; border:1px solid #f0dfbc; border-radius:9px; color:#926a24; background:#fffbf2; font-size:12px; line-height:1.8; }.coverage-callout.complete { color:#247764; background:#f1faf6; border-color:#c9e7db; }
.workspace-filters { display:flex; align-items:flex-end; flex-wrap:wrap; gap:15px; margin-bottom:16px; }.workspace-filters select { min-width:200px; }.station-search { flex:1; min-width:190px; }.workspace-filters>span { align-self:center; margin-left:auto; color:#8093a4; font-size:12px; }
.map-list-grid { display:grid; grid-template-columns:minmax(0,1fr) 300px; gap:16px; height:clamp(660px,76dvh,1000px); }
.station-list-panel { display:flex; flex-direction:column; min-height:0; min-width:0; overflow:hidden; border:1px solid #dce6ef; border-radius:16px; background:#f8fbfd; }.station-list-panel>header { display:flex; align-items:center; justify-content:space-between; padding:18px 16px; border-bottom:1px solid #e2ebf2; background:#fff; }.station-list-panel h4 { margin:0; font-size:14px; }.station-list-panel>header span { font-size:12px; color:#9a792b; }
.station-list { min-height:0; overflow-y:auto; overscroll-behavior:contain; padding:8px; scrollbar-width:thin; scrollbar-color:#c7d8e4 transparent; }
.station-row { display:flex; gap:12px; width:100%; padding:15px 10px; border:1px solid transparent; border-bottom-color:#e4ecf3; border-radius:9px; background:none; text-align:left; cursor:pointer; }.station-row:hover,.station-row.selected { border-color:#c2dce9; background:#eaf5fa; }
.station-number { padding-top:2px; color:#9badbd; font-size:12px; font-variant-numeric:tabular-nums; }.station-copy { display:grid; gap:6px; min-width:0; }.station-copy strong { font-size:14px; color:#254b64; }.station-copy>span { color:#7b91a3; font-size:11px; }.station-copy em { margin-left:8px; padding:1px 4px; border-radius:3px; background:#f1e8da; color:#927441; font-style:normal; }.station-copy small { color:#9aabba; font-size:11px; line-height:1.7; overflow-wrap:anywhere; }.station-copy b { color:#bb8430; font-size:11px; font-weight:500; }
.list-empty { padding:60px 20px; text-align:center; color:#8398a9; font-size:13px; }.list-empty p { line-height:1.8; font-size:12px; }
.selection-note { margin:14px 0 0; color:#547d94; font-size:12px; }.refresh-indicator { position:absolute; inset:0; display:grid; place-items:center; background:#ffffffcc; border-radius:inherit; color:#286381; font-size:14px; }
.methodology { padding:18px 22px; }.methodology summary { cursor:pointer; color:#5f7f95; font-size:13px; font-weight:700; }.methodology p { color:#8094a5; font-size:12px; line-height:1.9; margin-bottom:0; }.initial-loading,.denied { padding:60px 25px; color:#67879c; text-align:center; }
@media(max-width:1100px) { .map-list-grid { grid-template-columns:minmax(0,1fr) 250px; } .period-fields { margin-left:0; } }
@media(max-width:900px) { .map-list-grid { grid-template-columns:1fr; height:auto; }.station-list-panel { max-height:450px; }.coverage-stats { grid-template-columns:repeat(2,minmax(0,1fr)); }.coverage-workspace { padding:14px; } }
@media(max-width:600px) { .scheduling-page { gap:14px; }.scheduling-header { padding:20px; }.scheduling-header h2 { font-size:29px; }.read-only-tag { display:none; }.period-panel { padding:16px; gap:16px; }.mode-picker { width:100%; }.mode-picker button { flex:1; min-width:0; }.period-fields { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); width:100%; }.period-fields input,.period-fields select { width:100%; min-width:0; }.query-button { grid-column:1/-1; }.coverage-stats { gap:10px; }.coverage-stats article { padding:17px; }.workspace-header p span { display:block; margin-left:0; }.workspace-filters { display:grid; grid-template-columns:1fr; }.workspace-filters>span { margin-left:0; }.station-search { min-width:0; } }
</style>
