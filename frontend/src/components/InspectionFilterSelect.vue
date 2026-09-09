<template>
  <div ref="root" class="search-select" :class="{ 'multi-search-select': multiple }" @focusout="closeOutside">
    <div v-if="multiple" class="multi-select-control" @click="input?.focus()">
      <div class="multi-selected-values">
        <span v-for="value in modelValue" :key="value" class="multi-selected-chip">{{ value }}<button type="button" :aria-label="`移除${value}`" @click.stop="choose(value)">×</button></span>
        <input ref="input" v-model="search" :aria-label="label" :placeholder="modelValue.length ? `继续搜索${label}` : `搜索并多选${label}`" :aria-expanded="open" @focus="open = true" @input="open = true" @keydown.esc.stop="open = false" />
      </div>
      <span v-if="modelValue.length" class="multi-selected-count">已选 {{ modelValue.length }}</span>
    </div>
    <input v-else ref="input" :value="modelValue" :aria-label="label" :placeholder="`搜索或选择${label}`" :aria-expanded="open" @input="emit('update:modelValue', $event.target.value); open = true" @focus="open = true" @keydown.esc.stop="open = false" />
    <div v-if="open" class="search-select-dropdown">
      <button v-for="option in visibleOptions" :key="option" type="button" class="search-select-option" :class="{ 'multi-select-option': multiple, selected: multiple && modelValue.includes(option) }" @mousedown.prevent @click="choose(option)">
        <span v-if="multiple" class="multi-option-check">{{ modelValue.includes(option) ? '✓' : '' }}</span><span class="option-main">{{ option }}</span>
      </button>
      <div v-if="loading" class="search-select-empty option-loading">正在加载{{ label }}...</div>
      <button v-else-if="error" type="button" class="search-select-retry" @mousedown.prevent @click="emit('retry')">筛选项加载失败，点击重试</button>
      <div v-else-if="!visibleOptions.length" class="search-select-empty">无匹配{{ label }}</div>
    </div>
  </div>
</template>
<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { pinyin } from 'pinyin-pro'
const props = defineProps({ modelValue: { type: [Array, String], required: true }, options: { type: Array, default: () => [] }, multiple: Boolean, label: { type: String, required: true }, loading: Boolean, error: String })
const emit = defineEmits(['update:modelValue', 'retry'])
const search = ref(''), open = ref(false), input = ref(null), root = ref(null)
const indexedOptions = computed(() => props.options.map(value => ({ value, search: `${value} ${pinyin(value, { toneType: 'none', separator: '' })} ${pinyin(value, { pattern: 'first', toneType: 'none', separator: '' })}`.toLowerCase() })))
const visibleOptions = computed(() => {
  const query = String(props.multiple ? search.value : props.modelValue).trim().toLowerCase()
  return indexedOptions.value.filter(option => option.search.includes(query)).map(option => option.value)
})
function choose(value) {
  if (props.multiple) emit('update:modelValue', props.modelValue.includes(value) ? props.modelValue.filter(item => item !== value) : [...props.modelValue, value])
  else { emit('update:modelValue', value); open.value = false }
}
function closeOutside(event) { if (!root.value?.contains(event.relatedTarget)) open.value = false }
function pointerOutside(event) { if (!root.value?.contains(event.target)) open.value = false }
onMounted(() => document.addEventListener('pointerdown', pointerOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', pointerOutside))
</script>
<style scoped>
.search-select { position:relative; min-width:0; }
.search-select input { width:100%; height:42px; box-sizing:border-box; border:1px solid #d1d5db; border-radius:10px; padding:0 12px; font-size:14px; }
.multi-select-control { min-height:42px; width:100%; display:flex; align-items:center; gap:8px; border:1px solid #d1d5db; border-radius:10px; padding:5px 8px; background:#fff; cursor:text; box-sizing:border-box; }
.multi-select-control:focus-within { border-color:#2563eb; box-shadow:0 0 0 3px rgba(37,99,235,.12); }
.multi-selected-values { flex:1; display:flex; align-items:center; flex-wrap:wrap; gap:6px; min-width:0; }
.multi-selected-values input { flex:1; min-width:96px; width:auto; height:28px; border:0; border-radius:0; padding:0 4px; background:transparent; outline:none; }
.multi-selected-chip { display:inline-flex; align-items:center; gap:4px; max-width:100%; padding:4px 7px; border-radius:999px; background:#e0f2fe; color:#075985; font-size:12px; font-weight:800; overflow-wrap:anywhere; }
.multi-selected-chip button { display:inline-flex; align-items:center; justify-content:center; flex-shrink:0; width:16px; height:16px; border:0; border-radius:50%; background:rgba(7,89,133,.12); color:#075985; cursor:pointer; }
.multi-selected-count { flex:0 0 auto; padding:3px 7px; border-radius:999px; background:#f1f5f9; color:#475569; font-size:12px; font-weight:800; }
.search-select-dropdown { position:absolute; top:calc(100% + 6px); left:0; right:0; max-height:240px; overflow-y:auto; background:#fff; border:1px solid #dbe4ee; border-radius:14px; box-shadow:0 14px 30px rgba(15,23,42,.12); z-index:200; }
.search-select-option { width:100%; display:block; padding:10px 12px; border:0; cursor:pointer; border-bottom:1px solid #eef2f7; background:#fff; text-align:left; }
.search-select-option:last-child { border-bottom:none; }.search-select-option:hover { background:#f8fafc; }
.multi-select-option { display:flex; align-items:center; gap:8px; }.multi-select-option.selected { background:#eff6ff; }
.multi-option-check { display:inline-flex; align-items:center; justify-content:center; flex-shrink:0; width:18px; height:18px; border-radius:6px; border:1px solid #cbd5e1; color:#2563eb; font-size:12px; font-weight:900; background:#fff; }
.selected .multi-option-check { border-color:#2563eb; background:#dbeafe; }
.search-select-empty { padding:12px; color:#64748b; font-size:13px; }.option-loading { color:#2563eb; }.option-main { font-size:14px; color:#0f172a; }
.search-select-retry { width:100%; padding:12px; border:0; background:#fff7ed; color:#c2410c; font-size:13px; text-align:left; cursor:pointer; }
@media(max-width:768px) { .search-select input { font-size:16px; height:46px; }.multi-selected-values input { height:28px; }.multi-select-control { min-height:46px; } }
</style>
