<template>
  <div v-show="state.visible" class="table-horizontal-navigator" role="group" aria-label="问题清单横向浏览"
    :style="{ left: `${state.left}px`, top: `${state.top}px`, width: `${state.width}px` }">
    <span class="navigation-label">横向浏览</span>
    <button type="button" aria-label="向左浏览字段" :disabled="state.value <= 0" @click="movePage(-1)">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m15 6-6 6 6 6" /></svg>
    </button>
    <input type="range" min="0" :max="state.max" step="1" :value="state.value" aria-label="问题清单横向位置"
      :aria-valuetext="`已浏览 ${percent}%`" :style="{ '--navigation-progress': `${percent}%` }"
      @input="moveTo(Number($event.target.value))" @keydown="handleKey" />
    <button type="button" aria-label="向右浏览字段" :disabled="state.value >= state.max" @click="movePage(1)">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
    </button>
  </div>
</template>

<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { horizontalNavigationState, horizontalNavigationDestination } from '@/utils/tableHorizontalNavigation'

const props = defineProps({ target: { default: null }, disabled: Boolean, refreshKey: { default: '' } })
const state = ref({ visible: false, max: 0, value: 0, left: 0, top: 0, width: 0 })
const percent = computed(() => state.value.max ? Math.round(state.value.value / state.value.max * 100) : 0)
let frame = null, disconnect = () => {}

const measure = () => {
  frame = null
  const target = props.target
  if (props.disabled || !target?.isConnected || !target.getClientRects().length) {
    state.value = { ...state.value, visible: false }
    return
  }
  const visual = window.visualViewport
  const viewport = { left: visual?.offsetLeft || 0, top: visual?.offsetTop || 0 }
  viewport.right = viewport.left + (visual?.width || window.innerWidth)
  viewport.bottom = viewport.top + (visual?.height || window.innerHeight)
  const content = target.closest('.content')
  if (content) {
    const box = content.getBoundingClientRect()
    viewport.left = Math.max(viewport.left, box.left + content.clientLeft)
    viewport.right = Math.min(viewport.right, box.left + content.clientLeft + content.clientWidth)
    viewport.top = Math.max(viewport.top, box.top + content.clientTop)
    viewport.bottom = Math.min(viewport.bottom, box.top + content.clientTop + content.clientHeight)
  }
  state.value = horizontalNavigationState({ rect: target.getBoundingClientRect(), viewport,
    scrollWidth: target.scrollWidth, clientWidth: target.clientWidth, scrollLeft: target.scrollLeft })
}
const schedule = () => { if (frame === null) frame = requestAnimationFrame(measure) }
const moveTo = left => {
  if (!props.target || props.disabled) return
  props.target.scrollTo({ left, behavior: 'instant' })
  schedule()
}
const movePage = direction => {
  if (!props.target || props.disabled) return
  moveTo(horizontalNavigationDestination(direction < 0 ? 'PageUp' : 'PageDown',
    props.target.scrollLeft, state.value.max, props.target.clientWidth))
}
const handleKey = event => {
  if (!props.target || props.disabled) return
  const left = horizontalNavigationDestination(event.key, props.target.scrollLeft, state.value.max, props.target.clientWidth)
  if (left === null) return
  event.preventDefault()
  moveTo(left)
}

watch(() => [props.target, props.disabled], () => {
  disconnect()
  if (frame !== null) { cancelAnimationFrame(frame); frame = null }
  state.value = { ...state.value, visible: false }
  const target = props.target
  if (!target || props.disabled) return
  const content = target.closest('.content')
  const sources = [...new Set([target, content, window, window.visualViewport].filter(Boolean))]
  for (const source of sources) source.addEventListener('scroll', schedule, { passive: true })
  window.addEventListener('resize', schedule, { passive: true })
  window.visualViewport?.addEventListener('resize', schedule, { passive: true })
  const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(schedule) : null
  for (const node of [target, target.firstElementChild, content].filter(Boolean)) observer?.observe(node)
  disconnect = () => {
    observer?.disconnect()
    for (const source of sources) source.removeEventListener('scroll', schedule)
    window.removeEventListener('resize', schedule)
    window.visualViewport?.removeEventListener('resize', schedule)
  }
  schedule()
}, { immediate: true, flush: 'post' })
watch(() => props.refreshKey, schedule, { flush: 'post' })
onBeforeUnmount(() => { disconnect(); if (frame !== null) cancelAnimationFrame(frame) })
</script>

<style scoped>
.table-horizontal-navigator { position: fixed; z-index: 40; height: 52px; box-sizing: border-box; display: flex; align-items: center; gap: 12px; padding: 8px 12px; border: 1px solid #c2d5e5; border-radius: 12px; background: #f7fbff; box-shadow: 0 5px 22px #16365030; color: #294b65; }
.navigation-label { flex: 0 0 auto; font-size: 13px; font-weight: 600; }
button { flex: 0 0 32px; display: grid; place-items: center; width: 32px; height: 32px; padding: 0; border: 1px solid #cbdbe8; border-radius: 8px; color: #256080; background: #fff; cursor: pointer; }
button:hover:not(:disabled) { background: #e3f1f8; border-color: #80adc5; }
button:disabled { opacity: 0.4; cursor: default; }
input { flex: 1; min-width: 0; width: 0; height: 28px; margin: 0; padding: 0; appearance: none; -webkit-appearance: none; background: transparent; cursor: ew-resize; border: 0; }
input::-webkit-slider-runnable-track { height: 8px; border-radius: 8px; background: linear-gradient(to right, #5c95b5 var(--navigation-progress), #d6e4ef var(--navigation-progress)); }
input::-moz-range-track { height: 8px; border-radius: 8px; background: #d6e4ef; }
input::-moz-range-progress { height: 8px; border-radius: 8px; background: #5c95b5; }
input::-webkit-slider-thumb { width: 44px; height: 16px; margin-top: -4px; border: 1px solid #174f74; border-radius: 7px; background: #296d96; appearance: none; -webkit-appearance: none; box-shadow: 0 1px 3px #16365025; }
input::-moz-range-thumb { width: 44px; height: 16px; border: 1px solid #174f74; border-radius: 7px; background: #296d96; }
button:focus-visible, input:focus-visible { outline: 2px solid #3479ce; outline-offset: 3px; }
@media (max-width: 1000px) { .table-horizontal-navigator { gap: 8px; padding-inline: 8px; } .navigation-label { display: none; } }
</style>
