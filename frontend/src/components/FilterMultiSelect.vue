<template>
  <div class="filter-multi" @focusout="closeOutside">
    <div class="filter-multi-control">
      <span v-for="value in modelValue" :key="value">{{ value }}<button type="button" @click="toggle(value)" :aria-label="`移除${value}`">×</button></span>
      <input v-model="search" :placeholder="placeholder" @focus="open = true" @input="open = true" @keydown.esc="open = false" />
    </div>
    <div v-if="open" class="filter-multi-options">
      <button v-for="value in visibleOptions" :key="value" type="button" @mousedown.prevent @click="toggle(value)" :class="{ selected: modelValue.includes(value) }">{{ modelValue.includes(value) ? '✓ ' : '' }}{{ value }}</button>
      <p v-if="!visibleOptions.length">无匹配选项</p>
    </div>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
const props = defineProps({ modelValue: { type: Array, default: () => [] }, options: { type: Array, default: () => [] }, placeholder: { type: String, default: '搜索并多选' } })
const emit = defineEmits(['update:modelValue'])
const search = ref('')
const open = ref(false)
const visibleOptions = computed(() => props.options.filter(value => value.toLowerCase().includes(search.value.trim().toLowerCase())))
const toggle = value => emit('update:modelValue', props.modelValue.includes(value) ? props.modelValue.filter(item => item !== value) : [...props.modelValue, value])
const closeOutside = event => { if (!event.currentTarget.contains(event.relatedTarget)) open.value = false }
</script>
<style scoped>
.filter-multi { position: relative; min-width: 0; }
.filter-multi-control { display: flex; flex-wrap: wrap; gap: 5px; padding: 6px; border: 1px solid #cbd5e1; border-radius: 10px; background: white; min-height: 42px; }
.filter-multi-control span { display: inline-flex; align-items: center; background: #eaf3fb; color: #216896; border-radius: 6px; padding: 3px 7px; font-size: 12px; overflow-wrap: anywhere; }
.filter-multi-control button { border: 0; background: none; color: inherit; cursor: pointer; }
.filter-multi-control input { width: 100%; min-width: 0; border: 0; outline: 0; padding: 4px; font: inherit; }
.filter-multi-options { position: absolute; top: 100%; left: 0; right: 0; max-height: 240px; overflow: auto; z-index: 35; border: 1px solid #dce6f1; border-radius: 10px; background: white; box-shadow: 0 12px 24px #1e3a5f20; }
.filter-multi-options button { display: block; width: 100%; text-align: left; padding: 10px; border: 0; background: white; color: #334155; cursor: pointer; }
.filter-multi-options .selected,.filter-multi-options button:hover { background: #eaf3fb; color: #216896; }
@media(max-width:640px) { input { font-size: 16px !important; } }
</style>
