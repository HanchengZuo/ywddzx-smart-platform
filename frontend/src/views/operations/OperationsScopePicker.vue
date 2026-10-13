<template>
  <div ref="root" class="scope-picker" @keydown.esc.stop.prevent="close(true)" @focusout="leave">
    <button
      ref="trigger"
      type="button"
      class="scope-trigger"
      aria-haspopup="dialog"
      :aria-expanded="open"
      :aria-controls="panelId"
      :title="label"
      @click="toggle"
      @keydown.down.prevent="show"
    >
      <span>{{ label }}</span
      ><b aria-hidden="true">{{ open ? '▴' : '▾' }}</b>
    </button>
    <section
      v-if="open"
      :id="panelId"
      ref="panel"
      role="dialog"
      aria-label="选择片区或站点"
      class="scope-panel"
      :class="{ above }"
      :style="{ left: `${offset}px`, maxHeight: `${height}px` }"
    >
      <header>
        <button v-if="browsing" type="button" class="scope-back" @click="back">‹ 片区</button>
        <strong>{{ browsing || '选择数据范围' }}</strong>
        <button type="button" class="scope-close" aria-label="关闭选择面板" @click="close(true)">
          ×
        </button>
      </header>
      <input
        ref="search"
        v-model="keyword"
        type="search"
        :aria-label="browsing ? '搜索当前片区站点' : '搜索片区'"
        :placeholder="browsing ? '搜索该片区站点' : '搜索片区，点击后选择站点'"
        @keydown.enter.stop.prevent
      />
      <div class="scope-list">
        <button
          v-if="!browsing"
          type="button"
          class="scope-option scope-all"
          :aria-pressed="!modelValue.region && !modelValue.station_id"
          @click="select('', '')"
        >
          <span>全部可见片区</span><small>汇总当前可见范围</small>
        </button>
        <button
          v-if="browsing"
          type="button"
          class="scope-option scope-all"
          :aria-pressed="modelValue.region === browsing && !modelValue.station_id"
          @click="select(browsing, '')"
        >
          <span>查看整个片区</span
          ><small>{{ group?.stations.length || 0 }} 个可选站点 · 不限定单站</small>
        </button>
        <template v-if="!browsing">
          <button
            v-for="row in regions"
            :key="row.region"
            type="button"
            class="scope-option"
            @click="browse(row.region)"
          >
            <span
              >{{ row.region }}<small>{{ row.stations.length }} 个站点</small></span
            ><b aria-hidden="true">›</b>
          </button>
        </template>
        <template v-else>
          <button
            v-for="station in stations"
            :key="station.id"
            type="button"
            class="scope-option"
            :aria-pressed="
              modelValue.region === browsing && String(modelValue.station_id) === String(station.id)
            "
            @click="select(browsing, station.id)"
          >
            <span>{{ station.name }}</span
            ><small v-if="String(modelValue.station_id) === String(station.id)">已选</small>
          </button>
        </template>
        <p v-if="!(browsing ? stations.length : regions.length)" class="scope-empty">
          {{ keyword ? '没有匹配项' : '当前时间范围内暂无可见记录' }}
        </p>
      </div>
      <footer>
        站点来自当前分析日期内的可见问题、巡检及亮点，包含零问题巡检。选择后点击“开始分析”应用。
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { operationsScopeLabel } from '../../utils/operationsScope'

const props = defineProps({
  modelValue: { type: Object, required: true },
  options: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])
const panelId = useId()
const root = ref(null),
  trigger = ref(null),
  panel = ref(null),
  search = ref(null)
const open = ref(false),
  browsing = ref(''),
  keyword = ref('')
const offset = ref(0),
  height = ref(420),
  above = ref(false)
const label = computed(() => operationsScopeLabel(props.modelValue, props.options))
const group = computed(() => props.options.find((row) => row.region === browsing.value))
const regions = computed(() =>
  props.options.filter((row) => row.region.includes(keyword.value.trim())),
)
const stations = computed(() =>
  (group.value?.stations || []).filter((row) => row.name.includes(keyword.value.trim())),
)

function position() {
  if (!open.value || !panel.value) return
  const rect = trigger.value.getBoundingClientRect()
  const below = window.innerHeight - rect.bottom - 20
  above.value = below < 200 && rect.top > below
  height.value = Math.max(150, Math.min(520, above.value ? rect.top - 20 : below))
  const width = panel.value.getBoundingClientRect().width
  offset.value = Math.max(16 - rect.left, Math.min(0, window.innerWidth - 16 - rect.left - width))
}
async function show() {
  open.value = true
  browsing.value = props.modelValue.region || ''
  keyword.value = ''
  await nextTick()
  position()
  search.value?.focus()
}
function close(restore = false) {
  open.value = false
  if (restore) trigger.value?.focus()
}
function toggle() {
  if (open.value) close(true)
  else show()
}
function browse(region) {
  browsing.value = region
  keyword.value = ''
  nextTick(() => search.value?.focus())
}
function back() {
  browsing.value = ''
  keyword.value = ''
  nextTick(() => search.value?.focus())
}
function select(region, station) {
  emit('update:modelValue', { region, station_id: station ? String(station) : '' })
  close(true)
}
function outside(event) {
  if (!root.value?.contains(event.target)) close()
}
function leave(event) {
  if (root.value?.contains(event.relatedTarget)) return
  if (event.relatedTarget) {
    close()
    return
  }
  // Browsing replaces the focused option; let the next level restore focus first.
  nextTick(() => {
    if (!root.value?.contains(document.activeElement)) close()
  })
}
onMounted(() => {
  document.addEventListener('pointerdown', outside)
  window.addEventListener('resize', position)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', outside)
  window.removeEventListener('resize', position)
})
</script>

<style scoped>
.scope-picker {
  position: relative;
  min-width: 0;
  width: calc(220 * var(--c-unit));
  max-width: 100%;
}
.scope-trigger {
  width: 100%;
  height: calc(34 * var(--c-unit));
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: calc(5 * var(--c-unit)) calc(10 * var(--c-unit));
  background: #091c2a;
  border: 1px solid #315366;
  border-radius: 3px;
  color: #c9e6f3;
  font: inherit;
  font-size: calc(12 * var(--c-unit));
  cursor: pointer;
}
.scope-trigger span {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.scope-trigger b {
  color: #4ed5ee;
}
button:focus-visible,
input:focus-visible {
  outline: 2px solid #45cce9;
  outline-offset: 2px;
}
.scope-panel {
  position: absolute;
  z-index: 30;
  top: calc(100% + 8px);
  width: min(calc(340 * var(--c-unit)), calc(100vw - 32px));
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  padding: calc(12 * var(--c-unit));
  gap: calc(10 * var(--c-unit));
  color: #c9e6f3;
  background: #0b2232;
  border: 1px solid #38879c;
  border-radius: 5px;
  box-shadow:
    0 12px 40px #0009,
    inset 0 1px #55e1fa24;
  font-size: calc(12 * var(--c-unit));
}
.scope-panel.above {
  top: auto;
  bottom: calc(100% + 8px);
}
header {
  display: flex;
  align-items: center;
  gap: calc(10 * var(--c-unit));
}
header strong {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}
.scope-back,
.scope-close {
  background: none;
  border: 0;
  color: #63d9ef;
  cursor: pointer;
  font: inherit;
  padding: 4px;
}
.scope-close {
  font-size: calc(20 * var(--c-unit));
  line-height: 1;
}
input {
  box-sizing: border-box;
  width: 100%;
  flex-shrink: 0;
  min-height: calc(34 * var(--c-unit));
  border: 1px solid #315366;
  border-radius: 3px;
  background: #061725;
  color: #d2ecf5;
  padding: calc(8 * var(--c-unit));
  font: inherit;
  color-scheme: dark;
}
input::placeholder {
  color: #789eb1;
}
.scope-list {
  overflow: auto;
  min-height: 0;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: #315c70 #091c2a;
}
.scope-option {
  box-sizing: border-box;
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: calc(11 * var(--c-unit)) calc(9 * var(--c-unit));
  border: 0;
  border-bottom: 1px solid #214052;
  border-radius: 3px;
  background: transparent;
  color: #d2ecf5;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.scope-option span {
  overflow-wrap: anywhere;
}
.scope-option span small {
  display: block;
  margin-top: 4px;
}
.scope-option small {
  color: #87b6ca;
  font-size: calc(10 * var(--c-unit));
}
.scope-option:hover,
.scope-option[aria-pressed='true'] {
  background: #154258;
}
.scope-option[aria-pressed='true'] {
  box-shadow: inset 3px 0 #4ed5ee;
}
.scope-all {
  margin-bottom: 4px;
  background: #102f41;
}
.scope-empty {
  text-align: center;
  padding: 16px 4px;
  color: #89aab9;
}
footer {
  flex-shrink: 0;
  border-top: 1px solid #254759;
  padding-top: 8px;
  color: #87a7b9;
  font-size: calc(10 * var(--c-unit));
  line-height: 1.7;
}
@media (max-width: 680px) {
  .scope-picker {
    flex: 1 1 50%;
    width: auto;
  }
  .scope-trigger {
    height: 36px;
    font-size: 12px;
  }
  .scope-option {
    min-height: 44px;
  }
}
</style>
