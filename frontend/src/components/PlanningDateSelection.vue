<template>
  <section class="planning-dates">
    <header><div><strong>01 · 选择安排日期</strong><p>{{ hint }}</p></div><span>已选 {{ modelValue.length }} 天</span></header>
    <div class="date-options" role="group" aria-label="安排日期（可多选）">
      <label v-for="option in options" :key="option.day" :class="{ selected: modelValue.includes(option.day) }">
        <input type="checkbox" :value="option.day" :checked="modelValue.includes(option.day)"
          :disabled="disabled || (!modelValue.includes(option.day) && modelValue.length >= 31)" @change="toggle(option.day)" />
        <span><b>{{ option.day }}</b><small>{{ option.weekday }} · {{ option.grouped ? '已保存巡检安排' : '档期全部确认' }}</small></span>
      </label>
    </div>
    <p v-if="!options.length" class="no-dates">暂无符合条件的日期。请先在人员档期中完成工作日全部人员的有空/没空设置。</p>
    <small>支持单日或批量安排，每批最多31天；不包含过去日期及非工作日。</small>
  </section>
</template>
<script setup>
const props = defineProps({ modelValue: { type: Array, default: () => [] }, options: { type: Array, default: () => [] },
  disabled: Boolean, hint: { type: String, default: '先选择日期，再逐日确定管理人员分工；每个日期的草案独立保留。' } })
const emit = defineEmits(['update:modelValue'])
function toggle(day) {
  emit('update:modelValue', props.modelValue.includes(day) ? props.modelValue.filter(value => value !== day) : [...props.modelValue, day].sort())
}
</script>
<style scoped>
.planning-dates { padding:18px; border:1px solid #a9cbd7; border-radius:14px; background:linear-gradient(110deg,#eef7f9,#f4f7fc); color:#173e55; margin-bottom:18px; }
header { display:flex; justify-content:space-between; gap:12px; align-items:start; }
header strong { font-size:16px; } header span { white-space:nowrap; border-radius:8px; padding:6px 10px; background:#d6eaf1; color:#235c72; font-size:13px; font-weight:700; }
p { margin:7px 0; font-size:13px; line-height:1.7; color:#506b80; }
.date-options { display:grid; grid-template-columns:repeat(auto-fit,minmax(205px,1fr)); gap:9px; max-height:260px; overflow:auto; margin:12px 0; }
.date-options label { display:flex; align-items:center; gap:10px; padding:12px; border:1px solid #c4d6e1; border-radius:10px; background:white; cursor:pointer; }
.date-options label.selected { background:#dceff3; border-color:#32819a; box-shadow:inset 3px 0 #23718c; }
input { width:17px; height:17px; accent-color:#23718c; } label span { display:grid; gap:4px; } b { font-size:14px; }
small { color:#557183; font-size:12px; }.no-dates { padding:12px; background:#fff8e7; border-radius:8px; color:#866326; }
@media(max-width:600px) { .planning-dates { padding:13px; }.date-options { grid-template-columns:1fr; } }
</style>
