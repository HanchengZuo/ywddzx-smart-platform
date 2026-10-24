<template>
  <div
    class="report-view-switch"
    :class="{ 'on-hero': variant === 'hero' }"
    role="group"
    aria-label="报告显示方式"
  >
    <button
      v-for="mode in modes"
      :key="mode.value"
      type="button"
      :aria-pressed="modelValue === mode.value"
      aria-controls="report-studio-rendered"
      @click="$emit('update:modelValue', mode.value)"
    >
      {{ mode.label }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: 'ppt' },
  variant: { type: String, default: 'light' },
})
defineEmits(['update:modelValue'])
const modes = [
  { value: 'ppt', label: 'PPT报告' },
  { value: 'html', label: 'HTML报告' },
]
</script>

<style scoped>
.report-view-switch {
  display: inline-flex;
  align-items: stretch;
  gap: 4px;
  padding: 3px;
  border: 1px solid #b8cbd9;
  border-radius: 12px;
  background: #e9f0f6;
}
button {
  min-height: 34px;
  padding: 6px 14px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #36586e;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
  cursor: pointer;
  transition:
    background-color 150ms ease,
    color 150ms ease;
}
button:hover {
  background: #d9e5ef;
}
button[aria-pressed='true'] {
  background: #245d82;
  color: #fff;
}
button:focus-visible {
  outline: 2px solid #3479ce;
  outline-offset: 2px;
}
.on-hero {
  background: #ffffff14;
  border-color: #ffffff40;
}
.on-hero button {
  color: #e4eff7;
}
.on-hero button:hover {
  background: #ffffff18;
}
.on-hero button[aria-pressed='true'] {
  background: #f2f5f8;
  color: #294b65;
}
.on-hero button:focus-visible {
  outline-color: #e5f4ff;
}
@media (prefers-reduced-motion: reduce) {
  button {
    transition: none;
  }
}
@media (max-width: 520px) {
  .report-view-switch {
    width: 100%;
  }
  button {
    flex: 1;
  }
}
</style>
