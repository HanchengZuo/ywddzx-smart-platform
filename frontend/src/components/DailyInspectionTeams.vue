<template>
  <button type="button" class="team-trigger" @click="open">
    {{ canEdit ? '一键安排今日巡检' : '查看今日巡检分组' }}
  </button>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="team-dialog"
      aria-labelledby="daily-team-title"
      @cancel.prevent="close"
      @click="backdrop"
    >
      <header>
        <div>
          <small>DAILY INSPECTION TEAMS</small>
          <h3 id="daily-team-title">
            今日巡检安排 <span>{{ context?.day }}</span>
          </h3>
        </div>
        <button type="button" :disabled="saving" aria-label="关闭今日巡检安排" @click="close">
          ×
        </button>
      </header>
      <div class="team-body">
        <p class="method">
          今日未设置的档期默认有空，提前设置的没空及原因保持不变；仅安排有空且账号匹配的人员。上海时间
          17:00
          前的当日记录不阻止分组，已有站点派工仍须保留。先确定管理人员分工，再随机分配大学生。每个外勤组至少1人拥有准驾证，优先配2人；不足时不生成无持证人员的组。此处保存人员分组，具体站点与检查表仍在巡检排班安排。
        </p>
        <p v-if="loading" role="status" class="empty">正在核对今日档期与已有安排…</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <template v-if="context">
          <p v-if="context.unconfirmed?.length" class="warning" role="status">
            今日档期已确认 {{ context.confirmed_count }}/{{ context.total_count }} 人。请先为
            {{ context.unconfirmed.join('、') }} 选择有空或没空，全部确认后才能一键安排。
          </p>
          <p v-if="!context.working" class="warning">今天不是已发布的工作日，不能新安排巡检。</p>
          <details
            v-if="editable && context.working"
            class="manager-step"
            :open="!displayGroups.length"
          >
            <summary class="step-heading">
              <b>01</b>
              <div>
                <strong>确定管理人员分工</strong
                ><small
                  >今天有空的 {{ managers.length }} 位管理人员 ·
                  {{ students.length }} 位大学生</small
                >
              </div>
            </summary>
            <div v-for="person in managers" :key="person.id" class="manager-row">
              <div>
                <strong>{{ person.display_name }} <em v-if="person.has_driving_permit" class="permit-tag">准驾证</em></strong
                ><small v-if="lockedMode(person)"
                  >已有{{
                    lockedMode(person) === 'offline' ? '现场' : '视频'
                  }}站点安排或实绩，不可冲突</small
                >
              </div>
              <select
                v-model="managerModes[person.id]"
                :disabled="loading || saving"
                :aria-label="person.display_name + '今日巡检方式'"
                @change="invalidate"
              >
                <option value="">请选择分工</option>
                <option value="offline" :disabled="lockedMode(person) === 'online'">
                  现场巡检 · 带队
                </option>
                <option value="online" :disabled="lockedMode(person) === 'offline'">
                  视频巡检 · 内勤
                </option>
              </select>
            </div>
            <p v-if="!managers.length" class="warning">
              今天没有有空的管理人员，大学生只能安排视频巡检，不会形成无带队人的外勤组。
            </p>
            <p class="method">
              准驾证安全要求优先：现场组至少1人持证，条件允许时优先配2人，再尽量均分现场、视频人数及各组人数。已有站点安排或实绩优先保留，因此受约束时可能无法完全均分。请先在用户数据管理维护准驾证属性，未配置视为无证。
            </p>
            <button
              type="button"
              class="primary"
              :disabled="!ready || loading || saving"
              @click="createPreview"
            >
              {{ preview ? '重新随机分组' : '平均随机分组' }}
            </button>
          </details>
          <section class="result-step">
            <div class="step-heading">
              <b>02</b>
              <div>
                <strong>{{ preview ? '待确认的分组预览' : '已保存的今日分组' }}</strong
                ><small>{{
                  preview
                    ? '可拖动大学生调整分组，点击确认安排后统一保存'
                    : context.updated_at
                      ? context.updated_by_name + ' · ' + context.updated_at + ' 保存'
                      : '今日尚未安排分组'
                }}</small>
              </div>
            </div>
            <div v-if="displayGroups.length" class="team-groups">
              <article
                v-for="group in displayGroups"
                :key="group.name"
                :class="[group.mode, { 'drop-active': draggingStudent || selectedStudent }]"
                @dragover.prevent
                @drop.prevent="dropStudent(group, $event)"
              >
                <header>
                  <strong>{{ group.name }}</strong
                  ><span>{{ group.members.length }} 人</span>
                </header>
                <p v-if="group.mode === 'offline'" class="driver-status" :class="{ unsafe: !driverCount(group), preferred: driverCount(group) >= 2 }">{{ driverCount(group) ? driverCount(group) + ' 人拥有准驾证' + (driverCount(group) >= 2 ? ' · 优选配置' : ' · 已满足最低要求') : '缺少持准驾证人员 · 不可确认或派现场任务' }}</p>
                <div class="member-tags">
                  <button
                    v-for="person in group.members"
                    :key="person.id"
                    type="button"
                    :draggable="editable && !loading && !saving && person.position === '大学生'"
                    :disabled="!editable || loading || saving || person.position !== '大学生'"
                    :aria-label="
                      person.display_name +
                      (person.position === '大学生' ? '，点击或拖动调整分组' : '，管理人员固定带队')
                    "
                    :class="{
                      leader: person.id === group.leader_id,
                      selected: selectedStudent === person.id,
                    }"
                    :aria-pressed="
                      person.position === '大学生' ? selectedStudent === person.id : undefined
                    "
                    @dragstart="startStudentDrag($event, person)"
                    @dragend="draggingStudent = null"
                    @click="selectedStudent = selectedStudent === person.id ? null : person.id"
                  >
                    {{ person.display_name
                    }}<small v-if="person.id === group.leader_id">带队</small><small v-if="person.has_driving_permit" class="permit-tag">准驾</small>
                  </button>
                </div>
                <button
                  v-if="selectedStudent"
                  type="button"
                  class="move-here"
                  :disabled="saving"
                  @click="dropStudent(group)"
                >
                  移至{{ group.name }}
                </button>
              </article>
            </div>
            <p v-if="editable && displayGroups.length" class="method move-help" role="status">
              {{
                saving
                  ? '正在保存分组调整…'
                  : preview
                    ? '拖动大学生姓名到其他组调整预览；手机或键盘可先点姓名，再点目标组“移至”。调整暂不保存，确认安排后统一生效；人工调整不强制各组人数相同。'
                    : '拖动大学生姓名到其他组即可保存；手机或键盘可先点姓名，再点目标组“移至”。外勤组换人同步未检查的站点计划及待办；已派站人员跨现场/视频调组前需先撤销原派站。'
              }}
              <button v-if="selectedStudent" type="button" @click="selectedStudent = null">
                取消选择
              </button>
            </p>
            <p v-else-if="!displayGroups.length" class="empty">
              {{
                editable ? '完成上方管理人员分工后，点击平均随机分组。' : '今日暂未保存巡检分组。'
              }}
            </p>
            <p v-if="preview && !displayGroups.some((g) => g.mode === 'offline')" class="warning">
              没有现场带队管理人员，本次大学生全部安排视频巡检。
            </p>
            <p v-if="unsafeGroups.length" class="error" role="alert">{{ unsafeGroups.map(g => g.name).join('、') }}尚无持准驾证成员。请调整预览；已保存分组请先维护人员准驾证资料或调整成员，不能派现场任务。</p>
          </section>
          <details v-if="context.excluded.length" class="excluded">
            <summary>未参与安排的人员（{{ context.excluded.length }}）</summary>
            <span v-for="person in context.excluded" :key="person.name"
              >{{ person.name }} · {{ person.reason }}</span
            >
          </details>
        </template>
      </div>
      <footer>
        <span></span><button type="button" :disabled="saving" @click="close">关闭</button
        ><button
          v-if="editable"
          type="button"
          class="primary"
          :disabled="!preview || !ready || loading || saving || unsafeGroups.length > 0"
          @click="confirm"
        >
          {{ saving ? '保存中…' : '确认安排' }}
        </button>
      </footer>
    </dialog>
  </Teleport>
</template>
<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, ref } from 'vue'
import { fieldDriverCount, movePreviewStudent } from '@/utils/dailyTeamPreview'
const props = defineProps({ canEdit: { type: Boolean, default: false } })
const emit = defineEmits(['saved', 'opened', 'closed'])
const dialog = ref(null),
  context = ref(null),
  preview = ref(null),
  managerModes = ref({}),
  loading = ref(false),
  saving = ref(false),
  error = ref('')
const editable = computed(() => props.canEdit && context.value?.can_edit)
const managers = computed(() =>
  (context.value?.people || []).filter((p) => p.position === '管理人员'),
)
const students = computed(() =>
  (context.value?.people || []).filter((p) => p.position === '大学生'),
)
const ready = computed(
  () =>
    context.value?.working &&
    context.value.unconfirmed?.length === 0 &&
    context.value.people.length &&
    managers.value.every((p) => managerModes.value[p.id]),
)
const displayGroups = computed(() => {
  const groups = preview.value?.groups || context.value?.groups || []
  return editable.value && groups.length && !groups.some((g) => g.mode === 'online')
    ? [...groups, { name: '内勤视频组', mode: 'online', leader_id: null, members: [] }]
    : groups
})
const driverCount = (group) => fieldDriverCount(group, context.value?.people)
const unsafeGroups = computed(() => displayGroups.value.filter(group => group.mode === 'offline' && !driverCount(group)))
const draggingStudent = ref(null),
  selectedStudent = ref(null)
function startStudentDrag(event, person) {
  if (!editable.value || loading.value || saving.value || person.position !== '大学生') {
    event.preventDefault()
    return
  }
  draggingStudent.value = person.id
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/x-inspection-student', String(person.id))
  event.dataTransfer.setData('text/plain', person.display_name)
}
async function dropStudent(group, event) {
  const studentId =
    draggingStudent.value ||
    Number(event?.dataTransfer?.getData('application/x-inspection-student')) ||
    selectedStudent.value
  if (
    !Number.isInteger(studentId) ||
    studentId < 1 ||
    !editable.value ||
    loading.value ||
    saving.value
  )
    return
  const source = displayGroups.value.find((g) => g.members.some((p) => p.id === studentId))
  if (!source) return
  if (source?.name === group.name) {
    draggingStudent.value = selectedStudent.value = null
    return
  }
  if (preview.value) {
    try {
      preview.value = movePreviewStudent(
        preview.value,
        context.value.people,
        studentId,
        group.leader_id,
      )
      error.value = ''
    } catch (err) {
      error.value = err.message
    }
    draggingStudent.value = selectedStudent.value = null
    return
  }
  saving.value = true
  error.value = ''
  try {
    const { data } = await axios.post(
      '/api/staff-availability/today-inspection',
      {
        action: 'move',
        day: context.value.day,
        revision: context.value.revision,
        student_id: studentId,
        leader_id: group.leader_id,
      },
      { timeout: 30000 },
    )
    await load()
    emit('saved', { ...data, adjusted: true })
    window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
  } catch (err) {
    error.value = err.response?.data?.error || '调整结果未确认，请重新打开核对。'
    await load()
  } finally {
    saving.value = false
    draggingStudent.value = selectedStudent.value = null
  }
}
let controller,
  serial = 0,
  disposed = false
function lockedMode(person) {
  const modes = [
    ...new Set([
      ...(person.station_modes || []),
      ...(person.actual_modes || []).map((m) => m.mode),
    ]),
  ]
  return modes.length === 1 ? modes[0] : ''
}
function invalidate() {
  preview.value = null
  draggingStudent.value = selectedStudent.value = null
  error.value = ''
}
async function open() {
  selectedStudent.value = draggingStudent.value = null
  context.value = null
  preview.value = null
  error.value = ''
  dialog.value.showModal()
  emit('opened')
  await load()
}
async function load() {
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  try {
    const { data } = await axios.get('/api/staff-availability/today-inspection', {
      signal: controller.signal,
      timeout: 15000,
    })
    if (ticket !== serial || disposed) return
    context.value = data
    const old = data.groups.flatMap((g) => g.members)
    managerModes.value = Object.fromEntries(
      data.people
        .filter((p) => p.position === '管理人员')
        .map((p) => [p.id, lockedMode(p) || old.find((a) => a.id === p.id)?.mode || '']),
    )
  } catch (err) {
    if (ticket === serial && !disposed && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '今日档期读取失败，请关闭后重试。'
  } finally {
    if (ticket === serial) loading.value = false
  }
}
async function createPreview() {
  if (!editable.value || !ready.value || loading.value || saving.value) return
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  preview.value = null
  draggingStudent.value = selectedStudent.value = null
  try {
    const { data } = await axios.post(
      '/api/staff-availability/today-inspection',
      {
        action: 'preview',
        day: context.value.day,
        revision: context.value.revision,
        manager_modes: managerModes.value,
      },
      { signal: controller.signal, timeout: 15000 },
    )
    if (ticket === serial && !disposed) preview.value = data
  } catch (err) {
    if (ticket === serial && !disposed && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '分组预览失败，请重新打开核对。'
  } finally {
    if (ticket === serial) loading.value = false
  }
}
async function submit(action) {
  if (!editable.value || saving.value || loading.value || (action === 'confirm' && !preview.value))
    return
  saving.value = true
  error.value = ''
  try {
    const { data } = await axios.post(
      '/api/staff-availability/today-inspection',
      {
        action,
        day: context.value.day,
        revision: context.value.revision,
        manager_modes: managerModes.value,
        seed: preview.value?.seed,
        token: preview.value?.token,
        ...(action === 'confirm' ? { student_leaders: preview.value?.student_leaders || {} } : {}),
      },
      { timeout: 30000 },
    )
    if (!disposed) {
      dialog.value.close()
      emit('closed')
      emit('saved', data)
    }
  } catch (err) {
    if (!disposed) {
      preview.value = null
      error.value =
        (err.response?.data?.error || '保存结果未能确认，请关闭后重新核对。') +
        ' 请重新打开或重新预览后操作。'
    }
  } finally {
    saving.value = false
  }
}
function confirm() {
  submit('confirm')
}
function close() {
  if (saving.value) return
  serial++
  controller?.abort()
  loading.value = false
  dialog.value?.close()
  emit('closed')
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
onBeforeUnmount(() => {
  disposed = true
  serial++
  controller?.abort()
  dialog.value?.close()
})
</script>
<style scoped>
.permit-tag { display: inline-block; font-size: 11px; font-style: normal; color: #17634b; background: #e5f5ed; border-radius: 4px; padding: 2px 5px; }
.driver-status { margin: 0 0 12px; padding: 7px 9px; background: #fff3df; color: #805019; border-radius: 6px; font-size: 12px; }
.driver-status.preferred { background: #e5f5ed; color: #17634b; }
.driver-status.unsafe { background: #fff0ed; color: #9c352a; }
.team-trigger,
.primary {
  background: #1e6786;
  color: #fff;
  border-color: #1e6786;
}
.team-trigger {
  border: 1px solid #a5d2df;
  background: #f2c35c;
  color: #173c59;
  font-weight: 750;
  white-space: nowrap;
}
button {
  font: inherit;
  font-size: 12px;
  border: 1px solid #cbd9e7;
  border-radius: 8px;
  padding: 10px 14px;
  color: #365775;
  background: #fff;
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button:focus-visible,
select:focus-visible {
  outline: 2px solid #368db4;
  outline-offset: 2px;
}
.team-dialog {
  width: min(820px, calc(100vw - 24px));
  max-height: calc(100dvh - 28px);
  padding: 0;
  margin: auto;
  border: 1px solid #cbd9e7;
  border-radius: 18px;
  box-shadow: 0 24px 80px #0d263b55;
  color: #1c3b55;
}
.team-dialog[open] {
  display: flex;
  flex-direction: column;
}
.team-dialog::backdrop {
  background: #102b4866;
  backdrop-filter: blur(4px);
}
.team-dialog > header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 22px;
  background: #163c58;
  color: #fff;
  border-bottom: 3px solid #e7ae42;
  flex-shrink: 0;
}
header small {
  color: #acd0df;
  font-size: 10px;
  letter-spacing: 1px;
}
h3 {
  font-size: 22px;
  margin: 8px 0 0;
}
h3 span {
  font-size: 13px;
  color: #bcd7e4;
  margin-left: 8px;
}
header > button {
  background: #ffffff12;
  color: #d7e9f1;
  border-color: #ffffff33;
}
.team-body {
  padding: 22px;
  overflow-y: auto;
  min-height: 0;
}
.method {
  font-size: 12px;
  line-height: 1.85;
  color: #617b92;
  margin: 0 0 16px;
}
.step-heading {
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 18px 0 12px;
}
.step-heading > b {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #e3eef5;
  color: #25637f;
  font-size: 12px;
}
.step-heading strong {
  font-size: 14px;
}
.step-heading small {
  display: block;
  font-size: 10px;
  color: #73889c;
  margin-top: 4px;
}
.manager-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid #dce6ef;
  border-radius: 8px;
  margin-bottom: 8px;
}
.manager-row strong {
  font-size: 13px;
}
.manager-row small {
  display: block;
  font-size: 10px;
  color: #987237;
  margin-top: 4px;
}
select {
  font: inherit;
  font-size: 12px;
  background: #fff;
  border: 1px solid #c4d4e3;
  color: #365775;
  border-radius: 7px;
  padding: 8px;
  max-width: 55%;
}
.manager-step {
  border-bottom: 1px solid #dae5ee;
  padding-bottom: 18px;
}
.team-groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.team-groups article {
  border: 1px solid #e6c98c;
  border-top: 3px solid #d39d3b;
  border-radius: 10px;
  background: #fff7e4;
  padding: 14px;
}
.team-groups article.online {
  border-color: #a6c4ec;
  background: #edf4ff;
  border-top-color: #3175d1;
}
.team-groups article header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  color: #895013;
  margin-bottom: 12px;
}
.team-groups article.online header {
  color: #2056a3;
}
.team-groups article strong {
  font-size: 14px;
}
.team-groups article header span {
  font-size: 11px;
}
.member-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.member-tags > button {
  border: 1px solid #d7dfe8;
  border-radius: 5px;
  background: #fff;
  padding: 5px 8px;
  font-size: 11px;
  color: #465f75;
}
.member-tags .leader {
  border-color: #d6af5d;
  color: #895013;
  font-weight: 750;
}
.member-tags > button.selected {
  outline: 2px solid #2375a7;
  outline-offset: 2px;
  box-shadow: 0 0 0 4px #d8edf6;
}
.member-tags > button:not(:disabled) {
  cursor: grab;
  border: 1px solid #bdd4e8;
}
.member-tags > button:disabled {
  opacity: 1;
  cursor: default;
}
.drop-active {
  outline: 2px dashed #8bb4d0;
  outline-offset: -4px;
}
.move-here {
  margin-top: 12px;
  background: #e5f1ff;
  color: #205c91;
}
.move-help {
  margin-top: 12px;
}
.member-tags small {
  margin-left: 5px;
  font-size: 9px;
  color: #aa741b;
}
.excluded {
  margin-top: 16px;
  font-size: 11px;
  color: #7b8fa2;
}
.excluded summary {
  cursor: pointer;
}
.excluded span {
  display: inline-block;
  margin: 10px 12px 0 0;
}
.empty {
  color: #7b8fa2;
  padding: 20px 0;
  font-size: 12px;
}
.warning,
.error {
  padding: 10px 12px;
  border-radius: 7px;
  font-size: 12px;
  line-height: 1.8;
}
.warning {
  background: #fff3d9;
  color: #976529;
}
.error {
  background: #ffedf0;
  color: #b23442;
}
footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px 22px;
  border-top: 1px solid #dce5ee;
  flex-shrink: 0;
  background: #f7faff;
}
footer > span {
  flex: 1;
}
@media (max-width: 600px) {
  .team-dialog {
    width: calc(100vw - 16px);
    max-height: calc(100dvh - 20px);
  }
  .team-body,
  .team-dialog > header,
  footer {
    padding: 16px;
  }
  .team-groups {
    grid-template-columns: 1fr;
  }
  h3 {
    font-size: 19px;
  }
  h3 span {
    display: block;
    margin: 5px 0 0;
  }
  .manager-row {
    align-items: flex-start;
  }
}
</style>
