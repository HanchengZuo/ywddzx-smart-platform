<template>
  <section ref="frame" class="coverage-map" :class="{ fullscreen, 'beacons-paused': moving || !pageVisible }" aria-label="未检查站点分布">
    <header class="coverage-map-toolbar">
      <div><span class="pin-key" aria-hidden="true"></span><strong>未检查站点</strong><small>{{ located.length }} 座已定位</small></div>
      <div>
        <button class="map-tool motion-tool" :class="{ active: motionEnabled && !reducedMotion }" type="button" :aria-pressed="motionEnabled && !reducedMotion" :disabled="reducedMotion" :title="reducedMotion ? '已遵循系统减少动态效果设置' : '仅为少量可见站点启用轻量呼吸光效'" @click="motionEnabled = !motionEnabled">
          <span class="motion-dot" aria-hidden="true"></span>{{ reducedMotion ? '静态光效' : motionEnabled ? '呼吸光效：开' : '呼吸光效：关' }}
        </button>
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
      <p class="coverage-map-caption"><span class="caption-light" aria-hidden="true"></span>青色 · 未检查<span class="caption-light selected" aria-hidden="true"></span>金色 · 当前选中<small>点击信标查看站点</small></p>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { loadAmapSdk, SHANGHAI_CENTER, amapStationLabel } from '@/utils/amapSdk'
import { stationCoordinates } from '@/utils/schedulingCoverage'
import { schedulingBeaconIcon, choosePulseStations, beaconPhase } from '@/utils/schedulingBeacons'

const props = defineProps({ stations: { type: Array, default: () => [] }, viewportKey: { type:String, default:'' }, selectedId: { type: [String, Number], default: '' } })
const emit = defineEmits(['select'])
const frame = ref(null)
const canvas = ref(null)
const loading = ref(false)
const error = ref('')
const mapReady = ref(false)
const fullscreen = ref(false)
const fullscreenError = ref('')
const motionEnabled = ref(true)
const reducedMotion = ref(false)
const pageVisible = ref(true)
const moving = ref(false)
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
let effectFrame = 0
let motionPreference = null
let selectedMarker = null
let selectedMarkerId = null
const pulses = new Map()

function clearBeacons() {
  if (pulses.size) map?.remove([...pulses.values()].map(item => item.marker))
  pulses.clear()
  if (selectedMarker) map?.remove(selectedMarker)
  selectedMarker = null
  selectedMarkerId = null
}

function viewportBounds() {
  const bounds = map.getBounds()
  if (!bounds) return null
  const sw = bounds.getSouthWest()
  const ne = bounds.getNorthEast()
  const points = [[sw.getLng(), sw.getLat()], [ne.getLng(), ne.getLat()]]
  return points.flat().every(Number.isFinite) ? points : null
}

function syncBeacons() {
  if (!map || disposed) return
  const selected = located.value.find(item => String(item.station_id) === String(props.selectedId))
  const selectedKey = selected ? String(selected.station_id) : null
  if (selectedMarkerId !== selectedKey) {
    if (selectedMarker) map.remove(selectedMarker)
    selectedMarker = null
    selectedMarkerId = selectedKey
    if (selected) {
      const content = document.createElement('img')
      content.src = schedulingBeaconIcon(true)
      content.width = content.height = 40
      content.alt = ''
      content.className = 'coverage-beacon-selected'
      selectedMarker = new sdk.Marker({ position: stationCoordinates(selected), title: selected.station_name, content, anchor: 'center', zIndex: 124 })
      selectedMarker.on('click', () => { emit('select', selected.station_id); focus(selected) })
      map.add(selectedMarker)
    }
  }
  const budget = motionEnabled.value && !reducedMotion.value ? (canvas.value.clientWidth < 600 ? 6 : 12) : 0
  const stations = budget ? choosePulseStations(located.value, props.selectedId, viewportBounds(), budget) : []
  const ids = new Set(stations.map(station => String(station.station_id)))
  for (const [id, item] of pulses) {
    if (!ids.has(id)) { map.remove(item.marker); pulses.delete(id) }
  }
  for (const station of stations) {
    const id = String(station.station_id)
    if (!pulses.has(id)) {
      const content = document.createElement('span')
      content.className = 'coverage-beacon-pulse'
      content.setAttribute('aria-hidden', 'true')
      content.style.setProperty('--beacon-delay', beaconPhase(id))
      const marker = new sdk.Marker({ position: stationCoordinates(station), title: station.station_name, content, anchor: 'center', zIndex: 119 })
      marker.on('click', () => { emit('select', station.station_id); focus(station) })
      pulses.set(id, { marker, content })
      map.add(marker)
    }
    pulses.get(id).content.classList.toggle('is-selected', id === selectedKey)
  }
}

function scheduleBeacons() {
  cancelAnimationFrame(effectFrame)
  effectFrame = requestAnimationFrame(syncBeacons)
}
function mapMoving() { moving.value = true }
function mapSettled() { moving.value = false; scheduleBeacons() }
function visibilityChanged() { pageVisible.value = !document.hidden }
function motionChanged() { reducedMotion.value = motionPreference.matches }

function clearMarkers() {
  clearBeacons()
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
        icon: { type: 'image', image: schedulingBeaconIcon(), size: [40, 40], anchor: 'center' },
        text: amapStationLabel(station.station_name) })
      marker.on('click', () => { emit('select', station.station_id); focus(station) })
      return marker
    })
    layer.add(markers)
    map.add(layer)
  } else {
    markers = located.value.map(station => {
      const content = document.createElement('div')
      content.className = 'coverage-beacon-fallback'
      const label = document.createElement('strong')
      label.textContent = station.station_name
      const icon = document.createElement('img')
      icon.src = schedulingBeaconIcon()
      icon.width = icon.height = 40
      icon.alt = ''
      content.append(label, icon)
      const marker = new sdk.Marker({ position:stationCoordinates(station),title:station.station_name,content,anchor:'center',zIndex:120 })
      marker.on('click', () => { emit('select', station.station_id); focus(station) })
      return marker
    })
    map.add(markers)
  }
  if (fittedKey !== props.viewportKey) {
    fit()
    fittedKey = props.viewportKey
  }
  scheduleBeacons()
}

async function initialize() {
  if (disposed || loading.value || map) return
  loading.value = true
  error.value = ''
  try {
    sdk = await loadAmapSdk()
    if (disposed || !canvas.value) return
    map = new sdk.Map(canvas.value, { center: SHANGHAI_CENTER, zoom: 10.8, resizeEnable: true, animateEnable: false })
    map.on('movestart', mapMoving)
    map.on('zoomstart', mapMoving)
    map.on('moveend', mapSettled)
    map.on('zoomend', mapSettled)
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
  resizeFrame = requestAnimationFrame(() => { map?.resize(); scheduleBeacons() })
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
  scheduleBeacons()
  const station = located.value.find(item => String(item.station_id) === String(id))
  if (station) focus(station)
})
watch([motionEnabled, reducedMotion], scheduleBeacons)
defineExpose({ focus })
onMounted(() => {
  visibilityChanged()
  motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)')
  motionChanged()
  motionPreference.addEventListener('change', motionChanged)
  initialize()
  document.addEventListener('fullscreenchange', fullscreenChanged)
  document.addEventListener('visibilitychange', visibilityChanged)
  if (typeof ResizeObserver !== 'undefined') { observer = new ResizeObserver(resize); observer.observe(canvas.value) }
})
onBeforeUnmount(() => {
  disposed = true
  observer?.disconnect()
  cancelAnimationFrame(resizeFrame)
  cancelAnimationFrame(effectFrame)
  document.removeEventListener('fullscreenchange', fullscreenChanged)
  document.removeEventListener('visibilitychange', visibilityChanged)
  motionPreference?.removeEventListener('change', motionChanged)
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
.pin-key { width:11px; height:11px; border:2px solid #d3fff7; border-radius:3px; background:#12869b; box-shadow:0 0 0 3px #c4f5ed,0 0 12px #42ddce70; transform:rotate(45deg); margin-right:4px; }
.map-tool { min-height:36px; padding:7px 12px; border:1px solid #d4e1ec; border-radius:8px; background:#fff; color:#395972; font:inherit; font-size:12px; cursor:pointer; }
.map-tool.primary { color:#fff; border-color:#176e9c; background:#176e9c; }
.motion-tool { display:inline-flex; align-items:center; gap:7px; }
.motion-tool.active { color:#087b80; border-color:#9dded6; background:#edfbf7; }
.motion-dot { width:6px; height:6px; border-radius:50%; background:currentColor; box-shadow:0 0 0 3px #1fbf9e15; }
.map-tool:disabled { cursor:not-allowed; opacity:.5; }
.map-tool:focus-visible { outline:2px solid #168ec4; outline-offset:3px; }
.coverage-map-body { position:relative; flex:1; min-height:0; }
.coverage-map-canvas { position:absolute; inset:0; }
.coverage-map-state { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; flex-direction:column; gap:14px; padding:24px; color:#294f68; text-align:center; background:radial-gradient(ellipse at 30% 25%,#e3eef4,#eff4f8); }
.coverage-map-state p { max-width:340px; margin:0; font-size:13px; line-height:1.8; }
.loading-ring { width:28px; height:28px; border:3px solid #c7dce9; border-top-color:#2085b3; border-radius:50%; animation:coverage-spin .8s linear infinite; }
.coverage-map-caption { position:absolute; left:14px; bottom:12px; display:flex; flex-wrap:wrap; align-items:center; gap:7px; max-width:calc(100% - 28px); margin:0; padding:8px 11px; border:1px solid #526e7c; border-radius:8px; color:#e3f8f9; background:#0a283bea; box-shadow:0 4px 18px #082b3820; font-size:11px; line-height:1.7; pointer-events:none; }
.coverage-map-caption small { margin-left:5px; color:#a9c8d6; font-size:10px; }
.caption-light { width:7px; height:7px; margin-left:4px; background:#5bfff2; border-radius:2px; transform:rotate(45deg); box-shadow:0 0 7px #5bfff270; }
.caption-light.selected { background:#ffd76a; box-shadow:0 0 7px #ffd76a70; margin-left:10px; }
.coverage-map-canvas :deep(.coverage-beacon-pulse) { --beacon-color:#18c6c4; position:relative; display:block; width:40px; height:40px; cursor:pointer; }
.coverage-map-canvas :deep(.coverage-beacon-pulse.is-selected) { --beacon-color:#e5a62a; }
.coverage-map-canvas :deep(.coverage-beacon-pulse)::before,
.coverage-map-canvas :deep(.coverage-beacon-pulse)::after { content:''; position:absolute; inset:6px; border:1.5px solid var(--beacon-color); border-radius:50%; box-shadow:inset 0 0 5px #39e1d230,0 0 5px #39e1d230; pointer-events:none; animation:beacon-breathe 3.6s ease-out infinite; animation-delay:var(--beacon-delay); }
.coverage-map-canvas :deep(.coverage-beacon-pulse)::after { animation-delay:calc(var(--beacon-delay) - 1.8s); }
.beacons-paused :deep(.coverage-beacon-pulse)::before,
.beacons-paused :deep(.coverage-beacon-pulse)::after { animation-play-state:paused; }
.coverage-map-canvas :deep(.coverage-beacon-selected) { display:block; cursor:pointer; }
.coverage-map-canvas :deep(.coverage-beacon-fallback) { position:relative; width:40px; height:40px; cursor:pointer; }
.coverage-map-canvas :deep(.coverage-beacon-fallback strong) { position:absolute; bottom:100%; left:50%; transform:translateX(-50%); padding:2px 4px; white-space:nowrap; font-size:12px; color:#0f172a; background:#fffffff0; border-radius:4px; }
.coverage-map-empty { position:absolute; top:20px; left:50%; transform:translateX(-50%); width:max-content; max-width:calc(100% - 32px); padding:12px 16px; border-radius:10px; background:#fffffff5; color:#416177; font-size:13px; text-align:center; box-shadow:0 5px 24px #123b581a; pointer-events:none; }
@keyframes coverage-spin { to { transform:rotate(360deg); } }
@keyframes beacon-breathe { 0% { transform:scale(.55); opacity:.8; } 85%,100% { transform:scale(1.75); opacity:0; } }
@media(max-width:900px) { .coverage-map { height:520px; min-height:0; } .coverage-map.fullscreen { height:100dvh; } .coverage-map-toolbar { padding:12px; } }
@media(max-width:600px) { .map-tool { min-height:44px; } }
@media(prefers-reduced-motion:reduce) { .loading-ring { animation:none; } .coverage-map-canvas :deep(.coverage-beacon-pulse)::before,.coverage-map-canvas :deep(.coverage-beacon-pulse)::after { animation:none; opacity:0; } }
</style>
