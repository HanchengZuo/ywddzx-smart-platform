<template>
  <section class="department-report-month card-surface" aria-label="历史报告月份">
    <header>
      <div><span class="month-kicker">REPORT MONTH</span><h3>报告月份</h3><p>仅查看已生成成稿，不会触发 AI 或重新生成。</p></div>
      <label>查看年份<select v-model="year" aria-label="查看报告年份"><option v-for="item in years" :key="item" :value="item">{{ item }}年</option></select></label>
    </header>
    <div class="department-month-grid" role="group" aria-label="选择已生成报告月份">
      <button v-for="item in options" :key="item.month" type="button"
        :disabled="loading || !item.available" :aria-pressed="modelValue === item.month"
        :class="{ selected: modelValue === item.month }"
        :title="`${reportMonthLabel(item.month)} · ${item.available ? '查看历史成稿' : '尚未生成，暂不可选'}`"
        @click="$emit('update:modelValue', item.month)">
        <strong>{{ item.label }}</strong><small>{{ item.available ? '已生成' : '未生成' }}</small>
      </button>
    </div>
    <footer><span>当前阅读：<strong>{{ reportMonthLabel(modelValue) }}</strong></span><small>灰色月份暂无成稿。同月多份成稿取最后成功生成的一份。</small></footer>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { departmentMonthOptions, departmentReportYears, reportMonthLabel } from '@/utils/reportAccess'

const props = defineProps({ modelValue: { type: String, default: '' }, months: { type: Array, default: () => [] }, loading: Boolean })
defineEmits(['update:modelValue'])
const years = computed(() => departmentReportYears(props.months))
const year = ref(Number(props.modelValue.slice(0, 4)) || years.value[0])
watch(() => props.modelValue, month => { if (month) year.value = Number(month.slice(0, 4)) })
const options = computed(() => departmentMonthOptions(props.months, year.value))
</script>
<style scoped>
.department-report-month { padding: 22px 24px; border-left: 4px solid #277c96; }
header, footer { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px 24px; }
.month-kicker { color: #527185; letter-spacing: 1.5px; font-size: 10px; font-weight: 700; }
h3 { color: #183d56; font-size: 18px; margin: 5px 0; }
p, footer small { margin: 0; color: #60798b; font-size: 12px; line-height: 1.6; }
label { display: flex; align-items: center; gap: 10px; color: #47677f; font-size: 13px; }
select { min-height: 38px; border: 1px solid #adbfce; border-radius: 8px; background: #fff; color: #294b65; padding: 6px 12px; font: inherit; }
.department-month-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 8px; margin: 18px 0; }
button { display: grid; gap: 5px; justify-items: center; padding: 12px 4px; border: 1px solid #9dbfc9; border-radius: 9px; background: #f1f8fa; color: #245b70; cursor: pointer; transition: background .15s, border-color .15s; }
button:hover:not(:disabled) { background: #deeff3; border-color: #287c94; }
button strong { font-size: 15px; }
button small { font-size: 10px; }
button.selected { background: #205b76; border-color: #205b76; color: #fff; box-shadow: 0 2px 5px #163e541f; }
button:disabled:not(.selected) { background: #f0f2f4; color: #909ba4; border-color: #e0e5e9; cursor: not-allowed; }
button:focus-visible, select:focus-visible { outline: 3px solid #67aabf; outline-offset: 3px; }
footer { padding-top: 12px; border-top: 1px solid #e1e9ee; color: #47677f; font-size: 12px; }
footer strong { color: #183d56; }
@media (max-width: 1000px) { .department-month-grid { grid-template-columns: repeat(6, minmax(0, 1fr)); } }
@media (max-width: 600px) { .department-report-month { padding: 18px 16px; } .department-month-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
</style>
