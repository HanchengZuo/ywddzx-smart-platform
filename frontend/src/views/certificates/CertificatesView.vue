<template>
  <div class="certificate-page">
    <header class="hero">
      <div>
        <span class="eyebrow">证照系统 / CERTIFICATE CENTER</span>
        <h2>{{ title }}</h2>
        <p>{{ description }}</p>
      </div>
      <span class="scope-pill">{{ scopeLabel }}</span>
    </header>
    <p v-if="error" class="error" role="alert">
      {{ error }} <button @click="bootstrap">重试</button>
    </p>
    <div v-if="message" class="toast" role="status">{{ message }}</div>
    <template v-if="mode === 'register'">
      <form v-if="options.scope !== 'none'" class="registration" @submit.prevent="submit">
        <section class="panel entry">
          <div class="section-head">
            <div>
              <span class="step">01 / 基本信息</span>
              <h3>登记站点证照</h3>
            </div>
            <span>同站点、同类型更新为最新版本</span>
          </div>
          <fieldset class="form-grid" :disabled="saving">
            <label class="wide"
              >所属站点<input
                v-if="options.scope === 'station'"
                :value="options.stations[0]?.station_name || '未绑定站点'"
                disabled
                class="fixed-station"
                aria-label="所属站点（本站固定）" />
              <InspectionFilterSelect
                v-else
                v-model="stationLabel"
                :options="stationLabels"
                label="站点（支持名称或拼音）"
            /></label>
            <label
              >证照类型<select v-model="form.certificate_type">
                <option value="">请选择证照类型</option>
                <option
                  v-for="item in options.certificate_types"
                  :key="item.code"
                  :value="item.code"
                >
                  {{ item.name }}
                </option>
              </select></label
            >
            <label
              >是否拥有此类型证照<select v-model="form.is_present" :disabled="currentLoading">
                <option :value="true">有此证照</option>
                <option :value="false">无此证照</option>
              </select></label
            >
            <label v-if="form.is_present"
              >起始日期（选填）<input
                v-model="form.start_date"
                type="date"
                :disabled="currentLoading"
            /></label>
            <label v-if="form.is_present"
              >到期日期（必填）<input
                v-model="form.expiry_date"
                type="date"
                required
                :disabled="currentLoading"
            /></label>
            <label class="wide"
              >备注（选填）<textarea
                v-model="form.remark"
                maxlength="2000"
                rows="3"
                :disabled="currentLoading"
                placeholder="可填写证照补充说明；无此证照时可说明原因。"
              />
            </label>
          </fieldset>
          <p v-if="currentLoading" class="note">正在核对该站点的最新证照版本…</p>
          <p v-else-if="current" class="note">
            已存在第 {{ current.revision }} 版 ·
            {{
              current.is_present ? `到期日期 ${current.expiry_date || '未录入'}` : '已登记无此证照'
            }}。本次保存将覆盖台账展示，旧版本和照片完整保留。
          </p>
          <p v-else-if="currentReady" class="note">
            该站点尚未登记此类型证照。本次保存将建立第一版记录。
          </p>
          <p v-else class="note">
            请选择站点和证照类型。无此证照也会保存一条明确的台账记录，不参与到期提醒。
          </p>
        </section>
        <section class="panel photo-panel">
          <div class="section-head">
            <div>
              <span class="step">02 / 照片与确认</span>
              <h3>{{ form.is_present ? '上传证照图片' : '登记无此证照' }}</h3>
            </div>
            <span v-if="form.is_present" class="required">必传</span>
          </div>
          <InspectionPhotoUpload
            v-if="form.is_present"
            :key="uploadKey"
            v-model="photo"
            id-prefix="certificate"
            label="证照照片"
            :active="mode === 'register'"
            :disabled="saving || currentLoading"
            @notify="notify"
            @busy-change="photoBusy = $event"
          />
          <div v-else class="absence">
            <strong>本次登记：无此类型证照</strong>
            <p>不需要上传图片或填写有效期。以后取得证照后，可再次登记，历史仍可追溯。</p>
          </div>
          <div class="submit-bar">
            <p>保存人和时间由系统自动记录，不提供删除或直接编辑台账操作。</p>
            <button class="primary" :disabled="!canSubmit">
              {{ saving ? '正在保存…' : '确认登记' }}
            </button>
          </div>
        </section>
      </form>
      <p v-else class="panel empty">
        当前账号没有可登记的站点，请联系管理员配置“登记全部站点数据”或核对账号绑定。
      </p>
    </template>
    <template v-else>
      <div class="metrics">
        <article v-for="item in metricCards" :key="item.label">
          <span>{{ item.label }}</span
          ><strong>{{ item.value }}</strong
          ><small>当前账号可见范围</small>
        </article>
      </div>
      <section class="panel filters">
        <div class="section-head">
          <div>
            <span class="step">FILTER / 查询条件</span>
            <h3>{{ mode === 'reminders' ? '查找待提醒站点' : '筛选证照台账' }}</h3>
          </div>
          <span>{{ scopeLabel }}</span>
        </div>
        <form class="filter-grid" @submit.prevent="apply">
          <label
            >关键词<input
              v-model="draft.keyword"
              placeholder="站点、证照名称或备注"
              maxlength="200"
          /></label>
          <label
            >片区 / 单位<select v-model="draft.region">
              <option value="">全部片区</option>
              <option v-for="region in regionOptions" :key="region">{{ region }}</option>
            </select></label
          >
          <label
            >站点<InspectionFilterSelect
              v-model="filterStation"
              :options="stationLabels"
              label="站点"
          /></label>
          <label
            >证照类型<select v-model="draft.certificate_type">
              <option value="">全部证照类型</option>
              <option v-for="type in options.certificate_types" :key="type.code" :value="type.code">
                {{ type.name }}
              </option>
            </select></label
          >
          <label
            >状态<select v-model="draft.status">
              <option value="">全部状态</option>
              <option v-for="key in statusOptions" :key="key" :value="key">
                {{ statusNames[key] }}
              </option>
            </select></label
          >
          <label v-if="mode === 'reminders'" class="check"
            ><input v-model="draft.unread" type="checkbox" />只看未读提醒</label
          >
          <div class="filter-actions">
            <button type="button" @click="reset">重置</button
            ><button class="primary" :disabled="loading">
              {{ loading ? '正在筛选…' : '开始筛选' }}
            </button>
          </div>
        </form>
      </section>
      <section class="panel ledger" :aria-busy="loading">
        <div class="section-head">
          <div>
            <span class="step">{{
              mode === 'reminders' ? 'REMINDERS / 到期提醒' : 'LEDGER / 证照清单'
            }}</span>
            <h3>{{ mode === 'reminders' ? '需要关注的证照' : '站点证照台账' }}</h3>
          </div>
          <div class="ledger-tools">
            <span>筛选结果 {{ total }} 条</span>
            <button
              v-if="mode === 'ledger'"
              class="primary"
              :disabled="!canRegister"
              :title="
                canRegister ? '前往证照登记更新信息' : '当前账号没有证照登记权限，请联系管理员'
              "
              @click="router.push('/certificates/register')"
            >
              更新证照
            </button>
          </div>
        </div>
        <p v-if="mode === 'ledger'" class="note">
          需要更新证照或更正录入信息？点击“更新证照”，在证照登记中选择相同站点和证照类型，重新登记即可替换当前信息；旧照片、有效期和登记记录会保留在历史中。
        </p>
        <p v-if="mode === 'reminders'" class="note">
          已读只消除未读标记，不会移除到期事项；更新证照或进入新的提醒阶段后，会产生新的未读提醒。
        </p>
        <p v-if="loading" class="empty">正在读取证照数据…</p>
        <p v-else-if="!records.length" class="empty">
          当前筛选条件下没有{{ mode === 'reminders' ? '到期提醒' : '证照记录' }}。
        </p>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>站点 / 片区</th>
                <th>证照类型</th>
                <th>证照照片</th>
                <th>有效期</th>
                <th>状态</th>
                <th>最新登记</th>
                <th>记录</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in records"
                :key="row.id"
                :class="{ unread: mode === 'reminders' && row.unread }"
              >
                <td data-label="站点 / 片区">
                  <b>{{ row.station_name }}</b
                  ><small>{{ row.region }}</small>
                </td>
                <td data-label="证照类型">
                  {{ row.certificate_name }}<small v-if="!row.is_present">已明确登记无此证照</small>
                </td>
                <td data-label="证照照片">
                  <button
                    v-if="row.photo_url"
                    class="thumbnail"
                    @click="preview(row.photo_url, row.certificate_name)"
                  >
                    <img :src="row.photo_url" :alt="row.certificate_name" loading="lazy" /></button
                  ><span v-else class="muted">{{
                    row.is_present ? '历史记录未上传' : '无此证照'
                  }}</span>
                </td>
                <td data-label="有效期">
                  {{
                    row.is_present
                      ? `${row.start_date || '起始未录入'} 至 ${row.expiry_date || '未录入'}`
                      : '不适用'
                  }}
                </td>
                <td data-label="状态">
                  <span :class="['badge', row.status]">{{
                    statusNames[row.status] || row.status
                  }}</span
                  ><small v-if="row.days_remaining !== null && row.is_present">{{
                    row.days_remaining < 0
                      ? `已过期 ${-row.days_remaining} 天`
                      : `距到期 ${row.days_remaining} 天`
                  }}</small
                  ><span v-if="mode === 'reminders' && row.unread" class="unread-label">未读</span>
                </td>
                <td data-label="最新登记">
                  <b>第 {{ row.revision }} 版</b><small>{{ row.updated_at }}</small>
                </td>
                <td data-label="记录">
                  <div class="row-actions">
                    <button @click="showHistory(row)">查看历史</button
                    ><button
                      v-if="mode === 'reminders' && row.unread"
                      :disabled="reading.has(row.id)"
                      @click="markRead(row)"
                    >
                      标为已读
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <footer class="pagination">
          <span>每页 {{ pageSize }} 条 · 共 {{ pages }} 页</span>
          <div>
            <button :disabled="page <= 1 || loading" @click="load(page - 1)">上一页</button
            ><b>{{ page }} / {{ pages }}</b
            ><button :disabled="page >= pages || loading" @click="load(page + 1)">下一页</button>
          </div>
        </footer>
      </section>
      <section v-if="mode === 'reminders'" class="panel">
        <div class="section-head">
          <div>
            <span class="step">TYPES / 证件类型</span>
            <h3>证照录入与提醒覆盖</h3>
          </div>
          <span>沿用系统既有提醒规则</span>
        </div>
        <div class="type-grid">
          <article v-for="type in options.certificate_types" :key="type.code">
            <h4>{{ type.name }}</h4>
            <p>{{ type.rule }}</p>
            <div>
              <span>已录入 {{ typeCount(type.code).recorded || 0 }}</span
              ><span>无此证照 {{ typeCount(type.code).absent || 0 }}</span
              ><b>需提醒 {{ typeCount(type.code).due || 0 }}</b>
            </div>
          </article>
        </div>
      </section>
    </template>
    <Teleport to="body"
      ><dialog ref="historyDialog" class="history-dialog" @cancel.prevent="historyDialog.close()">
        <header>
          <div>
            <span class="step">证照历史</span>
            <h3>{{ historyTitle }}</h3>
          </div>
          <button aria-label="关闭证照历史" @click="historyDialog.close()">×</button>
        </header>
        <div class="history-body">
          <p v-if="historyLoading">正在加载历史记录…</p>
          <p v-if="historyError" class="error">{{ historyError }}</p>
          <article v-for="row in historyRows" :key="row.id">
            <div class="history-meta">
              <b>第 {{ row.revision }} 版 · {{ row.action }}</b
              ><small>{{ row.created_at }} · {{ row.actor_name || '历史保存人未记录' }}</small>
            </div>
            <div class="history-content">
              <button
                v-if="row.photo_url"
                class="history-photo"
                @click="preview(row.photo_url, historyTitle)"
              >
                <img :src="row.photo_url" alt="历史证照照片" loading="lazy" />
              </button>
              <p v-else class="muted">{{ row.is_present ? '历史记录未上传照片' : '无此证照' }}</p>
              <div>
                <p>
                  {{
                    row.is_present
                      ? `有效期：${row.start_date || '起始未录入'} 至 ${row.expiry_date || '未录入'}`
                      : '已登记无此类型证照'
                  }}
                </p>
                <p>{{ row.remark || '无备注' }}</p>
              </div>
            </div>
          </article>
        </div>
      </dialog></Teleport
    >
    <InspectionPhotoPreview
      v-if="previewUrl"
      :url="previewUrl"
      :title="previewTitle"
      :target="historyDialog?.open ? historyDialog : undefined"
      @close="previewUrl = ''"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import InspectionFilterSelect from '@/components/InspectionFilterSelect.vue'
import InspectionPhotoUpload from '@/components/InspectionPhotoUpload.vue'
import InspectionPhotoPreview from '@/components/InspectionPhotoPreview.vue'
const props = defineProps({ mode: { type: String, default: 'ledger' } })
const router = useRouter()
const options = ref({
  stations: [],
  certificate_types: [],
  scope: '',
  view_scope: '',
  register_scope: '',
})
const title = computed(
  () => ({ register: '证照登记', ledger: '证照台账', reminders: '证照提醒' })[props.mode],
)
const description = computed(
  () =>
    ({
      register: '一次登记，更新当前台账；旧照片、旧时间和操作人完整留痕。',
      ledger: '以站点为中心核对证照照片、有效期与历次登记记录。',
      reminders: '集中查看推荐提醒、法定提醒和过期事项，区分已读与未读。',
    })[props.mode],
)
const scopeLabel = computed(
  () =>
    ({ all: '全部站点', station: '本站数据', region: '管辖片区站点', none: '暂无数据权限' })[
      options.value.scope
    ] || '正在读取范围',
)
const error = ref(''),
  message = ref(''),
  saving = ref(false),
  loading = ref(false),
  currentLoading = ref(false),
  currentReady = ref(false),
  photoBusy = ref(false)
const photo = ref(null),
  uploadKey = ref(0),
  stationLabel = ref(''),
  current = ref(null)
const form = reactive({
  certificate_type: '',
  is_present: true,
  start_date: '',
  expiry_date: '',
  remark: '',
})
const stationLabels = computed(() =>
  options.value.stations.map((s) => `${s.region || '未填写片区'} / ${s.station_name}`),
)
const canRegister = computed(() =>
  ['all', 'region', 'station'].includes(options.value.register_scope),
)
const findStation = (label) =>
  options.value.stations.find((s, i) => stationLabels.value[i] === label)
const stationId = computed(() => findStation(stationLabel.value)?.id || '')
const draft = reactive({
    keyword: '',
    region: '',
    certificate_type: '',
    status: '',
    unread: false,
  }),
  filterStation = ref(''),
  applied = ref({})
const records = ref([]),
  total = ref(0),
  page = ref(1),
  pageSize = 20,
  summary = ref({}),
  typeSummary = ref([])
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const regionOptions = computed(() => [
  ...new Set(options.value.stations.map((s) => s.region).filter(Boolean)),
])
const statusNames = {
  normal: '正常',
  recommended: '推荐提醒期',
  legal: '法定提醒期',
  expired: '已过期',
  absent: '无此证照',
  undated: '有效期未录入',
}
const statusOptions = computed(() =>
  props.mode === 'reminders' ? ['recommended', 'legal', 'expired'] : Object.keys(statusNames),
)
const metricCards = computed(() => [
  { label: '已登记证照', value: summary.value.total || 0 },
  { label: '需要到期提醒', value: summary.value.due || 0 },
  { label: '已过期', value: summary.value.expired || 0 },
  { label: '未读提醒', value: summary.value.unread || 0 },
])
const canSubmit = computed(
  () =>
    stationId.value &&
    form.certificate_type &&
    currentReady.value &&
    !currentLoading.value &&
    !saving.value &&
    !photoBusy.value &&
    (!form.is_present || (photo.value && form.expiry_date)),
)
const historyDialog = ref(null),
  reading = ref(new Set()),
  historyRows = ref([]),
  historyTitle = ref(''),
  historyLoading = ref(false),
  historyError = ref(''),
  previewUrl = ref(''),
  previewTitle = ref('')
let alive = true,
  serial = 0,
  currentSerial = 0,
  bootstrapSerial = 0,
  historySerial = 0,
  controller,
  timer
function notify(text) {
  message.value = text
  clearTimeout(timer)
  timer = setTimeout(() => {
    if (alive) message.value = ''
  }, 5000)
}
function announce() {
  window.dispatchEvent(new CustomEvent('certificates-updated'))
}
function preview(url, name) {
  previewUrl.value = url
  previewTitle.value = name
}
const typeCount = (code) => typeSummary.value.find((t) => t.certificate_type === code) || {}
async function bootstrap() {
  const token = ++bootstrapSerial
  error.value = ''
  records.value = []
  summary.value = {}
  typeSummary.value = []
  serial++
  controller?.abort()
  currentSerial++
  currentReady.value = false
  current.value = null
  photo.value = null
  uploadKey.value++
  stationLabel.value = ''
  form.certificate_type = ''
  filterStation.value = ''
  Object.keys(draft).forEach((key) => {
    draft[key] = key === 'unread' ? false : ''
  })
  applied.value = {}
  try {
    const r = await axios.get('/api/station-certificates/options', {
      params: { purpose: props.mode === 'register' ? 'register' : 'view' },
    })
    if (!alive || token !== bootstrapSerial) return
    options.value = r.data
    if (props.mode === 'register' && r.data.stations.length === 1)
      stationLabel.value = stationLabels.value[0]
    if (props.mode !== 'register') await load(1)
  } catch (e) {
    if (alive && token === bootstrapSerial)
      error.value = e.response?.data?.error || '证照数据读取失败。'
  }
}
async function load(target = 1) {
  const token = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const r = await axios.get('/api/station-certificates', {
      params: { ...applied.value, mode: props.mode, page: target, page_size: pageSize },
      signal: controller.signal,
    })
    if (!alive || token !== serial) return
    records.value = r.data.records
    total.value = r.data.total
    summary.value = r.data.summary
    typeSummary.value = r.data.type_summary
    page.value = target
  } catch (e) {
    if (alive && token === serial && !axios.isCancel(e))
      error.value = e.response?.data?.error || '证照清单读取失败。'
  } finally {
    if (alive && token === serial) loading.value = false
  }
}
function apply() {
  if (filterStation.value && !findStation(filterStation.value)) {
    error.value = '请从搜索结果中选择站点。'
    return
  }
  applied.value = { ...draft, station_id: findStation(filterStation.value)?.id || '' }
  load(1)
}
function reset() {
  Object.keys(draft).forEach((key) => {
    draft[key] = key === 'unread' ? false : ''
  })
  filterStation.value = ''
  applied.value = {}
  load(1)
}
async function loadCurrent() {
  const token = ++currentSerial
  currentReady.value = false
  current.value = null
  photo.value = null
  uploadKey.value++
  Object.assign(form, { is_present: true, start_date: '', expiry_date: '', remark: '' })
  error.value = ''
  if (!stationId.value || !form.certificate_type) {
    currentLoading.value = false
    return
  }
  currentLoading.value = true
  try {
    const r = await axios.get('/api/station-certificates/current', {
      params: { station_id: stationId.value, certificate_type: form.certificate_type },
    })
    if (!alive || token !== currentSerial) return
    current.value = r.data.record
    currentReady.value = true
    if (r.data.record)
      Object.assign(form, {
        is_present: r.data.record.is_present,
        start_date: r.data.record.start_date || '',
        expiry_date: r.data.record.expiry_date || '',
        remark: r.data.record.remark || '',
      })
  } catch (e) {
    if (alive && token === currentSerial)
      error.value = e.response?.data?.error || '当前版本读取失败，请重新选择后重试。'
  } finally {
    if (alive && token === currentSerial) currentLoading.value = false
  }
}
async function submit() {
  if (!canSubmit.value) return
  const token = bootstrapSerial
  saving.value = true
  error.value = ''
  const body = new FormData()
  body.append('station_id', stationId.value)
  body.append('revision', current.value?.revision || 0)
  Object.entries(form).forEach(([key, value]) => body.append(key, String(value)))
  if (form.is_present && photo.value) body.append('photo', photo.value)
  try {
    await axios.post('/api/station-certificates', body)
    announce()
    if (!alive || token !== bootstrapSerial) return
    notify('登记成功，当前台账已更新，历史记录已保留。')
    await loadCurrent()
  } catch (e) {
    if (!alive || token !== bootstrapSerial) return
    const reason = e.response?.data?.error || '登记失败，请重试。'
    if (e.response?.status === 409) await loadCurrent()
    error.value = reason
  } finally {
    if (alive) saving.value = false
  }
}
async function markRead(row) {
  if (!row.unread || reading.value.has(row.id)) return
  reading.value.add(row.id)
  try {
    await axios.post(`/api/station-certificates/${row.id}/read`, {
      revision: row.revision,
      status: row.status,
    })
    row.unread = false
    summary.value.unread = Math.max(0, summary.value.unread - 1)
    announce()
    if (applied.value.unread)
      load(records.value.length === 1 ? Math.max(1, page.value - 1) : page.value)
  } catch (e) {
    error.value = e.response?.data?.error || '已读状态保存失败。'
  } finally {
    reading.value.delete(row.id)
  }
}
async function showHistory(row) {
  const token = ++historySerial
  historyTitle.value = `${row.station_name} · ${row.certificate_name}`
  historyRows.value = []
  historyLoading.value = true
  historyError.value = ''
  await nextTick()
  if (!alive) return
  if (!historyDialog.value.open) historyDialog.value.showModal()
  try {
    const r = await axios.get(`/api/station-certificates/${row.id}/history`)
    if (alive && token === historySerial) historyRows.value = r.data.records
  } catch (e) {
    if (alive && token === historySerial)
      historyError.value = e.response?.data?.error || '历史记录读取失败。'
  } finally {
    if (alive && token === historySerial) historyLoading.value = false
  }
}
watch(
  () => [stationId.value, form.certificate_type],
  () => {
    if (props.mode === 'register') loadCurrent()
  },
)
watch(() => props.mode, bootstrap, { immediate: true })
watch(
  () => form.is_present,
  () => {
    photoBusy.value = false
  },
)
onBeforeUnmount(() => {
  alive = false
  serial++
  currentSerial++
  bootstrapSerial++
  controller?.abort()
  clearTimeout(timer)
  historyDialog.value?.close()
})
</script>

<style scoped>
.certificate-page {
  display: grid;
  gap: 22px;
  color: #203e55;
}
* {
  box-sizing: border-box;
}
button,
input,
select,
textarea {
  font: inherit;
}
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
button {
  cursor: pointer;
  border: 1px solid #b9cedd;
  border-radius: 9px;
  padding: 10px 15px;
  background: white;
  color: #285773;
  font-weight: 600;
}
button:disabled {
  opacity: 0.45;
  cursor: default;
}
button:hover:not(:disabled) {
  background: #edf5fa;
}
button.primary {
  background: #237794;
  color: white;
  border-color: #237794;
}
button.primary:hover:not(:disabled) {
  background: #195e78;
  border-color: #195e78;
}
button:focus-visible {
  outline: 3px solid #68b4d0;
  outline-offset: 2px;
}
.fixed-station:disabled {
  background: #edf2f6;
  color: #486174;
  border-color: #d4dfe7;
  opacity: 1;
  cursor: not-allowed;
  -webkit-text-fill-color: #486174;
}
.ledger-tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 14px;
  color: #71879a;
  font-size: 13px;
}
.hero {
  padding: 30px;
  background: linear-gradient(110deg, #123653, #246d7d);
  border-radius: 22px;
  border-bottom: 4px solid #d9ae50;
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.eyebrow,
.step {
  font-size: 12px;
  letter-spacing: 1px;
  font-weight: 700;
}
.eyebrow {
  color: #b9e1e9;
}
h2 {
  font-size: 30px;
  margin: 12px 0;
}
.hero p {
  color: #d5e6ee;
  margin: 0;
  line-height: 1.7;
}
.scope-pill {
  padding: 10px 14px;
  border: 1px solid #ffffff45;
  border-radius: 10px;
  background: #ffffff15;
  white-space: nowrap;
  font-size: 13px;
}
.panel {
  padding: 24px;
  border: 1px solid #d3e0ea;
  border-radius: 18px;
  background: white;
  box-shadow: 0 7px 24px #20475c09;
}
.section-head {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 22px;
}
.section-head > span {
  color: #71879a;
  font-size: 12px;
}
.step {
  color: #347e94;
}
h3 {
  margin: 8px 0 0;
  font-size: 20px;
}
.registration {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr);
  gap: 22px;
  align-items: start;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
label {
  display: grid;
  gap: 9px;
  font-size: 14px;
  font-weight: 600;
}
.wide {
  grid-column: 1 / -1;
}
input,
select,
textarea {
  min-width: 0;
  max-width: 100%;
  width: 100%;
  color: #24465d;
  border: 1px solid #becfdd;
  border-radius: 9px;
  padding: 11px;
  background: white;
}
.note {
  padding: 12px 15px;
  background: #edf5f9;
  border-radius: 9px;
  color: #4d6e84;
  font-size: 13px;
  line-height: 1.8;
  margin: 18px 0 0;
}
.required {
  color: #af3c32 !important;
  background: #fff0ec;
  padding: 5px 9px;
  border-radius: 7px;
}
.absence {
  background: #edf4fa;
  border: 1px dashed #a8c2d5;
  padding: 36px 22px;
  border-radius: 12px;
  line-height: 1.8;
}
.submit-bar {
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px solid #d6e3eb;
  display: flex;
  align-items: center;
  gap: 16px;
  justify-content: space-between;
}
.submit-bar p {
  font-size: 12px;
  color: #6a8092;
  line-height: 1.8;
}
.submit-bar button {
  flex-shrink: 0;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.metrics article {
  border: 1px solid #cddfea;
  background: linear-gradient(130deg, #fff, #eff6fa);
  border-radius: 14px;
  padding: 20px;
}
.metrics span,
.metrics small {
  display: block;
  color: #607e92;
  font-size: 13px;
}
.metrics strong {
  display: block;
  font-size: 30px;
  margin: 10px 0;
  color: #1f5e7d;
}
.metrics small {
  font-size: 11px;
}
.filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.filter-actions {
  display: flex;
  gap: 10px;
  align-items: end;
  justify-content: flex-end;
}
.check {
  display: flex;
  align-items: center;
}
.check input {
  width: auto;
}
.table-wrap {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th {
  text-align: left;
  background: #e9f2f8;
  color: #285575;
  padding: 15px 12px;
}
td {
  border-bottom: 1px solid #e1eaf0;
  padding: 16px 12px;
  line-height: 1.7;
}
td small {
  display: block;
  color: #71879a;
  font-size: 12px;
  margin-top: 6px;
}
.thumbnail {
  padding: 3px;
  border-color: #d9e4ec;
}
.thumbnail img {
  width: 85px;
  height: 68px;
  object-fit: contain;
  display: block;
}
.badge {
  display: inline-block;
  padding: 4px 9px;
  border-radius: 6px;
  background: #e9f1f7;
  color: #4e6e84;
  white-space: nowrap;
}
.badge.normal {
  background: #e4f4ec;
  color: #217259;
}
.badge.recommended {
  background: #fff3ce;
  color: #956823;
}
.badge.legal {
  background: #ffead8;
  color: #ae5922;
}
.badge.expired {
  background: #ffe4df;
  color: #b44232;
}
.unread {
  background: #fffcf2;
}
.unread-label {
  display: inline-block;
  font-size: 11px;
  margin-left: 8px;
  color: #c04a34;
}
.row-actions {
  display: flex;
  flex-direction: column;
  align-items: start;
  gap: 8px;
}
.row-actions button {
  padding: 6px 10px;
  font-size: 12px;
  white-space: nowrap;
}
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding-top: 20px;
  color: #668196;
  font-size: 13px;
}
.pagination > div {
  display: flex;
  align-items: center;
  gap: 12px;
}
.type-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.type-grid article {
  border: 1px solid #d4e2ec;
  padding: 18px;
  border-radius: 12px;
  background: #f8fbfd;
}
.type-grid h4 {
  margin: 0;
}
.type-grid p {
  line-height: 1.8;
  color: #647e91;
  font-size: 13px;
}
.type-grid article > div {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #30738c;
}
.error {
  padding: 15px;
  border-radius: 10px;
  background: #ffefea;
  color: #a43c30;
  line-height: 1.8;
}
.empty {
  padding: 40px 20px;
  text-align: center;
  color: #71879a;
}
.muted {
  color: #8799a8;
  font-size: 12px;
}
.toast {
  position: fixed;
  top: 90px;
  left: 50%;
  transform: translateX(-50%);
  max-width: calc(100vw - 30px);
  background: #176d60;
  color: white;
  border-radius: 12px;
  padding: 15px 22px;
  z-index: 3500;
  box-shadow: 0 10px 30px #153d6030;
}
.history-dialog {
  width: min(900px, calc(100vw - 28px));
  max-height: 88dvh;
  border: 1px solid #bed1df;
  border-radius: 18px;
  padding: 0;
  color: #28465c;
}
.history-dialog::backdrop {
  background: #12314977;
}
.history-dialog[open] {
  display: flex;
  flex-direction: column;
}
.history-dialog header {
  padding: 22px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #eef5fa;
  flex-shrink: 0;
  border-bottom: 1px solid #d5e2eb;
}
.history-dialog header button {
  font-size: 22px;
  padding: 4px 11px;
}
.history-body {
  overflow: auto;
  padding: 22px;
}
.history-body > article {
  padding: 18px;
  border: 1px solid #cedfe9;
  border-left: 4px solid #36859a;
  border-radius: 12px;
  margin-bottom: 16px;
}
.history-meta small {
  display: block;
  margin-top: 8px;
  color: #6a8396;
}
.history-content {
  display: flex;
  gap: 20px;
  align-items: center;
  padding-top: 15px;
}
.history-photo {
  padding: 4px;
}
.history-photo img {
  width: 150px;
  height: 110px;
  object-fit: contain;
  display: block;
}
.history-content p {
  overflow-wrap: anywhere;
  line-height: 1.8;
}
@media (max-width: 1100px) {
  .registration {
    grid-template-columns: 1fr;
  }
  .type-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 700px) {
  .hero {
    padding: 24px 20px;
    flex-direction: column;
    align-items: start;
  }
  h2 {
    font-size: 27px;
  }
  .panel {
    padding: 18px;
  }
  .metrics {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
  .metrics article {
    padding: 15px;
  }
  .filter-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }
  .section-head {
    align-items: start;
    flex-direction: column;
    gap: 8px;
  }
  .type-grid {
    grid-template-columns: 1fr;
  }
  .table-wrap {
    overflow: visible;
  }
  table,
  tbody {
    display: block;
  }
  thead {
    display: none;
  }
  tr {
    display: block;
    margin: 15px 0;
    border: 1px solid #d2e2eb;
    border-radius: 12px;
    padding: 12px;
  }
  td {
    display: grid;
    grid-template-columns: 95px minmax(0, 1fr);
    align-items: start;
    padding: 9px 0;
  }
  td::before {
    content: attr(data-label);
    color: #6e8799;
    font-size: 12px;
  }
  td > small {
    grid-column: 2;
  }
  .row-actions {
    flex-direction: row;
    flex-wrap: wrap;
  }
  .pagination {
    flex-wrap: wrap;
  }
  .pagination > div {
    margin-left: auto;
  }
  .submit-bar {
    flex-direction: column;
    align-items: stretch;
  }
  .history-content {
    align-items: start;
    flex-direction: column;
  }
  input,
  select,
  textarea {
    font-size: 16px;
  }
}
</style>
