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
      <TransientNotice
        :message="warningToast"
        :sequence="warningSequence"
        @dismiss="warningToast = ''"
      />
      <div class="team-body">
        <p class="method">
          今日未设置的档期默认有空，提前设置的没空及原因保持不变；仅安排有空且账号匹配的人员。上海时间
          17:00
          前的当日记录不阻止分组。先确定管理人员分工，再智能生成方案；生成和拖动均不自动保存，采用后才覆盖今日人员安排。已派站的外勤组及视频人员保持锁定。每组只能有一位管理人员，且至少1人持准驾证，优先配2人。
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
                <strong
                  >{{ person.display_name }}
                  <em v-if="person.has_driving_permit" class="permit-tag">准驾证</em></strong
                ><small v-if="lockedMode(person)"
                  >已有{{
                    lockedMode(person) === 'offline' ? '现场' : '视频'
                  }}站点安排或实绩，不可冲突</small
                >
              </div>
              <select
                v-model="managerModes[person.id]"
                :disabled="loading || saving || personLocked(person)"
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
              智能生成今日巡检方案
            </button>
            <p v-if="hasDispatchedMembers" class="method">
              已派站的外勤组和视频人员将原样保留，仅重新生成其他有空人员的方案。
            </p>
          </details>
          <section class="result-step">
            <div class="step-heading">
              <b>02</b>
              <div>
                <strong>{{ preview ? '待采用的今日巡检方案' : '当前生效的今日巡检安排' }}</strong
                ><small>{{
                  preview
                    ? '仅为草案 · 调整不自动生效，采用后覆盖今日安排'
                    : context.updated_at
                      ? context.updated_by_name + ' · ' + context.updated_at + ' 保存'
                      : '今日尚未安排分组'
                }}</small>
              </div>
            </div>
            <p v-if="success" class="applied-notice" role="status">{{ success }}</p>
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
                <small v-if="groupLocked(group)" class="dispatch-lock"
                  >已有今日派工 · 不可调入或调出组员</small
                >
                <p
                  v-if="group.mode === 'offline'"
                  class="driver-status"
                  :class="{ unsafe: !driverCount(group), preferred: driverCount(group) >= 2 }"
                >
                  {{
                    driverCount(group)
                      ? driverCount(group) +
                        ' 人拥有准驾证' +
                        (driverCount(group) >= 2 ? ' · 优选配置' : ' · 已满足最低要求')
                      : '缺少持准驾证人员 · 不可确认或派现场任务'
                  }}
                </p>
                <div class="member-tags">
                  <button
                    v-for="person in group.members"
                    :key="person.id"
                    type="button"
                    :draggable="editable && !loading && !saving && !personLocked(person)"
                    :disabled="!editable || loading || saving || personLocked(person)"
                    :aria-label="person.display_name + '，点击或拖动调整分组'"
                    :class="{
                      leader: person.id === group.leader_id,
                      selected: selectedStudent === person.id,
                    }"
                    :aria-pressed="selectedStudent === person.id"
                    @dragstart="startStudentDrag($event, person)"
                    @dragend="draggingStudent = null"
                    @click="selectedStudent = selectedStudent === person.id ? null : person.id"
                  >
                    {{ person.display_name }}<small v-if="person.id === group.leader_id">带队</small
                    ><small v-if="person.has_driving_permit" class="permit-tag">准驾</small
                    ><small v-if="personLocked(person)">已派工</small>
                  </button>
                </div>
                <button
                  v-if="selectedStudent && canMoveTo(group)"
                  type="button"
                  class="move-here"
                  :disabled="saving || groupLocked(group)"
                  @click="dropStudent(group)"
                >
                  移至{{ group.name }}
                </button>
              </article>
            </div>
            <div v-if="editable && videoManagers.length" class="restore-leaders">
              <span>内勤管理人员也可独立带队：</span>
              <button
                v-for="person in videoManagers"
                :key="person.id"
                type="button"
                :disabled="loading || saving || personLocked(person)"
                @click="restoreLeader(person)"
              >
                {{ person.display_name }} · 设为外勤带队
              </button>
            </div>
            <p v-if="editable && displayGroups.length" class="method move-help" role="status">
              {{
                saving
                  ? '正在采用方案…'
                  : '拖动姓名可调整草案，手机或键盘可先点姓名，再点目标组“移至”。管理人员只能移至内勤或独立带队，离开外勤时原组大学生自动转内勤。所有调整须点击“采用方案并覆盖今日安排”才生效。'
              }}
              <button v-if="selectedStudent" type="button" @click="selectedStudent = null">
                取消选择
              </button>
            </p>
            <p v-else-if="!displayGroups.length" class="empty">
              {{
                editable
                  ? '完成上方管理人员分工后，点击“智能生成今日巡检方案”。'
                  : '今日暂未保存巡检分组。'
              }}
            </p>
            <p v-if="preview && !displayGroups.some((g) => g.mode === 'offline')" class="warning">
              没有现场带队管理人员，本次大学生全部安排视频巡检。
            </p>
            <p v-if="unsafeGroups.length" class="error" role="alert">
              {{
                unsafeGroups.map((g) => g.name).join('、')
              }}尚无持准驾证成员。请调整预览；已保存分组请先维护人员准驾证资料或调整成员，不能派现场任务。
            </p>
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
        <span>{{
          preview
            ? '草案未采用 · 当前安排不会自动变化'
            : '当前展示为已保存安排，可生成新方案或直接调整'
        }}</span>
        <button v-if="preview" type="button" :disabled="saving || loading" @click="discardDraft">
          放弃草案
        </button>
        <button type="button" :disabled="saving" @click="close">关闭</button
        ><button
          v-if="editable"
          type="button"
          class="primary"
          :disabled="!preview || !context?.working || loading || saving || unsafeGroups.length > 0"
          @click="confirm"
        >
          {{ saving ? '采用中…' : '采用方案并覆盖今日安排' }}
        </button>
      </footer>
    </dialog>
  </Teleport>
</template>
<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, ref } from 'vue'
import { fieldDriverCount, currentTeamDraft, movePreviewMember } from '@/utils/dailyTeamPreview'
import TransientNotice from '@/components/TransientNotice.vue'
const props = defineProps({ canEdit: { type: Boolean, default: false } })
const emit = defineEmits(['saved', 'opened', 'closed'])
const dialog = ref(null),
  context = ref(null),
  preview = ref(null),
  managerModes = ref({}),
  loading = ref(false),
  saving = ref(false),
  error = ref(''),
  success = ref('')
const editable = computed(() => props.canEdit && context.value?.can_edit)
const warningToast = ref(''),
  warningSequence = ref(0)
function warn(message) {
  warningToast.value = message
  warningSequence.value++
}
const lockGroups = computed(() => preview.value?.groups || context.value?.groups || [])
const hasDispatchedMembers = computed(() =>
  lockGroups.value.some((g) => g.members.some((p) => p.dispatch_locked)),
)
const personLocked = (p) =>
  lockGroups.value.some((g) =>
    g.members.some((m) => m.id === p.id && m.dispatch_locked),
  )
const groupLocked = (g) =>
  g.mode === 'offline' &&
  lockGroups.value.some(
    (saved) => saved.mode === 'offline' && saved.leader_id === g.leader_id && saved.dispatch_locked,
  )
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
const videoManagers = computed(() =>
  displayGroups.value
    .filter((g) => g.mode === 'online')
    .flatMap((g) => g.members)
    .filter((p) => p.position === '管理人员'),
)
const driverCount = (group) => fieldDriverCount(group, context.value?.people)
const unsafeGroups = computed(() =>
  displayGroups.value.filter((group) => group.mode === 'offline' && !driverCount(group)),
)
const draggingStudent = ref(null),
  selectedStudent = ref(null)
function startStudentDrag(event, person) {
  if (!editable.value || loading.value || saving.value || personLocked(person)) {
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
  const person = source.members.find((p) => p.id === studentId)
  if (personLocked(person) || groupLocked(group)) {
    warn('已有今日站点派工，须先撤下相关组或人员的全部今日排班，才能调整组员。')
    draggingStudent.value = selectedStudent.value = null
    return
  }
  if (source?.name === group.name) {
    draggingStudent.value = selectedStudent.value = null
    return
  }
  try {
    preview.value = movePreviewMember(
      preview.value || currentTeamDraft(context.value),
      context.value.people,
      studentId,
      group.leader_id,
    )
    success.value = ''
    error.value = ''
  } catch (err) {
    warn(err.message)
  } finally {
    draggingStudent.value = selectedStudent.value = null
  }
}
function canMoveTo(group) {
  const person = displayGroups.value
    .flatMap((g) => g.members)
    .find((p) => p.id === selectedStudent.value)
  return person?.position !== '管理人员' || group.mode === 'online' || group.leader_id === person.id
}
function restoreLeader(person) {
  selectedStudent.value = person.id
  dropStudent({ mode: 'offline', leader_id: person.id, name: `外勤${person.display_name}组` })
}
function discardDraft() {
  invalidate()
  success.value = ''
  load()
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
  success.value = ''
}
async function open() {
  selectedStudent.value = draggingStudent.value = null
  context.value = null
  preview.value = null
  error.value = ''
  success.value = ''
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
  success.value = ''
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
    if (ticket === serial && !disposed) {
      context.value.people = data.people
      context.value.excluded = data.excluded
      preview.value = data
    }
  } catch (err) {
    if (ticket === serial && !disposed && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '分组预览失败，请重新打开核对。'
  } finally {
    if (ticket === serial) loading.value = false
  }
}
async function submit() {
  if (!editable.value || saving.value || loading.value || !preview.value) return
  saving.value = true
  error.value = ''
  try {
    const { data } = await axios.post(
      '/api/staff-availability/today-inspection',
      {
        action: 'apply',
        source: preview.value.source,
        day: context.value.day,
        revision: context.value.revision,
        manager_modes: preview.value.manager_modes || managerModes.value,
        seed: preview.value?.seed,
        token: preview.value?.token,
        moves: preview.value.moves || [],
      },
      { timeout: 30000 },
    )
    if (!disposed) {
      preview.value = null
      await load()
      success.value = '已采用方案并覆盖今日人员安排，今日调度待选区已同步。可继续调整未派站人员。'
      emit('saved', data)
      window.dispatchEvent(new Event('inspection-schedule-changed'))
      window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
    }
  } catch (err) {
    if (!disposed) {
      preview.value = null
      await load()
      warn(err.response?.data?.error || '保存结果未能确认，已重新读取当前安排，请核对后调整。')
    }
  } finally {
    saving.value = false
  }
}
function confirm() {
  submit()
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
.dispatch-lock {
  display: block;
  margin: -4px 0 12px;
  color: #7e4b18;
  font-weight: 700;
  font-size: 11px;
}
.permit-tag {
  display: inline-block;
  font-size: 11px;
  font-style: normal;
  color: #17634b;
  background: #e5f5ed;
  border-radius: 4px;
  padding: 2px 5px;
}
.driver-status {
  margin: 0 0 12px;
  padding: 7px 9px;
  background: #fff3df;
  color: #805019;
  border-radius: 6px;
  font-size: 12px;
}
.driver-status.preferred {
  background: #e5f5ed;
  color: #17634b;
}
.driver-status.unsafe {
  background: #fff0ed;
  color: #9c352a;
}
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
  width: min(1000px, calc(100vw - 24px));
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
.applied-notice {
  padding: 12px 16px;
  border: 1px solid #a8cdbb;
  border-left: 4px solid #278364;
  border-radius: 8px;
  background: #edf8f1;
  color: #17583f;
  font-size: 13px;
}
.restore-leaders {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
  padding: 12px;
  border: 1px dashed #9ebcd6;
  border-radius: 8px;
  font-size: 12px;
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
  align-self: center;
  min-width: 180px;
  color: #526d84;
  font-size: 12px;
  line-height: 1.6;
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
  footer > span {
    flex-basis: 100%;
  }
  footer > .primary {
    flex: 1;
  }
}
</style>
