<template>
  <div class="register-standard-summary">
    <div class="register-standard-label">{{ getRegisterStandardLabel(standard) }}</div>
    <div class="register-standard-fields">{{ getRegisterStandardPreview(standard) }}</div>
  </div>
</template>

<script setup>
import { getRegisterStandardLabel, getRegisterStandardPreview } from '@/utils/registerStandardPresentation'
defineProps({ standard: { type: Object, required: true } })
</script>

<style scoped>
.register-standard-summary { min-width: 0; width: 100%; text-align: left; overflow-wrap: anywhere; }
.register-standard-label { color: #1e40af; font-size: 14px; font-weight: 800; line-height: 1.6; }
.register-standard-fields { margin-top: 6px; color: #475569; font-size: 13px; line-height: 1.7; white-space: pre-line; }
</style>
