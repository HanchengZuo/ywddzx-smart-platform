<template>
  <div class="schedule-page" :style="{ '--schedule-switcher-height': switcherHeight + 'px' }">
    <header class="schedule-page-head surface">
      <div>
        <span class="kicker">排班系统 / INSPECTION SCHEDULE</span>
        <h2>巡检排班</h2>
        <p>按站点、按检查表安排检查人，巡检记录自动反映实际检查情况。</p>
      </div>
      <div class="head-actions">
        <MeteringAnnualPlan v-if="allowed" @saved="refreshKey++" />
        <TodayInspectionDispatch v-if="allowed" />
        <AutomaticSchedule v-if="allowed" @scheduled="onScheduled" /><span class="access-label">{{
          allowed ? '全局共享 · 独立编辑授权' : '需要查看权限'
        }}</span>
      </div>
    </header>
    <template v-if="allowed">
      <div class="schedule-guide surface">
        <strong>计划与实绩，分开呈现</strong>
        <p>
          <span class="legend done"></span
          >绿色为本周期已有巡检记录，不论是否审核，均锁定为实际检查人。<span
            class="legend planned"
          ></span
          >红色为已排班；<span class="legend overdue"></span
          >黄色为计划日期已过但仍未检查。本站任一检查项变绿即整行锁定，未开始站点可调整，保存后同步个人待办。
        </p>
      </div>
      <p v-if="dispatchNotice" class="dispatch-notice" role="status">{{ dispatchNotice }}</p>
      <nav ref="switcher" class="schedule-switcher surface" aria-label="排班类型">
        <div role="tablist" aria-label="选择检查排班类型" class="schedule-tabs">
          <button
            v-for="mode in modes"
            :id="'schedule-tab-' + mode.key"
            :key="mode.key"
            type="button"
            role="tab"
            :aria-label="mode.label"
            :aria-selected="activeMode === mode.key"
            :aria-controls="'schedule-panel-' + mode.key"
            :tabindex="activeMode === mode.key ? 0 : -1"
            @click="activeMode = mode.key"
            @keydown="onTabKeydown($event, mode.key)"
          >
            {{ mode.label }}<small>{{ mode.period }}</small>
          </button>
        </div>
        <div class="switcher-actions">
          <button
            type="button"
            class="return-filters"
            :aria-controls="'schedule-panel-' + activeMode"
            aria-label="返回周期与筛选"
            @click="scrollToFilters"
          >
            <span aria-hidden="true">↑</span> 筛选
          </button>
        </div>
      </nav>
      <KeepAlive :max="3">
        <InspectionSchedulePanel :key="activeMode + ':' + refreshKey" :mode="activeMode" />
      </KeepAlive>
      <details class="schedule-help surface">
        <summary>统计口径与使用说明</summary>
        <p>
          上方三类指标按当前筛选站点互斥计数：全部应检表都有记录才算“已检查”，尚未检查的应检表全已安排才算“已排班”，其余为“待排班”。部分已检查和需补排可另行筛选；不适用的计量视频格不计入应检，缺失、停用或重复定义的检查表会提示异常。这里的整站完成不同于自动派工的片区触达覆盖率，后者仍以任一现场检查记录计触达，不改变原派工算法。
        </p>
        <p>
          计量年度计划按月配置片区站数；任一适用计量检查项有记录即计已查，同站去重，未审核也计数。圆环显示年度已查站点占全部纳入站点的覆盖率，本月目标和本月已查另列，避免混淆周期。今日及未来计量安排预留配额但不算实绩，过期未完成的安排释放预留。年度派站同步季度现场；季度派站只在片区当月尚有配额或本站已纳入本月计量安排时联动年度，已开始站点及关联的同组同日计划不可改派。配置变更不追溯撤销已保存派工。
        </p>
        <p>
          普通现场按季度覆盖六张表，计量现场按年度覆盖现场及必要的视频表，普通视频按月覆盖三张表。年度计量与季度现场共用155站名单和外勤组，年度视频仅用于监控未运行站点。实际展示遵循站点“纳入现场/视频计划”设置。获授权用户均查看同一份排班，不按数据范围过滤。
        </p>
        <p>
          绿色表示已有巡检记录，并非问题已审核、已整改；零问题记录同样计数。多人参与按人员去重，可点击查看全部姓名。删除或移走记录后，若已无对应记录，回到原保存排班或待排班状态。
        </p>
        <p>
          未启用、缺失或重复定义的检查表列不可安排。现场选择人员档期已保存的完整外勤组；视频整站由一位检查人完成安全、计量、现场。本站任一适用检查项已检查即整行只读，包括编辑、多选、拖拽及一键清空；季度与年度中同组同日的联动计划也锁定。过期未检查计划变黄，但原派工信息和个人视频待办仍保留。排班全局共享，保存操作人与时间，整批校验；切换筛选清空勾选，避免误改隐藏项目。
        </p>
        <p>
          今日智能排班基于人员档期已保存的现场组和视频人员，忽略今日未开始的手动派工来计算方案。现场默认每组2站、视频每人3站，可调整1至10站，已开始的今日站点计入该组/人的数量。确认替换范围后，同事务撤下今日未开始的安排并应用方案；已开始整行、原始记录及其他日期计划保留，失败全部回滚。现场先补当月计量目标，再均衡季度片区覆盖，最后按高德预计驾车时间组合站点；同耗时再参考行驶距离，不使用直线距离。实际派工在“今日已确认排班”独立窗口按现场/视频查看，右上角“今日安排”仍为个人待办。
        </p>
      </details>
    </template>
    <div v-else class="surface denied">当前账号无权查看巡检排班，请联系Root分配查看权限。</div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import InspectionSchedulePanel from '@/components/InspectionSchedulePanel.vue'
import AutomaticSchedule from '@/components/AutomaticSchedule.vue'
import MeteringAnnualPlan from '@/components/MeteringAnnualPlan.vue'
import TodayInspectionDispatch from '@/components/TodayInspectionDispatch.vue'
import { scrollScheduleToFilters } from '@/utils/scheduleViewport'
const refreshKey = ref(0),
  dispatchNotice = ref('')
function onScheduled(data) {
  refreshKey.value++
  activeMode.value = 'offline'
  dispatchNotice.value = `${data.day} ${data.strategy === 'replace_today' ? '今日智能方案已应用' : '排班已保存'}，本次安排 ${data.groups.length} 个站点任务，已同步个人待办；已开始站点及其他日期计划保持不变。`
}
const modes = [
  { key: 'offline', label: '现场检查排班', period: '按季度' },
  { key: 'annual', label: '计量现场排班', period: '按年度' },
  { key: 'online', label: '视频检查排班', period: '按月份' },
]
const activeMode = ref('offline')
const switcher = ref(null)
const switcherHeight = ref(76)
let switcherObserver
async function scrollToFilters() {
  await nextTick()
  scrollScheduleToFilters(document.getElementById('schedule-panel-' + activeMode.value))
}
watch(activeMode, scrollToFilters)
async function onTabKeydown(event, key) {
  const index = modes.findIndex((mode) => mode.key === key)
  const nextIndex =
    event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? modes.length - 1
        : event.key === 'ArrowRight'
          ? (index + 1) % modes.length
          : event.key === 'ArrowLeft'
            ? (index + modes.length - 1) % modes.length
            : -1
  if (nextIndex < 0) return
  event.preventDefault()
  activeMode.value = modes[nextIndex].key
  await nextTick()
  document.getElementById('schedule-tab-' + activeMode.value)?.focus({ preventScroll: true })
}
onMounted(() => {
  if (!switcher.value) return
  switcherObserver = new ResizeObserver(() => {
    switcherHeight.value = Math.ceil(switcher.value.getBoundingClientRect().height)
  })
  switcherObserver.observe(switcher.value)
})
onBeforeUnmount(() => switcherObserver?.disconnect())
let permissions = {}
try {
  permissions = JSON.parse(localStorage.getItem('permissions') || '{}') || {}
} catch {
  /* Route and API also enforce permissions. */
}
const allowed =
  (localStorage.getItem('user_role') || localStorage.getItem('role')) === 'root' ||
  Boolean(permissions.view_inspection_schedule)
</script>

<style scoped>
.schedule-page {
  display: grid;
  gap: 18px;
  min-width: 0;
  container-type: inline-size;
  /* Offset the shell's content padding so rows cannot show above the sticky bar. */
  --schedule-sticky-top: -24px;
  --schedule-mobile-topbar: 0px;
  color: #18324c;
}
.surface {
  border: 1px solid #dbe5ef;
  border-radius: 20px;
  padding: 22px;
  background: #fff;
  box-shadow: 0 12px 30px #18324c08;
}
.schedule-page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  background:
    radial-gradient(ellipse at 90% 0, #296d87 0, transparent 55%),
    linear-gradient(115deg, #102e4c, #194763);
  color: #fff;
  border-color: #173f5d;
  border-bottom: 4px solid #e7ae42;
}
.kicker {
  font-size: 11px;
  letter-spacing: 1px;
  color: #9bd6e2;
  font-weight: 750;
}
h2 {
  margin: 10px 0;
  font-size: 30px;
  letter-spacing: 2px;
}
.schedule-page-head p {
  color: #c2d5e4;
}
p {
  margin: 8px 0 0;
  color: #62748a;
  font-size: 13px;
  line-height: 1.85;
}
.access-label {
  flex-shrink: 0;
  padding: 8px 12px;
  border: 1px solid #ffffff3b;
  border-radius: 9px;
  color: #d3e8f2;
  background: #ffffff12;
  font-size: 12px;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.head-actions :deep(.plan-trigger),
.head-actions :deep(.auto-trigger),
.head-actions :deep(.today-dispatch-trigger) {
  box-sizing: border-box;
  height: 44px;
  padding: 0 18px;
  font-size: 13px;
  line-height: 1.4;
  border-radius: 12px;
  font-weight: 600;
  transition: background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}
.head-actions :deep(.plan-trigger) {
  background: #f2f5f8;
  color: #294b65;
  border-color: #dce5ed;
}
.head-actions :deep(.plan-trigger:hover:not(:disabled)) {
  background: #e5edf4;
  border-color: #b9cbd9;
}
.head-actions :deep(.today-dispatch-trigger) {
  background: #d8f0ea;
  color: #17665f;
  border-color: #b9ded4;
}
.head-actions :deep(.today-dispatch-trigger:hover:not(:disabled)) {
  background: #c5e7de;
  border-color: #8fc6b8;
}
.head-actions :deep(.auto-trigger) {
  background: #3479ce;
  color: #fff;
  border-color: #3479ce;
}
.head-actions :deep(.auto-trigger:hover:not(:disabled)) {
  background: #2b68b4;
  border-color: #2b68b4;
  box-shadow: 0 3px 10px #061f3b26;
}
.head-actions :deep(.plan-trigger:focus-visible),
.head-actions :deep(.today-dispatch-trigger:focus-visible),
.head-actions :deep(.auto-trigger:focus-visible) {
  outline: 2px solid #e5f4ff;
  outline-offset: 3px;
}
.dispatch-notice {
  margin: 0;
  padding: 12px 18px;
  background: #eaf7f0;
  border: 1px solid #cae7d7;
  border-radius: 10px;
  color: #307651;
}
.schedule-guide {
  padding: 16px 22px;
  border-left: 4px solid #1c738d;
}
.schedule-guide strong {
  font-size: 14px;
}
.schedule-switcher {
  position: sticky;
  top: var(--schedule-sticky-top);
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 14px;
  box-shadow: 0 6px 20px #18324c12;
}
.schedule-tabs {
  display: flex;
  gap: 6px;
  min-width: 0;
}
.schedule-tabs button {
  border: 1px solid transparent;
  border-radius: 9px;
  padding: 10px 16px;
  background: #f4f7fb;
  color: #62748a;
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}
.schedule-tabs button[aria-selected='true'] {
  border-color: #1e6786;
  background: #1e6786;
  color: #fff;
  box-shadow: 0 3px 8px #16476420;
}
.schedule-tabs button:focus-visible {
  outline: 2px solid #397bc1;
  outline-offset: 2px;
}
.schedule-tabs small {
  margin-left: 10px;
  font-size: 11px;
  font-weight: 400;
}
.switcher-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.return-filters {
  padding: 9px 10px;
  border: 1px solid #dbe5ef;
  border-radius: 8px;
  color: #426b96;
  background: #fff;
  font: inherit;
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
}
.return-filters:hover {
  background: #f2f7fd;
}
.return-filters:focus-visible {
  outline: 2px solid #397bc1;
  outline-offset: 2px;
}
.legend {
  display: inline-block;
  width: 10px;
  height: 10px;
  margin: 0 6px 0 12px;
  border-radius: 3px;
}
.legend:first-child {
  margin-left: 0;
}
.done {
  background: #6ab98b;
}
.planned {
  width: 20px;
  background: #ce625e;
}
.overdue {
  background: #e1b640;
}
.schedule-help summary {
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}
.denied {
  text-align: center;
  padding: 60px 20px;
}
@media (max-width: 900px) {
  .schedule-page {
    --schedule-sticky-top: -16px;
    --schedule-mobile-topbar: 58px;
  }
}
@container (max-width: 760px) {
  .schedule-tabs {
    flex: 1;
  }
  .schedule-tabs button {
    flex: 1;
    padding: 10px 6px;
    font-size: 13px;
  }
  .schedule-tabs small {
    display: block;
    margin: 4px 0 0;
  }
}
@media (max-width: 700px) {
  .surface {
    padding: 16px;
    border-radius: 15px;
  }
  .schedule-page-head {
    align-items: flex-start;
    flex-direction: column;
  }
  h2 {
    font-size: 26px;
  }
  .access-label {
    font-size: 11px;
  }
  .schedule-switcher {
    padding: 8px;
  }
}
</style>
