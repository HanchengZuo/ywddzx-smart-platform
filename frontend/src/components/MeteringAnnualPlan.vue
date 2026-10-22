<template>
  <button type="button" class="plan-trigger" @click="open">计量年度计划</button>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="metering-plan-dialog"
      aria-labelledby="metering-plan-title"
      @cancel.prevent="close"
      @click="backdrop"
    >
      <header>
        <div>
          <small>年度目标 / MONTHLY TARGETS</small>
          <h3 id="metering-plan-title">计量年度计划</h3>
        </div>
        <button type="button" :disabled="saving" aria-label="关闭计量计划" @click="close">×</button>
      </header>
      <div class="plan-body">
        <p class="plan-note">
          按月设置片区应完成的计量现场站数。同站全年只需覆盖一次；自动排班优先补足当月配额，再回到季度现场覆盖均衡。年度视频仅适用于监控未运行站点。
        </p>
        <div class="plan-controls">
          <label
            >计划年份
            <select
              v-model.number="year"
              :disabled="saving || loading || dirty"
              @change="load(true)"
            >
              <option v-for="y in years" :key="y" :value="y">{{ y }}年</option>
            </select></label
          ><span>{{ state?.can_edit ? '全局共享 · 可维护' : '只读查看' }}</span>
        </div>
        <div class="month-tabs" aria-label="选择计划月份">
          <button
            v-for="m in 12"
            :key="m"
            type="button"
            :aria-pressed="month === m"
            :disabled="saving || loading"
            @click="selectMonth(m)"
          >
            {{ m }}月<small v-if="monthTotal(m)">{{ monthTotal(m) }}站</small>
          </button>
        </div>
        <p v-if="loading" role="status">正在核对计划及计量巡检实绩…</p>
        <p v-if="error" class="plan-error" role="alert">{{ error }}</p>
        <template v-if="state">
          <div class="plan-summary">
            <strong>{{ year }}年{{ month }}月</strong
            ><span
              >计划 <b>{{ monthTotal(month) }}</b
              >站</span
            ><span
              >已查 <b>{{ total('completed') }}</b
              >站</span
            ><span
              >预留 <b>{{ total('reserved') }}</b
              >站</span
            >
          </div>
          <div class="region-targets">
            <article v-for="r in state.regions" :key="r.region">
              <div>
                <strong>{{ r.region }}</strong
                ><small>纳入 {{ r.total }}站 · 全年已配置 {{ annualTotal(r.region) }}站</small>
              </div>
              <label
                >{{ month }}月目标<input
                  :value="quotas[String(month)]?.[r.region] || 0"
                  type="number"
                  min="0"
                  :max="r.total"
                  step="1"
                  :aria-label="`${r.region}${month}月计划站数`"
                  :disabled="!state.can_edit || loading || saving || !!error"
                  @input="setQuota(r.region, $event.target.value)"
              /></label>
              <p>
                实际完成 <b>{{ r.completed }}</b> · 已排预留 <b>{{ r.reserved }}</b> · 尚需派站
                <b>{{
                  Math.max(
                    0,
                    Number(quotas[String(month)]?.[r.region] || 0) - r.completed - r.reserved,
                  )
                }}</b>
              </p>
            </article>
          </div>
          <p class="plan-note">
            实际完成以所选月份任一适用计量检查项的巡检记录为准（现场，或监控未运行站点的视频），未审核也计数，同站去重。今日及未来计量计划只作预留，过期未完成释放预留。配置不自动撤销原有派工；每片区全年目标合计不超过已纳入站点数。灰色年度视频格不参与排班。
          </p>
          <small class="saved-by">{{
            state.updated_at
              ? `最后保存：${state.updated_by_name} · ${state.updated_at}`
              : '尚未配置，默认不追加年度计量任务。'
          }}</small>
        </template>
      </div>
      <footer>
        <span>{{ dirty ? '有未保存的修改' : '配置保存后全局生效' }}</span
        ><button type="button" :disabled="saving" @click="close">关闭</button
        ><button
          v-if="state?.can_edit"
          type="button"
          class="primary"
          :disabled="loading || saving || !dirty || !!error"
          @click="save"
        >
          {{ saving ? '保存中…' : '保存年度计划' }}
        </button>
      </footer>
    </dialog>
  </Teleport>
</template>

<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, ref } from 'vue'
import { currentCoveragePeriod } from '@/utils/schedulingCoverage'
const emit = defineEmits(['saved'])
const current = currentCoveragePeriod()
const dialog = ref(null),
  state = ref(null),
  quotas = ref({}),
  baselineRevision = ref(0),
  original = ref('{}')
const year = ref(current.year),
  month = ref(current.month),
  loading = ref(false),
  saving = ref(false),
  error = ref('')
const years = Array.from({ length: 101 }, (_, i) => 2100 - i)
const dirty = computed(() => JSON.stringify(quotas.value) !== original.value)
let controller,
  serial = 0
const monthTotal = (m) =>
  Object.values(quotas.value[String(m)] || {}).reduce((a, n) => a + Number(n || 0), 0)
const annualTotal = (region) =>
  Object.values(quotas.value).reduce((a, items) => a + Number(items[region] || 0), 0)
const total = (key) => (state.value?.regions || []).reduce((a, r) => a + r[key], 0)
function setQuota(region, value) {
  const key = String(month.value)
  quotas.value[key] ||= {}
  quotas.value[key][region] = value === '' ? 0 : Number(value)
}
function open() {
  dialog.value.showModal()
  load(true)
}
function selectMonth(value) {
  month.value = value
  load(false)
}
function close() {
  if (saving.value || (dirty.value && !window.confirm('尚有未保存的年度计划，确定放弃修改？')))
    return
  serial++
  controller?.abort()
  loading.value = false
  dialog.value.close()
}
function backdrop(event) {
  if (event.target !== dialog.value) return
  const r = dialog.value.getBoundingClientRect()
  if (
    event.clientX < r.left ||
    event.clientX > r.right ||
    event.clientY < r.top ||
    event.clientY > r.bottom
  )
    close()
}
async function load(reset) {
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get('/api/inspection-schedule/metering-plan', {
      params: { year: year.value, month: month.value },
      signal: controller.signal,
      timeout: 20000,
    })
    if (ticket !== serial) return
    state.value = data
    if (reset || !dirty.value) {
      quotas.value = JSON.parse(JSON.stringify(data.quotas))
      original.value = JSON.stringify(quotas.value)
      baselineRevision.value = data.revision
    }
  } catch (err) {
    if (ticket === serial && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '计量计划读取失败，请关闭后重试。'
  } finally {
    if (ticket === serial) loading.value = false
  }
}
async function save() {
  saving.value = true
  error.value = ''
  try {
    const { data } = await axios.put(
      '/api/inspection-schedule/metering-plan',
      {
        year: year.value,
        month: month.value,
        quotas: quotas.value,
        revision: baselineRevision.value,
      },
      { timeout: 20000 },
    )
    state.value = data
    quotas.value = JSON.parse(JSON.stringify(data.quotas))
    original.value = JSON.stringify(quotas.value)
    baselineRevision.value = data.revision
    emit('saved')
    window.dispatchEvent(new Event('inspection-schedule-plan-changed'))
  } catch (err) {
    error.value = err.response?.data?.error || '计划未保存，请核对后重试。'
  } finally {
    saving.value = false
  }
}
onBeforeUnmount(() => {
  serial++
  controller?.abort()
})
</script>

<style scoped>
.plan-trigger {
  border: 1px solid #a6bcd1;
  border-radius: 9px;
  padding: 10px 15px;
  background: #fff;
  color: #244b70;
  font-weight: 700;
  cursor: pointer;
}
.metering-plan-dialog {
  width: min(1040px, 94vw);
  max-height: 90dvh;
  border: 1px solid #a8bed0;
  border-radius: 18px;
  padding: 0;
  color: #203b53;
}
.metering-plan-dialog::backdrop {
  background: #102d4c80;
}
header,
footer {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 24px;
  background: #f0f5fa;
}
header {
  justify-content: space-between;
  border-bottom: 1px solid #cbd9e6;
}
header small {
  color: #337394;
  letter-spacing: 1px;
  font-size: 10px;
}
h3 {
  margin: 5px 0 0;
}
button,
select,
input {
  font: inherit;
}
.metering-plan-dialog > header button {
  border: 0;
  background: #dce7f0;
  border-radius: 8px;
  width: 32px;
  height: 32px;
  font-size: 23px;
  cursor: pointer;
}
.plan-body {
  padding: 18px 24px;
}
.plan-note {
  color: #506a80;
  line-height: 1.8;
  font-size: 13px;
  margin: 0 0 16px;
}
.plan-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}
select {
  padding: 7px;
  border: 1px solid #b7c8d7;
  border-radius: 6px;
}
.month-tabs {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 5px;
  margin: 15px 0;
}
.month-tabs button {
  padding: 9px 0;
  background: #f4f7fa;
  border: 1px solid #c5d4e1;
  border-radius: 8px;
  color: #39566f;
  cursor: pointer;
}
.month-tabs button[aria-pressed='true'] {
  background: #1d597e;
  color: white;
  border-color: #1d597e;
}
.month-tabs small {
  display: block;
  font-size: 10px;
  margin-top: 4px;
}
.plan-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  padding: 13px 0;
  font-size: 13px;
}
.plan-summary b {
  font-size: 19px;
}
.region-targets {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}
article {
  border: 1px solid #cbd9e6;
  padding: 14px;
  border-radius: 10px;
  background: #fbfcfe;
}
article small {
  display: block;
  margin: 6px 0 10px;
  color: #667f93;
  font-size: 11px;
}
article label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}
article input {
  width: 66px;
  padding: 7px;
  border: 1px solid #b3c5d5;
  border-radius: 6px;
  text-align: center;
}
article p {
  font-size: 11px;
  color: #536e83;
  margin-bottom: 0;
}
.saved-by {
  color: #667f93;
}
.plan-error {
  color: #a22727;
  background: #fff0ee;
  padding: 12px;
}
footer {
  border-top: 1px solid #cbd9e6;
  position: sticky;
  bottom: 0;
}
footer span {
  margin-right: auto;
  font-size: 12px;
}
footer button {
  padding: 9px 14px;
  border: 1px solid #adc0d1;
  border-radius: 7px;
  background: white;
  color: #244b70;
  cursor: pointer;
}
footer .primary {
  background: #18597f;
  color: white;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
@media (max-width: 700px) {
  .month-tabs {
    grid-template-columns: repeat(6, 1fr);
  }
  .region-targets {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .plan-body,
  header,
  footer {
    padding: 14px;
  }
}
@media (max-width: 440px) {
  .region-targets {
    grid-template-columns: 1fr;
  }
}
</style>
