<template>
  <section class="service-config">
    <div class="source-panel">
      <header>
        <div>
          <span class="kicker">01 · 数据范围</span>
          <h4>本次报告数据来源</h4>
          <p>统计审核通过的问题与已完成巡检；排除已停用规范，现场、视频独立计数。</p>
        </div>
        <button @click="open('source')" :disabled="waiting || busy">设置数据来源</button>
      </header>
      <div class="metrics">
        <div v-for="item in metrics" :key="item.label">
          <span>{{ item.label }}</span
          ><strong>{{ item.value }}</strong>
        </div>
      </div>
      <p class="saved">
        {{
          data?.settings.station_ids === null
            ? '全部可用站点'
            : `自定义 ${data?.settings.station_ids?.length || 0} 个站点`
        }}
        ·
        {{
          data?.meta.updated_by_name
            ? `最近保存：${data.meta.updated_by_name} · ${data.meta.updated_at}`
            : '尚未保存人工配置，使用全部站点和 AI 分析结果。'
        }}
      </p>
    </div>
    <div class="config-grid">
      <article v-for="item in panels" :key="item.key">
        <span class="kicker">{{ item.number }} · {{ item.name }}</span>
        <h4>{{ item.title }}</h4>
        <p>{{ item.description }}</p>
        <button @click="open(item.key)" :disabled="waiting || busy">
          {{ item.action }} <span aria-hidden="true">→</span>
        </button>
      </article>
    </div>
    <p v-if="error && !panel" class="error" role="alert">
      {{ error }} <button @click="load" :disabled="waiting">重新读取配置</button>
    </p>
    <Teleport to="body">
      <dialog
        ref="dialog"
        class="service-config-dialog"
        :class="{ 'units-dialog': panel === 'units' }"
        aria-labelledby="service-config-title"
        @cancel.prevent="close"
      >
        <header class="dialog-head">
          <div>
            <span class="kicker">现场服务检查报告 · 专属配置</span>
            <h3 id="service-config-title">{{ titles[panel] }}</h3>
          </div>
          <button @click="close" :disabled="working" aria-label="关闭现场服务配置">×</button>
        </header>
        <div class="dialog-toolbar">
          <span>设置全局共享；保存不调用 AI，重新生成报告后应用。</span
          ><button
            v-if="panel !== 'source' && !(panel === 'stages' && selected === 'onsite')"
            :disabled="working || busy || !canGenerate || dirty"
            @click="analyze"
          >
            {{ analyzing ? '正在分析，历史结果自动复用…' : 'AI准备 / 复用历史结果' }}
          </button>
        </div>
        <p v-if="!canGenerate && panel !== 'source'" class="hint">
          可查看和保存人工调整；调用 AI 需要生成AI报告权限。
        </p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <div v-if="data" class="dialog-body" :class="{ 'units-dialog-body': panel === 'units' }">
          <template v-if="panel === 'source'">
            <aside>
              <h4>选择站点范围</h4>
              <label
                ><input
                  type="checkbox"
                  :checked="draft.station_ids === null"
                  @change="setAll($event.target.checked)"
                />全部可用站点</label
              >
              <p>不改变报告日期范围。未发现问题的已完成巡检也计入覆盖站数。</p>
              <strong
                >{{
                  draft.station_ids === null ? data.stations.length : draft.station_ids.length
                }}
                个站点</strong
              >
            </aside>
            <div class="workspace">
              <input
                v-model="keyword"
                class="search"
                placeholder="搜索片区、单位或站点"
                aria-label="搜索数据来源站点"
              />
              <div class="station-grid">
                <label v-for="station in filteredStations" :key="station.station_id"
                  ><input
                    type="checkbox"
                    :checked="
                      draft.station_ids === null || draft.station_ids.includes(station.station_id)
                    "
                    @change="toggleStation(station.station_id)"
                  /><span
                    ><b>{{ station.station_name }}</b
                    ><small>{{ station.region }} · {{ station.issue_count }} 项问题</small></span
                  ></label
                >
              </div>
            </div>
          </template>
          <template v-else-if="panel === 'stages'">
            <aside>
              <button
                v-for="mode in modes"
                :key="mode.key"
                class="tab"
                :class="{ active: selected === mode.key }"
                @click="selected = mode.key"
              >
                {{ mode.name
                }}<small
                  >{{ data.catalog.filter((s) => s.mode === mode.key).length }} 条有效规范</small
                >
              </button>
              <p>视频短语由 AI 准备并持久复用；现场新版使用“内容”，历史版使用“考察类别项目”。两者均可人工调整。</p>
            </aside>
            <div class="workspace">
              <input
                v-model="keyword"
                class="search"
                placeholder="搜索规范ID、字段或环节短语"
                aria-label="搜索环节规范"
              />
              <article v-for="standard in filteredStandards" :key="standard.key" class="standard">
                <header>
                  <b>规范 {{ standard.external_standard_id }}</b
                  ><span>{{ standard.mode === 'video' ? '视频' : '现场' }}</span>
                </header>
                <p>{{ standard.fields['检查内容'] || standard.fields['内容'] || standard.fields['考察类别项目'] }}</p>
                <label
                  >统计环节短语<input
                    :value="draft.phrases[standard.key] ?? standard.phrase"
                    maxlength="30"
                    @input="editPhrase(standard.key, $event.target.value)"
                    :placeholder="
                      standard.mode === 'video' ? '待调用AI生成，可人工填写' : '内容 / 考察类别项目'
                    "
                /></label>
                <details>
                  <summary>查看规范所有字段</summary>
                  <dl>
                    <template v-for="(value, key) in standard.fields" :key="key"
                      ><dt>{{ key }}</dt>
                      <dd>{{ value || '—' }}</dd></template
                    >
                  </dl>
                </details>
              </article>
            </div>
          </template>
          <ServiceReportUnits
            v-else-if="panel === 'units'"
            :units="data.unit_discoveries"
            :issues="data.issues"
            :overrides="draft.unit_evidence"
            :resolve-image="resolveImage"
            :disabled="working || busy"
            @edit="editUnit"
            @photo="$emit('photo', $event)"
          />
          <template v-else>
            <aside>
              <p v-if="panel === 'behaviors'" class="hint">
                已分类 {{ data.behaviors.classified_count }} /
                {{ data.behaviors.issue_count }} 项；{{
                  data.behaviors.complete ? '已完成' : '请先调用AI准备分类'
                }}
              </p>
              <button
                v-for="group in groups"
                :key="group.name"
                class="tab"
                :class="{ active: selected === group.name }"
                @click="selected = group.name"
              >
                {{ group.name
                }}<small
                  >{{ group.issue_ids.length }} 项{{
                    group.percentage !== undefined ? ` · ${group.percentage}%` : ''
                  }}</small
                >
              </button>
              <p v-if="!groups.length">暂无可用分类。问题表现需先调用 AI 分类。</p>
            </aside>
            <div class="workspace">
              <header class="workspace-head">
                <h4>{{ selected || '选择左侧类别' }}</h4>
                <span>{{
                  panel === 'photos'
                    ? 'PPT第4页 · 按选择顺序展示，最多3张'
                    : 'PPT第12页 · 前四类各展示1张代表图'
                }}</span>
              </header>
              <p class="hint">
                {{
                  panel === 'photos'
                    ? '选中的照片按顺序用于对应类别的图片行；未人工选定时使用AI选题。'
                    : '根据实际问题描述调整分类；保存后统计重新计算。选择照片可调整该类的PPT代表问题。'
                }}
              </p>
              <div class="selected-strip">
                <span v-for="(id, index) in selectedIds" :key="id"
                  >{{ index + 1 }} · #{{ id }}<button @click="toggleExample(id)">移除</button></span
                ><span v-if="!selectedIds.length">尚未选定代表照片</span>
              </div>
              <input
                v-model="keyword"
                class="search"
                placeholder="搜索问题ID、站点或描述"
                aria-label="搜索分类问题"
              />
              <article
                v-for="issue in filteredIssues"
                :key="issue.issue_id"
                class="issue"
                :class="{ picked: selectedIds.includes(issue.issue_id) }"
              >
                <button class="photo" :disabled="!issue.issue_photo" @click="$emit('photo', issue)">
                  <img
                    v-if="issue.issue_photo"
                    :src="resolveImage(issue.issue_photo)"
                    alt="问题照片，点击放大"
                    loading="lazy"
                  /><span v-else>暂无照片</span>
                </button>
                <div>
                  <header>
                    <b>#{{ issue.issue_id }} · {{ issue.station_name }}</b
                    ><span>{{ issue.mode === 'video' ? '视频' : '现场' }}</span>
                  </header>
                  <p>{{ issue.description }}</p>
                  <small>{{ issue.category }} · 规范 {{ issue.external_standard_id }}</small
                  ><label v-if="panel === 'behaviors'"
                    >问题具体表现<input
                      :value="
                        draft.behavior_assignments[String(issue.issue_id)] ??
                        data.behaviors.assignments[String(issue.issue_id)]
                      "
                      maxlength="30"
                      @input="
                        draft.behavior_assignments[String(issue.issue_id)] = $event.target.value
                      "
                  /></label>
                </div>
                <button
                  :disabled="!issue.issue_photo"
                  :class="{ primary: selectedIds.includes(issue.issue_id) }"
                  @click="toggleExample(issue.issue_id)"
                >
                  {{ selectedIds.includes(issue.issue_id) ? '已选用' : '选用照片' }}
                </button>
              </article>
              <p v-if="!filteredIssues.length" class="hint">当前类别没有符合条件的问题。</p>
            </div>
          </template>
        </div>
        <footer class="dialog-footer">
          <span>{{
            dirty
              ? '有未保存调整；先保存再调用AI。'
              : data?.meta.updated_by_name
                ? `最近保存：${data.meta.updated_by_name} · ${data.meta.updated_at}`
                : '当前使用默认设置与已有AI结果'
          }}</span>
          <div>
            <button @click="close" :disabled="working">取消</button
            ><button class="primary" @click="save" :disabled="working || busy || !dirty">
              {{ saving ? '正在保存…' : '保存调整' }}
            </button>
          </div>
        </footer>
      </dialog>
    </Teleport>
  </section>
</template>
<script setup>
import { ref, computed, watch, onBeforeUnmount, nextTick } from 'vue'
import axios from 'axios'
import ServiceReportUnits from './ServiceReportUnits.vue'
const props = defineProps({
  month: String,
  dateFrom: String,
  dateTo: String,
  generatedAt: String,
  resolveImage: Function,
  canGenerate: Boolean,
  busy: Boolean,
})
const emit = defineEmits(['change', 'saved', 'photo'])
const data = ref(null),
  draft = ref({}),
  panel = ref(''),
  selected = ref(''),
  keyword = ref(''),
  dialog = ref(null),
  error = ref(''),
  waiting = ref(false),
  saving = ref(false),
  analyzing = ref(false)
const working = computed(() => saving.value || analyzing.value)
const dirty = computed(
  () => data.value && JSON.stringify(draft.value) !== JSON.stringify(data.value.settings),
)
const modes = [
  { key: 'video', name: '视频检查' },
  { key: 'onsite', name: '现场检查' },
]
const panels = [
  {
    key: 'photos',
    number: '02',
    name: '总体情况照片',
    title: '高频类别代表照片',
    description: '问题最多的两个类别各选三张照片，对应第4页两行证据。',
    action: '查看与调整照片',
  },
  {
    key: 'stages',
    number: '03',
    name: '环节分类',
    title: '视频 / 现场环节短语',
    description: '视频由AI归纳，现场兼容新版内容与旧版考察类别项目；规范未变直接复用。',
    action: '查看与调整环节',
  },
  {
    key: 'behaviors',
    number: '04',
    name: '具体行为表现',
    title: '高频问题表现与选图',
    description: '按真实描述分类、计算数量占比，为前几类选择代表照片。',
    action: '查看分类与代表问题',
  },
  {
    key: 'units',
    number: '05',
    name: '各片区问题发现',
    title: '片区 · 类别 · 环节证据',
    description: '逐层查看环节问题概括、全部原始问题与PPT代表照片；证据未变复用历史AI结果。',
    action: '查看与调整片区问题发现',
  },
]
const titles = {
  units: '各片区问题发现 · 环节概括与代表照片',
  source: '本次报告数据来源',
  photos: '高频类别代表照片',
  stages: '环节分类与短语',
  behaviors: '问题具体表现与代表照片',
}
const metrics = computed(() => {
  const s = data.value?.summary || {},
    m = data.value?.modes || []
  return [
    { label: '片区', value: s.region_count || 0 },
    { label: '股权单位', value: s.holding_count || 0 },
    { label: '覆盖站点', value: s.station_count || 0 },
    { label: '问题总数', value: s.issue_count || 0 },
    { label: '视频问题', value: m[0]?.issue_count || 0 },
    { label: '现场问题', value: m[1]?.issue_count || 0 },
  ]
})
const groups = computed(() =>
  panel.value === 'photos' ? data.value?.category_groups || [] : data.value?.behaviors.groups || [],
)
const search = (value) =>
  !keyword.value || JSON.stringify(value).toLowerCase().includes(keyword.value.toLowerCase())
const filteredStations = computed(() => data.value?.stations.filter(search) || [])
const filteredStandards = computed(
  () => data.value?.catalog.filter((s) => s.mode === selected.value && search(s)) || [],
)
const filteredIssues = computed(() => {
  const group = groups.value.find((g) => g.name === selected.value)
  return data.value?.issues.filter((i) => group?.issue_ids.includes(i.issue_id) && search(i)) || []
})
const selectedIds = computed(() => {
  const key = panel.value === 'photos' ? 'examples' : 'behavior_examples'
  return draft.value[key]?.[selected.value] ?? data.value?.[key]?.[selected.value] ?? []
})
const params = () => ({ month: props.month, date_from: props.dateFrom, date_to: props.dateTo })
const copySettings = (value) => JSON.parse(JSON.stringify(value))
let controller,
  serial = 0,
  alive = true
function accept(value) {
  data.value = value
  draft.value = copySettings(value.settings)
  emit('change', copySettings(value.settings))
  if (!groups.value.some((g) => g.name === selected.value) && panel.value !== 'stages')
    selected.value = groups.value[0]?.name || ''
}
async function load() {
  if (!props.dateFrom || !props.dateTo || props.dateFrom > props.dateTo) return
  const id = ++serial
  controller?.abort()
  controller = new AbortController()
  waiting.value = true
  try {
    const response = await axios.get('/api/inspection-reports/service-config', {
      params: params(),
      signal: controller.signal,
    })
    if (alive && id === serial) {
      accept(response.data)
      error.value = ''
    }
  } catch (e) {
    if (alive && id === serial && !axios.isCancel(e))
      error.value = e.response?.data?.error || '配置读取失败，请重试。'
  } finally {
    if (alive && id === serial) waiting.value = false
  }
}
async function open(key) {
  panel.value = key
  keyword.value = ''
  selected.value = key === 'stages' ? 'video' : groups.value[0]?.name || ''
  error.value = ''
  await nextTick()
  dialog.value?.showModal()
}
function close() {
  if (working.value) return
  dialog.value?.close()
  panel.value = ''
  if (data.value) draft.value = copySettings(data.value.settings)
}
function setAll(all) {
  draft.value.station_ids = all ? null : []
}
function toggleStation(id) {
  if (draft.value.station_ids === null)
    draft.value.station_ids = data.value.stations.map((s) => s.station_id)
  const ids = draft.value.station_ids
  draft.value.station_ids = ids.includes(id)
    ? ids.filter((i) => i !== id)
    : [...ids, id].sort((a, b) => a - b)
}
function editPhrase(key, value) {
  if (value.trim()) draft.value.phrases[key] = value
  else delete draft.value.phrases[key]
}
function toggleExample(id) {
  const key = panel.value === 'photos' ? 'examples' : 'behavior_examples'
  const ids = [...selectedIds.value],
    max = key === 'examples' ? 3 : 1
  const index = ids.indexOf(id)
  if (index >= 0) ids.splice(index, 1)
  else {
    if (ids.length >= max) {
      if (max === 1) ids.length = 0
      else {
        error.value = '本类别最多选用3张照片，请先移除一张。'
        return
      }
    }
    ids.push(id)
  }
  draft.value[key][selected.value] = ids
  error.value = ''
}
async function save() {
  saving.value = true
  error.value = ''
  try {
    const response = await axios.put('/api/inspection-reports/service-config', {
      ...params(),
      settings: draft.value,
      revision: data.value.meta.revision,
      data_signature: data.value.data_signature,
    })
    if (alive) {
      accept(response.data)
      emit('saved')
    }
  } catch (e) {
    if (alive) error.value = e.response?.data?.error || '保存失败，请重试。'
  } finally {
    if (alive) saving.value = false
  }
}
function editUnit(key, value) {
  draft.value.unit_evidence ||= {}
  draft.value.unit_evidence[key] = value
}
async function analyze() {
  if (dirty.value || working.value || !props.canGenerate) return
  analyzing.value = true
  error.value = ''
  try {
    const response = await axios.post(
      '/api/inspection-reports/service-analysis',
      {
        ...params(),
        kind:
          panel.value === 'units'
            ? 'units'
            : panel.value === 'photos'
              ? 'examples'
              : panel.value === 'stages'
                ? 'phrases'
                : 'behaviors',
        revision: data.value.meta.revision,
        data_signature: data.value.data_signature,
      },
      { timeout: 600000 },
    )
    if (alive) accept(response.data)
  } catch (e) {
    if (alive) error.value = e.response?.data?.error || 'AI处理失败，原配置未改变，可重试。'
  } finally {
    if (alive) analyzing.value = false
  }
}
watch(
  () => [props.month, props.dateFrom, props.dateTo, props.generatedAt],
  () => {
    close()
    load()
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  alive = false
  serial++
  controller?.abort()
  dialog.value?.close()
})
</script>
<style scoped>
.service-config {
  color: #243d54;
  display: grid;
  gap: 22px;
  padding: 24px 24px 30px;
  background: #f4f8fb;
  box-sizing: border-box;
}
.source-panel,
.config-grid article {
  border: 1px solid #cadbe7;
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
}
.source-panel header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
}
.kicker {
  font-size: 13px;
  font-weight: 750;
  color: #176e87;
  letter-spacing: 0.06em;
}
h4 {
  font-size: 19px;
  margin: 10px 0;
}
p {
  font-size: 14px;
  line-height: 1.7;
  margin: 10px 0;
  color: #526a7d;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  margin: 22px 0;
  gap: 12px;
}
.metrics > div {
  padding: 15px;
  background: #f0f6fa;
  border: 1px solid #dce8ef;
  border-radius: 12px;
}
.metrics span {
  display: block;
  font-size: 13px;
  color: #586f83;
}
.metrics strong {
  display: block;
  font-size: 28px;
  color: #163d58;
  margin-top: 7px;
}
.saved {
  background: #e8f3f1;
  color: #245f57;
  padding: 12px 16px;
  border-radius: 9px;
  margin-bottom: 0;
}
.config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.config-grid article {
  display: flex;
  flex-direction: column;
  border-top: 3px solid #287c91;
  box-shadow: 0 4px 14px #234a6510;
}
.config-grid article > button {
  align-self: flex-start;
  margin-top: 15px;
}
.config-grid article p {
  flex: 1;
}
.service-config button,
.service-config-dialog button {
  border: 1px solid #bacfdd;
  border-radius: 9px;
  background: #fff;
  color: #214f6a;
  padding: 10px 14px;
  font-weight: 650;
  cursor: pointer;
}
.service-config button:hover,
.service-config-dialog button:hover {
  background: #e9f3f8;
}
.service-config button:disabled,
.service-config-dialog button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.service-config-dialog {
  width: min(1120px, calc(100vw - 28px));
  max-height: 90dvh;
  padding: 0;
  border: 1px solid #bdd0df;
  border-radius: 18px;
  color: #243d54;
  box-shadow: 0 28px 100px #102c4555;
}
.service-config-dialog::backdrop {
  background: #112c4866;
}
.service-config-dialog[open] {
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}
.service-config-dialog.units-dialog {
  width: min(1320px, calc(100vw - 32px));
  height: min(900px, 92dvh);
}
.dialog-body.units-dialog-body {
  display: block;
  overflow: hidden;
  max-height: none;
  background: #edf3f8;
}
.dialog-head,
.dialog-toolbar,
.dialog-footer {
  flex-shrink: 0;
}
.dialog-body {
  flex: 1;
  min-height: 0;
}
.dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 28px;
  background: linear-gradient(110deg, #123952, #22687a);
  color: white;
}
.dialog-head .kicker {
  color: #b9e0e8;
}
.dialog-head h3 {
  margin: 9px 0 0;
  font-size: 23px;
}
.dialog-head button {
  color: white;
  background: #ffffff18;
  border-color: #ffffff44;
  font-size: 23px;
  padding: 4px 12px;
}
.dialog-toolbar {
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid #dbe6ed;
  font-size: 13px;
}
.dialog-body {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  min-height: 0;
  max-height: 59dvh;
  overflow: auto;
}
.dialog-body aside {
  background: #f2f7fa;
  padding: 20px;
  border-right: 1px solid #d6e4ed;
}
.tab {
  display: block;
  width: 100%;
  text-align: left;
  margin-bottom: 10px;
}
.tab.active {
  background: #e0f1f6 !important;
  border-color: #28809b !important;
  color: #115b75;
}
.tab small {
  display: block;
  margin-top: 6px;
  color: #607a8d;
}
.workspace {
  padding: 20px;
  min-width: 0;
}
.workspace-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.workspace-head span {
  font-size: 12px;
  color: #5e7788;
}
.search {
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 16px;
}
.service-config-dialog input:not([type='checkbox']) {
  border: 1px solid #bfd2df;
  border-radius: 8px;
  padding: 10px 12px;
  color: #163c56;
  background: white;
  min-width: 0;
  font: inherit;
}
.station-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.station-grid label {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid #dce6ed;
  border-radius: 9px;
}
.station-grid small {
  display: block;
  font-size: 12px;
  margin-top: 6px;
  color: #6b8193;
}
.standard,
.issue {
  border: 1px solid #d3e1ea;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  background: #fff;
}
.standard header,
.issue header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
}
.standard header span,
.issue header span {
  font-size: 12px;
  color: #647e91;
}
.standard label,
.issue label {
  display: grid;
  gap: 8px;
  font-size: 13px;
}
.standard summary {
  cursor: pointer;
  font-size: 13px;
  margin-top: 12px;
  color: #176e87;
}
.standard dl {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 8px;
  font-size: 13px;
}
.standard dd {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.issue {
  display: grid;
  grid-template-columns: 108px minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
}
.issue.picked {
  background: #f0f8fc;
  border-color: #2982a0;
}
.photo {
  padding: 0 !important;
  overflow: hidden;
  background: #edf3f7 !important;
}
.photo img {
  width: 106px;
  height: 90px;
  object-fit: contain;
  display: block;
}
.photo span {
  font-size: 12px;
  display: block;
  padding: 24px 4px;
}
.issue p {
  color: #233e53;
  overflow-wrap: anywhere;
}
.issue small {
  display: block;
  color: #678093;
  margin: 8px 0;
}
.selected-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0 18px;
  font-size: 13px;
}
.selected-strip > span {
  background: #e8f3f8;
  border-radius: 8px;
  padding: 6px 10px;
}
.selected-strip button {
  border: 0;
  padding: 3px 6px;
  background: transparent;
}
.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 24px;
  border-top: 1px solid #d4e2eb;
  background: #f6fafd;
}
.dialog-footer > span {
  font-size: 13px;
  color: #526e82;
}
.dialog-footer > div {
  display: flex;
  gap: 10px;
}
.primary {
  background: #246f91 !important;
  color: white !important;
  border-color: #246f91 !important;
}
.error {
  background: #fff0ee;
  color: #a23a34;
  padding: 12px 20px;
  border-radius: 8px;
  margin: 12px 20px;
}
.hint {
  font-size: 13px;
  color: #5f788b;
}
.dialog-body aside label {
  display: flex;
  align-items: center;
  gap: 8px;
}
@media (max-width: 768px) {
  .service-config {
    padding: 16px 14px 22px;
    gap: 16px;
  }
  .source-panel,
  .config-grid article {
    padding: 18px;
  }
  .metrics {
    gap: 8px;
    margin: 18px 0;
  }
  .metrics > div {
    padding: 10px;
  }
  .metrics strong {
    font-size: 24px;
  }
  .units-dialog .dialog-head h3 {
    font-size: 18px;
    line-height: 1.45;
  }
  .units-dialog .dialog-toolbar {
    padding: 12px 16px;
    gap: 10px;
  }
  .units-dialog .dialog-footer {
    padding: 12px 16px;
    gap: 10px;
  }
  .metrics {
    grid-template-columns: repeat(3, 1fr);
  }
  .config-grid {
    grid-template-columns: 1fr;
  }
  .source-panel header,
  .dialog-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .dialog-head {
    padding: 18px;
  }
  .dialog-body {
    grid-template-columns: 1fr;
    max-height: 58dvh;
  }
  .dialog-body aside {
    border-right: 0;
    border-bottom: 1px solid #d5e2eb;
    padding: 14px;
  }
  .tab {
    display: inline-block;
    width: auto;
    margin-right: 8px;
  }
  .dialog-footer {
    flex-direction: column;
    align-items: stretch;
  }
  .dialog-footer > div {
    justify-content: flex-end;
  }
  .issue {
    grid-template-columns: 84px minmax(0, 1fr);
  }
  .photo img {
    width: 82px;
    height: 76px;
  }
  .issue > button:last-child {
    grid-column: 2;
  }
  .station-grid {
    grid-template-columns: 1fr;
  }
  .workspace-head {
    display: block;
  }
}
</style>
