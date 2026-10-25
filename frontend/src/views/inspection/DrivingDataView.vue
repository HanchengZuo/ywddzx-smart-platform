<template>
  <div class="road-page">
    <header class="road-hero">
      <div class="hero-copy">
        <span class="eyebrow">排班系统 / ROAD NETWORK</span>
        <h1>路网数据<span class="readonly">只读</span></h1>
        <p>以驾车用时连接站点，为智能排班提供可查询的路线依据。</p>
      </div>
      <div class="hero-network" aria-label="数据更新方式">
        <svg viewBox="0 0 116 46" fill="none" aria-hidden="true">
          <path d="M8 29H32L50 10H75L94 34H108" stroke="currentColor" stroke-width="2" />
          <path d="M32 29L56 38H84" stroke="currentColor" stroke-opacity=".4" stroke-width="2" />
          <g fill="currentColor">
            <circle cx="8" cy="29" r="4" />
            <circle cx="50" cy="10" r="4" />
            <circle cx="94" cy="34" r="4" />
          </g>
        </svg>
        <div><strong>高德驾车估算</strong><span>每周一 09:30 更新 · 北京时间</span></div>
      </div>
    </header>

    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <div v-if="!data && loading" class="surface initial-loading" role="status">
      <span class="spinner"></span>正在读取路网数据库…
    </div>

    <template v-if="data">
      <section class="road-stats" aria-label="路网概况">
        <article class="stat-primary">
          <span class="stat-label">已发布站间数据<small>STATION PAIRS</small></span
          ><strong>{{ number(data.active?.completed_pairs) }}<small>对</small></strong>
          <p>完整批次发布，排班直接读取</p>
        </article>
        <article>
          <span class="stat-label">有效坐标站点<small>STATIONS</small></span
          ><strong>{{ number(data.current_station_count) }}<small>站</small></strong>
          <p>覆盖全部站点基础档案</p>
        </article>
        <article>
          <span class="stat-label">最近成功更新<small>LAST UPDATED</small></span
          ><strong class="stat-date">{{ date(data.active?.finished_at) }}</strong>
          <p>{{ data.active ? `当前使用批次 #${data.active.id}` : '等待首次完整采集' }}</p>
        </article>
        <article>
          <span class="stat-label">下次自动更新<small>NEXT SYNC</small></span
          ><strong class="stat-date">{{ date(data.next_refresh_at) }}</strong>
          <p>后台定时采集，无需手动刷新</p>
        </article>
      </section>

      <section class="surface collection" aria-label="采集任务状态">
        <div class="collection-overview">
          <div class="collection-title">
            <span class="collection-icon" aria-hidden="true">采</span>
            <div>
              <h2>{{ statusLabel }}</h2>
              <p>
                {{
                  data.active
                    ? '完整路网可用，查询与排班不会实时调用高德。'
                    : '首次完整采集发布后，即可用于现场智能排班。'
                }}
              </p>
            </div>
          </div>
          <span class="status" :class="data.latest?.status"
            ><i></i>{{ statusText(data.latest?.status) }}</span
          >
        </div>
        <template v-if="data.latest">
          <div class="collection-progress">
            <div
              class="progress"
              role="progressbar"
              aria-label="站间数据采集进度"
              :aria-valuenow="progress"
              aria-valuemin="0"
              aria-valuemax="100"
            >
              <span :style="{ width: progress + '%' }"></span>
            </div>
            <strong>{{ progress }}%</strong>
            <span
              >{{ number(data.latest.completed_pairs) }} /
              {{ number(data.latest.expected_pairs) }} 对</span
            >
            <span
              >高德请求 <b>{{ number(data.latest.api_requests) }}</b> 次</span
            >
            <span
              >不可达 <b>{{ number(data.latest.unreachable_pairs) }}</b> 对</span
            >
          </div>
          <p v-if="data.latest.status === 'collecting'" class="collection-note">
            新批次正在后台采集，完成后整体发布。{{
              data.active ? '期间继续使用上一批完整数据。' : ''
            }}本页每分钟自动同步进度。
          </p>
          <p v-if="data.latest.last_error" class="notice error">{{ data.latest.last_error }}</p>
          <p v-if="data.latest.status === 'failed'" class="collection-note">
            后台失败后间隔10分钟有限重试，1小时内最多启动3次；已采集部分保留，旧批次继续可用。
          </p>
          <p v-if="data.latest.status === 'interrupted'" class="notice">
            采集进程已中断，已完成部分保留；下次任务可续采，不覆盖当前有效数据。
          </p>
        </template>
        <p v-else class="collection-note">
          初始化任务尚未启动，部署后由后台任务采集，不会在浏览或排班时调用高德。
        </p>
        <p v-if="data.registry_changed" class="notice">
          站点名单或坐标已有调整，当前仍展示上一批采样。新增或变更站点将在下次定时更新后纳入。
        </p>
        <p v-if="data.invalid_stations.length" class="notice">
          以下 {{ data.invalid_stations.length }} 个站点缺少有效坐标，尚无法采集：{{
            data.invalid_stations.map((s) => s.station_name).join('、')
          }}。
        </p>
      </section>

      <section class="surface road-workbench" aria-label="站间路网查询">
        <div class="workbench-heading">
          <div>
            <span class="eyebrow">ROUTE EXPLORER</span>
            <h2>查询站间路网</h2>
            <p>搜索任一端站名，查看驾车用时与行驶距离。</p>
          </div>
          <span class="dataset-tag">{{
            data.active ? `发布批次 #${data.active.id}` : '等待发布'
          }}</span>
        </div>
        <form class="filters filter-card" @submit.prevent="applyFilters">
          <div class="filter-grid">
            <div class="filter-item station-filter" :data-filter-state="fieldState('keyword')">
              <label for="road-station-search">站点名称</label>
              <div class="search-control">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" stroke-width="1.8" />
                  <path
                    d="m16 16 4 4"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                  />
                </svg>
                <input
                  id="road-station-search"
                  v-model="draft.keyword"
                  type="search"
                  list="road-station-names"
                  maxlength="80"
                  autocomplete="off"
                  placeholder="输入站点名称，如泗砖、乐都"
                />
                <datalist id="road-station-names">
                  <option v-for="s in stations" :key="s.station_id" :value="s.station_name">
                    {{ s.region }}
                  </option>
                </datalist>
              </div>
              <small>匹配任一端站名，支持部分名称</small>
            </div>
            <div class="filter-item" :data-filter-state="fieldState('state')">
              <label for="road-state">路线情况</label>
              <select id="road-state" v-model="draft.state">
                <option value="">全部路线</option>
                <option value="reachable">可通行</option>
                <option value="unreachable">不可达</option>
              </select>
              <small>不可达路线不按零距离处理</small>
            </div>
            <div class="filter-item" :data-filter-state="fieldState('sort')">
              <label for="road-sort">排序方式</label>
              <select id="road-sort" v-model="draft.sort">
                <option value="">默认 · 按站点顺序</option>
                <optgroup label="行车用时">
                  <option value="fastest">用时 · 从短到长</option>
                  <option value="slowest">用时 · 从长到短</option>
                </optgroup>
                <optgroup label="行驶距离">
                  <option value="distance_asc">距离 · 从近到远</option>
                  <option value="distance_desc">距离 · 从远到近</option>
                </optgroup>
              </select>
              <small>用时与距离均为数据库估算值</small>
            </div>
          </div>
          <FilterSummary :fields="filterFields" manual />
          <div class="filter-actions">
            <p>
              {{
                dirty
                  ? '条件已调整，点击开始查询后应用。'
                  : '当前条件已应用；输入站名后也可按回车查询。'
              }}
            </p>
            <button
              class="button secondary"
              type="button"
              :disabled="loading || !canReset"
              @click="resetFilters"
            >
              重置条件</button
            ><button class="button primary" type="submit" :disabled="loading">
              <span v-if="loading" class="spinner"></span>{{ loading ? '正在查询' : '开始查询' }}
            </button>
          </div>
        </form>

        <div class="result-heading">
          <h3>
            站间明细<span>{{ number(data.total) }} <small>对</small></span>
          </h3>
          <span class="result-caption" role="status">{{
            loading ? '正在查询，暂显示上次结果…' : '每分钟自动同步 · 每页30对'
          }}</span>
        </div>
        <div class="road-table-wrap" :aria-busy="loading">
          <table>
            <thead>
              <tr>
                <th class="row-number">序号</th>
                <th>站点 A</th>
                <th>站点 B</th>
                <th>行车用时</th>
                <th>行驶距离</th>
                <th>路线情况</th>
                <th>采样时间</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(item, index) in data.items"
                :key="`${item.origin_id}:${item.destination_id}`"
              >
                <td class="row-number" data-label="序号">{{ (data.page - 1) * 30 + index + 1 }}</td>
                <td data-label="站点 A">
                  <div class="station-name">
                    <strong>{{ item.origin?.station_name }}</strong
                    ><small>{{ item.origin?.region }}</small>
                  </div>
                </td>
                <td data-label="站点 B">
                  <div class="station-name">
                    <strong>{{ item.destination?.station_name }}</strong
                    ><small>{{ item.destination?.region }}</small>
                  </div>
                </td>
                <td data-label="行车用时" class="duration">
                  {{ item.reachable ? `${Math.ceil(item.seconds / 60)} 分钟` : '—' }}
                </td>
                <td data-label="行驶距离" class="distance">
                  {{ item.reachable ? `${(item.meters / 1000).toFixed(1)} 公里` : '—' }}
                </td>
                <td data-label="路线情况">
                  <span class="status" :class="item.reachable ? 'published' : 'failed'"
                    ><i></i>{{ item.reachable ? '可通行' : '不可达' }}</span
                  >
                </td>
                <td data-label="采样时间" class="sample-date">{{ date(item.sampled_at) }}</td>
              </tr>
              <tr v-if="!data.items.length">
                <td colspan="7" class="empty">
                  <strong>{{ data.active ? '未找到匹配的站间路线' : '路网数据尚未发布' }}</strong>
                  <p>
                    {{
                      data.active
                        ? '试试输入更简短的站名，或重置筛选条件。'
                        : '首次完整采集完成后，将在此展示明细。'
                    }}
                  </p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="pagination">
          <p>
            {{
              data.total
                ? `当前展示第 ${rangeStart}–${rangeEnd} 对，共 ${number(data.total)} 对`
                : '暂无查询结果'
            }}
          </p>
          <div>
            <span
              >{{ data.page }} <small>/ {{ pages }} 页</small></span
            ><button
              class="button secondary"
              :disabled="loading || data.page <= 1"
              @click="load(data.page - 1)"
            >
              上一页</button
            ><button
              class="button secondary"
              :disabled="loading || data.page >= pages"
              @click="load(data.page + 1)"
            >
              下一页
            </button>
          </div>
        </div>
        <p class="rule">
          <span aria-hidden="true">i</span
          >每对站点仅采样一个方向，往返共用估算；数据不代表实时导航结果。
        </p>
      </section>

      <details class="surface history">
        <summary>
          <span
            >最近采集记录<small>{{ data.runs.length }} 次记录</small></span
          ><span class="history-toggle" aria-hidden="true"></span>
        </summary>
        <div class="history-list">
          <article v-for="run in data.runs" :key="run.id">
            <div>
              <strong
                >{{ run.slot === 'initial-v1' ? '首次初始化' : '每周更新'
                }}<small>批次 #{{ run.id }}</small></strong
              ><span>{{ date(run.started_at) }}</span>
            </div>
            <span class="status" :class="run.status">{{ statusText(run.status) }}</span>
            <p>
              {{ number(run.completed_pairs) }} / {{ number(run.expected_pairs) }} 对<span
                >{{ run.attempts }} 次尝试</span
              >
            </p>
          </article>
          <p v-if="!data.runs.length" class="collection-note">暂无采集记录</p>
        </div>
      </details>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import axios from 'axios'
import FilterSummary from '@/components/FilterSummary.vue'
import { createAdaptivePolling } from '@/utils/adaptivePolling'

const emptyFilters = () => ({ keyword: '', state: '', sort: '' })
const data = ref(null),
  loading = ref(false),
  error = ref('')
const draft = ref(emptyFilters()),
  applied = ref(emptyFilters())
let controller,
  serial = 0,
  disposed = false
const stations = computed(() => data.value?.active?.stations || [])
const pages = computed(() => Math.max(1, Math.ceil((data.value?.total || 0) / 30)))
const rangeStart = computed(() => (data.value?.items.length ? (data.value.page - 1) * 30 + 1 : 0))
const rangeEnd = computed(() =>
  data.value?.items.length ? rangeStart.value + data.value.items.length - 1 : 0,
)
const progress = computed(() =>
  !data.value?.latest
    ? 0
    : data.value.latest.expected_pairs
      ? Math.min(
          100,
          Math.round((data.value.latest.completed_pairs * 100) / data.value.latest.expected_pairs),
        )
      : data.value.latest.status === 'published'
        ? 100
        : 0,
)
const statusText = (status) =>
  ({ collecting: '正在采集', published: '已发布', failed: '更新失败', interrupted: '已中断' })[
    status
  ] || '待初始化'
const statusLabel = computed(
  () =>
    ({
      published: '完整路网已就绪',
      collecting: '正在采集新批次',
      failed: '本次更新未完成',
      interrupted: '采集任务已中断',
    })[data.value?.latest?.status] || '等待首次采集',
)
const stateLabels = { reachable: '可通行', unreachable: '不可达' }
const sortLabels = {
  fastest: '用时 · 从短到长',
  slowest: '用时 · 从长到短',
  distance_asc: '距离 · 从近到远',
  distance_desc: '距离 · 从远到近',
}
const normalizedDraft = computed(() => ({ ...draft.value, keyword: draft.value.keyword.trim() }))
const filterFields = computed(() =>
  [
    { key: 'keyword', label: '站点名称', format: (value) => value },
    { key: 'state', label: '路线情况', format: (value) => stateLabels[value] },
    { key: 'sort', label: '排序方式', format: (value) => sortLabels[value] },
  ].map((field) => ({
    key: field.key,
    label: field.label,
    value: field.format(normalizedDraft.value[field.key]),
    applied: field.format(applied.value[field.key]),
    changed: normalizedDraft.value[field.key] !== applied.value[field.key],
  })),
)
const dirty = computed(() => filterFields.value.some((field) => field.changed))
const canReset = computed(
  () =>
    Object.values(normalizedDraft.value).some(Boolean) ||
    Object.values(applied.value).some(Boolean),
)
const fieldState = (key) =>
  normalizedDraft.value[key] !== applied.value[key]
    ? 'pending'
    : normalizedDraft.value[key]
      ? 'set'
      : 'empty'
const number = (value) => Number(value || 0).toLocaleString('zh-CN')
const timeFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})
const date = (value) => (value ? timeFormatter.format(new Date(value)) : '—')

async function load(page = 1, background = false, filters = applied.value) {
  const query = { ...filters }
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  if (!background) loading.value = true
  error.value = ''
  try {
    const response = await axios.get('/api/management/driving-matrix', {
      params: { ...query, page },
      signal: controller.signal,
      timeout: 15000,
    })
    if (!disposed && ticket === serial) {
      data.value = response.data
      applied.value = query
    }
  } catch (err) {
    if (!disposed && ticket === serial && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '路网数据读取失败，请稍后重试。'
  } finally {
    if (ticket === serial) loading.value = false
  }
}
function applyFilters() {
  load(1, false, normalizedDraft.value)
}
function resetFilters() {
  draft.value = emptyFilters()
  applyFilters()
}
const polling = createAdaptivePolling({
  task: () => (loading.value ? undefined : load(data.value?.page || 1, true)),
  canRun: () => !document.hidden && navigator.onLine,
})
function resume() {
  if (!document.hidden) polling.start({ immediate: true })
}
onMounted(() => {
  load()
  polling.start()
  document.addEventListener('visibilitychange', resume)
  window.addEventListener('online', resume)
})
onBeforeUnmount(() => {
  disposed = true
  serial++
  controller?.abort()
  polling.dispose()
  document.removeEventListener('visibilitychange', resume)
  window.removeEventListener('online', resume)
})
</script>

<style scoped>
.road-page {
  --road-ink: #203e55;
  --road-muted: #587084;
  --road-line: #cbdce7;
  --road-teal: #1c7180;
  display: grid;
  gap: 20px;
  min-width: 0;
  color: var(--road-ink);
}
.road-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 30px 32px;
  border-radius: 20px;
  border: 1px solid #22566d;
  border-bottom: 4px solid #d3b36a;
  color: #fff;
  background:
    radial-gradient(ellipse at 100% 0, #296f80, transparent 65%),
    linear-gradient(110deg, #14324c, #18475c);
}
.eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.6px;
  color: #39718a;
}
.road-hero .eyebrow {
  color: #b0d7e2;
}
h1 {
  display: flex;
  align-items: center;
  gap: 15px;
  margin: 10px 0 12px;
  font-size: 32px;
  letter-spacing: 1px;
}
h2 {
  margin: 0;
  font-size: 18px;
}
h3 {
  margin: 0;
  font-size: 17px;
}
.hero-copy p {
  margin: 0;
  color: #d5e6ef;
  font-size: 13px;
  line-height: 1.8;
}
.readonly {
  padding: 4px 9px;
  border: 1px solid #8cb8c16b;
  border-radius: 6px;
  background: #ffffff12;
  color: #c8e4e8;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0;
}
.hero-network {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 17px 0 17px 25px;
  border-left: 1px solid #8ac0cd40;
  flex-shrink: 0;
}
.hero-network svg {
  width: 100px;
  color: #75c5ca;
}
.hero-network strong,
.hero-network span {
  display: block;
}
.hero-network strong {
  margin-bottom: 8px;
  font-size: 14px;
}
.hero-network span {
  color: #c3dce5;
  font-size: 12px;
}
.surface {
  padding: 24px;
  background: #fff;
  border: 1px solid var(--road-line);
  border-radius: 16px;
  box-shadow: 0 5px 18px #133e5505;
}
.road-stats {
  display: grid;
  grid-template-columns: 1.05fr 0.85fr 1fr 1fr;
  gap: 14px;
}
.road-stats article {
  min-width: 0;
  position: relative;
  padding: 20px 22px;
  border: 1px solid var(--road-line);
  border-radius: 12px;
  background: #fff;
}
.road-stats article::before {
  content: '';
  display: block;
  position: absolute;
  left: 0;
  top: 21px;
  width: 3px;
  height: 24px;
  background: #6193a7;
  border-radius: 0 3px 3px 0;
}
.road-stats .stat-primary {
  background: linear-gradient(125deg, #e9f5f7, #f8fcfd);
  border-color: #a9cdd3;
}
.road-stats .stat-primary::before {
  background: var(--road-teal);
}
.stat-label {
  display: block;
  font-size: 13px;
  color: #38596e;
  font-weight: 600;
}
.stat-label > small {
  display: block;
  margin-top: 5px;
  color: #7c95a5;
  font-size: 9px;
  letter-spacing: 1px;
  font-weight: 500;
}
.road-stats strong {
  display: block;
  font-size: 32px;
  letter-spacing: -0.5px;
  margin: 12px 0 10px;
}
.road-stats strong > small {
  font-size: 12px;
  margin-left: 6px;
  font-weight: 500;
  letter-spacing: 0;
}
.road-stats .stat-date {
  font-size: 18px;
  letter-spacing: 0;
  line-height: 1.8;
  margin-top: 16px;
}
.road-stats p {
  margin: 0;
  color: var(--road-muted);
  font-size: 12px;
  line-height: 1.7;
}
.collection-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.collection-title {
  display: flex;
  gap: 13px;
  align-items: center;
}
.collection-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border: 1px solid #b9d7df;
  border-radius: 10px;
  background: #eaf5f7;
  color: var(--road-teal);
  font-size: 17px;
  font-weight: 700;
}
.collection-title p {
  margin: 6px 0 0;
  color: var(--road-muted);
  font-size: 12px;
  line-height: 1.7;
}
.status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 5px 9px;
  border: 1px solid #d7e1e9;
  border-radius: 6px;
  background: #f0f4f7;
  color: #5a7182;
  font-size: 12px;
  white-space: nowrap;
}
.status i {
  display: block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.status.published {
  color: #1c7057;
  background: #edf8f1;
  border-color: #c6e2d3;
}
.status.collecting {
  color: #2969a4;
  background: #edf5ff;
  border-color: #c5daef;
}
.status.failed,
.status.interrupted {
  color: #a05932;
  background: #fff5ec;
  border-color: #eed7c3;
}
.collection-progress {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px 18px;
  margin-top: 19px;
  color: var(--road-muted);
  font-size: 12px;
}
.collection-progress > strong {
  color: var(--road-teal);
}
.progress {
  flex: 1 1 100px;
  max-width: 240px;
  height: 7px;
  border-radius: 6px;
  background: #e5eef2;
  overflow: hidden;
}
.progress > span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #277388, #3b9c94);
  transition: width 0.3s;
}
.collection-note {
  margin: 15px 0 0;
  color: var(--road-muted);
  font-size: 12px;
  line-height: 1.8;
}
.notice {
  margin: 15px 0 0;
  padding: 12px 14px;
  border: 1px solid #e7d4ab;
  border-radius: 8px;
  background: #fff9eb;
  color: #826127;
  font-size: 13px;
  line-height: 1.7;
}
.error {
  margin: 0;
  border-color: #e6bfb5;
  background: #fff2ee;
  color: #9b4131;
}
.collection .error {
  margin-top: 15px;
}
.workbench-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.workbench-heading h2 {
  margin: 6px 0 7px;
  font-size: 21px;
}
.workbench-heading p {
  margin: 0;
  color: var(--road-muted);
  font-size: 13px;
}
.dataset-tag {
  padding: 6px 10px;
  border: 1px solid #cbdce5;
  border-radius: 6px;
  background: #f5f8fa;
  color: #537183;
  font-size: 12px;
  white-space: nowrap;
}
.filters {
  border: 1px solid #c2d7e3;
  border-radius: 12px;
  background: #f4f8fb;
  overflow: hidden;
}
.filter-grid {
  display: grid;
  grid-template-columns: 1.6fr 1fr 1.1fr;
  gap: 12px;
  padding: 16px;
}
.filters .filter-item {
  display: grid;
  align-content: start;
  gap: 9px;
  padding: 12px;
  border-color: #d3e0e8;
  background: #fff;
}
.filter-item > label {
  font-size: 13px;
  font-weight: 600;
  color: #345369;
}
.filter-item > small {
  color: #6c8294;
  font-size: 11px;
}
.filter-item select,
.search-control {
  width: 100%;
  height: 42px;
  border: 1px solid #b8cedc;
  border-radius: 8px;
  color: #25465f;
  background: #fff;
  font: inherit;
  font-size: 13px;
  box-sizing: border-box;
}
.filter-item select {
  padding: 0 10px;
}
.search-control {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 11px;
}
.search-control > svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: #5a8095;
}
.search-control input {
  min-width: 0;
  width: 100%;
  height: 100%;
  border: 0;
  outline: 0;
  color: #25465f;
  background: transparent;
  font: inherit;
}
.search-control input::placeholder {
  color: #8798a6;
}
.search-control:focus-within,
.filter-item select:focus-visible {
  outline: 2px solid #2a7c9a;
  outline-offset: 2px;
}
.filters :deep(.filter-summary) {
  margin: 0 16px 16px;
  padding: 12px 14px;
  border-color: #d3e2eb;
  background: #fff;
  border-radius: 8px;
}
.filter-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  border-top: 1px solid #d4e2eb;
  padding: 14px 16px;
  background: #eaf2f7;
}
.filter-actions p {
  flex: 1;
  margin: 0;
  color: #546e82;
  font-size: 12px;
  line-height: 1.7;
}
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 38px;
  padding: 8px 17px;
  border: 1px solid #adc6d5;
  border-radius: 8px;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  transition:
    background 0.15s,
    border-color 0.15s;
}
.button.secondary {
  background: #fff;
  color: #365a72;
}
.button.secondary:hover:not(:disabled) {
  background: #f1f7fa;
  border-color: #7fa6ba;
}
.button.primary {
  background: #1d6a87;
  color: #fff;
  border-color: #1d6a87;
  min-width: 112px;
}
.button.primary:hover:not(:disabled) {
  background: #165571;
  border-color: #165571;
}
.button:focus-visible {
  outline: 2px solid #277c99;
  outline-offset: 3px;
}
.button:disabled {
  opacity: 0.45;
  cursor: default;
}
.result-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  padding: 25px 0 16px;
}
.result-heading h3 {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.result-heading h3 > span {
  font-size: 21px;
  color: #206580;
}
.result-heading small {
  color: var(--road-muted);
  font-size: 12px;
  font-weight: 500;
}
.result-caption {
  color: #6c8293;
  font-size: 12px;
}
.road-table-wrap {
  border: 1px solid #c8d9e5;
  border-radius: 10px;
  overflow: hidden;
}
.road-table-wrap[aria-busy='true'] tbody {
  opacity: 0.5;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th {
  text-align: left;
  padding: 13px 14px;
  background: #e5eff5;
  color: #36566d;
  border-bottom: 1px solid #b9d0df;
  font-size: 12px;
  font-weight: 650;
}
td {
  padding: 15px 14px;
  border-bottom: 1px solid #e1eaf0;
  overflow-wrap: anywhere;
}
tbody tr:last-child td {
  border-bottom: 0;
}
tbody tr:nth-child(even) {
  background: #f8fafc;
}
tbody tr:hover {
  background: #f0f7fa;
}
.row-number {
  width: 56px;
  color: #7990a1;
  text-align: center;
  white-space: nowrap;
}
.station-name strong {
  display: block;
  color: #25475e;
  font-size: 13px;
}
.station-name small {
  display: inline-block;
  margin-top: 6px;
  color: #688294;
  font-size: 11px;
}
.duration {
  color: #24668d;
  font-weight: 700;
  white-space: nowrap;
}
.distance {
  color: #24796e;
  font-weight: 600;
  white-space: nowrap;
}
.sample-date {
  color: #6b8295;
  font-size: 12px;
}
.empty {
  text-align: center;
  padding: 40px 16px;
  color: #637d90;
}
.empty strong {
  font-size: 14px;
}
.empty p {
  font-size: 12px;
  margin: 10px 0 0;
}
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 18px;
}
.pagination p {
  margin: 0;
  color: #627e91;
  font-size: 12px;
}
.pagination > div {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 700;
}
.pagination small {
  color: #7a8d9b;
  font-size: 12px;
  font-weight: 400;
}
.rule {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding-top: 15px;
  margin: 18px 0 0;
  border-top: 1px dashed #d1e0e9;
  color: #688192;
  font-size: 12px;
  line-height: 1.7;
}
.rule > span {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 15px;
  height: 15px;
  margin-top: 2px;
  border: 1px solid #7e9aa9;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
}
.history summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  cursor: pointer;
  list-style: none;
  font-size: 14px;
  font-weight: 600;
}
.history summary::-webkit-details-marker {
  display: none;
}
.history summary small {
  margin-left: 12px;
  color: #7890a0;
  font-size: 12px;
  font-weight: 400;
}
.history-toggle {
  color: #3e718d;
  font-size: 12px;
  font-weight: 500;
}
.history-toggle::after {
  content: '+';
  margin-left: 10px;
}
.history-toggle::before {
  content: '展开查看';
}
.history[open] .history-toggle::before {
  content: '收起记录';
}
.history[open] .history-toggle::after {
  content: '−';
}
.history-list {
  padding-top: 16px;
}
.history-list article {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 15px 0;
  border-top: 1px solid #e0eaf0;
  font-size: 12px;
}
.history-list article > div {
  flex: 1;
}
.history-list article strong {
  display: block;
  margin-bottom: 7px;
  font-size: 13px;
}
.history-list article small {
  margin-left: 10px;
  color: #7c92a2;
  font-weight: 400;
}
.history-list article > div > span {
  color: #6f8696;
}
.history-list p {
  margin: 0;
  color: #4e6e83;
}
.history-list p > span {
  display: block;
  margin-top: 7px;
  text-align: right;
  color: #7d91a0;
}
.initial-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 40px;
  color: #5f7b90;
  font-size: 14px;
}
.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: road-spin 0.8s linear infinite;
}
@keyframes road-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 1150px) {
  .hero-network svg {
    display: none;
  }
  .road-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .station-filter {
    grid-column: 1/-1;
  }
  th,
  td {
    padding: 12px 10px;
  }
}
@media (max-width: 700px) {
  .road-page {
    gap: 14px;
  }
  .road-hero {
    padding: 22px;
    flex-direction: column;
    align-items: flex-start;
    gap: 18px;
  }
  h1 {
    font-size: 29px;
  }
  .hero-network {
    border-left: 0;
    border-top: 1px solid #8ac0cd40;
    padding: 15px 0 0;
    width: 100%;
  }
  .hero-network svg {
    display: block;
    width: 65px;
  }
  .hero-network span {
    font-size: 11px;
  }
  .surface {
    padding: 16px;
  }
  .road-stats {
    gap: 9px;
  }
  .road-stats article {
    padding: 17px 13px;
  }
  .road-stats strong {
    font-size: 29px;
  }
  .road-stats .stat-date {
    font-size: 15px;
  }
  .stat-label {
    font-size: 12px;
  }
  .road-stats p {
    font-size: 11px;
  }
  .collection-overview {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .collection-title h2 {
    font-size: 16px;
  }
  .collection-icon {
    width: 33px;
    height: 33px;
  }
  .collection-progress {
    gap: 10px 13px;
  }
  .progress {
    flex-basis: 75%;
    max-width: none;
  }
  .collection-progress > span {
    font-size: 11px;
  }
  .workbench-heading {
    align-items: flex-start;
  }
  .workbench-heading h2 {
    font-size: 20px;
  }
  .workbench-heading p {
    font-size: 12px;
    line-height: 1.8;
  }
  .dataset-tag {
    padding: 5px 7px;
    font-size: 10px;
  }
  .filter-grid {
    grid-template-columns: 1fr;
    padding: 12px;
    gap: 10px;
  }
  .station-filter {
    grid-column: auto;
  }
  .filters :deep(.filter-summary) {
    margin: 0 12px 12px;
  }
  .filter-item select,
  .search-control {
    height: 44px;
    font-size: 16px;
  }
  .filter-actions {
    padding: 12px;
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .filter-actions p {
    grid-column: 1/-1;
    margin-bottom: 3px;
  }
  .result-heading {
    flex-wrap: wrap;
    gap: 8px;
  }
  .road-table-wrap {
    border: 0;
    border-radius: 0;
  }
  table,
  tbody {
    display: block;
  }
  thead {
    display: none;
  }
  tr {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 10px;
    margin-bottom: 12px;
    padding: 12px;
    border: 1px solid #c8dce7;
    border-radius: 10px;
    background: #fff;
  }
  tbody tr:nth-child(even) {
    background: #f7fafc;
  }
  td {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 10px 0;
    text-align: right;
    font-size: 12px;
  }
  td::before {
    content: attr(data-label);
    color: #718a9c;
    font-size: 11px;
    font-weight: 400;
    text-align: left;
  }
  td.row-number {
    display: none;
  }
  td[data-label='站点 A'],
  td[data-label='站点 B'] {
    grid-column: 1/-1;
  }
  .station-name {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .station-name small {
    margin-top: 0;
    font-size: 10px;
  }
  .station-name strong {
    font-size: 14px;
  }
  td.sample-date {
    grid-column: 1/-1;
    border: 0;
    font-size: 11px;
  }
  .status {
    font-size: 11px;
    padding: 4px 7px;
  }
  .empty {
    grid-column: 1/-1;
    display: block;
    padding: 20px 8px;
  }
  .empty::before {
    display: none;
  }
  .pagination {
    align-items: flex-start;
    flex-wrap: wrap;
    margin-top: 8px;
  }
  .pagination > div {
    width: 100%;
    justify-content: flex-end;
    gap: 8px;
  }
  .pagination .button {
    padding: 7px 12px;
  }
  .history summary small {
    display: none;
  }
  .history-list article {
    flex-wrap: wrap;
    gap: 12px;
  }
  .history-list article > div {
    min-width: 50%;
  }
  .history-list article > p {
    width: 100%;
    display: flex;
    justify-content: space-between;
  }
  .history-list p > span {
    display: inline;
    margin: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation: none;
  }
  .progress > span,
  .button {
    transition: none;
  }
}
</style>
