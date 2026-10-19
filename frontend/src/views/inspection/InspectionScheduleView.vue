<template>
  <div class="schedule-page" :style="{ '--schedule-switcher-height': switcherHeight + 'px' }">
    <header class="schedule-page-head surface">
      <div>
        <span class="kicker">排班系统 / INSPECTION SCHEDULE</span>
        <h2>巡检排班</h2>
        <p>按站点、按检查表安排检查人，巡检记录自动反映实际检查情况。</p>
      </div>
      <div class="head-actions">
        <AutomaticSchedule v-if="allowed" @scheduled="onScheduled" /><span class="access-label">{{
          allowed ? '查看与编辑独立授权' : '需要查看权限'
        }}</span>
      </div>
    </header>
    <template v-if="allowed">
      <div class="schedule-guide surface">
        <strong>计划与实绩，分开呈现</strong>
        <p>
          <span class="legend done"></span
          >黄色为本周期已有巡检记录，不论是否审核，均锁定为实际检查人。<span
            class="legend planned"
          ></span
          >蓝色为已安排；无记录时可调整，保存日期和检查人后同步个人待办。
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
          <span class="switcher-hint">全部站点展开 · 切换保留各自筛选</span>
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
      <KeepAlive :max="2">
        <InspectionSchedulePanel :key="activeMode + ':' + refreshKey" :mode="activeMode" />
      </KeepAlive>
      <details class="schedule-help surface">
        <summary>统计口径与使用说明</summary>
        <p>
          现场以自然季度覆盖六张检查表，不包含年度覆盖的计量现场检查。视频以自然月覆盖安全、计量、现场三张检查表。两张表各用独立的固定站点名单和顺序；只显示账号范围内、且在站点档案中已纳入对应计划的站点。
        </p>
        <p>
          黄色表示已有巡检记录，并非问题已审核、已整改或检查人已完成流程确认；零问题记录同样计数。多人参与按人员去重，可点击单元格查看全部姓名。删除或移走记录后，若已无对应记录，单元格回到原保存排班或待排班状态。
        </p>
        <p>
          未启用、缺失、重复定义或不在权限范围内的检查表列不可安排。选择计划工作日后，只能安排人员档期中明确有空且当天没有另一种检查的人员。未补日期的历史排班仍保留，但不会猜测日期生成待办；调整并保存后生效。排班全局共享，保存操作人与时间，批量更新整批校验；多选支持按格、按站或按列，切换筛选清空勾选，避免误改隐藏项目。
        </p>
        <p>
          今日一键排班先预览再确认，按本自然季度的现场、视频站点任务组尽量平衡，每人当天自动安排一个站点，不覆盖已有安排。个人待办包括今日和逾期任务，同站同表有本周期巡检记录即自动完成，不依赖审核或录入人；没有完成记录不会因跨天或跨周期自动销项。提前检查和跨周期补做也可完成，实际执行人以记录为准。
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
const refreshKey = ref(0),
  dispatchNotice = ref('')
function onScheduled(data) {
  refreshKey.value++
  activeMode.value = 'offline'
  dispatchNotice.value = `${data.day} 已安排 ${data.groups.length} 个站点任务组、${data.cell_count} 个单元格，已同步个人待办。`
}
const modes = [
  { key: 'offline', label: '现场检查排班', period: '按季度' },
  { key: 'online', label: '视频检查排班', period: '按月份' },
]
const activeMode = ref('offline')
const switcher = ref(null)
const switcherHeight = ref(76)
let switcherObserver
async function scrollToFilters() {
  await nextTick()
  document.getElementById('schedule-panel-' + activeMode.value)?.scrollIntoView({ block: 'start' })
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
  background: linear-gradient(125deg, #f4f9ff, #fff 65%);
}
.kicker {
  font-size: 11px;
  letter-spacing: 1px;
  color: #2769a0;
  font-weight: 750;
}
h2 {
  margin: 10px 0;
  font-size: 30px;
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
  border: 1px solid #dbe6f4;
  border-radius: 9px;
  color: #4b6c8c;
  background: #f7faff;
  font-size: 12px;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
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
  border-color: #bed5ef;
  background: #eaf3ff;
  color: #215c9e;
  box-shadow: inset 0 -2px #397bc1;
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
.switcher-hint {
  font-size: 11px;
  color: #788ba1;
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
  background: #f1c75b;
}
.planned {
  background: #74a7e5;
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
  .switcher-hint {
    display: none;
  }
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
