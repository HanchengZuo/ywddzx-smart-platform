<template>
  <section class="report-distribution" :aria-label="title">
    <header><div><small v-if="eyebrow">{{ eyebrow }}</small><h3>{{ title }}</h3></div><span>{{ rows.length }} 类</span></header>
    <div class="distribution-rows">
      <div v-for="(row, index) in rows" :key="`${row.name}-${index}`" class="distribution-row" :style="{ '--bar-color': row.color }">
        <div class="distribution-row-label"><strong><i aria-hidden="true"></i>{{ row.name }}</strong><span><b>{{ row.count }}项</b><em>{{ Number(row.percentage.toFixed(1)) }}%</em></span></div>
        <div class="distribution-track" role="img" :aria-label="`${row.name}，${row.count}项，占比${Number(row.percentage.toFixed(1))}%`">
          <span :style="{ width: `${row.percentage}%`, minWidth: row.count && row.percentage ? '3px' : '0' }"></span>
        </div>
      </div>
      <p v-if="!rows.length" class="distribution-empty">暂无此分类的统计数据。</p>
    </div>
    <details v-if="text" class="distribution-explanation"><summary>查看统计说明</summary><p>{{ text }}</p></details>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { distributionRows } from '@/utils/reportDistributions'
const props = defineProps({ title: { type: String, default: '问题类别分布' }, eyebrow: String, text: String, items: { type: Array, default: () => [] } })
const rows = computed(() => distributionRows(props.items))
</script>
<style scoped>
.report-distribution { align-self: start; min-width: 0; border: 1px solid #c5d7e3; border-radius: 12px; overflow: hidden; background: #fff; }
header { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 18px 20px; background: #f0f5f8; border-bottom: 1px solid #d6e3eb; }
header small { color: #47728a; font-size: 10px; font-weight: 700; letter-spacing: 1.4px; }
header h3 { color: #203d54; margin: 4px 0 0; font-size: 17px; }
header > span { color: #44647a; font-size: 12px; white-space: nowrap; }
.distribution-rows { display: grid; gap: 18px; padding: 20px; }
.distribution-row-label, .distribution-row-label > span { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.distribution-row-label { margin-bottom: 8px; }
.distribution-row-label strong { color: #2b465a; font-size: 14px; overflow-wrap: anywhere; }
.distribution-row-label i { display: inline-block; width: 7px; height: 7px; margin-right: 8px; border-radius: 2px; background: var(--bar-color, #256c9b); }
.distribution-row-label > span { flex-shrink: 0; gap: 8px; }
.distribution-row-label b { font-size: 15px; color: #1c3e57; }
.distribution-row-label em { color: #506c80; font-size: 12px; font-style: normal; min-width: 42px; text-align: right; }
.distribution-track { height: 9px; overflow: hidden; background: #e8eff4; border-radius: 5px; }
.distribution-track > span { display: block; height: 100%; background: var(--bar-color, #256c9b); border-radius: inherit; }
.distribution-explanation { border-top: 1px solid #e2eaf0; padding: 12px 20px; font-size: 12px; color: #526e81; }
summary { cursor: pointer; font-weight: 600; }
.distribution-explanation p { margin: 10px 0 0; line-height: 1.8; white-space: pre-wrap; }
.distribution-empty { color: #526e81; margin: 0; }
@media (max-width: 600px) { header, .distribution-rows { padding: 16px; } .distribution-row-label { gap: 8px; } }
</style>
