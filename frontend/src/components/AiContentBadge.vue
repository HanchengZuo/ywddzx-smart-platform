<template>
  <span class="ai-content-badge" :class="[generated ? 'is-ai' : 'is-rule', { compact }]">
    <span class="ai-content-badge-mark" aria-hidden="true">{{ generated ? 'AI' : 'R' }}</span>
    <span>{{ generated ? aiLabel : fallbackLabel }}</span>
  </span>
</template>

<script setup>
defineProps({
  generated: {
    type: Boolean,
    default: true
  },
  aiLabel: {
    type: String,
    default: 'AI生成'
  },
  fallbackLabel: {
    type: String,
    default: '规则生成'
  },
  compact: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.ai-content-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: fit-content;
  min-height: 28px;
  padding: 4px 10px 4px 5px;
  border: 1px solid;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.ai-content-badge-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 10px;
  letter-spacing: -0.02em;
}

.ai-content-badge.is-ai {
  color: #075985;
  border-color: #bae6fd;
  background: linear-gradient(135deg, #f0f9ff, #ecfeff);
  box-shadow: 0 5px 14px rgba(14, 165, 233, 0.1);
}

.ai-content-badge.is-ai .ai-content-badge-mark {
  color: #ffffff;
  background: linear-gradient(135deg, #0284c7, #0891b2);
}

.ai-content-badge.is-rule {
  color: #57534e;
  border-color: #d6d3d1;
  background: #fafaf9;
}

.ai-content-badge.is-rule .ai-content-badge-mark {
  color: #ffffff;
  background: #78716c;
}

.ai-content-badge.compact {
  min-height: 24px;
  padding: 3px 8px 3px 4px;
  font-size: 11px;
}

.ai-content-badge.compact .ai-content-badge-mark {
  width: 17px;
  height: 17px;
  font-size: 9px;
}
</style>
