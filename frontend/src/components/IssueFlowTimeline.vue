<template>
  <section class="flow-timeline-card">
    <header><span>处理轨迹</span><h4>问题流转记录</h4></header>
    <p v-if="loading">正在读取流转记录...</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <ol v-else>
      <li v-for="event in events" :key="event.id" :class="{ returned: ['整改不通过', '驳回站级无法整改'].includes(event.result) }">
        <div class="flow-event-heading"><strong>{{ event.action_label }}</strong><time>{{ event.created_at || '时间未记录' }}</time></div>
        <div class="flow-event-meta">{{ event.actor_display_name }}<span v-if="event.round_no"> · 第 {{ event.round_no }} 轮</span><span v-if="event.result"> · {{ event.result }}</span></div>
        <p v-if="event.from_status">{{ event.from_status }} → {{ event.to_status }}</p>
        <p v-if="event.note">{{ event.note }}</p>
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
ol { margin: 0; padding: 0 0 0 14px; list-style: none; border-left: 2px solid #d1e1f1; }
li { position: relative; padding: 14px; margin-bottom: 12px; background: white; border: 1px solid #e2e8f0; border-radius: 12px; }
li::before { content: ''; position: absolute; left: -21px; top: 20px; width: 10px; height: 10px; border-radius: 50%; background: #2985be; }
li.returned::before { background: #dc6a46; }
.flow-event-heading { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.flow-event-meta { margin-top: 8px; }
p { line-height: 1.65; overflow-wrap: anywhere; white-space: pre-wrap; margin: 8px 0; }
.flow-photo-thumb { display: block; width: 180px; max-width: 100%; height: 128px; padding: 4px; margin-top: 12px; background: #f6f9fd; border: 1px solid #dce6f1; border-radius: 10px; cursor: zoom-in; }
.flow-photo-thumb img { display: block; width: 100%; height: 100%; object-fit: contain; border-radius: 6px; }
.flow-photo-thumb:focus-visible { outline: 2px solid #2985be; outline-offset: 3px; }
@media(max-width:640px) { .flow-timeline-card { padding: 12px; } }
</style>
