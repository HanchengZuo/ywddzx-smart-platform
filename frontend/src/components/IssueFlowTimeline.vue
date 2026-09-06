<template>
  <section class="flow-timeline-card">
    <header><span>按发生时间从早到晚 · 问题审核与申诉审核分别记录</span><h4>问题流转记录 <small>{{ events.length }} 个事件</small></h4></header>
    <p v-if="loading">正在读取流转记录...</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <ol v-else>
      <li v-for="(event, index) in events" :key="event.id" :class="event.tone || 'info'">
        <span class="event-number">{{ index + 1 }}</span>
        <div class="event-top"><span class="stage-pill">{{ event.stage_label || '巡检流程' }}</span><time>{{ event.created_at || '时间未记录' }}</time></div>
        <div class="flow-event-heading"><strong>{{ event.action_label }}</strong></div>
        <p v-if="event.result && event.result !== event.action_label" class="event-result">处理结果：{{ event.result }}</p>
        <div class="flow-event-meta">操作人：{{ event.actor_display_name }}<span v-if="event.round_no"> · 第 {{ event.round_no }} 轮整改复核</span></div>
        <div v-if="event.from_label || event.from_status" class="status-path"><span>{{ event.from_label || event.from_status }}</span><b>→</b><strong>{{ event.to_label || event.to_status }}</strong></div>
        <p v-if="event.note" class="event-note"><span>处理说明</span>{{ event.note }}</p>
        <p v-if="event.history_notice" class="history-notice">{{ event.history_notice }}</p>
        <button v-if="event.photo_path" class="flow-photo-thumb" type="button" :aria-label="`放大查看${event.action_label}照片`" @click="$emit('photo', event)">
          <img :src="resolvePhoto(event.photo_path)" :alt="`${event.action_label}照片`" loading="lazy" />
        </button>
      </li>
      <li v-if="!events.length">暂无流转记录</li>
    </ol>
  </section>
</template>
<script setup>
defineProps({ loading: Boolean, error: String, events: { type: Array, default: () => [] }, resolvePhoto: { type: Function, default: path => path } })
defineEmits(['photo'])
</script>
<style scoped>
.flow-timeline-card { padding: 20px; background: #f6f9fd; border: 1px solid #dce6f1; border-radius: 16px; }
header span,.flow-event-meta,time { color: #64748b; font-size: 12px; }
h4 { margin: 5px 0 18px; font-size: 17px; }
h4 small { font-weight: 400; font-size: 12px; color: #64748b; }
ol { margin: 0 0 0 12px; padding: 0 0 0 24px; list-style: none; border-left: 2px solid #d1e1f1; }
li { --event-color: #2985be; position: relative; padding: 16px; margin-bottom: 18px; background: white; border: 1px solid #e2e8f0; border-radius: 12px; }
li.returned { --event-color: #c7463f; border-color: #f1ceca; } li.success { --event-color: #238668; }
.event-number { position: absolute; display: grid; place-items: center; left: -38px; top: 16px; width: 24px; height: 24px; background: var(--event-color); color: white; font-size: 12px; border-radius: 50%; }
.event-top { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.stage-pill { border-radius: 6px; padding: 4px 8px; background: #f0f5fa; color: var(--event-color); font-size: 12px; }
.status-path { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 12px 0; font-size: 13px; }.status-path span { color: #64748b; }.status-path strong { color: var(--event-color); }
.event-note { padding: 10px 12px; background: #f7f9fc; border-radius: 8px; font-size: 14px; }.event-note > span { display: block; color: #718096; font-size: 11px; margin-bottom: 4px; }.history-notice { color: #9a642c; font-size: 12px; }
.flow-event-heading { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.flow-event-meta { margin-top: 8px; }
p { line-height: 1.65; overflow-wrap: anywhere; white-space: pre-wrap; margin: 8px 0; }
.flow-photo-thumb { display: block; width: 180px; max-width: 100%; height: 128px; padding: 4px; margin-top: 12px; background: #f6f9fd; border: 1px solid #dce6f1; border-radius: 10px; cursor: zoom-in; }
.flow-photo-thumb img { display: block; width: 100%; height: 100%; object-fit: contain; border-radius: 6px; }
.flow-photo-thumb:focus-visible { outline: 2px solid #2985be; outline-offset: 3px; }
@media(max-width:640px) { .flow-timeline-card { padding: 12px; } }
</style>
