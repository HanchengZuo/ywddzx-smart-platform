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

      <div class="mobile-map-brief">
        <div class="mobile-map-brief-head">
          <div>
            <span class="mobile-map-kicker">移动端事件视图</span>
            <h3>实时事件流</h3>
          </div>
          <span class="mobile-event-count">最近 {{ displayedEventFeed.length }} 条</span>
        </div>

        <p class="mobile-map-copy">
          移动端优先呈现站点风险动态，地图分布图请在电脑端查看，便于获得更完整的空间定位体验。
        </p>

        <div class="mobile-map-stat-row">
          <div class="mobile-map-stat">
            <span>站点</span>
            <strong>{{ filteredStations.length }}</strong>
          </div>
          <div class="mobile-map-stat danger">
            <span>未整改问题</span>
            <strong>{{ pendingRectificationIssueCount }}</strong>
          </div>
          <div class="mobile-map-stat warning">
            <span>待复核问题</span>
            <strong>{{ pendingReviewIssueCount }}</strong>
          </div>
        </div>

        <div v-if="autoRotateTarget" class="mobile-selected-station">
          <span>已选择事件站点</span>
          <strong>{{ autoRotateTarget.station_name }}</strong>
          <em>
            {{ autoRotateTarget.region || '暂无区域' }}｜未整改 {{ autoRotateTarget.pending_rectification_count || 0 }}｜待复核
            {{ autoRotateTarget.pending_review_count || 0 }}
          </em>
        </div>

        <div class="mobile-event-timeline">
          <button v-for="event in displayedEventFeed" :key="event.id" class="mobile-event-card"
            :class="event.level" type="button" @click="handleEventClick(event)">
            <span class="mobile-event-dot"></span>
            <span class="mobile-event-body">
              <strong>{{ event.stationName }}</strong>
              <span>{{ event.text }}</span>
              <em>{{ event.time }}</em>
            </span>
          </button>

          <div v-if="displayedEventFeed.length === 0" class="mobile-event-empty">
            当前暂无实时事件，系统会自动刷新新的站点动态。
          </div>
        </div>
      </div>

      <div class="map-frame" :class="{ fullscreen: isFullscreen }" ref="mapFrameRef">
        <div ref="mapContainer" class="map-container"></div>
        <div v-if="!isMobileMapMode && (mapBooting || mapError)" class="map-loading-layer">
          <div class="map-loading-card glass-panel">
            <div v-if="!mapError" class="map-loading-spinner"></div>
            <strong>{{ mapError ? '地图加载遇到问题' : '站点地图加载中' }}</strong>
            <span>{{ mapError || '正在优先加载站点数据，地图会在页面稳定后自动呈现。' }}</span>
          </div>
        </div>

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
              <span class="overlay-chip danger">未整改问题 {{ pendingRectificationIssueCount }}</span>
              <span class="overlay-chip warning">待复核问题 {{ pendingReviewIssueCount }}</span>
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

    <div v-if="issueDialog.visible" class="station-issue-dialog-backdrop" @click.self="closeStationIssueDialog">
      <section class="station-issue-dialog card-surface" role="dialog" aria-modal="true"
        :aria-label="stationIssueDialogTitle">
        <header class="station-issue-dialog-head">
          <div>
            <span class="station-issue-dialog-kicker">站点问题清单</span>
            <h3>{{ stationIssueDialogTitle }}</h3>
            <p>{{ issueDialog.station?.region || '暂无片区' }}｜共 {{ issueDialog.total }} 项｜轮巡已暂停</p>
          </div>
          <button class="station-issue-dialog-close" type="button" aria-label="关闭" @click="closeStationIssueDialog">×</button>
        </header>

        <div v-if="issueDialog.loading" class="station-issue-dialog-state">
          <span class="station-issue-loading-orb"></span>
          <strong>正在读取关联问题</strong>
          <p>仅加载当前页数据，请稍候。</p>
        </div>
        <div v-else-if="issueDialog.error" class="station-issue-dialog-state error">
          <strong>问题清单加载失败</strong>
          <p>{{ issueDialog.error }}</p>
          <button class="btn btn-secondary" type="button" @click="fetchStationIssues(issueDialog.page)">重新加载</button>
        </div>
        <div v-else-if="!issueDialog.items.length" class="station-issue-dialog-state">
          <strong>当前状态下暂无问题</strong>
          <p>站点统计数据刷新后可能发生变化。</p>
        </div>
        <div v-else class="station-issue-list">
          <article v-for="item in issueDialog.items" :key="item.id" class="station-issue-card">
            <div class="station-issue-card-main">
              <div class="station-issue-card-title">
                <span class="station-issue-id">#{{ item.id }}</span>
                <span class="station-issue-time">{{ item.inspection_time || item.inspection_date || '暂无检查时间' }}</span>
                <span class="station-issue-status" :class="issueDialog.statusKey">{{ item.status }}</span>
              </div>
              <p class="station-issue-description">{{ item.description || '暂无问题描述' }}</p>

              <dl v-if="showReviewIssueFields" class="station-issue-detail-grid">
                <div><dt>整改结果</dt><dd>{{ item.rectification_result || '待复核' }}</dd></div>
                <div><dt>整改时间</dt><dd>{{ item.rectification_at || '暂无' }}</dd></div>
                <div class="wide"><dt>整改说明</dt><dd>{{ item.rectification_note || '暂无整改说明' }}</dd></div>
                <template v-if="showFullIssueFields">
                  <div><dt>检查表</dt><dd>{{ item.inspection_table_name || '暂无' }}</dd></div>
                  <div><dt>检查人</dt><dd>{{ item.inspector || '暂无' }}</dd></div>
                  <div><dt>站点负责人</dt><dd>{{ item.station_manager_name || '暂无' }}</dd></div>
                  <div><dt>问题状态</dt><dd>{{ item.status || '暂无' }}</dd></div>
                  <div><dt>外部规范ID</dt><dd>{{ item.standard_id || '暂无' }}</dd></div>
                  <div><dt>内部规范ID</dt><dd>{{ item.internal_standard_id || '暂无' }}</dd></div>
                  <div class="wide"><dt>外部规范</dt><dd>{{ item.standard_detail_text || '暂无' }}</dd></div>
                  <div class="wide"><dt>内部规范</dt><dd>{{ item.internal_standard_detail_text || '暂无' }}</dd></div>
                  <div><dt>审核状态</dt><dd>{{ item.audit_status_label || '暂无' }}</dd></div>
                  <div><dt>审核来源</dt><dd>{{ item.audit_source === 'automatic' ? '自动审核' : item.audit_source ? '人工审核' : '暂无' }}</dd></div>
                  <div><dt>审核人</dt><dd>{{ item.audited_by_name || '暂无' }}</dd></div>
                  <div><dt>审核时间</dt><dd>{{ item.audited_at || '暂无' }}</dd></div>
                  <div><dt>复核结果</dt><dd>{{ item.review_result || '暂无' }}</dd></div>
                  <div><dt>复核时间</dt><dd>{{ item.review_at || '暂无' }}</dd></div>
                  <div class="wide"><dt>复核说明</dt><dd>{{ item.review_note || '暂无复核说明' }}</dd></div>
                </template>
              </dl>
            </div>

            <div class="station-issue-photo-column">
              <button v-if="item.issue_photo" class="station-issue-photo-button" type="button"
                @click="openImagePreview(item.issue_photo, `问题 #${item.id} 照片`)">
                <img :src="resolveImage(item.issue_photo)" alt="问题照片" loading="lazy" />
                <span>查看问题照片</span>
              </button>
              <div v-else class="station-issue-photo-empty">暂无问题照片</div>
              <button v-if="showReviewIssueFields && item.rectification_photo" class="station-issue-photo-link" type="button"
                @click="openImagePreview(item.rectification_photo, `问题 #${item.id} 整改照片`)">查看整改照片</button>
              <button v-if="showFullIssueFields && item.review_photo" class="station-issue-photo-link" type="button"
                @click="openImagePreview(item.review_photo, `问题 #${item.id} 复核照片`)">查看复核照片</button>
            </div>
          </article>
        </div>

        <footer v-if="!issueDialog.loading && issueDialog.totalPages > 1" class="station-issue-dialog-footer">
          <span>第 {{ issueDialog.page }} / {{ issueDialog.totalPages }} 页</span>
          <div>
            <button class="btn btn-secondary" type="button" :disabled="issueDialog.page <= 1"
              @click="fetchStationIssues(issueDialog.page - 1)">上一页</button>
            <button class="btn btn-primary" type="button" :disabled="issueDialog.page >= issueDialog.totalPages"
              @click="fetchStationIssues(issueDialog.page + 1)">下一页</button>
          </div>
        </footer>
      </section>
    </div>

    <div v-if="imagePreview.visible" class="station-image-preview-backdrop" @click.self="closeImagePreview">
      <section class="station-image-preview" role="dialog" aria-modal="true" :aria-label="imagePreview.title">
        <header><strong>{{ imagePreview.title }}</strong><button type="button" @click="closeImagePreview">×</button></header>
        <img :src="imagePreview.src" :alt="imagePreview.title" />
      </section>
    </div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const AMAP_KEY = '9f35886b6810874b8578ab8dd3d2525e'
const SHANGHAI_CENTER = [121.4737, 31.2304]

const mapContainer = ref(null)
const mapFrameRef = ref(null)
const mapBooting = ref(false)
const mapError = ref('')
const isFullscreen = ref(false)
const stations = ref([])
const autoRotateEnabled = ref(true)
const autoRotateTarget = ref(null)
const eventFeed = ref([])
const currentRole = ref('')
const isMobileMapMode = ref(false)
const issueDialog = ref({
  visible: false,
  loading: false,
  error: '',
  station: null,
  statusKey: '',
  items: [],
  total: 0,
  page: 1,
  pageSize: 12,
  totalPages: 1
})
const imagePreview = ref({ visible: false, src: '', title: '' })
const MOBILE_MAP_QUERY = '(max-width: 900px)'
const STATION_MAP_CACHE_KEY = 'station_map_cache_v1'
const STATION_MAP_CACHE_TTL = 5 * 60 * 1000
const STATION_ISSUE_STATUS_META = {
  pending_rectification: { label: '未整改问题', shortLabel: '未整改' },
  pending_review: { label: '待复核问题', shortLabel: '待复核' },
  closed: { label: '已闭环问题', shortLabel: '已闭环' }
}

const resolveCurrentRole = () => {
  const directRole = localStorage.getItem('role') || localStorage.getItem('user_role') || ''
  if (directRole) return String(directRole).trim()

  const rawUser = localStorage.getItem('user') || localStorage.getItem('currentUser') || ''
  if (!rawUser) return ''

  try {
    const parsedUser = JSON.parse(rawUser)
    return String(parsedUser?.role || '').trim()
  } catch {
    return ''
  }
}

let localPermissions = {}
try {
  localPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch {
  localPermissions = {}
}
const hasPermission = computed(() => currentRole.value === 'root' || Boolean(localPermissions.view_station_map))

let mapInstance = null
let mapScriptPromise = null
let markers = []
let labelsLayer = null
let infoWindowInstance = null
let autoRotateTimer = null
let eventFeedRefreshTimer = null
let stationRefreshTimer = null
let markerRenderToken = 0
let markerVisualSignature = ''
let mapInteracting = false
let markerRenderPending = false
let pausedViewSnapshot = null
let issueDialogRequestSequence = 0
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
const stationIssueDialogTitle = computed(() => {
  const stationName = issueDialog.value.station?.station_name || '站点'
  const statusLabel = STATION_ISSUE_STATUS_META[issueDialog.value.statusKey]?.label || '问题'
  return `${stationName} · ${statusLabel}`
})
const showReviewIssueFields = computed(() => ['pending_review', 'closed'].includes(issueDialog.value.statusKey))
const showFullIssueFields = computed(() => issueDialog.value.statusKey === 'closed')

const resolveImage = (path) => {
  const value = String(path || '').trim()
  if (!value) return ''
  if (/^https?:\/\//i.test(value)) return value
  return `/storage/${value.startsWith('/') ? value.slice(1) : value}`
}

const escapeHtml = (value) => String(value ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#039;')

const waitForBrowserIdle = (timeout = 700) => {
  if (typeof window === 'undefined') return Promise.resolve()
  if ('requestIdleCallback' in window) {
    return new Promise((resolve) => window.requestIdleCallback(resolve, { timeout }))
  }
  return new Promise((resolve) => window.setTimeout(resolve, Math.min(timeout, 320)))
}

const yieldToBrowserFrame = () => {
  if (typeof window === 'undefined') return Promise.resolve()
  return new Promise((resolve) => window.requestAnimationFrame(() => resolve()))
}

const readCachedStations = () => {
  try {
    const cached = JSON.parse(sessionStorage.getItem(STATION_MAP_CACHE_KEY) || '{}')
    if (!cached?.createdAt || !Array.isArray(cached.items)) return null
    if (Date.now() - Number(cached.createdAt) > STATION_MAP_CACHE_TTL) return null
    return cached.items
  } catch {
    return null
  }
}

const writeCachedStations = (items) => {
  try {
    sessionStorage.setItem(STATION_MAP_CACHE_KEY, JSON.stringify({
      createdAt: Date.now(),
      items
    }))
  } catch {
    // 缓存只是首屏加速手段，失败不影响页面功能。
  }
}

const syncMobileMapMode = () => {
  if (typeof window === 'undefined' || !window.matchMedia) {
    isMobileMapMode.value = false
    return
  }
  isMobileMapMode.value = window.matchMedia(MOBILE_MAP_QUERY).matches
}

const handleViewportResize = () => {
  const wasMobile = isMobileMapMode.value
  syncMobileMapMode()

  if (!wasMobile && isMobileMapMode.value) {
    stopAutoRotate()
    return
  }

  if (wasMobile && !isMobileMapMode.value && !mapInstance && hasPermission.value) {
    initMap().catch((error) => {
      console.error(error)
    })
    return
  }

  if (wasMobile && !isMobileMapMode.value && mapInstance && autoRotateEnabled.value) {
    startAutoRotate()
  }
}


const fetchEventFeed = async () => {
  try {
    const response = await axios.get('/api/event-feed', {
      params: {
        user_id: localStorage.getItem('user_id') || '',
        _ts: Date.now()
      }
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

const captureMapView = () => {
  if (!mapInstance) return null
  const center = mapInstance.getCenter?.()
  const lng = Number(center?.lng ?? center?.getLng?.())
  const lat = Number(center?.lat ?? center?.getLat?.())
  const zoom = Number(mapInstance.getZoom?.())
  if (!Number.isFinite(lng) || !Number.isFinite(lat) || !Number.isFinite(zoom)) return null
  return { center: [lng, lat], zoom }
}

const restoreMapView = (snapshot) => {
  if (!mapInstance || !snapshot) return
  mapInstance.setZoomAndCenter(snapshot.zoom, snapshot.center, true)
}

const setMapAnimationEnabled = (enabled) => {
  mapInstance?.setStatus?.({ animateEnable: Boolean(enabled) })
}

const startAutoRotate = () => {
  if (autoRotateTimer) {
    clearInterval(autoRotateTimer)
    autoRotateTimer = null
  }

  if (isMobileMapMode.value || !mapInstance || !autoRotateEnabled.value || prioritizedStations.value.length === 0) return

  pausedViewSnapshot = null
  setMapAnimationEnabled(true)

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
  }, 10000)
}

const stopEventFeedRefresh = () => {
  if (eventFeedRefreshTimer) {
    clearInterval(eventFeedRefreshTimer)
    eventFeedRefreshTimer = null
  }
}

const startStationRefresh = () => {
  if (stationRefreshTimer) {
    clearInterval(stationRefreshTimer)
    stationRefreshTimer = null
  }

  stationRefreshTimer = setInterval(() => {
    fetchStations()
  }, 60000)
}

const stopStationRefresh = () => {
  if (stationRefreshTimer) {
    clearInterval(stationRefreshTimer)
    stationRefreshTimer = null
  }
}

const stopAutoRotate = () => {
  if (autoRotateTimer) {
    clearInterval(autoRotateTimer)
    autoRotateTimer = null
  }
}

const pauseAutoRotate = () => {
  if (mapInstance) pausedViewSnapshot = captureMapView()
  autoRotateEnabled.value = false
  stopAutoRotate()
  setMapAnimationEnabled(false)
  restoreMapView(pausedViewSnapshot)
}

const toggleAutoRotate = () => {
  if (!autoRotateEnabled.value) {
    autoRotateEnabled.value = true
    fetchEventFeed()
    startAutoRotate()
  } else {
    pauseAutoRotate()
  }
}

const filteredStations = computed(() => stations.value)

const pendingRectificationStationCount = computed(() => {
  return filteredStations.value.filter((station) => Number(station.pending_rectification_count || 0) > 0).length
})

const pendingReviewStationCount = computed(() => {
  return filteredStations.value.filter((station) => Number(station.pending_review_count || 0) > 0).length
})

const sumPendingIssueCount = (field) => {
  return filteredStations.value.reduce((total, station) => {
    const count = Number(station[field] || 0)
    return total + (Number.isFinite(count) ? count : 0)
  }, 0)
}

const pendingRectificationIssueCount = computed(() => sumPendingIssueCount('pending_rectification_count'))

const pendingReviewIssueCount = computed(() => sumPendingIssueCount('pending_review_count'))

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

const syncAutoRotateTarget = () => {
  if (!autoRotateTarget.value) return
  const targetId = String(autoRotateTarget.value.station_id || autoRotateTarget.value.id || '').trim()
  if (!targetId) return

  const latestStation = stations.value.find((station) => {
    return String(station.station_id || station.id || '').trim() === targetId
  })
  if (latestStation) {
    autoRotateTarget.value = latestStation
  }
}

const buildMarkerVisualSignature = (rows) => {
  return (Array.isArray(rows) ? rows : []).map((station) => [
    station.station_id || station.id || '',
    station.station_name || '',
    station.longitude || '',
    station.latitude || '',
    station.pending_rectification_count || 0,
    station.pending_review_count || 0
  ].join(':')).join('|')
}

const requestMarkerRender = () => {
  if (!mapInstance) return
  if (mapInteracting) {
    markerRenderPending = true
    return
  }
  markerRenderPending = false
  waitForBrowserIdle(500).then(() => renderMarkers()).catch((error) => console.error(error))
}

const applyStationRows = (rows, { cache = true } = {}) => {
  const nextRows = Array.isArray(rows) ? rows : []
  const nextVisualSignature = buildMarkerVisualSignature(nextRows)
  const markerAppearanceChanged = nextVisualSignature !== markerVisualSignature
  stations.value = nextRows
  if (cache) writeCachedStations(nextRows)
  syncAutoRotateTarget()
  if (markerAppearanceChanged) {
    markerVisualSignature = nextVisualSignature
    requestMarkerRender()
  } else if (autoRotateTarget.value && infoWindowInstance) {
    infoWindowInstance.setContent(buildInfoHtml(autoRotateTarget.value))
  }
}

const fetchStations = async (options = {}) => {
  const preferCache = Boolean(options.preferCache)
  if (preferCache && !stations.value.length) {
    const cachedRows = readCachedStations()
    if (cachedRows) {
      applyStationRows(cachedRows, { cache: false })
      window.setTimeout(() => fetchStations().catch((error) => console.error(error)), 0)
      return
    }
  }

  try {
    const response = await axios.get('/api/station-map', {
      params: {
        user_id: localStorage.getItem('user_id') || '',
        _ts: Date.now()
      }
    })
    applyStationRows(response.data || [])
  } catch (error) {
    console.error(error)
    if (!stations.value.length) {
      stations.value = []
    }
  }
}

const buildInfoHtml = (station) => {
  const stationId = escapeHtml(station.station_id || station.id || '')
  const stationName = escapeHtml(station.station_name || '暂无站点')
  const region = escapeHtml(station.region || '暂无区域')
  const latestInspection = escapeHtml(station.latest_inspection_date || '暂无')
  const stationType = escapeHtml(station.station_type || '暂无')
  const assetType = escapeHtml(station.asset_type || '站点')
  const address = escapeHtml(station.address || '暂无')
  const managerName = escapeHtml(station.station_manager_name || '暂无')
  const managerPhone = escapeHtml(station.station_manager_phone || '暂无')
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
            <div style="font-size:18px;font-weight:800;line-height:1.35;margin-bottom:4px;color:#f8fafc;">${stationName}</div>
            <div style="font-size:12px;color:#94a3b8;line-height:1.6;">${region} · ${stationType} · ${assetType}</div>
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
            <button type="button" data-map-issue-status="pending_rectification" data-station-id="${stationId}" style="padding:0;border:0;background:transparent;font:inherit;cursor:pointer;font-size:18px;font-weight:800;color:#fecaca;text-shadow:0 0 16px rgba(239,68,68,0.55);">${pendingRectification}</button>
          </div>
          <div style="padding:10px 10px;border-radius:16px;background:rgba(15,23,42,0.34);border:1px solid rgba(148,163,184,0.16);text-align:center;box-shadow:inset 0 1px 0 rgba(255,255,255,0.04);">
            <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">待复核</div>
            <button type="button" data-map-issue-status="pending_review" data-station-id="${stationId}" style="padding:0;border:0;background:transparent;font:inherit;cursor:pointer;font-size:18px;font-weight:800;color:#fed7aa;text-shadow:0 0 16px rgba(245,158,11,0.55);">${pendingReview}</button>
          </div>
          <div style="padding:10px 10px;border-radius:16px;background:rgba(15,23,42,0.34);border:1px solid rgba(148,163,184,0.16);text-align:center;box-shadow:inset 0 1px 0 rgba(255,255,255,0.04);">
            <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">已闭环</div>
            <button type="button" data-map-issue-status="closed" data-station-id="${stationId}" style="padding:0;border:0;background:transparent;font:inherit;cursor:pointer;font-size:18px;font-weight:800;color:#bbf7d0;text-shadow:0 0 16px rgba(34,197,94,0.5);">${closedCount}</button>
          </div>
        </div>

        <div style="display:flex;flex-direction:column;gap:8px;font-size:13px;line-height:1.75;color:#cbd5e1;position:relative;z-index:1;">
          <div><span style="color:#94a3b8;">站点类型：</span>${stationType}</div>
          <div><span style="color:#94a3b8;">资产类型：</span>${assetType}</div>
          <div><span style="color:#94a3b8;">站点负责人：</span>${managerName}</div>
          <div><span style="color:#94a3b8;">联系电话：</span>${managerPhone}</div>
          <div><span style="color:#94a3b8;">站点地址：</span>${address}</div>
          <div><span style="color:#94a3b8;">最近巡检日期：</span>${latestInspection}</div>
        </div>
      </div>
    </div>
  `
}

const fetchStationIssues = async (targetPage = 1) => {
  const stationId = issueDialog.value.station?.station_id || issueDialog.value.station?.id
  const statusKey = issueDialog.value.statusKey
  if (!stationId || !statusKey) return

  const sequence = ++issueDialogRequestSequence
  issueDialog.value.loading = true
  issueDialog.value.error = ''
  try {
    const response = await axios.get(`/api/station-map/${stationId}/issues`, {
      params: {
        user_id: localStorage.getItem('user_id') || '',
        status: statusKey,
        page: targetPage,
        page_size: issueDialog.value.pageSize
      }
    })
    if (sequence !== issueDialogRequestSequence) return
    const payload = response.data || {}
    issueDialog.value.items = Array.isArray(payload.items) ? payload.items : []
    issueDialog.value.total = Number(payload.total || 0)
    issueDialog.value.page = Number(payload.page || targetPage)
    issueDialog.value.totalPages = Number(payload.total_pages || 1)
  } catch (error) {
    if (sequence !== issueDialogRequestSequence) return
    issueDialog.value.items = []
    issueDialog.value.error = error?.response?.data?.error || '关联问题读取失败，请稍后重试。'
  } finally {
    if (sequence === issueDialogRequestSequence) issueDialog.value.loading = false
  }
}

const openStationIssueDialog = async (station, statusKey) => {
  if (!station || !STATION_ISSUE_STATUS_META[statusKey]) return
  pauseAutoRotate()
  issueDialog.value = {
    visible: true,
    loading: true,
    error: '',
    station,
    statusKey,
    items: [],
    total: Number(station[statusKey === 'pending_rectification'
      ? 'pending_rectification_count'
      : statusKey === 'pending_review' ? 'pending_review_count' : 'closed_count'] || 0),
    page: 1,
    pageSize: 12,
    totalPages: 1
  }
  await fetchStationIssues(1)
}

const closeStationIssueDialog = () => {
  issueDialogRequestSequence += 1
  issueDialog.value.visible = false
  issueDialog.value.loading = false
}

const openImagePreview = (path, title) => {
  const src = resolveImage(path)
  if (!src) return
  imagePreview.value = { visible: true, src, title }
}

const closeImagePreview = () => {
  imagePreview.value = { visible: false, src: '', title: '' }
}

const handleMapContainerClick = (event) => {
  const trigger = event.target?.closest?.('[data-map-issue-status][data-station-id]')
  if (!trigger || !mapContainer.value?.contains(trigger)) return
  event.preventDefault()
  event.stopPropagation()
  const stationId = String(trigger.dataset.stationId || '')
  const statusKey = String(trigger.dataset.mapIssueStatus || '')
  const station = filteredStations.value.find((item) => (
    String(item.station_id || item.id || '') === stationId
  ))
  if (station) openStationIssueDialog(station, statusKey)
}

const handleEventClick = (event) => {
  const matchedStation = filteredStations.value.find((station) => {
    return String(station.station_id || station.id || '').trim() === String(event.stationId || '').trim()
  })

  if (!matchedStation) return

  autoRotateTarget.value = matchedStation

  if (!mapInstance) return

  pauseAutoRotate()
  focusStationOnMap(matchedStation, { zoom: 12.5 })
}

const getMarkerColor = (station) => {
  if (Number(station.pending_rectification_count || 0) > 0) return '#ef4444'
  if (Number(station.pending_review_count || 0) > 0) return '#f59e0b'
  return '#22c55e'
}

const clearMarkers = () => {
  markerRenderToken += 1
  if (labelsLayer) {
    labelsLayer.clear?.()
    mapInstance?.remove?.(labelsLayer)
    labelsLayer = null
  } else if (mapInstance && markers.length) {
    markers.forEach((marker) => mapInstance.remove(marker))
  }
  markers = []
}

const renderDomMarkers = async (options = {}) => {
  if (!mapInstance || !window.AMap) return

  const renderToken = ++markerRenderToken
  const AMap = window.AMap
  if (markers.length) {
    markers.forEach((marker) => mapInstance.remove(marker))
    markers = []
  }

  if (infoWindowInstance) {
    infoWindowInstance.close()
  }

  infoWindowInstance = new AMap.InfoWindow({
    offset: new AMap.Pixel(0, -24),
    isCustom: true,
    closeWhenClickMap: true,
    autoMove: false
  })

  const positions = []

  for (const [index, station] of filteredStations.value.entries()) {
    if (renderToken !== markerRenderToken) return
    if (index > 0 && index % 35 === 0) {
      await yieldToBrowserFrame()
      if (renderToken !== markerRenderToken || !mapInstance) return
    }

    const lng = Number(station.longitude)
    const lat = Number(station.latitude)

    if (Number.isNaN(lng) || Number.isNaN(lat)) continue

    positions.push([lng, lat])

    const color = getMarkerColor(station)
    const pendingRectification = Number(station.pending_rectification_count || 0)
    const pendingReview = Number(station.pending_review_count || 0)
    const pulseDuration = pendingRectification > 0 ? '1.35s' : pendingReview > 0 ? '1.8s' : '2.6s'
    const pulseOpacity = pendingRectification > 0 ? '0.34' : pendingReview > 0 ? '0.26' : '0.16'
    const pulseScale = pendingRectification > 0 ? '2.4' : pendingReview > 0 ? '2.0' : '1.7'
    const pulseAnimation = pendingRectification > 0 || pendingReview > 0
      ? `animation: mapPulse ${pulseDuration} ease-out infinite;`
      : ''

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
            ${pulseAnimation}
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
      pauseAutoRotate()
      autoRotateTarget.value = station
      infoWindowInstance.setContent(buildInfoHtml(station))
      infoWindowInstance.open(mapInstance, [lng, lat])
    })

    mapInstance.add(marker)
    markers.push(marker)
  }

  if (renderToken !== markerRenderToken) return

  if (options.fitView && positions.length === 1) {
    mapInstance.setZoomAndCenter(13, positions[0])
    return
  }

  if (options.fitView && positions.length > 1) {
    mapInstance.setFitView(markers, false, [80, 80, 80, 80])
  }
}

const markerIconCache = new Map()

const getLabelMarkerIcon = (color) => {
  if (markerIconCache.has(color)) return markerIconCache.get(color)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="36" viewBox="0 0 30 36"><path d="M15 1C7.82 1 2 6.82 2 14c0 9.25 13 21 13 21s13-11.75 13-21C28 6.82 22.18 1 15 1z" fill="${color}" stroke="white" stroke-width="2"/><circle cx="15" cy="14" r="5" fill="white" fill-opacity=".92"/></svg>`
  const icon = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
  markerIconCache.set(color, icon)
  return icon
}

const renderLabelMarkers = async (options = {}) => {
  if (!mapInstance || !window.AMap) return
  const AMap = window.AMap
  clearMarkers()
  const renderToken = ++markerRenderToken

  labelsLayer = new AMap.LabelsLayer({
    zooms: [7, 20],
    zIndex: 120,
    collision: true,
    allowCollision: false
  })
  if (!infoWindowInstance) {
    infoWindowInstance = new AMap.InfoWindow({
      offset: new AMap.Pixel(0, -24),
      isCustom: true,
      closeWhenClickMap: true,
      autoMove: false
    })
  }

  const nextMarkers = []
  for (const [index, station] of filteredStations.value.entries()) {
    if (index > 0 && index % 80 === 0) {
      await yieldToBrowserFrame()
      if (renderToken !== markerRenderToken || !mapInstance) return
    }
    const lng = Number(station.longitude)
    const lat = Number(station.latitude)
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) continue
    const color = getMarkerColor(station)
    const riskScore = Number(station.pending_rectification_count || 0) * 100
      + Number(station.pending_review_count || 0) * 10
    const marker = new AMap.LabelMarker({
      name: String(station.station_id || station.id || ''),
      position: [lng, lat],
      zooms: [7, 20],
      opacity: 1,
      zIndex: Math.min(999, 20 + riskScore),
      icon: {
        type: 'image',
        image: getLabelMarkerIcon(color),
        size: [30, 36],
        anchor: 'bottom-center'
      },
      text: {
        content: String(station.station_name || ''),
        direction: 'top',
        offset: [0, -4],
        style: {
          fontSize: 12,
          fontWeight: '600',
          fillColor: '#0f172a',
          strokeColor: '#ffffff',
          strokeWidth: 3,
          padding: [2, 4]
        }
      }
    })
    marker.on('click', () => {
      pauseAutoRotate()
      const stationId = String(station.station_id || station.id || '')
      const latestStation = filteredStations.value.find((item) => (
        String(item.station_id || item.id || '') === stationId
      )) || station
      autoRotateTarget.value = latestStation
      infoWindowInstance?.setContent(buildInfoHtml(latestStation))
      infoWindowInstance?.open(mapInstance, [lng, lat])
    })
    nextMarkers.push(marker)
  }

  if (!mapInstance || !labelsLayer || renderToken !== markerRenderToken) return
  markers = nextMarkers
  labelsLayer.add(markers)
  mapInstance.add(labelsLayer)
  if (options.fitView && markers.length) {
    mapInstance.setFitView(null, false, [80, 80, 80, 80])
  }
}

const renderMarkers = async (options = {}) => {
  if (window.AMap?.LabelsLayer && window.AMap?.LabelMarker) {
    await renderLabelMarkers(options)
    return
  }
  await renderDomMarkers(options)
}

const initMap = async () => {
  if (mapInstance || mapBooting.value) return

  mapBooting.value = true
  mapError.value = ''

  try {
    await Promise.all([
      fetchStations({ preferCache: true }),
      fetchEventFeed()
    ])

    await waitForBrowserIdle()
    if (isMobileMapMode.value || !mapContainer.value) return

    const AMap = await loadAmapScript()
    await waitForBrowserIdle(450)

    mapInstance = new AMap.Map(mapContainer.value, {
      zoom: 10.8,
      center: SHANGHAI_CENTER,
      resizeEnable: true,
      animateEnable: true
    })

    mapInstance.on('dragstart', () => {
      mapInteracting = true
    })
    mapInstance.on('dragend', () => {
      mapInteracting = false
      if (!autoRotateEnabled.value) pausedViewSnapshot = captureMapView()
      if (markerRenderPending) requestMarkerRender()
    })
    mapInstance.on('zoomstart', () => {
      mapInteracting = true
    })
    mapInstance.on('zoomend', () => {
      mapInteracting = false
      if (!autoRotateEnabled.value) pausedViewSnapshot = captureMapView()
      if (markerRenderPending) requestMarkerRender()
    })

    await renderMarkers({ fitView: autoRotateEnabled.value })
    if (autoRotateEnabled.value) {
      startAutoRotate()
    } else {
      setMapAnimationEnabled(false)
      pausedViewSnapshot = captureMapView()
    }
    startEventFeedRefresh()
    startStationRefresh()
  } catch (error) {
    console.error(error)
    mapError.value = '地图资源加载较慢，请稍后刷新或检查网络。'
  } finally {
    mapBooting.value = false
  }
}

const initMobileEventView = async () => {
  await Promise.all([
    fetchStations({ preferCache: true }),
    fetchEventFeed()
  ])
  startEventFeedRefresh()
  startStationRefresh()
}

const refreshStationMapData = () => {
  if (document.visibilityState === 'hidden') return
  fetchStations()
  fetchEventFeed()
}

const recenterMap = () => {
  if (!mapInstance) return
  autoRotateTarget.value = null
  mapInstance.setZoomAndCenter(10.8, SHANGHAI_CENTER)
  if (!autoRotateEnabled.value) {
    pausedViewSnapshot = { center: [...SHANGHAI_CENTER], zoom: 10.8 }
  }
  if (infoWindowInstance) infoWindowInstance.close()
}

const toggleFullscreen = async () => {
  const target = mapFrameRef.value
  if (!target) return

  try {
    if (!autoRotateEnabled.value) pausedViewSnapshot = captureMapView()
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
      if (!autoRotateEnabled.value) restoreMapView(pausedViewSnapshot)
    }
  }, 120)
}

const handleDialogKeydown = (event) => {
  if (event.key !== 'Escape') return
  if (imagePreview.value.visible) {
    closeImagePreview()
  } else if (issueDialog.value.visible) {
    closeStationIssueDialog()
  }
}

onMounted(() => {
  currentRole.value = resolveCurrentRole()
  syncMobileMapMode()

  if (!hasPermission.value) {
    return
  }

  if (isMobileMapMode.value) {
    initMobileEventView().catch((error) => {
      console.error(error)
    })
  } else {
    initMap().catch((error) => {
      console.error(error)
    })
  }

  window.addEventListener('resize', handleViewportResize)
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  window.addEventListener('focus', refreshStationMapData)
  document.addEventListener('visibilitychange', refreshStationMapData)
  mapContainer.value?.addEventListener('click', handleMapContainerClick)
  document.addEventListener('keydown', handleDialogKeydown)
})

onBeforeUnmount(() => {
  if (!hasPermission.value) {
    return
  }

  window.removeEventListener('resize', handleViewportResize)
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  window.removeEventListener('focus', refreshStationMapData)
  document.removeEventListener('visibilitychange', refreshStationMapData)
  mapContainer.value?.removeEventListener('click', handleMapContainerClick)
  document.removeEventListener('keydown', handleDialogKeydown)
  stopAutoRotate()
  stopEventFeedRefresh()
  stopStationRefresh()
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
  color: #ef4444;
  text-shadow: 0 8px 22px rgba(239, 68, 68, 0.2);
}

.summary-value.warning {
  color: #f59e0b;
  text-shadow: 0 8px 22px rgba(245, 158, 11, 0.2);
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

.mobile-map-brief {
  display: none;
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
  width: 11px;
  height: 11px;
  border-radius: 999px;
  display: inline-block;
  flex-shrink: 0;
}

.overlay-dot.danger {
  background: #ef4444;
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.18), 0 0 18px rgba(239, 68, 68, 0.62);
}

.overlay-dot.warning {
  background: #f59e0b;
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.18), 0 0 18px rgba(245, 158, 11, 0.58);
}

.overlay-dot.success {
  background: #22c55e;
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.18), 0 0 18px rgba(34, 197, 94, 0.54);
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
  color: #fee2e2;
  background: rgba(127, 29, 29, 0.58);
  border-color: rgba(248, 113, 113, 0.45);
  box-shadow: 0 0 20px rgba(239, 68, 68, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.overlay-chip.warning {
  color: #ffedd5;
  background: rgba(120, 53, 15, 0.58);
  border-color: rgba(251, 191, 36, 0.48);
  box-shadow: 0 0 20px rgba(245, 158, 11, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.map-container {
  width: 100%;
  height: calc(100vh - 380px);
  min-height: 620px;
  border-radius: 20px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.18);
}

.map-loading-layer {
  position: absolute;
  inset: 0;
  z-index: 6;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  pointer-events: none;
  background:
    radial-gradient(circle at 50% 42%, rgba(59, 130, 246, 0.18), transparent 30%),
    linear-gradient(180deg, rgba(2, 6, 23, 0.26), rgba(15, 23, 42, 0.1));
}

.map-loading-card {
  width: min(320px, 100%);
  padding: 20px 22px;
  border-radius: 22px;
  text-align: center;
  color: #e2e8f0;
}

.map-loading-card strong,
.map-loading-card span {
  display: block;
}

.map-loading-card strong {
  margin-top: 12px;
  color: #f8fafc;
  font-size: 16px;
  font-weight: 900;
}

.map-loading-card span {
  margin-top: 7px;
  color: #cbd5e1;
  font-size: 13px;
  line-height: 1.7;
}

.map-loading-spinner {
  width: 34px;
  height: 34px;
  margin: 0 auto;
  border-radius: 999px;
  border: 3px solid rgba(191, 219, 254, 0.32);
  border-top-color: #bfdbfe;
  animation: mapLoadingSpin 0.9s linear infinite;
}

.map-frame.fullscreen .map-container {
  height: calc(100vh - 32px);
  min-height: auto;
}

@keyframes mapLoadingSpin {
  to {
    transform: rotate(360deg);
  }
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

.mobile-map-brief-head,
.mobile-map-stat-row,
.mobile-event-card {
  position: relative;
  z-index: 1;
}

.mobile-map-brief-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.mobile-map-kicker {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.09);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 9px;
}

.mobile-map-brief h3 {
  margin: 0;
  font-size: 22px;
  line-height: 1.25;
  color: #0f172a;
}

.mobile-event-count {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 7px 11px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
  border: 1px solid rgba(37, 99, 235, 0.12);
}

.mobile-map-copy {
  position: relative;
  z-index: 1;
  margin: 0 0 16px;
  color: #475569;
  font-size: 14px;
  line-height: 1.8;
}

.mobile-map-stat-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.mobile-map-stat {
  padding: 12px 10px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.9);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85);
}

.mobile-map-stat span {
  display: block;
  margin-bottom: 5px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.mobile-map-stat strong {
  display: block;
  color: #0f172a;
  font-size: 22px;
  line-height: 1;
}

.mobile-map-stat.danger strong {
  color: #ef4444;
}

.mobile-map-stat.warning strong {
  color: #f59e0b;
}

.mobile-map-stat.danger {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(254, 226, 226, 0.88));
  border-color: rgba(248, 113, 113, 0.34);
}

.mobile-map-stat.warning {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(255, 237, 213, 0.9));
  border-color: rgba(251, 191, 36, 0.38);
}

.mobile-selected-station {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 14px;
  padding: 13px 14px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.88);
  border: 1px solid rgba(96, 165, 250, 0.2);
  box-shadow: 0 14px 26px rgba(15, 23, 42, 0.12);
}

.mobile-selected-station span {
  color: #93c5fd;
  font-size: 12px;
  font-weight: 900;
}

.mobile-selected-station strong {
  color: #f8fafc;
  font-size: 16px;
  line-height: 1.35;
}

.mobile-selected-station em {
  color: #cbd5e1;
  font-size: 12px;
  font-style: normal;
  line-height: 1.6;
}

.mobile-event-timeline {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mobile-event-card {
  width: 100%;
  display: grid;
  grid-template-columns: 12px minmax(0, 1fr);
  gap: 10px;
  padding: 13px;
  text-align: left;
  border: 1px solid rgba(37, 99, 235, 0.1);
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.94), rgba(248, 250, 252, 0.86)),
    #fff;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.06);
  cursor: pointer;
}

.mobile-event-card.danger {
  border-color: rgba(239, 68, 68, 0.28);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(254, 242, 242, 0.86)),
    #fff;
}

.mobile-event-card.warning {
  border-color: rgba(245, 158, 11, 0.3);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(255, 247, 237, 0.9)),
    #fff;
}

.mobile-event-dot {
  width: 9px;
  height: 9px;
  margin-top: 6px;
  border-radius: 999px;
  background: #2563eb;
  box-shadow: 0 0 0 5px rgba(37, 99, 235, 0.08);
}

.mobile-event-card.danger .mobile-event-dot {
  background: #ef4444;
  box-shadow: 0 0 0 5px rgba(239, 68, 68, 0.14), 0 0 16px rgba(239, 68, 68, 0.42);
}

.mobile-event-card.warning .mobile-event-dot {
  background: #f59e0b;
  box-shadow: 0 0 0 5px rgba(245, 158, 11, 0.15), 0 0 16px rgba(245, 158, 11, 0.42);
}

.mobile-event-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.mobile-event-body strong {
  color: #0f172a;
  font-size: 14px;
  line-height: 1.35;
}

.mobile-event-body span {
  color: #475569;
  font-size: 13px;
  line-height: 1.65;
}

.mobile-event-body em {
  color: #94a3b8;
  font-size: 12px;
  font-style: normal;
}

.mobile-event-empty {
  padding: 22px 16px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.86);
  border: 1px dashed #cbd5e1;
  color: #64748b;
  font-size: 14px;
  line-height: 1.7;
  text-align: center;
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
  color: #fee2e2;
  background: rgba(127, 29, 29, 0.54);
  border-color: rgba(248, 113, 113, 0.38);
}

.focus-chip.warning {
  color: #ffedd5;
  background: rgba(120, 53, 15, 0.54);
  border-color: rgba(251, 191, 36, 0.42);
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

.station-issue-dialog-backdrop,
.station-image-preview-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2600;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(8px);
}

.station-issue-dialog {
  width: min(1080px, 96vw);
  max-height: min(86vh, 900px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f8fafc;
}

.station-issue-dialog-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 24px 18px;
  border-bottom: 1px solid #dbe4ee;
  background: linear-gradient(135deg, #ffffff, #eff6ff);
}

.station-issue-dialog-kicker {
  color: #2563eb;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.16em;
}

.station-issue-dialog-head h3 {
  margin: 6px 0 4px;
  color: #0f172a;
  font-size: 24px;
}

.station-issue-dialog-head p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.station-issue-dialog-close,
.station-image-preview header button {
  width: 38px;
  height: 38px;
  border: 1px solid #d7e0ea;
  border-radius: 12px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  font-size: 24px;
  line-height: 1;
}

.station-issue-list {
  min-height: 0;
  overflow: auto;
  display: grid;
  gap: 12px;
  padding: 18px 20px;
}

.station-issue-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 170px;
  gap: 18px;
  padding: 18px;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.station-issue-card-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.station-issue-id {
  color: #1d4ed8;
  font-weight: 900;
}

.station-issue-time {
  color: #64748b;
  font-size: 12px;
}

.station-issue-status {
  padding: 4px 8px;
  border-radius: 999px;
  color: #991b1b;
  background: #fee2e2;
  font-size: 11px;
  font-weight: 800;
}

.station-issue-status.pending_review {
  color: #92400e;
  background: #fef3c7;
}

.station-issue-status.closed {
  color: #166534;
  background: #dcfce7;
}

.station-issue-description {
  margin: 12px 0 0;
  color: #1e293b;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.8;
}

.station-issue-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
  margin: 14px 0 0;
}

.station-issue-detail-grid > div {
  min-width: 0;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f8fafc;
}

.station-issue-detail-grid .wide {
  grid-column: 1 / -1;
}

.station-issue-detail-grid dt {
  margin-bottom: 4px;
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
}

.station-issue-detail-grid dd {
  margin: 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.65;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.station-issue-photo-column {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.station-issue-photo-button {
  overflow: hidden;
  padding: 0;
  border: 1px solid #dbe4ee;
  border-radius: 14px;
  background: #f8fafc;
  cursor: pointer;
}

.station-issue-photo-button img {
  display: block;
  width: 100%;
  height: 112px;
  object-fit: cover;
}

.station-issue-photo-button span,
.station-issue-photo-link {
  display: block;
  padding: 8px;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
}

.station-issue-photo-link {
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  background: #eff6ff;
  cursor: pointer;
}

.station-issue-photo-empty {
  display: grid;
  min-height: 112px;
  place-items: center;
  border: 1px dashed #cbd5e1;
  border-radius: 14px;
  color: #94a3b8;
  background: #f8fafc;
  font-size: 12px;
}

.station-issue-dialog-state {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 9px;
  padding: 30px;
  color: #475569;
  text-align: center;
}

.station-issue-dialog-state p {
  margin: 0;
  color: #64748b;
}

.station-issue-dialog-state.error strong {
  color: #b91c1c;
}

.station-issue-loading-orb {
  width: 32px;
  height: 32px;
  border: 3px solid #bfdbfe;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: stationIssueSpin 0.8s linear infinite;
}

@keyframes stationIssueSpin {
  to { transform: rotate(360deg); }
}

.station-issue-dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  border-top: 1px solid #dbe4ee;
  background: #fff;
  color: #64748b;
  font-size: 13px;
}

.station-issue-dialog-footer > div {
  display: flex;
  gap: 8px;
}

.station-image-preview-backdrop {
  z-index: 2800;
}

.station-image-preview {
  width: min(1100px, 96vw);
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 18px;
  background: #0f172a;
  box-shadow: 0 30px 70px rgba(2, 6, 23, 0.5);
}

.station-image-preview header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  color: #f8fafc;
}

.station-image-preview img {
  display: block;
  width: 100%;
  max-height: calc(92vh - 64px);
  object-fit: contain;
  background: #020617;
}

@media (max-width: 1200px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .station-issue-dialog-backdrop,
  .station-image-preview-backdrop {
    padding: 10px;
  }

  .station-issue-dialog {
    width: 100%;
    max-height: 94vh;
    border-radius: 18px;
  }

  .station-issue-dialog-head {
    padding: 17px;
  }

  .station-issue-dialog-head h3 {
    font-size: 19px;
  }

  .station-issue-list {
    padding: 12px;
  }

  .station-issue-card {
    grid-template-columns: 1fr;
    padding: 14px;
  }

  .station-issue-photo-column {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .station-issue-detail-grid {
    grid-template-columns: 1fr;
  }

  .station-issue-detail-grid .wide {
    grid-column: auto;
  }

  .page-header h2 {
    font-size: 30px;
  }

  .map-card {
    padding: 14px;
    overflow: hidden;
  }

  .map-toolbar {
    align-items: flex-start;
    margin-bottom: 12px;
  }

  .map-toolbar-right {
    display: none;
  }

  .mobile-map-brief {
    position: relative;
    display: block;
    overflow: hidden;
    padding: 18px;
    border-radius: 22px;
    background:
      radial-gradient(circle at top right, rgba(59, 130, 246, 0.16), transparent 36%),
      linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.92));
    border: 1px solid rgba(203, 213, 225, 0.9);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
  }

  .mobile-map-brief::before {
    content: '';
    position: absolute;
    right: -42px;
    top: -52px;
    width: 150px;
    height: 150px;
    border-radius: 999px;
    background: rgba(37, 99, 235, 0.1);
    filter: blur(2px);
  }

  .map-overlay-left,
  .map-overlay-right,
  .map-overlay-bottom-right,
  .map-overlay-bottom-left {
    position: static;
  }

  .map-frame {
    display: none;
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
