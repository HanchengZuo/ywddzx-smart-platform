<template>
  <dialog v-if="visible" ref="dialog" class="location-dialog" aria-labelledby="location-title" @cancel.prevent="finish(false)">
    <header>
      <span class="location-kicker">站点位置核对 · 仅提醒</span>
      <h3 id="location-title">{{ result.kind === 'checking' ? '正在核对所选站点' : '请核对所选站点' }}</h3>
      <strong>{{ stationName }}</strong>
    </header>
    <div class="location-body" role="status" aria-live="polite">
      <div class="location-message" :class="{ checking: result.kind === 'checking' }">{{ result.message }}</div>
      <div v-if="Number.isFinite(result.distance)" class="location-metrics">
        <div><span>距所选站点约</span><strong>{{ (result.distance / 1000).toFixed(2) }} <small>公里</small></strong></div>
        <div v-if="result.accuracy !== null"><span>设备定位精度约</span><strong>{{ Math.round(result.accuracy) }} <small>米</small></strong></div>
      </div>
      <p>仅供防止选错站点，不限制异地登记或复核。定位可能有偏差，请以实际情况为准。</p>
      <p class="location-privacy">经授权获取一次设备位置，通过高德转换坐标用于本次核对，不写入业务记录或保存位置轨迹。</p>
      <button v-if="result.kind !== 'checking'" type="button" class="location-retry" @click="locate">重新定位</button>
    </div>
    <footer>
      <button autofocus type="button" class="btn btn-secondary" @click="finish(false)">返回核对</button>
      <button type="button" class="btn btn-primary" @click="finish(true)">{{ result.kind === 'checking' ? '跳过核对并提交' : '仍然提交' }}</button>
    </footer>
  </dialog>
</template>

<script setup>
import { ref, nextTick, onBeforeUnmount } from 'vue'
import { loadAmapSdk } from '@/utils/amapSdk'
import { checkStationProximity, locationErrorMessage } from '@/utils/stationProximity'

const dialog = ref(null), visible = ref(false), stationName = ref(''), result = ref({})
let resolver, station, controller, sequence = 0, disposed = false
const finish = accepted => {
  sequence++
  controller?.abort()
  dialog.value?.close?.()
  visible.value = false
  const resolve = resolver
  resolver = null
  resolve?.(accepted)
}
const locate = async () => {
  controller?.abort()
  controller = new AbortController()
  const request = ++sequence
  result.value = { kind: 'checking', message: '正在获取设备位置并核对距站距离，可随时返回或跳过。' }
  try {
    const value = await checkStationProximity(station, { geolocation: navigator.geolocation,
      secure: window.isSecureContext, loadMap: loadAmapSdk, signal: controller.signal })
    if (request !== sequence || !visible.value) return
    result.value = value
    if (value.kind === 'near') finish(true)
  } catch (error) {
    if (request === sequence && visible.value) result.value = { kind: 'unavailable', message: locationErrorMessage(error) }
  }
}
const confirm = async value => {
  // Width follows the same mobile breakpoint as the registration/review pages.
  // Desktop never requests permission, loads the map SDK or waits for location.
  if (!window.matchMedia('(max-width: 768px)').matches) return true
  if (disposed || resolver) return false
  station = value
  stationName.value = value?.station_name || '所选站点'
  result.value = { kind: 'checking', message: '正在准备定位核对…' }
  visible.value = true
  const promise = new Promise(resolve => { resolver = resolve })
  await nextTick()
  if (!disposed && visible.value) {
    // An optional reminder must not break submission on older embedded browsers.
    try {
      if (typeof dialog.value?.showModal !== 'function') finish(true)
      else { dialog.value.showModal(); locate() }
    } catch { finish(true) }
  }
  return promise
}
defineExpose({ confirm })
onBeforeUnmount(() => { disposed = true; finish(false) })
</script>

<style scoped>
.location-dialog { width: min(440px, calc(100vw - 28px)); max-height: calc(100dvh - 32px); box-sizing: border-box; padding: 0; border: 1px solid #dbe4ee; border-radius: 20px; color: #243c50; background: #fff; box-shadow: 0 24px 80px #0f172a40; }
.location-dialog[open] { display: flex; flex-direction: column; }
.location-dialog::backdrop { background: #0f172a85; }
header { padding: 22px 20px; color: white; background: linear-gradient(120deg, #133650, #1c6777); }
.location-kicker { font-size: 12px; color: #c3e6ed; font-weight: 600; }
h3 { margin: 10px 0; font-size: 20px; }
header strong { font-size: 16px; overflow-wrap: anywhere; }
.location-body { overflow: auto; padding: 20px; }
.location-message { padding: 12px; border: 1px solid #edd5ab; border-radius: 12px; color: #8b5310; background: #fff7e9; font-size: 14px; font-weight: 600; line-height: 1.7; }
.location-message.checking { background: #eef6fb; border-color: #c8dce9; color: #265d7a; }
.location-metrics { display: flex; flex-wrap: wrap; gap: 14px; margin: 18px 0; }
.location-metrics > div { flex: 1; min-width: 110px; }
.location-metrics span { display: block; font-size: 12px; color: #667b8d; }
.location-metrics strong { display: block; margin-top: 6px; font-size: 23px; font-variant-numeric: tabular-nums; }
.location-metrics small { font-size: 12px; font-weight: 400; }
p { font-size: 13px; line-height: 1.7; margin: 14px 0 0; }
.location-privacy { color: #718294; font-size: 12px; }
.location-retry { margin-top: 14px; border: 0; background: transparent; padding: 6px 0; color: #216a99; font-size: 14px; font-weight: 600; cursor: pointer; }
footer { display: flex; gap: 10px; padding: 16px 20px; border-top: 1px solid #e2e8f0; }
footer .btn { flex: 1; min-height: 44px; height: auto; padding: 10px 8px; font-size: 14px; white-space: normal; }
</style>
