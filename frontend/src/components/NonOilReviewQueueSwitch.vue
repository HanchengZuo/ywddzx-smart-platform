<template>
  <div class="review-queue-switch" role="group" aria-label="切换非油复核清单">
    <button v-if="view" class="queue-switch-button return-switch" type="button" @click="emit('select', '')">
      返回待我处理
    </button>
    <button v-if="counts.field > 0 || view === 'field'" class="queue-switch-button" type="button"
      :aria-pressed="view === 'field'" @click="emit('select', 'field')">
      盛大现场复核中
      <span v-if="counts.field != null" class="queue-count">{{ counts.field }}</span>
    </button>
    <button class="queue-switch-button area-switch" type="button" :aria-pressed="view === 'area'"
      title="角标为全部待片区复核事项数" @click="emit('select', 'area')">
      等待片区复核
      <span v-if="counts.area != null" class="queue-count">{{ counts.area }}</span>
    </button>
  </div>
</template>

<script setup>
defineProps({
  view: { type: String, required: true },
  counts: { type: Object, required: true },
})
const emit = defineEmits(['select'])
</script>

<style scoped>
.review-queue-switch { display:flex; align-items:center; flex-wrap:wrap; gap:8px; }
.queue-switch-button {
  display:inline-flex; align-items:center; gap:7px; min-height:36px; padding:6px 10px;
  border:1px solid #c6dbe6; border-radius:9px; background:#f1f7fa; color:#234e66;
  font:inherit; font-size:13px; font-weight:650; cursor:pointer; white-space:nowrap;
}
.queue-switch-button:hover { border-color:#548ca3; background:#e5f1f6; }
.queue-switch-button[aria-pressed="true"] { background:#1e5973; color:#fff; border-color:#1e5973; }
.queue-switch-button:focus-visible { outline:2px solid #297897; outline-offset:2px; }
.queue-count {
  min-width:22px; padding:2px 5px; border-radius:999px; background:#d9e9f1; color:#234e66;
  text-align:center; font-size:11px; font-variant-numeric:tabular-nums;
}
.area-switch .queue-count { background:#ffebc1; color:#804807; }
.return-switch { background:#fff; }
</style>
