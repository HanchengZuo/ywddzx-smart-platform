<template>
  <div ref="overlay" class="issue-photo-preview-overlay" role="dialog" aria-modal="true" :aria-label="title" tabindex="-1" @click.self="emit('close')" @keydown.esc.stop="emit('close')" @keydown.tab.prevent>
    <div class="issue-photo-preview-dialog" @wheel.prevent="zoom" @dblclick="scale = 1">
      <img :src="url" :alt="title" :style="{ transform: `scale(${scale})` }" />
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
defineProps({ url: { type: String, required: true }, title: { type: String, default: '图片预览' } })
const emit = defineEmits(['close'])
const scale = ref(1), overlay = ref(null)
let previousFocus
function zoom(event) { scale.value = Math.min(4, Math.max(.5, Number((scale.value + (event.deltaY > 0 ? -.12 : .12)).toFixed(2)))) }
onMounted(() => { previousFocus = document.activeElement; overlay.value?.focus() })
onBeforeUnmount(() => { if (previousFocus?.isConnected) previousFocus.focus() })
</script>
<style scoped>
.issue-photo-preview-overlay { position:fixed; inset:0; z-index:4000; display:flex; align-items:center; justify-content:center; padding:24px; background:rgba(15,23,42,.76); outline:none; }
.issue-photo-preview-dialog { position:relative; display:flex; align-items:center; justify-content:center; max-width:min(980px,96vw); max-height:92vh; overflow:visible; cursor:zoom-in; }
.issue-photo-preview-dialog img { display:block; max-width:100%; max-height:92vh; border-radius:18px; background:#fff; box-shadow:0 24px 54px rgba(15,23,42,.32); transform-origin:center center; transition:transform .12s ease-out; will-change:transform; }
@media(prefers-reduced-motion:reduce) { .issue-photo-preview-dialog img { transition:none; } }
</style>
