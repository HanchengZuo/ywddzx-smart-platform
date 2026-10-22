<template>
  <section class="dispatch-details" aria-label="派工进度与实绩详情">
    <p v-if="cell.actuals_pending" class="release-note" role="status">
      当日实绩将在上海时间 17:00
      后自动核对；现在按原档期和计划排班，不因早间录入记录锁定。巡检记录和任务销项仍实时更新。
    </p>
    <div v-if="cell.actual_modes?.length" class="actuals-summary" aria-label="现场与视频实绩">
      <div v-for="item in cell.actual_modes" :key="item.mode" :class="item.mode">
        <span>{{ item.mode === 'offline' ? '现场巡检实绩' : '视频巡检实绩' }}</span>
        <strong>{{ item.count }}<small> 张检查表记录</small></strong>
      </div>
      <p>
        包含原派工对应记录及本人当日录入 /
        参与记录，按巡检记录去重。两类实绩独立保留，不覆盖原安排。
      </p>
    </div>
    <p v-if="assignment" class="original-assignment">原分组：{{ assignment.group_name }}</p>
    <div v-if="summary.total" class="progress-summary">
      <div>
        <span>检查表完成</span
        ><strong
          >{{ summary.completed }}<small> / {{ summary.total }} 项</small></strong
        >
      </div>
      <div>
        <span>站点全部完成</span
        ><strong
          >{{ summary.station_completed }}<small> / {{ summary.station_total }} 站</small></strong
        >
      </div>
      <div
        class="progress-track"
        role="progressbar"
        :aria-valuenow="summary.completed"
        :aria-valuemax="summary.total"
        aria-valuemin="0"
        aria-label="委派检查表完成进度"
      >
        <i :style="{ width: summary.percent + '%' }"></i>
      </div>
      <p>
        按原委派站点、检查表及计划日起的巡检记录核对，不要求审核，也不以录入人是否为组员判定。现场待办次日归档不等于实际完成。
      </p>
    </div>
    <details
      v-for="group in groups"
      :key="group.key"
      class="station-progress"
      :open="groups.length === 1"
    >
      <summary class="station-progress-head">
        <div>
          <small>{{ group.mode === 'offline' ? '现场巡检' : '视频巡检' }}</small>
          <h4>{{ group.station_name }}</h4>
        </div>
        <span
          >{{ group.tasks.filter((t) => t.record_count).length }} /
          {{ group.tasks.length }} 项完成</span
        >
      </summary>
      <div class="station-checks">
        <div v-for="task in group.tasks" :key="task.id" class="dispatch-task">
          <div class="task-title">
            <strong>{{ task.table_name }}</strong
            ><span :class="task.record_count ? 'done' : 'pending'">{{
              task.record_count ? '已完成' : '未完成'
            }}</span>
          </div>
          <p v-if="task.plan_team" class="team-evidence">
            {{ task.plan_team.name }} ·
            {{ task.plan_team.members.map((p) => p.display_name).join('、') }}
          </p>
          <p class="dispatch-meta">
            原派工：{{ task.assigned_by_name }} · {{ task.assigned_at
            }}<span>计划日期 {{ task.day }}</span>
          </p>
          <ul v-if="task.records.length" class="record-list">
            <li v-for="record in task.records" :key="record.id">
              <b>巡检记录 #{{ record.id }}</b
              ><span>{{ record.day }} · {{ record.inspector_name }}</span>
            </li>
          </ul>
          <p v-else class="pending-note">
            {{
              !task.station_id || !task.table_id
                ? '站点或检查表已删除，原派工信息仍保留。'
                : cell.actuals_pending
                  ? '当日记录待 17:00 后统一核对。'
                  : '尚未发现对应巡检记录。'
            }}
          </p>
        </div>
      </div>
    </details>
    <details v-if="cancelled.length" class="dispatch-history">
      <summary>已撤销 / 改派的原始任务（{{ cancelled.length }}）</summary>
      <article v-for="task in cancelled" :key="task.id">
        <strong>{{ task.station_name }} · {{ task.table_name }}</strong>
        <p>
          {{ task.plan_team?.name || (task.mode === 'offline' ? '现场巡检' : '视频巡检') }} · 原计划
          {{ task.day }}
        </p>
        <p v-if="task.plan_team?.members?.length">
          原组员：{{ task.plan_team.members.map((p) => p.display_name).join('、') }}
        </p>
        <p>
          {{ task.assigned_by_name }}于{{ task.assigned_at }}委派；{{
            task.cancelled_at || '后续调整时'
          }}撤销 / 改派。此任务不计入当前进度。
        </p>
      </article>
    </details>
    <details v-if="records.length" class="dispatch-history" :open="!tasks.length">
      <summary>本人当日录入 / 参与的巡检记录（{{ records.length }}）</summary>
      <article v-for="record in records" :key="record.id">
        <strong>{{ record.station_name }} · {{ record.table_name }}</strong>
        <p>巡检记录 #{{ record.id }} · {{ record.day }} · {{ record.inspector_name }}</p>
      </article>
    </details>
    <p v-if="!tasks.length && !records.length" class="no-tasks">
      {{
        assignment
          ? assignment.group_name + '：当天已分组，尚无站点委派记录。'
          : '当天尚无站点委派或实际巡检记录。'
      }}
    </p>
  </section>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({
  cell: { type: Object, required: true },
  records: { type: Array, default: () => [] },
})
const tasks = computed(() => props.cell.tasks || [])
const assignment = computed(() => props.cell.daily_assignment)
const summary = computed(() => props.cell.dispatch || {})
const cancelled = computed(() => tasks.value.filter((t) => t.status === 'cancelled'))
const groups = computed(() => {
  const rows = new Map()
  for (const task of tasks.value.filter((t) => t.status !== 'cancelled')) {
    const key = `${task.mode}:${task.station_id}:${task.station_name}`
    if (!rows.has(key)) rows.set(key, { ...task, key, tasks: [] })
    rows.get(key).tasks.push(task)
  }
  return [...rows.values()]
})
</script>
<style scoped>
.dispatch-details {
  margin: 16px 0;
  min-width: 0;
}
.release-note {
  padding: 12px 14px;
  border: 1px solid #c6ddec;
  border-radius: 10px;
  background: #f0f8fd;
  color: #34657f;
  font-size: 12px;
  line-height: 1.8;
}
.actuals-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 14px;
}
.actuals-summary > div {
  flex: 1 1 160px;
  min-width: 0;
  padding: 14px;
  border: 1px solid #dfc79e;
  border-radius: 10px;
  background: #fff6e6;
  color: #835516;
}
.actuals-summary > .online {
  background: #eaf3ff;
  border-color: #bcd4ed;
  color: #235e9d;
}
.actuals-summary span {
  display: block;
  font-size: 12px;
}
.actuals-summary strong {
  display: block;
  font-size: 24px;
  margin-top: 6px;
}
.actuals-summary small {
  font-size: 11px;
  font-weight: 400;
}
.actuals-summary > p,
.original-assignment {
  width: 100%;
  margin: 0;
  color: #597487;
  font-size: 11px;
  line-height: 1.8;
}
.progress-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
  background: #eef6fc;
  border: 1px solid #d0e1ee;
  border-radius: 12px;
}
.progress-summary > div > span {
  display: block;
  font-size: 11px;
  color: #57758c;
}
.progress-summary strong {
  display: block;
  margin-top: 6px;
  font-size: 25px;
  color: #185475;
}
.progress-summary small {
  font-size: 12px;
  font-weight: 500;
}
.progress-track {
  grid-column: 1 / -1;
  height: 7px;
  border-radius: 6px;
  background: #d0e0ec;
  overflow: hidden;
}
.progress-track i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #1e6786, #18a08c);
}
.progress-summary p {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 11px;
  line-height: 1.8;
  color: #617d90;
}
.station-progress {
  border: 1px solid #d5e1ec;
  border-radius: 12px;
  overflow: hidden;
  margin-top: 14px;
}
.station-progress-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: #f2f6fa;
}
.station-progress-head small {
  font-size: 10px;
  color: #6d8497;
}
h4 {
  font-size: 15px;
  color: #244f6c;
  margin: 4px 0 0;
}
.station-progress-head > span {
  font-size: 11px;
  color: #4f7386;
  white-space: nowrap;
}
.station-checks {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.station-checks > .dispatch-task {
  min-width: 0;
  border-right: 1px solid #e0e8f0;
}
@media (max-width: 900px) {
  .station-checks {
    grid-template-columns: 1fr;
  }
}
.dispatch-task {
  padding: 12px 14px;
  border-top: 1px solid #e0e8f0;
}
.task-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}
.task-title strong {
  font-size: 12px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.task-title > span {
  padding: 4px 6px;
  border-radius: 5px;
  font-size: 10px;
  white-space: nowrap;
}
.done {
  background: #dbf2e8;
  color: #187a55;
}
.pending {
  background: #fff0d5;
  color: #9a641f;
}
.team-evidence {
  font-size: 11px;
  line-height: 1.8;
  color: #476e82;
}
.dispatch-meta {
  color: #748b9d;
  font-size: 10px;
  line-height: 1.8;
  margin: 8px 0;
}
.dispatch-meta span {
  display: block;
}
.record-list {
  list-style: none;
  padding: 0;
  margin: 8px 0 0;
}
.record-list li {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  flex-wrap: wrap;
  padding: 7px 10px;
  background: #edf8f3;
  border-radius: 6px;
  margin-top: 4px;
  font-size: 11px;
  color: #39745d;
}
.pending-note,
.no-tasks {
  color: #8798a7;
  font-size: 11px;
  line-height: 1.8;
  margin: 8px 0 0;
}
.dispatch-history {
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid #d8e2eb;
  border-radius: 10px;
}
summary {
  cursor: pointer;
  font-size: 12px;
  font-weight: 650;
  color: #365a76;
}
.dispatch-history article {
  padding-top: 12px;
  font-size: 11px;
  overflow-wrap: anywhere;
}
.dispatch-history p {
  margin: 6px 0;
  line-height: 1.8;
  color: #7c91a3;
}
@media (max-width: 400px) {
  .progress-summary {
    padding: 12px;
  }
  .dispatch-task {
    padding: 10px;
  }
}
</style>
