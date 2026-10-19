<template>
  <div class="schedule-page">
    <header class="schedule-page-head surface">
      <div>
        <span class="kicker">排班系统 / INSPECTION SCHEDULE</span>
        <h2>巡检计划</h2>
        <p>按站点、按检查表安排检查人，巡检记录自动反映实际检查情况。</p>
      </div>
      <span class="access-label">{{ allowed ? '查看与编辑独立授权' : '需要查看权限' }}</span>
    </header>
    <template v-if="allowed">
      <div class="schedule-guide surface">
        <strong>计划与实绩，分开呈现</strong>
        <p>
          <span class="legend done"></span
          >黄色为本周期已有巡检记录，不论是否审核，均锁定为实际检查人。<span
            class="legend planned"
          ></span
          >蓝色为手动安排；无记录时才可调整，暂不推送待办任务。
        </p>
      </div>
      <InspectionSchedulePanel mode="offline" />
      <InspectionSchedulePanel mode="online" />
      <details class="schedule-help surface">
        <summary>统计口径与使用说明</summary>
        <p>
          现场以自然季度覆盖六张检查表，不包含年度覆盖的计量现场检查。视频以自然月覆盖安全、计量、现场三张检查表。两张表各用独立的固定站点名单和顺序；只显示账号范围内、且在站点档案中已纳入对应计划的站点。
        </p>
        <p>
          黄色表示已有巡检记录，并非问题已审核、已整改或检查人已完成流程确认；零问题记录同样计数。多人参与按人员去重，可点击单元格查看全部姓名。删除或移走记录后，若已无对应记录，单元格回到原保存排班或待排班状态。
        </p>
        <p>
          未启用、缺失、重复定义或不在权限范围内的检查表列不可安排。排班选择范围仅为启用的督导组管理人员和督导组组员。排班全局共享，保存记录操作人、时间及修改历史；多人同时修改同一格会提示冲突，不静默覆盖。页面可见、联网时每分钟核对实绩，切换周期自动加载。
        </p>
      </details>
    </template>
    <div v-else class="surface denied">当前账号无权查看巡检计划，请联系Root分配查看权限。</div>
  </div>
</template>

<script setup>
import InspectionSchedulePanel from '@/components/InspectionSchedulePanel.vue'
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
.schedule-guide {
  padding: 16px 22px;
}
.schedule-guide strong {
  font-size: 14px;
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
}
</style>
