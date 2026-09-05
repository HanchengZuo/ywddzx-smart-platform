<template>
  <section class="filter-summary" aria-label="筛选条件概览">
    <header class="filter-summary-heading">
      <strong>已设置 {{ selected.length }} 项 <small>／ {{ fields.length }} 项条件</small></strong>
      <span :class="{ 'filter-summary-warning': dirty }">{{ dirty ? '有修改待应用 · 点击开始筛选' : manual ? '与已提交筛选一致' : '条件即时生效' }}</span>
    </header>
    <div class="filter-summary-tags">
      <span v-for="item in visibleFields" :key="item.key" class="filter-summary-tag" :class="{ pending: item.changed }">
        <b>{{ item.label }}</b><span>{{ item.value || '已清空' }}</span><em v-if="item.changed">待应用</em>
      </span>
      <span v-if="!visibleFields.length" class="filter-summary-empty">未设置筛选条件，所有字段均不限。</span>
    </div>
    <details v-if="dirty && manual" class="filter-summary-applied">
      <summary>查看已提交的筛选条件（{{ applied.length }} 项）</summary>
      <div class="filter-summary-tags">
        <span v-for="item in applied" :key="item.key" class="filter-summary-tag"><b>{{ item.label }}</b><span>{{ item.applied }}</span></span>
        <span v-if="!applied.length" class="filter-summary-empty">未设置筛选条件</span>
      </div>
    </details>
  </section>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ fields: { type: Array, required: true }, manual: Boolean })
const selected = computed(() => props.fields.filter((item) => item.value))
const visibleFields = computed(() => props.fields.filter((item) => item.value || item.changed))
const applied = computed(() => props.fields.filter((item) => item.applied))
const dirty = computed(() => props.fields.some((item) => item.changed))
</script>

<style>
.filter-summary { margin: 0 0 18px; padding: 15px 17px; border: 1px solid #d7e5f1; border-radius: 16px; background: linear-gradient(120deg, #f0f7fc, #f8fafc); }
.filter-summary-heading { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 11px; color: #155e85; font-size: 13px; }
.filter-summary-heading small { font-size: 12px; font-weight: 400; color: #64748b; }
.filter-summary-heading > span { color: #64748b; font-size: 12px; }
.filter-summary-heading > .filter-summary-warning { color: #a65d0b; }
.filter-summary-tags { display: flex; flex-wrap: wrap; gap: 8px; min-width: 0; }
.filter-summary-tag { display: inline-flex; flex-wrap: wrap; align-items: baseline; gap: 5px 8px; max-width: 100%; padding: 6px 10px; border: 1px solid #c6deed; border-radius: 10px; background: #fff; color: #155e85; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.filter-summary-tag > span { min-width: 0; white-space: normal; }
.filter-summary-tag.pending { border-color: #edcf9b; background: #fffaf0; color: #935312; }
.filter-summary-tag em { font-size: 10px; font-style: normal; font-weight: 700; }
.filter-summary-empty { color: #64748b; font-size: 12px; }
.filter-summary-applied { margin-top: 12px; border-top: 1px dashed #cbd5e1; padding-top: 10px; color: #64748b; font-size: 12px; }
.filter-summary-applied summary { cursor: pointer; }
.filter-summary-applied .filter-summary-tags { margin-top: 10px; }
.filter-card .filter-item[data-filter-state] { border-radius: 12px; padding: 9px 10px; border: 1px solid #e5eaf0; background: #fafbfd; min-width: 0; }
.filter-card .filter-item[data-filter-state="set"] { border-color: #a8d0e8; background: #f0f8fd; }
.filter-card .filter-item[data-filter-state="pending"] { border-color: #eac487; background: #fffbf3; }
.filter-card .filter-item[data-filter-state] > label { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 5px; }
.filter-card .filter-item[data-filter-state] > label::after { content: '不限'; color: #8391a3; font-size: 10px; font-weight: 400; }
.filter-card .filter-item[data-filter-state="set"] > label::after { content: '已设置'; color: #176b98; font-weight: 700; }
.filter-card .filter-item[data-filter-state="pending"] > label::after { content: '待应用'; color: #a65d0b; font-weight: 700; }
@media (max-width: 720px) {
  .filter-summary { padding: 12px; border-radius: 13px; }
  .filter-summary-tags { gap: 6px; }
  .filter-summary-tag { padding: 5px 8px; }
  .filter-summary-heading { align-items: flex-start; flex-direction: column; }
}
</style>
