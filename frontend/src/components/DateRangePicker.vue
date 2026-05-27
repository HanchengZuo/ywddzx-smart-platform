<template>
  <div ref="pickerRef" class="date-range-picker">
    <div
      class="date-range-trigger"
      :class="{ active: hasValue, open: panelOpen }"
      role="button"
      tabindex="0"
      :aria-label="ariaLabel"
      @click="togglePanel"
      @keydown.enter.prevent="togglePanel"
      @keydown.space.prevent="togglePanel"
    >
      <span :class="{ placeholder: !hasValue }">{{ displayText }}</span>
      <button
        v-if="hasValue"
        class="date-range-clear"
        type="button"
        aria-label="清空日期范围"
        @click.stop="clearRange"
      >
        ×
      </button>
    </div>

    <div v-if="panelOpen" class="date-range-panel">
      <div class="date-range-panel-head">
        <strong>选择日期范围</strong>
        <span>开始和结束日期都可自由选择</span>
      </div>

      <div class="date-range-fields">
        <label>
          <span>开始日期</span>
          <input v-model="draftFrom" type="date" />
        </label>
        <label>
          <span>结束日期</span>
          <input v-model="draftTo" type="date" />
        </label>
      </div>

      <div class="date-range-actions">
        <button class="secondary" type="button" @click="clearRange">清空</button>
        <button class="primary" type="button" @click="applyRange">确定</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  dateFrom: {
    type: String,
    default: ''
  },
  dateTo: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: '选择日期范围'
  },
  ariaLabel: {
    type: String,
    default: '选择日期范围'
  }
})

const emit = defineEmits(['update:dateFrom', 'update:dateTo', 'change'])

const pickerRef = ref(null)
const panelOpen = ref(false)
const draftFrom = ref(props.dateFrom)
const draftTo = ref(props.dateTo)

const hasValue = computed(() => Boolean(props.dateFrom || props.dateTo))
const displayText = computed(() => {
  if (props.dateFrom && props.dateTo) {
    return props.dateFrom === props.dateTo
      ? props.dateFrom
      : `${props.dateFrom} 至 ${props.dateTo}`
  }
  if (props.dateFrom) return `${props.dateFrom} 起`
  if (props.dateTo) return `截至 ${props.dateTo}`
  return props.placeholder
})

const syncDraft = () => {
  draftFrom.value = props.dateFrom
  draftTo.value = props.dateTo
}

watch(
  () => [props.dateFrom, props.dateTo],
  syncDraft
)

const togglePanel = () => {
  syncDraft()
  panelOpen.value = !panelOpen.value
}

const closePanel = () => {
  panelOpen.value = false
}

const emitRange = (dateFrom, dateTo) => {
  emit('update:dateFrom', dateFrom)
  emit('update:dateTo', dateTo)
  emit('change', { dateFrom, dateTo })
}

const applyRange = () => {
  let nextFrom = String(draftFrom.value || '').trim()
  let nextTo = String(draftTo.value || '').trim()
  if (nextFrom && nextTo && nextFrom > nextTo) {
    ;[nextFrom, nextTo] = [nextTo, nextFrom]
  }
  emitRange(nextFrom, nextTo)
  closePanel()
}

const clearRange = () => {
  draftFrom.value = ''
  draftTo.value = ''
  emitRange('', '')
  closePanel()
}

const handleDocumentClick = (event) => {
  if (!panelOpen.value) return
  if (pickerRef.value?.contains(event.target)) return
  closePanel()
}

const handleKeydown = (event) => {
  if (event.key === 'Escape') closePanel()
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.date-range-picker {
  position: relative;
  width: 100%;
  min-width: 0;
}

.date-range-trigger {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 42px;
  gap: 10px;
  border: 1px solid var(--date-range-border, #d1d5db);
  border-radius: var(--date-range-radius, 10px);
  padding: 0 12px;
  background: #fff;
  color: #0f172a;
  font: inherit;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
  box-sizing: border-box;
  color-scheme: light;
}

.date-range-trigger.open,
.date-range-trigger:focus-visible {
  outline: none;
  border-color: var(--date-range-focus, #2563eb);
  box-shadow: 0 0 0 4px var(--date-range-focus-shadow, rgba(37, 99, 235, 0.12));
}

.date-range-trigger span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 800;
}

.date-range-trigger .placeholder {
  color: #9ca3af;
  font-weight: 600;
}

.date-range-clear {
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}

.date-range-panel {
  position: absolute;
  z-index: 80;
  top: calc(100% + 8px);
  left: 0;
  width: min(360px, 92vw);
  padding: 14px;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 22px 46px rgba(15, 23, 42, 0.18);
}

.date-range-panel-head strong,
.date-range-panel-head span {
  display: block;
}

.date-range-panel-head strong {
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
}

.date-range-panel-head span {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.date-range-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.date-range-fields label span {
  display: block;
  margin-bottom: 6px;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
}

.date-range-fields input {
  width: 100%;
  min-height: 40px;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 0 10px;
  background: #f8fafc;
  color: #0f172a;
  font: inherit;
  font-size: 13px;
  box-sizing: border-box;
  color-scheme: light;
}

.date-range-fields input:focus {
  outline: none;
  border-color: #2563eb;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.date-range-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}

.date-range-actions button {
  min-width: 72px;
  height: 36px;
  border: none;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
}

.date-range-actions .secondary {
  background: #f1f5f9;
  color: #475569;
}

.date-range-actions .primary {
  background: #0f172a;
  color: #fff;
}

@media (max-width: 520px) {
  .date-range-panel {
    width: min(330px, calc(100vw - 36px));
  }

  .date-range-fields {
    grid-template-columns: 1fr;
  }
}
</style>
