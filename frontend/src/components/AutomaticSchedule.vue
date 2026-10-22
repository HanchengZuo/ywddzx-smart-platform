<template>
  <button v-if="allowed" type="button" class="auto-trigger" @click="open">今日智能排班</button>
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
          <small>SMART DISPATCH / 人员方案驱动</small>
          <h3 id="auto-schedule-title">
            今日智能排班 <span>{{ day }}</span>
          </h3>
        </div>
        <button type="button" :disabled="saving" aria-label="关闭今日智能排班" @click="close">
          ×
        </button>
      </header>
      <div class="auto-body">
        <div class="smart-flow" aria-label="智能排班步骤">
          <span><b>01</b> 人员档期方案</span><span><b>02</b> 算法推荐站点</span
          ><span><b>03</b> 应用到今日排班</span>
        </div>
        <p class="method">
          以人员档期已保存的现场组和视频人员为基础，不因今日手动派工而减少候选人员或改变方案。应用时替换今日尚未开始的排班；已开始整行和其他日期计划保留。现场先补足当月计量年度计划，再均衡季度片区覆盖，让同组站点彼此靠近；无有效坐标不自动派现场站点。
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
          <small>包含已开始的今日站点；调整后点击“计算智能方案”全局保存，并更新待选区角标</small>
          <small v-if="quotaSettings"
            >{{ quotaSettings.updated_by_name }} {{ quotaSettings.updated_at }} 保存</small
          >
        </div>
        <p v-if="loading" role="status" class="empty">正在核对档期、巡检记录和本季度任务量…</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <p v-if="savedNotice" class="saved-notice" role="status">{{ savedNotice }}</p>
        <template v-if="preview">
          <section class="personnel-basis">
            <div class="basis-heading">
              <h4>人员档期 · 今日分工依据</h4>
              <small
                >{{ preview.personnel?.updated_by_name || '尚未保存' }}
                {{ preview.personnel?.updated_at || '' }}</small
              >
            </div>
            <div class="basis-groups">
              <div v-for="g in preview.personnel?.groups || []" :key="g.name" :class="g.mode">
                <strong>{{ g.name }}</strong
                ><span>{{ g.members.map((p) => p.display_name).join('、') }}</span>
              </div>
            </div>
            <p v-if="!preview.personnel?.groups?.length" class="method">
              请先前往人员档期保存今日现场/视频分组，再计算智能方案。
            </p>
          </section>
          <details class="coverage-panel" :class="{ 'basis-applied': basis.metering.applied }" open>
            <summary>
              <span class="basis-name"><b>01</b> 当月计量年度计划 · 优先派站依据</span>
              <span class="basis-badge" :class="{ applied: basis.metering.applied, stale }">{{
                stale ? '方案待重新计算' : basis.metering.label
              }}</span>
            </summary>
            <p class="basis-explanation">{{ basis.metering.detail }}</p>
            <p v-if="targetRegions.length">
              圆环为年度站点覆盖：年度表任一适用检查项为绿色即计已查，每站只计一次。月度目标与本月已查单独列出；未审核记录同样计数，计划预留不算已查。
            </p>
            <div class="quota-progress-grid">
              <article v-for="r in targetRegions" :key="r.region">
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
          <details class="coverage-panel" :class="{ 'basis-applied': basis.coverage.applied }">
            <summary>
              <span class="basis-name"><b>02</b> 现场片区覆盖均衡 · 查看本次分配依据</span>
              <span class="basis-badge" :class="{ applied: basis.coverage.applied, stale }">{{
                stale ? '方案待重新计算' : basis.coverage.label
              }}</span>
            </summary>
            <p class="basis-explanation">{{ basis.coverage.detail }}</p>
            <p>
              本季度有任一现场检查记录即计覆盖，不依赖审核。忽略今日未开始的手动计划，未来计划仍受保护；先补齐低覆盖片区，再缩小组内站点距离。
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
            <p v-if="!preview.regional_coverage?.length">暂无可供比较的现场片区覆盖数据。</p>
          </details>
          <section class="scheme-summary" aria-label="今日智能排班方案概况">
            <h4 class="upcoming-title">今日智能排班方案 <small>仅预览，不自动修改排班表</small></h4>
            <div class="preview-summary">
              <span
                ><b>{{ preview.available_count }}</b> 可派工人员</span
              >
              <span
                ><b>{{ preview.groups.length }}</b> 站点任务组</span
              >
              <span
                ><b>{{ preview.cell_count }}</b> 排班单元格</span
              >
              <small>{{ preview.quarter }}实绩平衡口径</small>
            </div>
          </section>
          <template v-for="mode in ['offline', 'online']" :key="mode"
            ><section
              v-if="proposalGroups.some((g) => g.mode === mode)"
              :class="['smart-mode', mode]"
            >
              <h4>{{ mode === 'offline' ? '现场巡检 · 外勤组方案' : '视频巡检 · 单人方案' }}</h4>
              <div class="proposal-list">
                <article
                  v-for="group in proposalGroups.filter((g) => g.mode === mode)"
                  :key="group.key"
                >
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
            </section></template
          >
          <p v-if="!preview.groups.length" class="empty">
            当前没有可应用的新增组合。请核对今日已保存的人员分工、未检查站点及已开始任务；当前已确认派工可在独立窗口查看。
          </p>
          <p v-for="warning in preview.warnings" :key="warning" class="method">{{ warning }}</p>
          <details v-if="preview.excluded.length" class="excluded">
            <summary>未参与自动派工的人员（{{ preview.excluded.length }}）</summary>
            <p v-for="person in preview.excluded" :key="person.name">
              {{ person.name }} · {{ person.reason }}
            </p>
          </details>
        </template>
        <section v-if="preview?.groups.length" class="replace-confirmation">
          <strong>应用将替换今日尚未开始的排班</strong>
          <p>
            当前可替换 {{ preview.replacement?.stations || 0 }} 个站点任务，保留已开始的
            {{ preview.replacement?.protected || 0 }}
            个站点任务及其他日期计划。原派工、取消记录和新派工全程留痕，保存失败不会清空原计划。
          </p>
          <label
            ><input
              v-model="replaceConfirmed"
              type="checkbox"
              :disabled="saving || loading || stale"
            />我已确认以上替换范围</label
          >
        </section>
      </div>
      <footer>
        <span>实际安排请从“今日已确认排班”独立窗口查看。</span
        ><button type="button" :disabled="loading || saving" @click="createPreview">
          计算智能方案</button
        ><button
          type="button"
          class="primary"
          :disabled="loading || saving || !preview?.groups.length || stale || !replaceConfirmed"
          @click="confirm"
        >
          {{ saving ? '正在原子替换…' : '应用方案并替换今日排班' }}
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
import { scheduleBasis } from '@/utils/scheduleBasis'
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
const quotaSettings = ref(null)
const proposalGroups = computed(() => groupScheduleProposals(preview.value?.groups))
const basis = computed(() => scheduleBasis(preview.value))
const targetRegions = computed(() =>
  (preview.value?.metering_plan?.regions || []).filter((r) => r.target > 0),
)
const replaceConfirmed = ref(false)
const coveragePercent = (r) =>
  r.total ? Math.min(100, Math.round((100 * (r.annual_completed || 0)) / r.total)) : 0
let controller,
  disposed = false,
  serial = 0
async function open() {
  day.value = shanghaiToday()
  preview.value = null
  quotaSettings.value = null
  savedNotice.value = ''
  error.value = ''
  dialog.value.showModal()
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  try {
    const { data } = await axios.get('/api/inspection-schedule/quotas', {
      signal: controller.signal,
      timeout: 15000,
    })
    if (ticket !== serial || disposed) return
    quotaSettings.value = data
    offlineCount.value = data.offline_count
    onlineCount.value = data.online_count
    await createPreview()
  } catch (err) {
    if (ticket === serial && !disposed && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '站数配置读取失败，请关闭后重新打开。'
  } finally {
    if (ticket === serial) loading.value = false
  }
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
  if (!quotaSettings.value) {
    error.value = '请重新打开智能排班，读取最新站数配置后再计算。'
    return
  }
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  stale.value = true
  replaceConfirmed.value = false
  try {
    const { data } = await axios.post(
      '/api/inspection-schedule/auto',
      {
        action: 'preview',
        strategy: 'replace_today',
        day: day.value,
        offline_count: offlineCount.value,
        online_count: onlineCount.value,
        quota_revision: quotaSettings.value.revision,
        save_quotas:
          offlineCount.value !== quotaSettings.value.offline_count ||
          onlineCount.value !== quotaSettings.value.online_count,
      },
      { signal: controller.signal, timeout: 60000 },
    )
    if (ticket === serial && !disposed) {
      const changed = data.quota_settings?.revision !== quotaSettings.value.revision
      if (data.quota_settings) quotaSettings.value = data.quota_settings
      preview.value = data
      stale.value = false
      if (changed) window.dispatchEvent(new Event('inspection-schedule-changed'))
    }
  } catch (err) {
    if (ticket === serial && !disposed && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '自动排班预览失败，请重试。'
  } finally {
    if (ticket === serial) loading.value = false
  }
}
async function confirm() {
  if (
    saving.value ||
    loading.value ||
    stale.value ||
    !preview.value?.groups.length ||
    !replaceConfirmed.value
  )
    return
  saving.value = true
  error.value = ''
  try {
    const { data } = await axios.post(
      '/api/inspection-schedule/auto',
      {
        action: 'confirm',
        strategy: 'replace_today',
        replace_confirmed: replaceConfirmed.value,
        day: day.value,
        token: preview.value.token,
        offline_count: offlineCount.value,
        online_count: onlineCount.value,
      },
      { timeout: 120000 },
    )
    if (!disposed) {
      savedNotice.value = `今日智能方案已应用，个人待办已同步。可关闭本窗口，从“今日已确认排班”查看实际安排。`
      preview.value = { ...data, groups: [], cell_count: 0 }
      emit('scheduled', data)
      window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
      window.dispatchEvent(new Event('inspection-schedule-changed'))
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
.smart-flow {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding-bottom: 18px;
  border-bottom: 1px solid #cbdce7;
  margin-bottom: 16px;
}
.smart-flow > span {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #274c64;
  font-size: 12px;
  font-weight: 700;
}
.smart-flow b {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  border: 1px solid #2a6c86;
  border-radius: 7px;
  color: #fff;
  background: #236a84;
  font-size: 10px;
}
.personnel-basis {
  border: 1px solid #b6cbd8;
  border-left: 4px solid #39728a;
  padding: 14px;
  border-radius: 10px;
  margin: 14px 0;
  background: #f7fafc;
}
.basis-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.basis-heading h4 {
  margin: 0;
  font-size: 14px;
}
.basis-heading small {
  font-size: 10px;
  color: #59778c;
}
.basis-groups {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.basis-groups > div {
  display: grid;
  gap: 5px;
  border: 1px solid #d5bb8d;
  border-radius: 6px;
  background: #fff6e7;
  padding: 8px 10px;
  font-size: 11px;
  color: #78511b;
}
.basis-groups > .online {
  border-color: #9dbce0;
  background: #eaf2ff;
  color: #215b94;
}
.basis-groups span {
  line-height: 1.6;
}
.upcoming-title small {
  display: block;
  font-size: 11px;
  font-weight: 400;
  margin: 8px 0;
  color: #59758b;
}
.smart-mode {
  margin: 18px 0;
  padding: 16px;
  border: 1px solid #d8bb88;
  border-top: 4px solid #bc8a35;
  border-radius: 12px;
  background: #fffaf0;
}
.smart-mode > h4 {
  color: #805417;
  margin: 0 0 15px;
  font-size: 16px;
}
.smart-mode.online {
  border-color: #a9c6e6;
  border-top-color: #2e73b9;
  background: #f0f6ff;
}
.smart-mode.online > h4 {
  color: #215c98;
}
.smart-mode .proposal-list {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
}
.smart-mode article {
  background: white;
}
.replace-confirmation {
  padding: 16px;
  border: 1px solid #d4b16f;
  border-left: 4px solid #b47a1e;
  border-radius: 10px;
  background: #fff6e3;
  margin: 20px 0 0;
  color: #744e19;
  font-size: 13px;
}
.replace-confirmation p {
  line-height: 1.8;
  font-size: 12px;
}
.replace-confirmation label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
}
.replace-confirmation input {
  width: 17px;
  height: 17px;
  accent-color: #b47a1e;
}
.auto-dialog > header {
  background: #173e58;
  color: white;
  border-bottom: 3px solid #dfb24b;
}
.auto-dialog > header small {
  color: #b9dbe7;
}
.auto-dialog > header > button {
  background: #ffffff12;
  border-color: #ffffff40;
  color: #fff;
  width: 36px;
  height: 36px;
  padding: 0;
  font-size: 23px;
}
.auto-dialog h3 span {
  color: #b9dbe7;
  font-size: 13px;
  margin-left: 10px;
  font-weight: 400;
}
.auto-trigger {
  min-height: 44px;
  line-height: 1.4;
}
input[type='number'] {
  appearance: textfield;
}
input[type='number']::-webkit-inner-spin-button,
input[type='number']::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
@media (max-width: 600px) {
  .smart-flow {
    gap: 7px;
  }
  .smart-flow > span {
    flex-direction: column;
    align-items: flex-start;
    font-size: 11px;
  }
  .smart-mode {
    padding: 12px;
  }
  .auto-dialog h3 span {
    display: block;
    margin: 6px 0 0;
  }
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
.upcoming-title {
  margin: 0;
  font-size: 16px;
  color: #21465c;
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  list-style: none;
}
.coverage-panel summary::-webkit-details-marker {
  display: none;
}
.basis-name {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  line-height: 1.6;
}
.basis-name b {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  background: #ddeaf0;
  border-radius: 7px;
  font-size: 11px;
}
.basis-badge {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 10px;
  border: 1px solid #b8c7d0;
  border-radius: 7px;
  background: #e8eef2;
  color: #4c6373;
  font-size: 12px;
  white-space: nowrap;
}
.basis-badge::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.basis-badge.applied {
  border-color: #84b9a4;
  color: #176044;
  background: #e1f3e9;
}
.basis-badge.stale {
  border-color: #cdb275;
  color: #7d5919;
  background: #fff2d8;
}
.basis-applied {
  border-left: 4px solid #2c8669;
}
.coverage-panel summary::after {
  content: '+';
  font-size: 19px;
  width: 18px;
  flex-shrink: 0;
  text-align: center;
}
.coverage-panel[open] summary::after {
  content: '−';
}
.basis-badge {
  margin-left: auto;
}
.coverage-panel .basis-explanation {
  color: #294c61;
}
.scheme-summary {
  border-top: 2px solid #bdcfdc;
  margin-top: 24px;
  padding-top: 22px;
}
.scheme-summary .preview-summary {
  margin-bottom: 0;
}
@media (max-width: 600px) {
  .coverage-panel summary {
    flex-wrap: wrap;
    gap: 8px;
  }
  .basis-name {
    flex: 1 1 calc(100% - 28px);
    font-size: 13px;
  }
  .basis-badge {
    order: 1;
    margin-left: 38px;
    white-space: normal;
    font-size: 11px;
  }
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
  width: min(1280px, calc(100vw - 32px));
  max-width: none;
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
