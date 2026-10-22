<template>
  <Transition name="notice"
    ><div v-if="message" class="transient-notice" role="alert">
      <span class="notice-symbol" aria-hidden="true">!</span>
      <p>{{ message }}</p>
      <button type="button" aria-label="关闭提示" @click="$emit('dismiss')">×</button>
    </div></Transition
  >
</template>
<script setup>
import { onBeforeUnmount, watch } from 'vue'
const props = defineProps({
  message: { type: String, default: '' },
  sequence: { type: Number, default: 0 },
})
const emit = defineEmits(['dismiss'])
let timer
watch(
  () => [props.message, props.sequence],
  () => {
    clearTimeout(timer)
    if (props.message) timer = setTimeout(() => emit('dismiss'), 5500)
  },
  { immediate: true },
)
onBeforeUnmount(() => clearTimeout(timer))
</script>
<style scoped>
.transient-notice {
  position: absolute;
  z-index: 20;
  top: 86px;
  left: 50%;
  transform: translateX(-50%);
  width: min(620px, calc(100% - 28px));
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #dfaaa1;
  border-left: 4px solid #bb4c3e;
  border-radius: 12px;
  background: #fff5f0;
  color: #8d342b;
  box-shadow: 0 12px 30px #45291929;
}
.transient-notice p {
  flex: 1;
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.notice-symbol {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  border-radius: 50%;
  color: white;
  background: #b84a3f;
  font-weight: 800;
}
.transient-notice button {
  flex-shrink: 0;
  border: 0;
  background: transparent;
  color: #8d342b;
  font-size: 21px;
  cursor: pointer;
  padding: 2px 6px;
}
.notice-enter-active,
.notice-leave-active {
  transition:
    opacity 0.18s,
    margin-top 0.18s;
}
.notice-enter-from,
.notice-leave-to {
  opacity: 0;
  margin-top: -6px;
}
@media (prefers-reduced-motion: reduce) {
  .notice-enter-active,
  .notice-leave-active {
    transition: none;
  }
}
</style>
