<template>
  <div v-show="state.visible" class="table-horizontal-navigator" role="group" aria-label="问题清单横向浏览"
    :style="{ left: `${state.left}px`, top: `${state.top}px`, width: `${state.width}px` }">
    <input type="range" min="0" :max="state.max" step="1" :value="state.value" aria-label="问题清单横向位置"
      :aria-valuetext="`已浏览 ${percent}%`"
      @input="moveTo(Number($event.target.value))" @keydown="handleKey" />
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
.table-horizontal-navigator { position: fixed; z-index: 40; height: 24px; box-sizing: border-box; display: flex; align-items: center; padding: 0 4px; background: transparent; }
input { flex: 1; min-width: 0; width: 0; height: 24px; margin: 0; padding: 0; appearance: none; -webkit-appearance: none; background: transparent; cursor: ew-resize; border: 0; border-radius: 4px; }
input::-webkit-slider-runnable-track { height: 6px; border-radius: 4px; background: #dce4eb; }
input::-moz-range-track { height: 6px; border-radius: 4px; background: #dce4eb; }
input::-moz-range-progress { height: 6px; border-radius: 4px; background: #dce4eb; }
input::-webkit-slider-thumb { width: 60px; height: 8px; margin-top: -1px; border: 0; border-radius: 4px; background: #7b93a5; appearance: none; -webkit-appearance: none; }
input::-moz-range-thumb { width: 60px; height: 8px; border: 0; border-radius: 4px; background: #7b93a5; }
input:hover::-webkit-slider-thumb { background: #526f85; }
input:hover::-moz-range-thumb { background: #526f85; }
input:focus-visible { outline: 2px solid #3479ce; outline-offset: 2px; }
</style>
