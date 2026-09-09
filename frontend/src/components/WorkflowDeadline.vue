<template>
  <div class="workflow-deadline" :class="{ expired, urgent: remaining < 86400000 }">
    <div><strong>{{ title }}</strong><span>{{ workingLabel(deadline, now, calendar) }}</span></div>
    <small v-if="deadline">截止 {{ new Date(Number(deadline)).toLocaleString('zh-CN', { hour12: false }) }}</small>
    <p>{{ expired ? expiredHint : hint }}</p>
  </div>
</template>
<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { deadlineExpired, deadlineRemaining } from '@/utils/deadline'
import { workingLabel } from '@/utils/workingDeadline'
import { loadWorkCalendar } from '@/utils/workCalendar'
const props = defineProps({ deadline: [String, Number], serverNow: [String, Number], title: String, hint: String, expiredHint: String })
const emit = defineEmits(['expired'])
const offset = ref(0), now = ref(Date.now())
const calendar = ref(null)
watch(() => props.serverNow, value => { offset.value = value ? Number(value) - Date.now() : 0; now.value = Date.now() + offset.value }, { immediate: true })
const expired = computed(() => deadlineExpired(props.deadline, now.value))
const remaining = computed(() => deadlineRemaining(props.deadline, now.value))
watch(expired, value => { if (value) emit('expired') }, { immediate: true })
let timer
onMounted(() => { loadWorkCalendar().then(days => { calendar.value = days }).catch(() => {}); timer = setInterval(() => { now.value = Date.now() + offset.value }, 60000) })
onBeforeUnmount(() => clearInterval(timer))
</script>
<style scoped>
.workflow-deadline { padding: 12px; margin: 10px 0; border: 1px solid #b8d9ee; border-radius: 12px; background: linear-gradient(125deg,#edf7ff,#fff); color: #24618d; white-space: normal; }
.workflow-deadline > div { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px; font-size: 13px; }
small { display: block; font-size: 11px; margin-top: 6px; } p { margin: 6px 0 0; font-size: 12px; line-height: 1.6; }
.urgent { border-color: #f5d092; background: #fff9ed; color: #925b14; }.expired { border-color: #efbabc; background: #fff2f2; color: #ab3741; }
</style>
