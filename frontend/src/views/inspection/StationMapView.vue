<template>
  <div v-if="hasPermission" class="page-shell station-map-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>站点地图</h2>
      </div>
    </div>


    <div class="summary-grid">
      <div class="summary-card card-surface">
        <div class="summary-label">地图站点数</div>
        <div class="summary-value">{{ filteredStations.length }}</div>
        <div class="summary-desc">当前满足筛选条件的站点数</div>
      </div>

      <div class="summary-card card-surface">
        <div class="summary-label">存在未整改问题站点</div>
        <div class="summary-value danger">{{ pendingRectificationStationCount }}</div>
        <div class="summary-desc">用于快速定位重点风险站点</div>
      </div>

      <div class="summary-card card-surface">
        <div class="summary-label">存在待复核问题站点</div>
        <div class="summary-value warning">{{ pendingReviewStationCount }}</div>
        <div class="summary-desc">用于跟踪整改后待复核站点</div>
      </div>
    </div>

    <div class="map-card card-surface">
      <div class="map-toolbar">
        <div class="map-toolbar-left">
          <span class="map-toolbar-title">站点分布图</span>
        </div>
        <div class="map-toolbar-right">
          <button class="btn btn-secondary" type="button" @click="toggleAutoRotate">
            {{ autoRotateEnabled ? '暂停轮巡' : '开启轮巡' }}
          </button>
          <button class="btn btn-secondary" type="button" @click="recenterMap">回到上海</button>
          <button class="btn btn-primary" type="button" @click="toggleFullscreen">
            {{ isFullscreen ? '退出全屏' : '全屏显示地图' }}
          </button>
        </div>
      </div>

      <div class="map-frame" :class="{ fullscreen: isFullscreen }" ref="mapFrameRef">
        <div ref="mapContainer" class="map-container"></div>

        <div class="map-overlay map-overlay-left">
          <div class="map-overlay-card glass-panel">
            <div class="overlay-title">地图图例</div>
            <div class="overlay-legend-list">
              <div class="overlay-legend-item">
                <span class="overlay-dot danger"></span>
                <span>存在未整改问题</span>
              </div>
              <div class="overlay-legend-item">
                <span class="overlay-dot warning"></span>
                <span>存在待复核问题</span>
              </div>
              <div class="overlay-legend-item">
                <span class="overlay-dot success"></span>
                <span>当前无待办问题</span>
              </div>
            </div>
          </div>
        </div>

        <div class="map-overlay map-overlay-right">
          <div class="map-overlay-card glass-panel compact">
            <div class="overlay-chip-row">
              <span class="overlay-chip">站点 {{ filteredStations.length }}</span>
              <span class="overlay-chip danger">未整改 {{ pendingRectificationStationCount }}</span>
              <span class="overlay-chip warning">待复核 {{ pendingReviewStationCount }}</span>
            </div>
          </div>
        </div>

        <div class="map-overlay map-overlay-bottom-right">
          <div class="map-overlay-card glass-panel event-panel">
            <div class="event-panel-header">
              <div class="overlay-title event-title">实时事件流</div>
              <div class="event-badge">最近 {{ displayedEventFeed.length }} 条</div>
            </div>
            <div class="event-feed-list">
              <button v-for="event in displayedEventFeed" :key="event.id" class="event-feed-item event-feed-button"
                :class="event.level" type="button" @click="handleEventClick(event)">
                <div class="event-feed-dot"></div>
                <div class="event-feed-content">
                  <div class="event-feed-station">{{ event.stationName }}</div>
                  <div class="event-feed-text">{{ event.text }}</div>
                  <div class="event-feed-time">{{ event.time }}</div>
                </div>
              </button>
            </div>
          </div>
        </div>

        <div v-if="autoRotateTarget" class="map-overlay map-overlay-bottom-left">
          <div class="map-overlay-card glass-panel focus-panel">
            <div class="overlay-title focus-title">当前轮巡站点</div>
            <div class="focus-station-name">{{ autoRotateTarget.station_name }}</div>
            <div class="focus-meta-row">
              <span class="focus-chip">{{ autoRotateTarget.region || '暂无区域' }}</span>
              <span class="focus-chip danger">未整改 {{ autoRotateTarget.pending_rectification_count || 0 }}</span>
              <span class="focus-chip warning">待复核 {{ autoRotateTarget.pending_review_count || 0 }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const AMAP_KEY = '9f35886b6810874b8578ab8dd3d2525e'
const SHANGHAI_CENTER = [121.4737, 31.2304]

const mapContainer = ref(null)
const mapFrameRef = ref(null)
const loading = ref(false)
const isFullscreen = ref(false)
const stations = ref([])
const autoRotateEnabled = ref(true)
const autoRotateTarget = ref(null)
const eventFeed = ref([])
const currentRole = ref('')

const resolveCurrentRole = () => {
  const directRole = localStorage.getItem('role') || localStorage.getItem('user_role') || ''
  if (directRole) return String(directRole).trim()

  const rawUser = localStorage.getItem('user') || localStorage.getItem('currentUser') || ''
  if (!rawUser) return ''

  try {
    const parsedUser = JSON.parse(rawUser)
    return String(parsedUser?.role || '').trim()
  } catch (error) {
    return ''
  }
}

const hasPermission = computed(() => currentRole.value === 'supervisor')

let mapInstance = null
let mapScriptPromise = null
let markers = []
let infoWindowInstance = null
let autoRotateTimer = null
let eventFeedRefreshTimer = null
const prioritizedStations = computed(() => {
  return [...filteredStations.value]
    .filter((station) => !Number.isNaN(Number(station.longitude)) && !Number.isNaN(Number(station.latitude)))
    .sort((a, b) => {
      const aScore = Number(a.pending_rectification_count || 0) * 100 + Number(a.pending_review_count || 0) * 10
      const bScore = Number(b.pending_rectification_count || 0) * 100 + Number(b.pending_review_count || 0) * 10
      return bScore - aScore
    })
})

const displayedEventFeed = computed(() => eventFeed.value.slice(0, 5))


const fetchEventFeed = async () => {
  try {
    const response = await axios.get('/api/event-feed', {
      params: { _ts: Date.now() }
    })
    eventFeed.value = response.data || []
  } catch (error) {
    console.error(error)
    eventFeed.value = []
  }
}

const focusStationOnMap = (station, options = {}) => {
  if (!mapInstance || !window.AMap || !station) return

  const lng = Number(station.longitude)
  const lat = Number(station.latitude)
  if (Number.isNaN(lng) || Number.isNaN(lat)) return

  autoRotateTarget.value = station
  mapInstance.setZoomAndCenter(options.zoom || 12.5, [lng, lat])

  if (infoWindowInstance) {
    infoWindowInstance.setContent(buildInfoHtml(station))
    infoWindowInstance.open(mapInstance, [lng, lat])
  }
}

const startAutoRotate = () => {
  if (autoRotateTimer) {
    clearInterval(autoRotateTimer)
    autoRotateTimer = null
  }

  if (!autoRotateEnabled.value || prioritizedStations.value.length === 0) return

  let currentIndex = 0
  focusStationOnMap(prioritizedStations.value[currentIndex], { zoom: 12.5 })

  autoRotateTimer = setInterval(() => {
    if (!autoRotateEnabled.value || prioritizedStations.value.length === 0) return
    currentIndex = (currentIndex + 1) % prioritizedStations.value.length
    focusStationOnMap(prioritizedStations.value[currentIndex], { zoom: 12.5 })
  }, 6000)
}

const startEventFeedRefresh = () => {
  if (eventFeedRefreshTimer) {
    clearInterval(eventFeedRefreshTimer)
    eventFeedRefreshTimer = null
  }

  eventFeedRefreshTimer = setInterval(() => {
    fetchEventFeed()
  }, 3000)
}

const stopEventFeedRefresh = () => {
  if (eventFeedRefreshTimer) {
    clearInterval(eventFeedRefreshTimer)
    eventFeedRefreshTimer = null
  }
}

const stopAutoRotate = () => {
  if (autoRotateTimer) {
    clearInterval(autoRotateTimer)
    autoRotateTimer = null
  }
}

const toggleAutoRotate = () => {
  autoRotateEnabled.value = !autoRotateEnabled.value
  if (autoRotateEnabled.value) {
    fetchEventFeed()
    startAutoRotate()
  } else {
    stopAutoRotate()
  }
}

const filteredStations = computed(() => stations.value)

const pendingRectificationStationCount = computed(() => {
  return filteredStations.value.filter((station) => Number(station.pending_rectification_count || 0) > 0).length
})

const pendingReviewStationCount = computed(() => {
  return filteredStations.value.filter((station) => Number(station.pending_review_count || 0) > 0).length
})

const loadAmapScript = () => {
  if (window.AMap) {
    return Promise.resolve(window.AMap)
  }

  if (mapScriptPromise) {
    return mapScriptPromise
  }

  mapScriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${AMAP_KEY}`
    script.async = true
    script.onload = () => {
      if (window.AMap) {
        resolve(window.AMap)
      } else {
        reject(new Error('高德地图加载失败'))
      }
    }
    script.onerror = () => reject(new Error('高德地图脚本加载失败'))
    document.head.appendChild(script)
  })

  return mapScriptPromise
}

const fetchStations = async () => {
  try {
    const response = await axios.get('/api/station-map')
    stations.value = response.data || []
  } catch (error) {
    console.error(error)
    stations.value = []
  }
}

const buildInfoHtml = (station) => {
  const latestInspection = station.latest_inspection_date || '暂无'
  const stationType = station.station_type || '暂无'
  const address = station.address || '暂无'
  const managerName = station.station_manager_name || '暂无'
  const managerPhone = station.station_manager_phone || '暂无'
  const pendingRectification = Number(station.pending_rectification_count || 0)
  const pendingReview = Number(station.pending_review_count || 0)
  const closedCount = Number(station.closed_count || 0)

  return `
    <div style="
      background: transparent;
      border: none;
      box-shadow: none;
      padding: 0;
      margin: 0;
    ">
      <div style="
        min-width: 328px;
        padding: 16px;
        border-radius: 22px;
        background: linear-gradient(180deg, rgba(15,23,42,0.78) 0%, rgba(30,41,59,0.72) 100%);
        backdrop-filter: blur(18px) saturate(1.15);
        -webkit-backdrop-filter: blur(18px) saturate(1.15);
        border: 1px solid rgba(96,165,250,0.26);
        box-shadow: 0 22px 44px rgba(2,6,23,0.36), inset 0 1px 0 rgba(255,255,255,0.06);
        color: #e2e8f0;
        position: relative;
        overflow: hidden;
      ">
        <div style="
          position:absolute;
          top:-42px;
          right:-10px;
          width:120px;
          height:120px;
          border-radius:999px;
          background:rgba(59,130,246,0.22);
          filter:blur(20px);
        "></div>
        <div style="
          position:absolute;
          left:0;
          right:0;
          top:0;
          height:1px;
          background:linear-gradient(90deg, rgba(96,165,250,0), rgba(96,165,250,0.75), rgba(96,165,250,0));
        "></div>
        <div style="
          position:absolute;
          left:14px;
          right:14px;
          bottom:0;
          height:1px;
          background:linear-gradient(90deg, rgba(37,99,235,0), rgba(96,165,250,0.55), rgba(37,99,235,0));
        "></div>
        <div style="
          position:absolute;
          top:10px;
          left:-40px;
          width:120px;
          height:2px;
          transform:rotate(-28deg);
          background:linear-gradient(90deg, rgba(255,255,255,0), rgba(96,165,250,0.26), rgba(255,255,255,0));
        "></div>

        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px;position:relative;z-index:1;">
          <div>
            <div style="font-size:18px;font-weight:800;line-height:1.35;margin-bottom:4px;color:#f8fafc;">${station.station_name}</div>
            <div style="font-size:12px;color:#94a3b8;line-height:1.6;">${station.region || '暂无区域'} · ${stationType} · ${station.asset_type || '站点'}</div>
          </div>
          <div style="
            padding: 5px 10px;
            border-radius: 999px;
            background: rgba(37,99,235,0.16);
            color: #bfdbfe;
            font-size: 12px;
            font-weight: 800;
            white-space: nowrap;
            border: 1px solid rgba(96,165,250,0.26);
            box-shadow: inset 0 0 18px rgba(59,130,246,0.12);
          ">站点详情</div>
        </div>

        <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-bottom:14px;position:relative;z-index:1;">
          <div style="padding:10px 10px;border-radius:16px;background:rgba(15,23,42,0.34);border:1px solid rgba(148,163,184,0.16);text-align:center;box-shadow:inset 0 1px 0 rgba(255,255,255,0.04);">
            <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">未整改</div>
            <div style="font-size:18px;font-weight:800;color:#fca5a5;">${pendingRectification}</div>
          </div>
          <div style="padding:10px 10px;border-radius:16px;background:rgba(15,23,42,0.34);border:1px solid rgba(148,163,184,0.16);text-align:center;box-shadow:inset 0 1px 0 rgba(255,255,255,0.04);">
            <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">待复核</div>
            <div style="font-size:18px;font-weight:800;color:#fdba74;">${pendingReview}</div>
          </div>
          <div style="padding:10px 10px;border-radius:16px;background:rgba(15,23,42,0.34);border:1px solid rgba(148,163,184,0.16);text-align:center;box-shadow:inset 0 1px 0 rgba(255,255,255,0.04);">
            <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">已闭环</div>
            <div style="font-size:18px;font-weight:800;color:#86efac;">${closedCount}</div>
          </div>
        </div>

        <div style="display:flex;flex-direction:column;gap:8px;font-size:13px;line-height:1.75;color:#cbd5e1;position:relative;z-index:1;">
          <div><span style="color:#94a3b8;">站点类型：</span>${stationType}</div>
          <div><span style="color:#94a3b8;">资产类型：</span>${station.asset_type || '暂无'}</div>
          <div><span style="color:#94a3b8;">站点负责人：</span>${managerName}</div>
          <div><span style="color:#94a3b8;">联系电话：</span>${managerPhone}</div>
          <div><span style="color:#94a3b8;">站点地址：</span>${address}</div>
          <div><span style="color:#94a3b8;">最近巡检日期：</span>${latestInspection}</div>
        </div>
      </div>
    </div>
  `
}
const handleEventClick = (event) => {
  const matchedStation = filteredStations.value.find((station) => {
    return String(station.station_id || station.id || '').trim() === String(event.stationId || '').trim()
  })

  if (!matchedStation) return

  autoRotateEnabled.value = false
  stopAutoRotate()
  focusStationOnMap(matchedStation, { zoom: 12.5 })
}

const getMarkerColor = (station) => {
  if (Number(station.pending_rectification_count || 0) > 0) return '#dc2626'
  if (Number(station.pending_review_count || 0) > 0) return '#d97706'
  return '#16a34a'
}

const clearMarkers = () => {
  if (!mapInstance || !markers.length) return
  markers.forEach((marker) => mapInstance.remove(marker))
  markers = []
}

const renderMarkers = async () => {
  if (!mapInstance || !window.AMap) return

  const AMap = window.AMap
  clearMarkers()

  if (infoWindowInstance) {
    infoWindowInstance.close()
  }

  infoWindowInstance = new AMap.InfoWindow({
    offset: new AMap.Pixel(0, -24),
    isCustom: true,
    closeWhenClickMap: true,
    autoMove: true
  })

  const positions = []

  filteredStations.value.forEach((station) => {
    const lng = Number(station.longitude)
    const lat = Number(station.latitude)

    if (Number.isNaN(lng) || Number.isNaN(lat)) return

    positions.push([lng, lat])

    const color = getMarkerColor(station)
    const pendingRectification = Number(station.pending_rectification_count || 0)
    const pendingReview = Number(station.pending_review_count || 0)
    const pulseDuration = pendingRectification > 0 ? '1.35s' : pendingReview > 0 ? '1.8s' : '2.6s'
    const pulseOpacity = pendingRectification > 0 ? '0.34' : pendingReview > 0 ? '0.26' : '0.16'
    const pulseScale = pendingRectification > 0 ? '2.4' : pendingReview > 0 ? '2.0' : '1.7'

    const marker = new AMap.Marker({
      position: [lng, lat],
      title: station.station_name,
      anchor: 'bottom-center',
      content: `
        <div style="
          position: relative;
          width: 18px;
          height: 18px;
          display: flex;
          align-items: center;
          justify-content: center;
        ">
          <span style="
            position: absolute;
            inset: 0;
            border-radius: 999px;
            background: ${color};
            opacity: ${pulseOpacity};
            animation: mapPulse ${pulseDuration} ease-out infinite;
            transform-origin: center;
            box-shadow: 0 0 18px ${color};
            --pulse-scale: ${pulseScale};
          "></span>
          <span style="
            position: absolute;
            width: 18px;
            height: 18px;
            border-radius: 999px;
            background: rgba(255,255,255,0.14);
            border: 1px solid rgba(255,255,255,0.22);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            box-shadow: 0 0 14px rgba(15,23,42,0.22);
          "></span>
          <span style="
            position: relative;
            width: 8px;
            height: 8px;
            border-radius: 999px;
            background: ${color};
            box-shadow: 0 0 10px ${color};
          "></span>
        </div>
      `
    })

    marker.setLabel({
      direction: 'top',
      offset: new AMap.Pixel(0, -6),
      content: `
        <div style="
          background: transparent;
          border: none;
          box-shadow: none;
          padding: 0;
          margin: 0;
        ">
          <div style="
            position: relative;
            display:flex;
            align-items:center;
            gap:8px;
            padding:5px 12px 5px 9px;
            border-radius:999px;
            color:#e2e8f0;
            font-size:12px;
            font-weight:700;
            background:linear-gradient(180deg, rgba(15,23,42,0.76) 0%, rgba(30,41,59,0.70) 100%);
            border:1px solid rgba(96,165,250,0.22);
            backdrop-filter:blur(14px);
            -webkit-backdrop-filter:blur(14px);
            box-shadow:0 12px 24px rgba(2,6,23,.24), inset 0 1px 0 rgba(255,255,255,0.05);
            white-space:nowrap;
            overflow:hidden;
          ">
            <span style="
              position:absolute;
              top:0;
              left:-60%;
              width:40%;
              height:100%;
              background:linear-gradient(90deg, rgba(255,255,255,0), rgba(148,163,184,0.16), rgba(255,255,255,0));
              transform:skewX(-22deg);
              animation: labelScan 3.6s linear infinite;
            "></span>
            <span style="
              width:9px;
              height:9px;
              border-radius:999px;
              display:inline-block;
              background:${color};
              box-shadow:0 0 0 4px rgba(255,255,255,0.10), 0 0 14px ${color};
              flex-shrink:0;
              position:relative;
              z-index:1;
            "></span>
            <span style="position:relative;z-index:1;">${station.station_name}</span>
          </div>
        </div>
      `
    })

    marker.on('click', () => {
      autoRotateTarget.value = station
      infoWindowInstance.setContent(buildInfoHtml(station))
      infoWindowInstance.open(mapInstance, [lng, lat])
    })

    mapInstance.add(marker)
    markers.push(marker)
  })

  if (positions.length === 1) {
    mapInstance.setZoomAndCenter(13, positions[0])
    return
  }

  if (positions.length > 1) {
    mapInstance.setFitView(markers, false, [80, 80, 80, 80])
  }
}

const initMap = async () => {
  const AMap = await loadAmapScript()

  mapInstance = new AMap.Map(mapContainer.value, {
    zoom: 10.8,
    center: SHANGHAI_CENTER,
    resizeEnable: true
  })

  await fetchStations()
  await fetchEventFeed()
  await renderMarkers()
  startAutoRotate()
  startEventFeedRefresh()
}

const recenterMap = () => {
  if (!mapInstance) return
  autoRotateTarget.value = null
  mapInstance.setZoomAndCenter(10.8, SHANGHAI_CENTER)
  if (infoWindowInstance) infoWindowInstance.close()
}

const toggleFullscreen = async () => {
  const target = mapFrameRef.value
  if (!target) return

  try {
    if (!document.fullscreenElement) {
      await target.requestFullscreen()
    } else {
      await document.exitFullscreen()
    }
  } catch (error) {
    console.error(error)
  }
}

const handleFullscreenChange = () => {
  isFullscreen.value = Boolean(document.fullscreenElement)
  setTimeout(() => {
    if (mapInstance) {
      mapInstance.resize()
      if (filteredStations.value.length > 1) {
        mapInstance.setFitView(markers, false, [80, 80, 80, 80])
      }
    }
  }, 120)
  if (autoRotateEnabled.value) startAutoRotate()
}

watch(
  filteredStations,
  async () => {
    await renderMarkers()
    if (autoRotateEnabled.value) {
      startAutoRotate()
    }
  },
  { deep: true }
)

onMounted(() => {
  currentRole.value = resolveCurrentRole()

  if (!hasPermission.value) {
    return
  }

  initMap().catch((error) => {
    console.error(error)
  })
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  window.addEventListener('focus', fetchEventFeed)
  document.addEventListener('visibilitychange', fetchEventFeed)
})

onBeforeUnmount(() => {
  if (!hasPermission.value) {
    return
  }

  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  window.removeEventListener('focus', fetchEventFeed)
  document.removeEventListener('visibilitychange', fetchEventFeed)
  stopAutoRotate()
  stopEventFeedRefresh()
  clearMarkers()
  if (mapInstance) {
    mapInstance.destroy()
    mapInstance = null
  }
})
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-surface {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dbe4ee;
  border-radius: 22px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
}

.page-header {
  padding: 24px 28px;
}

.page-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 14px;
}

.page-header h2 {
  margin: 0;
  font-size: 34px;
  color: #0f172a;
}


.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(220px, 1fr));
  gap: 16px;
}

.summary-card {
  padding: 22px;
}

.summary-label {
  color: #64748b;
  font-size: 14px;
  margin-bottom: 10px;
}

.summary-value {
  font-size: 34px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
  margin-bottom: 8px;
}

.summary-value.danger {
  color: #dc2626;
}

.summary-value.warning {
  color: #d97706;
}

.summary-desc {
  color: #64748b;
  font-size: 14px;
  line-height: 1.7;
}

.map-card {
  padding: 16px;
}

.map-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.map-toolbar-title {
  font-size: 15px;
  font-weight: 800;
  color: #334155;
}

.map-toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.map-frame {
  width: 100%;
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  background:
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.12), transparent 26%),
    linear-gradient(180deg, rgba(2, 6, 23, 0.88) 0%, rgba(15, 23, 42, 0.86) 100%);
  border: 1px solid rgba(59, 130, 246, 0.16);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 16px 36px rgba(15, 23, 42, 0.12);
}

.map-frame.fullscreen {
  width: 100vw;
  height: 100vh;
  padding: 16px;
  background:
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.16), transparent 24%),
    linear-gradient(180deg, rgba(2, 6, 23, 0.96) 0%, rgba(15, 23, 42, 0.94) 100%);
}

.map-overlay {
  position: absolute;
  z-index: 12;
  pointer-events: none;
}

.map-overlay-left {
  top: 16px;
  left: 16px;
}

.map-overlay-right {
  top: 16px;
  right: 16px;
}

.glass-panel {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(16px) saturate(1.08);
  -webkit-backdrop-filter: blur(16px) saturate(1.08);
  border: 1px solid rgba(96, 165, 250, 0.18);
  box-shadow:
    0 16px 30px rgba(2, 6, 23, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.glass-panel.compact {
  padding: 10px 12px;
}

.overlay-title {
  font-size: 13px;
  font-weight: 800;
  color: #dbeafe;
  margin-bottom: 10px;
}

.overlay-legend-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.overlay-legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #cbd5e1;
}

.overlay-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  display: inline-block;
  flex-shrink: 0;
}

.overlay-dot.danger {
  background: #dc2626;
  box-shadow: 0 0 10px rgba(220, 38, 38, 0.35);
}

.overlay-dot.warning {
  background: #d97706;
  box-shadow: 0 0 10px rgba(217, 119, 6, 0.35);
}

.overlay-dot.success {
  background: #16a34a;
  box-shadow: 0 0 10px rgba(22, 163, 74, 0.35);
}

.overlay-chip-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.overlay-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.42);
  border: 1px solid rgba(96, 165, 250, 0.14);
  color: #dbeafe;
  font-size: 12px;
  font-weight: 800;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.overlay-chip.danger {
  color: #fca5a5;
}

.overlay-chip.warning {
  color: #fdba74;
}

.map-container {
  width: 100%;
  height: calc(100vh - 380px);
  min-height: 620px;
  border-radius: 20px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.18);
}

.map-frame.fullscreen .map-container {
  height: calc(100vh - 32px);
  min-height: auto;
}

@keyframes mapPulse {
  0% {
    transform: scale(0.92);
    opacity: 0.32;
  }

  70% {
    transform: scale(var(--pulse-scale, 2));
    opacity: 0;
  }

  100% {
    transform: scale(var(--pulse-scale, 2));
    opacity: 0;
  }
}

.map-overlay-bottom-right {
  right: 16px;
  bottom: 16px;
}

.map-overlay-bottom-left {
  left: 16px;
  bottom: 16px;
}

.event-panel {
  width: 320px;
}

.event-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.event-title {
  margin-bottom: 0;
}

.event-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.42);
  border: 1px solid rgba(96, 165, 250, 0.16);
  color: #dbeafe;
  font-size: 12px;
  font-weight: 800;
}

.event-feed-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.event-feed-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.32);
  border: 1px solid rgba(96, 165, 250, 0.10);
}

.event-feed-button {
  width: 100%;
  text-align: left;
  border: 1px solid rgba(96, 165, 250, 0.10);
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
}

.event-feed-button:hover {
  background: rgba(30, 41, 59, 0.48);
}

.event-feed-item.danger {
  border-color: rgba(248, 113, 113, 0.18);
}

.event-feed-item.warning {
  border-color: rgba(251, 191, 36, 0.18);
}

.event-feed-dot {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 999px;
  background: #60a5fa;
  flex-shrink: 0;
  box-shadow: 0 0 10px rgba(96, 165, 250, 0.45);
}

.event-feed-item.danger .event-feed-dot {
  background: #f87171;
  box-shadow: 0 0 10px rgba(248, 113, 113, 0.5);
}

.event-feed-item.warning .event-feed-dot {
  background: #fbbf24;
  box-shadow: 0 0 10px rgba(251, 191, 36, 0.5);
}

.event-feed-content {
  min-width: 0;
}

.event-feed-station {
  font-size: 13px;
  font-weight: 800;
  color: #f8fafc;
  margin-bottom: 4px;
}

.event-feed-text {
  font-size: 12px;
  line-height: 1.7;
  color: #cbd5e1;
  margin-bottom: 4px;
}

.event-feed-time {
  font-size: 11px;
  color: #94a3b8;
}

.focus-panel {
  min-width: 260px;
}

.focus-title {
  margin-bottom: 8px;
}

.focus-station-name {
  font-size: 18px;
  font-weight: 800;
  color: #f8fafc;
  margin-bottom: 10px;
}

.focus-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.focus-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.38);
  border: 1px solid rgba(96, 165, 250, 0.14);
  color: #dbeafe;
  font-size: 12px;
  font-weight: 800;
}

.focus-chip.danger {
  color: #fca5a5;
}

.focus-chip.warning {
  color: #fdba74;
}

@keyframes labelScan {
  0% {
    left: -60%;
  }

  100% {
    left: 130%;
  }
}

.map-frame::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  background-image:
    linear-gradient(rgba(96, 165, 250, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(96, 165, 250, 0.05) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: linear-gradient(180deg, rgba(255, 255, 255, 0.42), rgba(255, 255, 255, 0.12));
  -webkit-mask-image: linear-gradient(180deg, rgba(255, 255, 255, 0.42), rgba(255, 255, 255, 0.12));
  z-index: 1;
}

.btn {
  height: 42px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.18s ease;
}

.btn-primary {
  background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
  border-color: #2563eb;
  color: #fff;
  box-shadow: 0 12px 22px rgba(37, 99, 235, 0.16);
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%);
}

.btn-secondary:hover:not(:disabled) {
  background: #f8fafc;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

@media (max-width: 1200px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .page-header h2 {
    font-size: 30px;
  }

  .map-container {
    min-height: 500px;
  }

  .map-overlay-left,
  .map-overlay-right,
  .map-overlay-bottom-right,
  .map-overlay-bottom-left {
    position: static;
  }

  .map-frame {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 10px;
  }

  .glass-panel {
    width: 100%;
  }

  .event-panel {
    width: 100%;
  }
}

:deep(.amap-info-contentContainer) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}

:deep(.amap-info-content) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}

:deep(.amap-info-sharp) {
  display: none !important;
}

:deep(.amap-info-close) {
  display: none !important;
}

:deep(.amap-marker-label) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}
</style>