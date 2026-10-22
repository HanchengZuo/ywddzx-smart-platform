<template>
  <button v-if="allowed" type="button" class="auto-trigger" @click="open">今日一键排班</button>
  <Teleport to="body"
    ><dialog
      ref="dialog"
      class="auto-dialog"
      aria-labelledby="auto-schedule-title"
      @cancel.prevent="close"
      @click="backdrop"
    >
      <header>
        <div>
          <small>平衡派工 / DAILY DISPATCH</small>
          <h3 id="auto-schedule-title">今日一键排班</h3>
        </div>
        <button type="button" :disabled="saving" aria-label="关闭自动排班" @click="close">×</button>
      </header>
      <div class="auto-body">
        <p class="method">
          {{ day }} · 今日未设置的档期默认有空，已标记没空者不参与。当天实绩自上海时间 17:00
          后参与派工校验，早间录入不阻止排班；已有站点安排仍不覆盖。现场按已保存外勤组整行派站，视频每站一人统一完成安全、计量、现场。
        </p>
        <p class="method">
          现场先补足当月计量年度计划的片区站数，再均衡季度片区覆盖，并让同组站点彼此靠近。缺失坐标的站点不自动派现场任务。可在页面“计量年度计划”维护月度配额；视频仍按本季度工作量安排。
        </p>
        <div class="quota-controls">
          <label
            >现场每组站点数<input
              v-model.number="offlineCount"
              type="number"
              min="1"
              max="10"
              :disabled="loading || saving"
              @input="stale = true"
          /></label>
          <label
            >视频每人站点数<input
              v-model.number="onlineCount"
              type="number"
              min="1"
              max="10"
              :disabled="loading || saving"
              @input="stale = true"
          /></label>
          <small>调整数量后点击“重新预览”</small>
        </div>
        <p v-if="loading" role="status" class="empty">正在核对档期、巡检记录和本季度任务量…</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <p v-if="savedNotice" class="saved-notice" role="status">{{ savedNotice }}</p>
        <section v-if="preview?.current_assignments?.length" class="today-saved">
          <div class="today-saved-title">
            <h4>今日已确认排班</h4>
            <span>全局共享 · 含手动派工与实际进度</span>
          </div>
          <div class="proposal-list">
            <article v-for="group in preview.current_assignments" :key="group.key">
              <div class="proposal-person">
                <strong>{{ group.name }}</strong
                ><span :class="group.mode"
                  >{{ group.mode === 'offline' ? '现场巡检' : '视频巡检' }} ·
                  {{ group.stations.length }}站</span
                >
              </div>
              <p>{{ group.people.map((p) => p.display_name).join('、') }}</p>
              <strong class="saved-progress">已查 {{ group.completed }}/{{ group.total }}项</strong>
              <ol class="proposal-stations">
                <li v-for="station in group.stations" :key="station.station_id">
                  <b>{{ station.region }} · {{ station.station_name }}</b
                  ><small v-if="station.locked" class="execution-lock">已开始 · 整行锁定</small>
                  <div class="saved-checks">
                    <span v-for="cell in station.cells" :key="cell.key" :class="cell.status"
                      >{{ cell.label }} ·
                      {{
                        cell.status === 'completed'
                          ? '已检查'
                          : cell.status === 'unavailable'
                            ? '不可安排'
                            : '已排班'
                      }}</span
                    >
                  </div>
                </li>
              </ol>
            </article>
          </div>
        </section>
        <template v-if="preview">
          <details v-if="preview.metering_plan?.regions?.length" class="coverage-panel" open>
            <summary>当月计量年度计划 · 优先派站依据</summary>
            <p>
              圆环为年度站点覆盖：年度表任一适用检查项为绿色即计已查，每站只计一次。月度目标与本月已查单独列出；未审核记录同样计数，计划预留不算已查。
            </p>
            <div class="quota-progress-grid">
              <article v-for="r in preview.metering_plan.regions" :key="r.region">
                <div
                  class="quota-ring"
                  role="progressbar"
                  :aria-label="r.region + '年度站点覆盖'"
                  :aria-valuenow="r.annual_completed || 0"
                  :aria-valuemin="0"
                  :aria-valuemax="r.total"
                >
                  <svg viewBox="0 0 80 80" aria-hidden="true">
                    <circle cx="40" cy="40" r="33" class="ring-track" />
                    <circle
                      cx="40"
                      cy="40"
                      r="33"
                      class="ring-value"
                      pathLength="100"
                      :stroke-dasharray="`${coveragePercent(r)} 100`"
                    />
                  </svg>
                  <b>{{ coveragePercent(r) }}<small>%</small></b>
                </div>
                <div class="quota-caption">
                  <strong>{{ r.region }}</strong
                  ><b>年度已查 {{ r.annual_completed || 0 }}/{{ r.total }}站</b
                  ><small
                    >{{ preview.metering_plan.month }}月目标 {{ r.target }} · 本月已查
                    {{ r.completed }}站</small
                  >
                  <div
                    v-if="r.target"
                    class="month-progress"
                    role="progressbar"
                    :aria-label="r.region + '本月目标完成'"
                    :aria-valuenow="Math.min(r.completed, r.target)"
                    :aria-valuemin="0"
                    :aria-valuemax="r.target"
                  >
                    <i :style="{ width: Math.min(100, (100 * r.completed) / r.target) + '%' }"></i>
                  </div>
                  <small>预留 {{ r.reserved }} · 本次拟派 {{ r.proposed || 0 }}站</small>
                </div>
              </article>
            </div>
          </details>
          <h4 class="upcoming-title">待确认的新派工预览</h4>
          <div class="preview-summary">
            <span
              ><b>{{ preview.available_count }}</b> 可派工人员</span
            ><span
              ><b>{{ preview.groups.length }}</b> 站点任务组</span
            ><span
              ><b>{{ preview.cell_count }}</b> 排班单元格</span
            ><small>{{ preview.quarter }}平衡口径</small>
          </div>
          <details v-if="preview.regional_coverage?.length" class="coverage-panel">
            <summary>现场片区覆盖均衡 · 查看本次分配依据</summary>
            <p>
              本季度有任一现场检查记录即计覆盖，不依赖审核。今日及未来已有计划仅作预留，不算实绩；在此基础上优先补齐低覆盖片区，再缩小组内站点距离。
            </p>
            <div class="coverage-grid">
              <div
                v-for="region in preview.regional_coverage"
                :key="region.region"
                :class="{ chosen: region.selected }"
              >
                <strong>{{ region.region }}</strong
                ><b title="当前实绩覆盖率 → 含计划预留及本次派工的预计覆盖率"
                  >{{ region.current_rate }}% → {{ region.projected_rate }}%</b
                >
                <small
                  >已查 {{ region.checked }}/{{ region.total }}站 · 预留 {{ region.reserved }}站 ·
                  本次 {{ region.selected }}站</small
                >
              </div>
            </div>
          </details>
          <div v-if="preview.groups.length" class="proposal-list">
            <article v-for="group in proposalGroups" :key="group.key">
              <div class="proposal-person">
                <strong>{{ group.group_name || group.person.display_name }}</strong
                ><span :class="group.mode"
                  >{{ group.mode === 'offline' ? '现场巡检' : '视频巡检' }} ·
                  {{ group.stations.length }}站</span
                >
              </div>
              <p v-if="group.team_members">
                {{ group.team_members.map((p) => p.display_name).join('、') }}
              </p>
              <ol
                class="proposal-stations"
                :aria-label="(group.group_name || group.person.display_name) + '负责的站点'"
              >
                <li v-for="station in group.stations" :key="station.station_id">
                  <b>{{ station.region }} · {{ station.station_name }}</b>
                  <p>
                    {{
                      [...station.cells, ...(station.metering_cells || [])]
                        .map((c) => c.label)
                        .join('、')
                    }}<b v-if="station.metering_priority"> · 计量计划优先</b>
                  </p>
                  <small v-if="group.mode === 'offline'">{{ station.address }}</small>
                </li>
              </ol>
              <p v-if="group.mode === 'offline'">
                组内站点最远直线距离 {{ group.cluster_max_km }} km · 非行车路线
              </p>
              <small
                >本季度现场 {{ group.before.offline }} → {{ group.after.offline }} 组 · 视频
                {{ group.before.online }} → {{ group.after.online }} 组</small
              >
            </article>
          </div>
          <p v-else class="empty">
            没有可以自动安排的组合。请先设置今日人员有空，或核对当前季度 / 月份是否还有待排班项目。
          </p>
          <p v-for="warning in preview.warnings" :key="warning" class="method">{{ warning }}</p>
          <details v-if="preview.excluded.length" class="excluded">
            <summary>未参与自动派工的人员（{{ preview.excluded.length }}）</summary>
            <p v-for="person in preview.excluded" :key="person.name">
              {{ person.name }} · {{ person.reason }}
            </p>
          </details>
        </template>
      </div>
      <footer>
        <span>确认后同步个人待办，已确认的今日排班仍保留在本窗口。</span
        ><button type="button" :disabled="loading || saving" @click="createPreview">重新预览</button
        ><button
          type="button"
          class="primary"
          :disabled="loading || saving || !preview?.groups.length || stale"
          @click="confirm"
        >
          {{ saving ? '正在保存…' : '确认派工' }}
        </button>
      </footer>
    </dialog></Teleport
  >
</template>
<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, ref } from 'vue'
import { shanghaiToday } from '@/utils/staffScheduling'
import { groupScheduleProposals } from '@/utils/scheduleProposals'
const emit = defineEmits(['scheduled'])
let permissions = {}
try {
  permissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch {
  /* API checks effective permissions. */
}
const allowed =
  (localStorage.getItem('user_role') || localStorage.getItem('role')) === 'root' ||
  permissions.edit_inspection_schedule
const dialog = ref(null),
  preview = ref(null),
  loading = ref(false),
  saving = ref(false),
  error = ref(''),
  savedNotice = ref(''),
  stale = ref(false),
  day = ref(shanghaiToday())
const offlineCount = ref(2),
  onlineCount = ref(3)
const proposalGroups = computed(() => groupScheduleProposals(preview.value?.groups))
const coveragePercent = (r) =>
  r.total ? Math.min(100, Math.round((100 * (r.annual_completed || 0)) / r.total)) : 0
let controller,
  disposed = false,
  serial = 0
function open() {
  day.value = shanghaiToday()
  preview.value = null
  savedNotice.value = ''
  dialog.value.showModal()
  createPreview()
}
function close() {
  if (saving.value) return
  serial++
  controller?.abort()
  loading.value = false
  dialog.value?.close()
}
function backdrop(event) {
  if (event.target === dialog.value) {
    const r = dialog.value.getBoundingClientRect()
    if (
      event.clientX < r.left ||
      event.clientX > r.right ||
      event.clientY < r.top ||
      event.clientY > r.bottom
    )
      close()
  }
}
async function createPreview() {
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  stale.value = true
  try {
    const { data } = await axios.post(
      '/api/inspection-schedule/auto',
      {
        action: 'preview',
        day: day.value,
        offline_count: offlineCount.value,
        online_count: onlineCount.value,
      },
      { signal: controller.signal, timeout: 60000 },
    )
    if (ticket === serial && !disposed) {
      preview.value = data
      stale.value = false
    }
  } catch (err) {
    if (ticket === serial && !disposed && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '自动排班预览失败，请重试。'
  } finally {
    if (ticket === serial) loading.value = false
  }
}
async function confirm() {
  if (saving.value || loading.value || stale.value || !preview.value?.groups.length) return
  saving.value = true
  error.value = ''
  try {
    const { data } = await axios.post(
      '/api/inspection-schedule/auto',
      {
        action: 'confirm',
        day: day.value,
        token: preview.value.token,
        offline_count: offlineCount.value,
        online_count: onlineCount.value,
      },
      { timeout: 120000 },
    )
    if (!disposed) {
      savedNotice.value = `已确认 ${data.groups.length} 个站点任务，个人待办已同步。下方“今日已确认排班”可持续查看。`
      preview.value = { ...data, groups: [], cell_count: 0 }
      emit('scheduled', data)
      window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
      await createPreview()
    }
  } catch (err) {
    if (!disposed) {
      error.value = err.response?.data?.error || '未确认派工结果，请重新预览核对，避免重复派工。'
      stale.value = true
    }
  } finally {
    saving.value = false
  }
}
onBeforeUnmount(() => {
  disposed = true
  serial++
  controller?.abort()
  dialog.value?.close()
})
</script>
<style scoped>
.today-saved {
  border: 1px solid #a6c6d5;
  border-top: 4px solid #176b80;
  border-radius: 12px;
  padding: 16px;
  margin: 16px 0 24px;
  background: #f5fafc;
}
.today-saved-title {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.today-saved .proposal-list {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
}
.month-progress {
  height: 5px;
  background: #dcebf2;
  border-radius: 4px;
  overflow: hidden;
}
.month-progress i {
  height: 100%;
  display: block;
  background: #237ea0;
}
.today-saved-title h4,
.upcoming-title {
  margin: 0;
  font-size: 16px;
  color: #21465c;
}
.today-saved-title > span {
  font-size: 11px;
  color: #527184;
}
.saved-checks {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 8px;
}
.saved-checks > span {
  font-size: 11px;
  padding: 4px 6px;
  border: 1px solid #d68c88;
  background: #ffe7e5;
  color: #8b302a;
  border-radius: 4px;
}
.saved-checks > .completed {
  background: #d3f1df;
  color: #155437;
  border-color: #7fb797;
}
.saved-checks > .unavailable {
  background: #eee;
  border-color: #aaa;
  color: #666;
}
.execution-lock {
  display: block;
  color: #17654a;
  margin-top: 5px;
}
.saved-progress {
  font-size: 12px;
  color: #17654a;
}
.saved-notice {
  background: #e7f6ee;
  border: 1px solid #a6ceb9;
  padding: 12px;
  border-radius: 8px;
  color: #155437;
  font-size: 13px;
}
.quota-progress-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 245px), 1fr));
  gap: 10px;
}
.quota-progress-grid article {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #c9dce4;
  background: #fff;
  padding: 12px;
  border-radius: 10px;
}
.quota-ring {
  width: 76px;
  height: 76px;
  position: relative;
  flex-shrink: 0;
}
.quota-ring svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}
.quota-ring circle {
  fill: none;
  stroke-width: 8;
}
.ring-track {
  stroke: #e2edf1;
}
.ring-value {
  stroke: #18846a;
  stroke-linecap: round;
}
.quota-ring > b {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #155941;
}
.quota-ring small {
  font-size: 11px;
}
.quota-caption {
  display: grid;
  gap: 5px;
  min-width: 0;
}
.quota-caption strong {
  font-size: 14px;
  color: #234358;
}
.quota-caption b {
  font-size: 12px;
  color: #17654a;
}
.quota-caption small {
  font-size: 11px;
  line-height: 1.5;
  color: #526d80;
}
.coverage-panel {
  margin: 14px 0;
  padding: 14px;
  border: 1px solid #b7d4df;
  border-radius: 12px;
  background: #f3f9fb;
  color: #31596b;
}
.coverage-panel summary {
  cursor: pointer;
  font-weight: 700;
}
.coverage-panel p {
  font-size: 13px;
  line-height: 1.7;
}
.coverage-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 8px;
}
.coverage-grid > div {
  display: grid;
  gap: 5px;
  padding: 10px;
  background: #fff;
  border: 1px solid #dce8ee;
  border-radius: 8px;
}
.coverage-grid > .chosen {
  border-color: #2d93a9;
  background: #e8f7f8;
}
.coverage-grid b {
  color: #12647b;
}
.coverage-grid small {
  line-height: 1.5;
}
.quota-controls {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  align-items: end;
  padding: 16px;
  background: #eef4fa;
  border-radius: 12px;
  margin: 14px 0;
}
.quota-controls label {
  display: grid;
  gap: 8px;
  color: #3d5e7b;
  font-size: 12px;
}
.quota-controls input {
  width: 100px;
  padding: 9px;
  border: 1px solid #bfd0e1;
  border-radius: 7px;
  font: inherit;
}
.quota-controls small {
  font-size: 11px;
  color: #738aa0;
}
.auto-trigger {
  border: 1px solid #2866b5;
  background: #2866b5;
  color: #fff;
  border-radius: 10px;
  padding: 12px 16px;
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  white-space: nowrap;
}
.auto-dialog {
  width: min(940px, calc(100vw - 24px));
  max-height: calc(100dvh - 32px);
  padding: 0;
  border: 1px solid #d6e1ed;
  border-radius: 20px;
  margin: auto;
  color: #203a54;
  box-shadow: 0 24px 80px #18324c44;
  overflow: hidden;
}
.auto-dialog[open] {
  display: flex;
  flex-direction: column;
}
.auto-dialog::backdrop {
  background: #182c4b66;
  backdrop-filter: blur(4px);
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 24px;
  border-bottom: 1px solid #dfe8f2;
  flex-shrink: 0;
  background: linear-gradient(120deg, #edf5ff, #fff);
}
header small {
  font-size: 10px;
  letter-spacing: 1px;
  color: #6483a5;
}
h3 {
  margin: 8px 0 0;
  font-size: 22px;
}
.auto-body {
  padding: 20px 24px;
  overflow: auto;
  min-height: 0;
}
.method {
  font-size: 12px;
  color: #71859c;
  line-height: 1.8;
  margin: 0 0 10px;
}
.preview-summary {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  align-items: center;
  padding: 16px;
  background: #f2f7fd;
  border-radius: 12px;
  margin: 18px 0;
  font-size: 12px;
  color: #56738f;
}
.preview-summary b {
  font-size: 23px;
  color: #2c6096;
  margin-right: 4px;
}
.preview-summary small {
  margin-left: auto;
  color: #8399ad;
}
.proposal-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.proposal-list article {
  padding: 16px;
  border: 1px solid #dce6f1;
  border-radius: 12px;
}
.proposal-stations {
  display: grid;
  gap: 10px;
  padding: 0 0 0 24px;
  margin: 12px 0;
}
.proposal-stations li {
  padding: 7px 8px;
  background: #f4f8fc;
  border-radius: 6px;
}
.proposal-stations li::marker {
  color: #467bad;
  font-weight: 700;
}
.proposal-stations p {
  margin: 4px 0;
}
.proposal-person {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.proposal-person strong {
  font-size: 16px;
}
.proposal-person span {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  background: #eaf2ff;
  color: #2866b5;
}
.proposal-person .offline {
  background: #e8f6f2;
  color: #287764;
}
.proposal-list b {
  font-size: 13px;
}
.proposal-list p {
  font-size: 12px;
  line-height: 1.6;
  color: #71849b;
}
.proposal-list small {
  font-size: 11px;
  color: #8899ae;
}
.excluded {
  margin-top: 18px;
  font-size: 12px;
  color: #8394a8;
}
.excluded summary {
  cursor: pointer;
}
.excluded p {
  display: inline-block;
  margin: 10px 14px 0 0;
}
.error {
  background: #fff0ed;
  color: #b04d39;
  border-radius: 10px;
  padding: 12px;
  font-size: 13px;
}
.empty {
  text-align: center;
  padding: 32px 8px;
  font-size: 13px;
  color: #8394a8;
}
footer {
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
  border-top: 1px solid #dfe8f2;
  flex-shrink: 0;
}
footer span {
  flex: 1;
  font-size: 11px;
  color: #899bb0;
}
button {
  font: inherit;
  border: 1px solid #d5e1ee;
  padding: 9px 12px;
  border-radius: 8px;
  color: #54718d;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button:focus-visible {
  outline: 2px solid #70a1d6;
  outline-offset: 2px;
}
.primary {
  background: #2866b5;
  color: #fff;
  border-color: #2866b5;
}
@media (max-width: 650px) {
  .proposal-list {
    grid-template-columns: 1fr;
  }
  header,
  .auto-body,
  footer {
    padding: 16px;
  }
  h3 {
    font-size: 20px;
  }
  footer span {
    flex-basis: 100%;
  }
  .preview-summary {
    gap: 10px;
  }
  .preview-summary small {
    margin-left: 0;
    width: 100%;
  }
  .auto-dialog {
    width: calc(100vw - 16px);
    max-height: calc(100dvh - 16px);
    border-radius: 15px;
  }
}
</style>
