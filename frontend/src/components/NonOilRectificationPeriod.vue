<template>
  <section class="rectification-period card-surface" aria-labelledby="rectification-period-title">
    <div class="period-heading">
      <div>
        <span class="period-kicker">RECTIFICATION REVIEW · 第四页</span>
        <h3 id="rectification-period-title">整改统计日期范围</h3>
        <p>仅用于“一、总体情况概述”的整改文字与图表，不改变本次报告问题库。</p>
      </div>
      <span class="period-mode">{{ customized ? '自定义范围' : '自动取前一个月' }}</span>
    </div>
    <div class="period-fields">
      <label>
        <span>开始日期</span>
        <input
          type="date"
          :value="modelValue.date_from"
          :disabled="readonly || busy"
          @input="changeDate('date_from', $event.target.value)"
        />
      </label>
      <span class="period-separator" aria-hidden="true">至</span>
      <label>
        <span>结束日期</span>
        <input
          type="date"
          :value="modelValue.date_to"
          :disabled="readonly || busy"
          @input="changeDate('date_to', $event.target.value)"
        />
      </label>
      <button type="button" :disabled="readonly || busy || !customized" @click="$emit('reset')">
        恢复默认范围
      </button>
    </div>
    <p v-if="error" class="period-error" role="alert">{{ error }}</p>
    <div class="period-note">
      <p>默认从主报告开始日期向前推一个月，统计至主报告开始日期的前一天（含当天）。</p>
      <p v-if="readonly">当前为只读。修改范围需具备“生成AI报告”权限。</p>
      <p v-else-if="busy">后台正在生成报告，当前范围暂不可修改。</p>
      <p v-else>
        调整后，请使用上方“生成此时间段报告 / 覆盖此时间段报告”应用；查看历史报告会还原当时的范围。
      </p>
    </div>
  </section>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Object, required: true },
  customized: Boolean,
  readonly: Boolean,
  busy: Boolean,
  error: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'reset'])
const changeDate = (key, value) => {
  if (!props.readonly && !props.busy)
    emit('update:modelValue', { ...props.modelValue, [key]: value })
}
</script>

<style scoped>
.rectification-period {
  padding: 24px;
  border: 1px solid #c9e0ea;
  border-radius: 20px;
  background: linear-gradient(115deg, #f0f8fc, #fff 72%);
  margin-bottom: 22px;
}
.period-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}
.period-kicker {
  color: #37718d;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.3px;
}
h3 {
  margin: 7px 0;
  color: #193952;
  font-size: 19px;
}
p {
  margin: 0;
  color: #5c7085;
  font-size: 13px;
  line-height: 1.7;
}
.period-mode {
  flex-shrink: 0;
  border: 1px solid #c2dce7;
  border-radius: 20px;
  color: #266a8a;
  background: #e8f4fa;
  padding: 5px 12px;
  font-size: 12px;
}
.period-fields {
  display: grid;
  grid-template-columns: minmax(0, 230px) auto minmax(0, 230px) auto;
  justify-content: start;
  align-items: end;
  gap: 14px;
  margin: 20px 0 16px;
}
label {
  min-width: 0;
  display: grid;
  gap: 7px;
  color: #344a61;
  font-size: 13px;
  font-weight: 700;
}
input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  height: 44px;
  border: 1px solid #c4d8e4;
  border-radius: 10px;
  padding: 8px 12px;
  background: white;
  color: #193952;
  font: inherit;
  font-size: 16px;
}
input:focus-visible,
button:focus-visible {
  outline: 2px solid #2d86b0;
  outline-offset: 3px;
}
.period-separator {
  line-height: 44px;
  color: #879aae;
}
button {
  height: 44px;
  padding: 0 16px;
  border: 1px solid #b7d1df;
  border-radius: 10px;
  background: #fff;
  color: #256a8a;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.period-note {
  border-top: 1px solid #d8e8ef;
  padding-top: 12px;
}
.period-error {
  color: #b42318;
  margin-bottom: 12px;
}
@media (max-width: 700px) {
  .rectification-period {
    padding: 18px 16px;
  }
  .period-heading {
    flex-wrap: wrap;
    gap: 10px;
  }
  .period-fields {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 12px;
  }
  .period-separator {
    display: none;
  }
  button {
    grid-column: 1 / -1;
  }
}
@media (max-width: 380px) {
  .period-fields {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
