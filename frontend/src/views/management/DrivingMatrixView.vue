<template>
  <div class="road-page">
    <header class="road-hero">
      <div><span class="eyebrow">管理系统 / ROAD NETWORK DATABASE</span><h1>路网数据管理</h1><p>完整采集、定期更新，让智能排班专注于计算。</p></div>
      <span class="readonly">只读数据库 · 独立查看授权</span>
    </header>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="!data && loading" class="surface" role="status">正在读取路网数据库…</p>
    <template v-if="data">
      <section class="road-stats" aria-label="路网概况">
        <article><span>有效站点</span><strong>{{ data.current_station_count }}<small>站</small></strong><p>全部基础档案，不限排班名单</p></article>
        <article><span>已发布站间数据</span><strong>{{ number(data.active?.completed_pairs) }}<small>对</small></strong><p>每对一次采样，双向共用估算</p></article>
        <article><span>最近成功更新</span><strong class="date">{{ date(data.active?.finished_at) }}</strong><p>{{ data.active ? `当前批次 #${data.active.id}` : '等待首次完整采集' }}</p></article>
        <article><span>下次定时更新 · 北京时间</span><strong class="date">{{ date(data.next_refresh_at) }}</strong><p>每周一 09:30 · 自动后台执行</p></article>
      </section>
      <section class="surface collection" aria-label="采集任务状态">
        <div class="section-head"><div><span class="eyebrow">COLLECTION STATUS</span><h2>{{ statusLabel }}</h2></div><span class="status" :class="data.latest?.status">{{ statusText(data.latest?.status) }}</span></div>
        <template v-if="data.latest">
          <div class="progress"><span :style="{ width: progress + '%' }"></span></div>
          <div class="progress-meta"><strong>{{ progress }}%</strong><span>{{ number(data.latest.completed_pairs) }} / {{ number(data.latest.expected_pairs) }} 对</span><span>高德请求 {{ number(data.latest.api_requests) }} 次</span><span>不可达 {{ number(data.latest.unreachable_pairs) }} 对</span></div>
          <p v-if="data.latest.status === 'collecting'">新数据在后台采集，完成后整体发布。{{ data.active ? '排班继续使用上一批完整数据。' : '首次完成后即可读取完整路网。' }}本页每分钟自动同步进度。</p>
          <p v-if="data.latest.last_error" class="error">{{ data.latest.last_error }}</p>
          <p v-if="data.latest.status === 'failed'">后台失败后间隔10分钟有限重试，1小时内最多启动3次；已采集部分保留，旧批次继续可用。</p>
          <p v-if="data.latest.status === 'interrupted'" class="error">采集进程已中断，已完成部分保留；下次任务可续采，不覆盖当前有效数据。</p>
        </template>
        <p v-else>初始化任务尚未启动，部署后由后台任务采集，不会在浏览或排班时调用高德。</p>
        <p v-if="data.registry_changed" class="notice">站点名单或坐标已有调整，当前仍展示上一批采样。新增或变更站点将在下次定时更新后纳入。</p>
        <p v-if="data.invalid_stations.length" class="notice">以下 {{ data.invalid_stations.length }} 个站点缺少有效坐标，尚无法采集：{{ data.invalid_stations.map(s => s.station_name).join('、') }}。</p>
      </section>
      <section class="surface">
        <div class="section-head"><div><span class="eyebrow">STATION PAIRS</span><h2>站间驾车估算明细</h2></div><span class="muted">{{ number(data.total) }} 对 · 仅查看</span></div>
        <form class="filters" @submit.prevent="applyFilters">
          <label>包含站点<select v-model="draft.station"><option value="">全部站点</option><option v-for="s in stations" :key="s.station_id" :value="String(s.station_id)">{{ s.region }} · {{ s.station_name }}</option></select></label>
          <label>另一站点<select v-model="draft.counterpart"><option value="">不限</option><option v-for="s in stations" :key="s.station_id" :value="String(s.station_id)">{{ s.region }} · {{ s.station_name }}</option></select></label>
          <label>路线情况<select v-model="draft.state"><option value="">全部</option><option value="reachable">可通行</option><option value="unreachable">不可达</option></select></label>
          <label>排序<select v-model="draft.sort"><option value="">按站点</option><option value="fastest">用时从短到长</option><option value="slowest">用时从长到短</option></select></label>
          <button type="submit" :disabled="loading">{{ loading ? '查询中…' : '开始查询' }}</button>
        </form>
        <p class="muted rule">采样方向固定为站点 A → 站点 B；排班时不区分往返，共用此估算。未实时调用高德，也不代表实时导航结果。</p>
        <div class="road-table-wrap"><table><thead><tr><th>站点 A</th><th>站点 B</th><th>预计驾车用时</th><th>行驶距离</th><th>情况</th><th>采样时间</th></tr></thead><tbody>
          <tr v-for="item in data.items" :key="`${item.origin_id}:${item.destination_id}`">
            <td data-label="站点 A"><strong>{{ item.origin?.station_name }}</strong><small>{{ item.origin?.region }}</small></td>
            <td data-label="站点 B"><strong>{{ item.destination?.station_name }}</strong><small>{{ item.destination?.region }}</small></td>
            <td data-label="预计驾车用时" class="duration">{{ item.reachable ? `${Math.ceil(item.seconds / 60)} 分钟` : '—' }}</td>
            <td data-label="行驶距离">{{ item.reachable ? `${(item.meters / 1000).toFixed(1)} 公里` : '—' }}</td>
            <td data-label="情况"><span class="status" :class="item.reachable ? 'published' : 'failed'">{{ item.reachable ? '可通行' : '不可达' }}</span></td>
            <td data-label="采样时间">{{ date(item.sampled_at) }}</td>
          </tr>
          <tr v-if="!data.items.length"><td colspan="6" class="empty">{{ data.active ? '没有符合条件的站间数据。' : '首次采集完成后展示明细。' }}</td></tr>
        </tbody></table></div>
        <div class="pagination"><span>第 {{ data.page }} / {{ pages }} 页</span><button :disabled="loading || data.page <= 1" @click="load(data.page - 1)">上一页</button><button :disabled="loading || data.page >= pages" @click="load(data.page + 1)">下一页</button></div>
      </section>
      <details class="surface history"><summary>最近采集任务</summary><article v-for="run in data.runs" :key="run.id"><span>#{{ run.id }} · {{ run.slot === 'initial-v1' ? '首次初始化' : '每周更新' }}</span><span>{{ date(run.started_at) }}</span><strong>{{ statusText(run.status) }}</strong><span>{{ number(run.completed_pairs) }}/{{ number(run.expected_pairs) }} 对 · {{ run.attempts }} 次尝试</span></article></details>
    </template>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import axios from 'axios'
import { createAdaptivePolling } from '@/utils/adaptivePolling'

const data = ref(null), loading = ref(false), error = ref('')
const draft = ref({ station: '', counterpart: '', state: '', sort: '' })
let applied = { ...draft.value }, controller, serial = 0, disposed = false
const stations = computed(() => data.value?.active?.stations || [])
const pages = computed(() => Math.max(1, Math.ceil((data.value?.total || 0) / 30)))
const progress = computed(() => !data.value?.latest ? 0 : data.value.latest.expected_pairs ? Math.min(100, Math.round(data.value.latest.completed_pairs * 100 / data.value.latest.expected_pairs)) : data.value.latest.status === 'published' ? 100 : 0)
const statusText = status => ({ collecting: '正在采集', published: '已发布', failed: '更新失败', interrupted: '已中断' })[status] || '待初始化'
const statusLabel = computed(() => data.value?.latest?.status === 'published' ? '完整路网已就绪，智能排班只读数据库' : statusText(data.value?.latest?.status))
const number = value => Number(value || 0).toLocaleString('zh-CN')
const date = value => value ? new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value)) : '—'
async function load(page = 1, background = false) {
  const ticket = ++serial
  controller?.abort(); controller = new AbortController()
  if (!background) loading.value = true
  error.value = ''
  try {
    const response = await axios.get('/api/management/driving-matrix', { params: { ...applied, page }, signal: controller.signal, timeout: 15000 })
    if (!disposed && ticket === serial) data.value = response.data
  } catch (err) {
    if (!disposed && ticket === serial && err.code !== 'ERR_CANCELED') error.value = err.response?.data?.error || '路网数据读取失败，请稍后重试。'
  } finally { if (ticket === serial) loading.value = false }
}
function applyFilters() { applied = { ...draft.value }; load(1) }
const polling = createAdaptivePolling({ task: () => loading.value ? undefined : load(data.value?.page || 1, true), canRun: () => !document.hidden && navigator.onLine })
function resume() { if (!document.hidden) polling.start({ immediate: true }) }
onMounted(() => { load(); polling.start(); document.addEventListener('visibilitychange', resume); window.addEventListener('online', resume) })
onBeforeUnmount(() => { disposed = true; serial++; controller?.abort(); polling.dispose(); document.removeEventListener('visibilitychange', resume); window.removeEventListener('online', resume) })
</script>
<style scoped>
.road-page { display:grid; gap:20px; color:#19354c; }
.road-hero { display:flex; align-items:center; justify-content:space-between; gap:20px; padding:28px 30px; border-radius:20px; border-bottom:4px solid #dab45d; color:#fff; background:radial-gradient(ellipse at 95% 0,#28788b,transparent 65%),linear-gradient(110deg,#142f4a,#18465f); }
.eyebrow { font-size:11px; font-weight:750; letter-spacing:1.5px; }
.road-hero .eyebrow { color:#a7d6e1; } h1 { margin:10px 0; font-size:30px; } h2 { margin:7px 0; font-size:19px; }
.road-hero p { color:#c3dbe7; margin:0; font-size:13px; }.readonly { padding:9px 13px; border:1px solid #ffffff40; border-radius:9px; font-size:12px; white-space:nowrap; background:#ffffff10; }
.surface { padding:22px; background:#fff; border:1px solid #ccdde8; border-radius:16px; box-shadow:0 8px 25px #173e5906; }.road-stats { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; }.road-stats article { padding:20px; border:1px solid #cadde6; border-top:3px solid #337c91; background:linear-gradient(150deg,#fff,#f1f7fb); border-radius:12px; }.road-stats span { font-size:12px; color:#526c7e; }.road-stats strong { display:block; font-size:30px; margin:12px 0 8px; }.road-stats small { font-size:12px; margin-left:5px; }.road-stats .date { font-size:17px; line-height:1.8; }.road-stats p { margin:0; font-size:11px; color:#5d7889; }
.section-head { display:flex; align-items:center; justify-content:space-between; gap:14px; margin-bottom:18px; }.status { display:inline-flex; padding:5px 9px; border-radius:6px; background:#eaf0f5; color:#526d80; font-size:12px; white-space:nowrap; }.published { color:#1f7158; background:#dbf2e9; }.collecting { background:#e4f2ff; color:#236b9d; }.failed,.interrupted { background:#fff0e9; color:#a3532d; }.progress { height:10px; border-radius:8px; background:#e6eef3; overflow:hidden; }.progress > span { display:block; height:100%; background:linear-gradient(90deg,#236b8b,#42aa9b); transition:width .3s; }.progress-meta { display:flex; flex-wrap:wrap; gap:16px; align-items:center; margin:14px 0; font-size:13px; }.collection p { font-size:13px; line-height:1.8; }.muted { color:#597388; font-size:12px; }.notice { padding:10px 13px; background:#fff8e9; border-radius:7px; color:#87672e; }.error { color:#a14434; padding:12px; border:1px solid #ebc3b7; border-radius:8px; background:#fff1eb; }
.filters { display:flex; flex-wrap:wrap; align-items:end; gap:12px; padding:16px; background:#f0f5f8; border:1px solid #d2e1e9; border-radius:10px; }.filters label { display:grid; gap:7px; font-size:12px; color:#3f6177; }.filters select { min-height:38px; min-width:150px; max-width:100%; border:1px solid #b9cfdd; border-radius:7px; padding:7px 10px; background:#fff; color:#24465f; }.filters button, .pagination button { padding:9px 15px; border:1px solid #b8cdd9; border-radius:7px; background:#fff; color:#264d66; cursor:pointer; font-weight:650; }.filters button { color:#fff; background:#246c88; border-color:#246c88; }.filters button:disabled,.pagination button:disabled { opacity:.5; cursor:default; }.rule { margin:14px 0; line-height:1.7; }
table { width:100%; border-collapse:collapse; font-size:13px; } th { text-align:left; padding:13px; background:#e9f1f6; color:#294e66; border-bottom:1px solid #bcd2df; } td { padding:13px; border-bottom:1px solid #e0e9ef; } td small { display:block; color:#678193; margin-top:6px; font-size:11px; }.duration { font-weight:750; color:#236b75; }.empty { text-align:center; padding:35px; color:#738a99; }.pagination { display:flex; align-items:center; justify-content:flex-end; gap:10px; padding-top:20px; font-size:12px; }.history summary { cursor:pointer; font-size:14px; font-weight:700; }.history article { display:flex; flex-wrap:wrap; gap:16px; padding:14px 0; border-bottom:1px solid #e1eaf0; font-size:12px; }
@media(max-width:1100px) { .road-stats { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media(max-width:700px) { .road-hero { flex-direction:column; align-items:flex-start; padding:20px; }.surface { padding:15px; }.road-stats { gap:8px; }.road-stats article { padding:12px; }.road-stats .date { font-size:14px; }.section-head { align-items:flex-start; flex-wrap:wrap; }.filters { display:grid; grid-template-columns:1fr; }.filters select { width:100%; min-width:0; } table,tbody { display:block; } thead { display:none; } tr { display:block; padding:12px 0; border-bottom:2px solid #d7e4eb; } td { display:flex; align-items:center; justify-content:space-between; gap:8px; padding:8px 0; text-align:right; } td::before { content:attr(data-label); color:#658092; font-size:12px; text-align:left; } td small { display:none; }.pagination { flex-wrap:wrap; }.progress-meta { gap:10px; } }
</style>
