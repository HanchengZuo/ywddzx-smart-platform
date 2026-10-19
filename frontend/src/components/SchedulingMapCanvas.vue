<template>
  <section ref="frame" class="coverage-map" :class="{ fullscreen }" aria-label="未检查站点分布">
    <header class="coverage-map-toolbar">
      <div><span class="pin-key" aria-hidden="true"></span><strong>未检查站点</strong><small>{{ located.length }} 座已定位</small></div>
      <div>
        <button class="map-tool" type="button" :disabled="!mapReady" @click="fit">显示全部图钉</button>
        <button class="map-tool primary" type="button" :disabled="!canFullscreen" @click="toggleFullscreen">{{ fullscreen ? '退出全屏' : '全屏地图' }}</button>
      </div>
    </header>
    <p v-if="fullscreenError" class="fullscreen-error" role="status">{{ fullscreenError }}</p>
    <div class="coverage-map-body">
      <div ref="canvas" class="coverage-map-canvas"></div>
      <div v-if="loading || error" class="coverage-map-state" role="status">
        <span v-if="loading" class="loading-ring" aria-hidden="true"></span>
        <strong>{{ error ? '暂时无法加载地图' : '正在加载地图' }}</strong>
        <p>{{ error || '检查覆盖数据与地图资源独立加载，请稍候。' }}</p>
        <button v-if="error" class="map-tool" type="button" @click="initialize">重新加载地图</button>
      </div>
      <div v-else-if="mapReady && !located.length" class="coverage-map-empty" role="status">
        当前视图没有可定位的待检查站点
      </div>
      <p class="coverage-map-caption">图钉仅显示未检查站点 · 点击图钉查看站点</p>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { loadAmapSdk, SHANGHAI_CENTER, amapPinIcon, amapStationLabel } from '@/utils/amapSdk'
import { stationCoordinates } from '@/utils/schedulingCoverage'

const props = defineProps({ stations: { type: Array, default: () => [] }, viewportKey: { type:String, default:'' }, selectedId: { type: [String, Number], default: '' } })
const emit = defineEmits(['select'])
const frame = ref(null)
const canvas = ref(null)
const loading = ref(false)
const error = ref('')
const mapReady = ref(false)
const fullscreen = ref(false)
const fullscreenError = ref('')
const canFullscreen = typeof document !== 'undefined' && Boolean(document.documentElement.requestFullscreen)
const located = computed(() => props.stations.filter(station => stationCoordinates(station)))
let map = null
let sdk = null
let layer = null
let markers = []
let info = null
let disposed = false
let observer = null
let resizeFrame = 0
let fittedKey = null

function clearMarkers() {
  info?.close()
  if (layer) { map?.remove(layer); layer.clear(); layer = null }
  else if (markers.length) map?.remove(markers)
  markers = []
}

function fit() {
  if (!map) return
  const positions = located.value.map(stationCoordinates)
  if (positions.length === 1) map.setZoomAndCenter(13, positions[0], true)
  else if (positions.length) {
    // LabelsLayer pins are not ordinary map overlays; fit their coordinates explicitly.
    const lngs = positions.map(point => point[0])
    const lats = positions.map(point => point[1])
    map.setBounds(new sdk.Bounds([Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]), true, [65, 45, 70, 45])
  }
  else map.setZoomAndCenter(10.8, SHANGHAI_CENTER, true)
}

function focus(station) {
  if (!map || !stationCoordinates(station)) return
  const content = document.createElement('div')
  content.style.cssText = 'padding:8px 10px;max-width:250px;line-height:1.7;color:#243b53;'
  const title = document.createElement('strong')
  title.textContent = station.station_name
  const text = document.createElement('p')
  text.style.margin = '5px 0 0'
  text.textContent = `${station.region} · 本周期未检查${station.address ? ' · ' + station.address : ''}`
  content.append(title, text)
  info ||= new sdk.InfoWindow({ offset: new sdk.Pixel(0, -24), autoMove: false, closeWhenClickMap: true })
  info.setContent(content)
  map.setZoomAndCenter(13, stationCoordinates(station), true)
  info.open(map, stationCoordinates(station))
}

function renderMarkers() {
  if (!map) return
  clearMarkers()
  if (sdk.LabelsLayer && sdk.LabelMarker) {
    layer = new sdk.LabelsLayer({ zIndex: 120, collision: false })
    markers = located.value.map(station => {
      const marker = new sdk.LabelMarker({ name: String(station.station_id), position: stationCoordinates(station),
        zIndex:120,
        icon: { type: 'image', image: amapPinIcon('#d97706'), size: [30, 36], anchor: 'bottom-center' },
        text: amapStationLabel(station.station_name) })
      marker.on('click', () => { emit('select', station.station_id); focus(station) })
      return marker
    })
    layer.add(markers)
    map.add(layer)
  } else {
    markers = located.value.map(station => {
      const content = document.createElement('div')
      content.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:4px;'
      const label = document.createElement('strong')
      label.textContent = station.station_name
      label.style.cssText = 'padding:2px 4px;white-space:nowrap;font-size:12px;color:#0f172a;background:#fffffff0;border-radius:4px;'
      const icon = document.createElement('img')
      icon.src = amapPinIcon('#d97706')
      icon.width = 30
      icon.height = 36
      icon.alt = ''
      content.append(label, icon)
      const marker = new sdk.Marker({ position:stationCoordinates(station),title:station.station_name,content,anchor:'bottom-center',zIndex:120 })
      marker.on('click', () => { emit('select', station.station_id); focus(station) })
      return marker
    })
    map.add(markers)
  }
  if (fittedKey !== props.viewportKey) {
    fit()
    fittedKey = props.viewportKey
  }
}

async function initialize() {
  if (disposed || loading.value || map) return
  loading.value = true
  error.value = ''
  try {
    sdk = await loadAmapSdk()
    if (disposed || !canvas.value) return
    map = new sdk.Map(canvas.value, { center: SHANGHAI_CENTER, zoom: 10.8, resizeEnable: true, animateEnable: false })
    fittedKey = null
    mapReady.value = true
    renderMarkers()
  } catch (cause) {
    if (!disposed) {
      clearMarkers()
      map?.destroy()
      map = null
      mapReady.value = false
      error.value = cause.message || '请检查网络后重试，站点清单仍可正常查看。'
    }
  } finally {
    loading.value = false
  }
}

function resize() {
  cancelAnimationFrame(resizeFrame)
  resizeFrame = requestAnimationFrame(() => map?.resize())
}
async function toggleFullscreen() {
  fullscreenError.value = ''
  try {
    if (document.fullscreenElement === frame.value) await document.exitFullscreen()
    else await frame.value?.requestFullscreen()
  } catch { fullscreenError.value = '浏览器暂时无法切换全屏，请使用普通地图视图。' }
}
function fullscreenChanged() {
  fullscreen.value = document.fullscreenElement === frame.value
  nextTick(resize)
}
watch([() => props.stations, () => props.viewportKey], renderMarkers)
watch(() => props.selectedId, id => {
  const station = located.value.find(item => String(item.station_id) === String(id))
  if (station) focus(station)
})
defineExpose({ focus })
onMounted(() => {
  initialize()
  document.addEventListener('fullscreenchange', fullscreenChanged)
  if (typeof ResizeObserver !== 'undefined') { observer = new ResizeObserver(resize); observer.observe(canvas.value) }
})
onBeforeUnmount(() => {
  disposed = true
  observer?.disconnect()
  cancelAnimationFrame(resizeFrame)
  document.removeEventListener('fullscreenchange', fullscreenChanged)
  clearMarkers()
  info?.close()
  map?.destroy()
  map = null
})
</script>

<style scoped>
.coverage-map { display:flex; flex-direction:column; min-width:0; min-height:0; height:100%; overflow:hidden; border:1px solid #cddce8; border-radius:14px; background:#e8eff4; }
.coverage-map.fullscreen { height:100dvh; min-height:0; border:0; border-radius:0; }
.coverage-map.fullscreen .coverage-map-body { min-height:0; }
.fullscreen-error { margin:0; padding:10px 16px; background:#fffbeb; color:#926a24; font-size:12px; }
.coverage-map-toolbar { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px; padding:16px 18px; background:#fff; border-bottom:1px solid #dce6ee; }
.coverage-map-toolbar>div { display:flex; align-items:center; flex-wrap:wrap; gap:10px; }
.coverage-map-toolbar strong { color:#183b56; font-size:14px; }
.coverage-map-toolbar small { color:#6e8296; font-size:12px; }
.pin-key { width:10px; height:10px; border-radius:50%; background:#d97706; box-shadow:0 0 0 4px #fef3c7; margin-right:3px; }
.map-tool { min-height:36px; padding:7px 12px; border:1px solid #d4e1ec; border-radius:8px; background:#fff; color:#395972; font:inherit; font-size:12px; cursor:pointer; }
.map-tool.primary { color:#fff; border-color:#176e9c; background:#176e9c; }
.map-tool:disabled { cursor:not-allowed; opacity:.5; }
.map-tool:focus-visible { outline:2px solid #168ec4; outline-offset:3px; }
.coverage-map-body { position:relative; flex:1; min-height:0; }
.coverage-map-canvas { position:absolute; inset:0; }
.coverage-map-state { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; flex-direction:column; gap:14px; padding:24px; color:#294f68; text-align:center; background:radial-gradient(ellipse at 30% 25%,#e3eef4,#eff4f8); }
.coverage-map-state p { max-width:340px; margin:0; font-size:13px; line-height:1.8; }
.loading-ring { width:28px; height:28px; border:3px solid #c7dce9; border-top-color:#2085b3; border-radius:50%; animation:coverage-spin .8s linear infinite; }
.coverage-map-caption { position:absolute; left:14px; bottom:12px; max-width:calc(100% - 28px); margin:0; padding:8px 11px; border:1px solid #ffffffc9; border-radius:8px; color:#36556b; background:#fffffff0; font-size:11px; line-height:1.7; pointer-events:none; }
.coverage-map-empty { position:absolute; top:20px; left:50%; transform:translateX(-50%); width:max-content; max-width:calc(100% - 32px); padding:12px 16px; border-radius:10px; background:#fffffff5; color:#416177; font-size:13px; text-align:center; box-shadow:0 5px 24px #123b581a; pointer-events:none; }
@keyframes coverage-spin { to { transform:rotate(360deg); } }
@media(max-width:900px) { .coverage-map { height:520px; min-height:0; } .coverage-map.fullscreen { height:100dvh; } .coverage-map-toolbar { padding:12px; } }
@media(max-width:600px) { .map-tool { min-height:44px; } }
@media(prefers-reduced-motion:reduce) { .loading-ring { animation:none; } }
</style>
