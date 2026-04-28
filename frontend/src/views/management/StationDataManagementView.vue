<template>
  <div class="page-shell station-management-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">管理系统</div>
        <h2>站点数据管理</h2>
        <p class="page-desc">维护站点主数据，包括片区、地址、坐标、负责人、资产类型、上线状态和 HOS 编码等信息。</p>
      </div>
      <div v-if="hasPermission" class="header-actions">
        <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchStations">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
        <button class="btn btn-secondary" type="button" :disabled="exporting" @click="exportStations">
          {{ exporting ? '导出中...' : '导出备份' }}
        </button>
        <label class="btn btn-secondary file-action" :class="{ disabled: importing }">
          <input type="file" accept="application/json,.json" :disabled="importing" @change="importStations" />
          <span>{{ importing ? '导入中...' : '导入备份' }}</span>
        </label>
      </div>
    </div>

    <div v-if="!hasPermission" class="card-surface permission-card">
      <div class="permission-icon">!</div>
      <div class="permission-title">无权限访问</div>
      <div class="permission-desc">当前页面仅 supervisor 账号可访问和操作。</div>
    </div>

    <template v-else>
      <div v-if="message.text" :class="['message-card', message.type]">{{ message.text }}</div>

      <div class="management-stack">
        <section ref="formCardRef" class="card-surface form-card" :class="{ editing: editingId }">
          <div class="section-head compact">
            <div>
              <div class="section-kicker">{{ editingId ? '编辑站点' : '新增站点' }}</div>
              <h3>{{ editingId ? '维护站点主数据' : '录入新站点' }}</h3>
              <p v-if="editingId" class="editing-hint">正在编辑：{{ form.station_name }}</p>
            </div>
          </div>

          <div class="form-sections">
            <div class="form-section">
              <div class="form-section-title">
                <span class="section-index">01</span>
                <div>
                  <strong>基础档案</strong>
                  <p>先确认站点身份、片区和业务类型。</p>
                </div>
              </div>

              <div class="form-section-grid">
                <label class="form-field span-2">
                  <span>站点名称</span>
                  <input v-model.trim="form.station_name" type="text" placeholder="请输入站点名称" />
                </label>

                <label class="form-field">
                  <span>所属片区/归属地</span>
                  <input v-model.trim="form.region" type="text" placeholder="例如：宝静片区" />
                </label>

                <label class="form-field">
                  <span>HOS加油站编码</span>
                  <input v-model.trim="form.hos_station_code" type="text" placeholder="例如：PQ04" />
                  <small>站点唯一标识，用于防止重复添加。</small>
                </label>

                <label class="form-field">
                  <span>站点类型</span>
                  <select v-model="form.station_type">
                    <option value="加油站">加油站</option>
                    <option value="充电站">充电站</option>
                  </select>
                </label>
              </div>
            </div>

            <div class="form-section">
              <div class="form-section-title">
                <span class="section-index">02</span>
                <div>
                  <strong>地址与联系人</strong>
                  <p>补充地图坐标、负责人和站内联系电话。</p>
                </div>
              </div>

              <div class="form-section-grid">
                <label class="form-field span-2">
                  <span>站点地址</span>
                  <input v-model.trim="form.address" type="text" placeholder="请输入站点地址" />
                </label>

                <label class="form-field">
                  <span>经度</span>
                  <input v-model.trim="form.longitude" type="text" placeholder="例如：121.174976" />
                </label>

                <label class="form-field">
                  <span>纬度</span>
                  <input v-model.trim="form.latitude" type="text" placeholder="例如：30.886129" />
                </label>

                <label class="form-field">
                  <span>站点负责人姓名</span>
                  <input v-model.trim="form.station_manager_name" type="text" />
                </label>

                <label class="form-field">
                  <span>负责人手机号</span>
                  <input v-model.trim="form.station_manager_phone" type="text" />
                </label>

                <label class="form-field">
                  <span>固定电话</span>
                  <input v-model.trim="form.landline_phone" type="text" placeholder="例如：021-67220331" />
                </label>
              </div>
            </div>

            <div class="form-section">
              <div class="form-section-title">
                <span class="section-index">03</span>
                <div>
                  <strong>经营属性</strong>
                  <p>使用选项统一口径，减少后续数据清洗。</p>
                </div>
              </div>

              <div class="form-section-grid">
                <label class="form-field">
                  <span>资产类型</span>
                  <select v-model="form.asset_type">
                    <option value="全资">全资</option>
                    <option value="股权">股权</option>
                  </select>
                </label>

                <label class="form-field">
                  <span>是否并表</span>
                  <select v-model="form.is_consolidated">
                    <option value="否">否</option>
                    <option value="是">是</option>
                  </select>
                </label>

                <label class="form-field">
                  <span>是否上线3.0</span>
                  <select v-model="form.online_3_status">
                    <option value="未上线">未上线</option>
                    <option value="上线">上线</option>
                    <option value="上线参股模式">上线参股模式</option>
                  </select>
                </label>

                <label class="form-field">
                  <span>站点状态</span>
                  <select v-model="form.status">
                    <option value="营业中">营业中</option>
                    <option value="停业">停业</option>
                  </select>
                </label>

                <div class="form-field operating-field span-2">
                  <span>营运时间</span>
                  <div class="operating-control">
                    <select v-model="operatingMode">
                      <option value="24小时">24小时营业</option>
                      <option value="custom">固定时段营业</option>
                    </select>
                    <template v-if="operatingMode === 'custom'">
                      <select v-model="operatingStart">
                        <option v-for="time in timeOptions" :key="`start-${time}`" :value="time">{{ time }}</option>
                      </select>
                      <span class="time-separator">至</span>
                      <select v-model="operatingEnd">
                        <option v-for="time in timeOptions" :key="`end-${time}`" :value="time">{{ time }}</option>
                      </select>
                    </template>
                  </div>
                  <small>系统统一保存为：{{ form.operating_hours }}</small>
                </div>
              </div>
            </div>
          </div>

          <div v-if="formError" class="form-error">{{ formError }}</div>

          <div class="form-actions">
            <button class="btn btn-secondary" type="button" @click="resetForm">清空</button>
            <button class="btn btn-primary" type="button" :disabled="saving" @click="saveStation">
              {{ saving ? '保存中...' : editingId ? '保存修改' : '保存站点' }}
            </button>
          </div>
        </section>

        <section class="card-surface table-card">
          <div class="section-head">
            <div>
              <div class="section-kicker">站点清单</div>
              <h3>共 {{ filteredStations.length }} 个站点</h3>
            </div>
          </div>

          <div class="filter-bar">
            <label class="filter-field keyword-field">
              <span>关键词</span>
              <input v-model.trim="filters.keyword" type="text" placeholder="站点名称、地址、负责人、HOS编码" />
            </label>

            <label class="filter-field">
              <span>所属片区</span>
              <select v-model="filters.region">
                <option value="">全部片区</option>
                <option v-for="region in regionOptions" :key="region" :value="region">{{ region }}</option>
              </select>
            </label>

            <label class="filter-field">
              <span>站点类型</span>
              <select v-model="filters.station_type">
                <option value="">全部类型</option>
                <option value="加油站">加油站</option>
                <option value="充电站">充电站</option>
              </select>
            </label>

            <label class="filter-field">
              <span>站点状态</span>
              <select v-model="filters.status">
                <option value="">全部状态</option>
                <option value="营业中">营业中</option>
                <option value="停业">停业</option>
              </select>
            </label>

            <button class="btn btn-secondary" type="button" @click="resetFilters">重置筛选</button>
          </div>

          <div class="table-wrap">
            <table class="station-table">
              <thead>
                <tr>
                  <th>站点名称</th>
                  <th>所属片区/归属地</th>
                  <th>站点类型</th>
                  <th>资产类型</th>
                  <th>是否并表</th>
                  <th>是否上线3.0</th>
                  <th>HOS编码</th>
                  <th>固定电话</th>
                  <th>站点状态</th>
                  <th>营运时间</th>
                  <th>负责人</th>
                  <th>创建时间</th>
                  <th>更新时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="loading">
                  <td colspan="14" class="empty-cell">正在加载站点数据...</td>
                </tr>
                <tr v-else-if="!filteredStations.length">
                  <td colspan="14" class="empty-cell">暂无匹配的站点数据。</td>
                </tr>
                <tr v-for="station in pagedStations" :key="station.id" :class="{ active: editingId === station.id }">
                  <td>
                    <div class="table-title">{{ station.station_name }}</div>
                    <div class="table-sub">{{ station.address || '-' }}</div>
                  </td>
                  <td>{{ station.region || '-' }}</td>
                  <td>{{ station.station_type || '-' }}</td>
                  <td>{{ normalizeAssetType(station.asset_type) }}</td>
                  <td>{{ station.is_consolidated || '否' }}</td>
                  <td>{{ station.online_3_status || '未上线' }}</td>
                  <td>{{ station.hos_station_code || '-' }}</td>
                  <td>{{ station.landline_phone || '-' }}</td>
                  <td>{{ station.status || '-' }}</td>
                  <td>{{ station.operating_hours || '-' }}</td>
                  <td>
                    <div>{{ station.station_manager_name || '-' }}</div>
                    <div class="table-sub">{{ station.station_manager_phone || '-' }}</div>
                  </td>
                  <td>{{ station.created_at || '-' }}</td>
                  <td>{{ station.updated_at || '-' }}</td>
                  <td>
                    <div class="row-actions">
                      <button class="btn btn-secondary btn-sm" type="button" @click="startEdit(station)">编辑</button>
                      <button class="btn btn-danger btn-sm" type="button" :disabled="deletingId === station.id"
                        @click="deleteStation(station)">
                        {{ deletingId === station.id ? '删除中' : '删除' }}
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="filteredStations.length" class="pagination-bar">
            <div class="pagination-summary">显示第 {{ pageStart }}-{{ pageEnd }} 条，共 {{ filteredStations.length }} 条</div>
            <div class="pagination-actions">
              <label class="page-size-field">
                <span>每页</span>
                <select v-model.number="pageSize">
                  <option :value="10">10</option>
                  <option :value="20">20</option>
                  <option :value="50">50</option>
                </select>
              </label>
              <button class="btn btn-secondary btn-sm" type="button" :disabled="currentPage === 1"
                @click="currentPage -= 1">
                上一页
              </button>
              <span class="page-indicator">{{ currentPage }} / {{ totalPages }}</span>
              <button class="btn btn-secondary btn-sm" type="button" :disabled="currentPage === totalPages"
                @click="currentPage += 1">
                下一页
              </button>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'

const currentUserId = localStorage.getItem('user_id') || ''
const currentUsername = localStorage.getItem('username') || ''
const hasPermission = currentUsername === 'supervisor'

const stations = ref([])
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const importing = ref(false)
const deletingId = ref(null)
const editingId = ref(null)
const formError = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const formCardRef = ref(null)
const operatingMode = ref('24小时')
const operatingStart = ref('06:00')
const operatingEnd = ref('22:00')
const message = reactive({
  text: '',
  type: 'info'
})
const filters = reactive({
  keyword: '',
  region: '',
  station_type: '',
  status: ''
})

const createEmptyForm = () => ({
  station_name: '',
  region: '',
  address: '',
  longitude: '',
  latitude: '',
  station_manager_name: '',
  station_manager_phone: '',
  station_type: '加油站',
  asset_type: '全资',
  is_consolidated: '否',
  online_3_status: '未上线',
  hos_station_code: '',
  landline_phone: '',
  status: '营业中',
  operating_hours: '24小时'
})

const form = reactive(createEmptyForm())
const timeOptions = Array.from({ length: 48 }, (_, index) => {
  const hour = String(Math.floor(index / 2)).padStart(2, '0')
  const minute = index % 2 === 0 ? '00' : '30'
  return `${hour}:${minute}`
})

const normalizeAssetType = (assetType) => {
  if (['股权', '控股', '参股'].some((keyword) => String(assetType || '').includes(keyword))) return '股权'
  return assetType || '-'
}

const regionOptions = computed(() => {
  return Array.from(new Set(stations.value.map((station) => station.region).filter(Boolean))).sort((a, b) =>
    String(a).localeCompare(String(b), 'zh-Hans-CN')
  )
})

const filteredStations = computed(() => {
  const keyword = filters.keyword.toLowerCase()
  return stations.value.filter((station) => {
    const text = [
      station.station_name,
      station.region,
      station.address,
      station.station_manager_name,
      station.station_manager_phone,
      station.hos_station_code,
      station.landline_phone
    ].join(' ').toLowerCase()
    const matchesKeyword = !keyword || text.includes(keyword)
    const matchesRegion = !filters.region || station.region === filters.region
    const matchesType = !filters.station_type || station.station_type === filters.station_type
    const matchesStatus = !filters.status || station.status === filters.status
    return matchesKeyword && matchesRegion && matchesType && matchesStatus
  })
})

const getOperatingHoursValue = () => {
  if (operatingMode.value === '24小时') return '24小时'
  return `${operatingStart.value}-${operatingEnd.value}`
}

const parseOperatingHours = (value) => {
  const text = String(value || '').replace(/\s+/g, '').replace(/[－—–]/g, '-')
  if (!text || ['24小时', '全天', '全天营业'].includes(text)) {
    return {
      mode: '24小时',
      start: '06:00',
      end: '22:00'
    }
  }

  const matched = text.match(/^(\d{1,2}):([0-5]\d)-(\d{1,2}):([0-5]\d)$/)
  if (!matched) {
    return {
      mode: '24小时',
      start: '06:00',
      end: '22:00'
    }
  }

  const startHour = Number(matched[1])
  const endHour = Number(matched[3])
  const start = `${String(startHour).padStart(2, '0')}:${matched[2]}`
  const end = `${String(endHour).padStart(2, '0')}:${matched[4]}`
  if (startHour > 23 || endHour > 23 || !timeOptions.includes(start) || !timeOptions.includes(end)) {
    return {
      mode: '24小时',
      start: '06:00',
      end: '22:00'
    }
  }

  return {
    mode: 'custom',
    start,
    end
  }
}

const applyOperatingHoursToControls = (value) => {
  const parsed = parseOperatingHours(value)
  operatingMode.value = parsed.mode
  operatingStart.value = parsed.start
  operatingEnd.value = parsed.end
  form.operating_hours = getOperatingHoursValue()
}

const totalPages = computed(() => Math.max(1, Math.ceil(filteredStations.value.length / pageSize.value)))
const pagedStations = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredStations.value.slice(start, start + pageSize.value)
})
const pageStart = computed(() => (filteredStations.value.length ? (currentPage.value - 1) * pageSize.value + 1 : 0))
const pageEnd = computed(() => Math.min(currentPage.value * pageSize.value, filteredStations.value.length))

const setMessage = (text, type = 'info') => {
  message.text = text
  message.type = type
}

const resetForm = () => {
  Object.assign(form, createEmptyForm())
  applyOperatingHoursToControls(form.operating_hours)
  editingId.value = null
  formError.value = ''
}

const resetFilters = () => {
  Object.assign(filters, {
    keyword: '',
    region: '',
    station_type: '',
    status: ''
  })
}

const normalizeStationForForm = (station) => ({
  station_name: station.station_name || '',
  region: station.region || '',
  address: station.address || '',
  longitude: station.longitude ?? '',
  latitude: station.latitude ?? '',
  station_manager_name: station.station_manager_name || '',
  station_manager_phone: station.station_manager_phone || '',
  station_type: station.station_type || '加油站',
  asset_type: normalizeAssetType(station.asset_type) === '股权' ? '股权' : '全资',
  is_consolidated: station.is_consolidated || '否',
  online_3_status: station.online_3_status || '未上线',
  hos_station_code: station.hos_station_code || '',
  landline_phone: station.landline_phone || '',
  status: station.status || '营业中',
  operating_hours: station.operating_hours || '24小时'
})

const startEdit = (station) => {
  editingId.value = station.id
  formError.value = ''
  const normalizedStation = normalizeStationForForm(station)
  Object.assign(form, normalizedStation)
  applyOperatingHoursToControls(normalizedStation.operating_hours)
  setMessage(`已进入【${station.station_name}】编辑状态，请在上方表单修改后保存。`, 'info')
  nextTick(() => {
    formCardRef.value?.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    })
  })
}

const fetchStations = async () => {
  if (!hasPermission) return

  try {
    loading.value = true
    const response = await axios.get('/api/management/stations', {
      params: {
        user_id: currentUserId,
        _ts: Date.now()
      }
    })
    stations.value = response.data?.stations || []
    if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
  } catch (error) {
    setMessage(error?.response?.data?.error || '站点数据加载失败。', 'error')
  } finally {
    loading.value = false
  }
}

const getDownloadFileName = (disposition) => {
  const value = String(disposition || '')
  const matched = value.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i)
  const filename = decodeURIComponent(matched?.[1] || matched?.[2] || '')
  return filename || `ywddzx_stations_backup_${new Date().toISOString().slice(0, 10)}.json`
}

const exportStations = async () => {
  try {
    exporting.value = true
    setMessage('')
    const response = await axios.get('/api/management/stations/export', {
      params: {
        user_id: currentUserId,
        _ts: Date.now()
      },
      responseType: 'blob'
    })
    const blobUrl = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = getDownloadFileName(response.headers['content-disposition'])
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(blobUrl)
    setMessage('站点数据备份文件已生成。', 'success')
  } catch (error) {
    setMessage('站点数据导出失败，请稍后重试。', 'error')
  } finally {
    exporting.value = false
  }
}

const importStations = async (event) => {
  const input = event.target
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  if (!file.name.toLowerCase().endsWith('.json')) {
    setMessage('只能导入 JSON 格式的站点备份文件。', 'error')
    return
  }

  const confirmed = window.confirm('导入后会按备份文件中的站点ID恢复或更新站点数据，确定继续吗？')
  if (!confirmed) return

  try {
    importing.value = true
    setMessage('')
    const formData = new FormData()
    formData.append('user_id', currentUserId)
    formData.append('file', file)
    const response = await axios.post('/api/management/stations/import', formData)
    setMessage(response.data?.message || '站点数据导入完成。', 'success')
    resetForm()
    await fetchStations()
  } catch (error) {
    setMessage(error?.response?.data?.error || '站点数据导入失败。', 'error')
  } finally {
    importing.value = false
  }
}

const validateForm = () => {
  form.hos_station_code = String(form.hos_station_code || '').trim().toUpperCase()
  form.operating_hours = getOperatingHoursValue()
  if (!form.station_name) return '请填写站点名称。'
  if (!form.hos_station_code) return '请填写 HOS加油站编码。'
  if (!form.station_type) return '请选择站点类型。'
  if (!form.asset_type) return '请选择资产类型。'
  if (!form.is_consolidated) return '请选择是否并表。'
  if (!form.online_3_status) return '请选择是否上线3.0。'
  if (!form.status) return '请选择站点状态。'
  if (operatingMode.value === 'custom' && operatingStart.value === operatingEnd.value) return '营运时间的开始时间和结束时间不能相同。'
  return ''
}

const saveStation = async () => {
  formError.value = validateForm()
  if (formError.value) return

  try {
    saving.value = true
    const payload = {
      ...form,
      user_id: currentUserId
    }
    const response = editingId.value
      ? await axios.put(`/api/management/stations/${editingId.value}`, payload)
      : await axios.post('/api/management/stations', payload)

    setMessage(response.data?.message || '站点已保存。', 'success')
    const savedId = response.data?.id || editingId.value
    await fetchStations()
    if (savedId) {
      const savedRow = stations.value.find((item) => String(item.id) === String(savedId))
      if (savedRow) startEdit(savedRow)
    } else {
      resetForm()
    }
  } catch (error) {
    formError.value = error?.response?.data?.error || '站点保存失败。'
  } finally {
    saving.value = false
  }
}

const deleteStation = async (station) => {
  const confirmed = window.confirm(`确定删除站点【${station.station_name}】吗？`)
  if (!confirmed) return

  try {
    deletingId.value = station.id
    const response = await axios.delete(`/api/management/stations/${station.id}`, {
      data: {
        user_id: currentUserId
      }
    })
    setMessage(response.data?.message || '站点已删除。', 'success')
    if (editingId.value === station.id) resetForm()
    await fetchStations()
  } catch (error) {
    setMessage(error?.response?.data?.error || '站点删除失败。', 'error')
  } finally {
    deletingId.value = null
  }
}

watch(
  () => [filters.keyword, filters.region, filters.station_type, filters.status, pageSize.value],
  () => {
    currentPage.value = 1
  }
)

watch([operatingMode, operatingStart, operatingEnd], () => {
  form.operating_hours = getOperatingHoursValue()
})

watch(totalPages, (value) => {
  if (currentPage.value > value) currentPage.value = value
})

onMounted(fetchStations)
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
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.page-kicker,
.section-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 12px;
}

.page-header h2,
.section-head h3 {
  margin: 0;
  color: #0f172a;
}

.page-header h2 {
  font-size: 34px;
}

.page-desc {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
}

.header-actions,
.row-actions,
.form-actions,
.pagination-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.management-stack {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.table-card,
.form-card {
  padding: 20px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.section-head.compact {
  margin-bottom: 18px;
}

.editing-hint {
  margin: 8px 0 0;
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
}

.form-card.editing {
  border-color: #bfdbfe;
  box-shadow: 0 18px 40px rgba(37, 99, 235, 0.12);
}

.filter-bar {
  display: grid;
  grid-template-columns: minmax(260px, 1.4fr) repeat(3, minmax(150px, 0.7fr)) auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 16px;
  padding: 14px;
  border-radius: 18px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.filter-field,
.page-size-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.filter-field span,
.page-size-field span {
  color: #475569;
  font-size: 12px;
  font-weight: 800;
}

.filter-field input,
.filter-field select,
.page-size-field select {
  width: 100%;
  height: 38px;
  border: 1px solid #d7e0ea;
  border-radius: 11px;
  padding: 0 11px;
  background: #fff;
  color: #0f172a;
  font-size: 13px;
}

.table-wrap {
  overflow-x: auto;
}

.station-table {
  min-width: 1680px;
  width: 100%;
  border-collapse: collapse;
}

.station-table th,
.station-table td {
  padding: 13px 12px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  white-space: nowrap;
  vertical-align: middle;
  color: #0f172a;
  font-size: 13px;
}

.station-table th {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.station-table tr.active td {
  background: #eff6ff;
}

.table-title {
  font-size: 14px;
  font-weight: 900;
}

.table-sub {
  margin-top: 5px;
  color: #64748b;
  font-size: 12px;
  white-space: normal;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 22px 12px;
}

.pagination-bar {
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  color: #64748b;
  font-size: 13px;
}

.pagination-summary,
.page-indicator {
  font-weight: 800;
}

.page-size-field {
  flex-direction: row;
  align-items: center;
}

.page-size-field select {
  width: 76px;
}

.form-sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-section {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%);
}

.form-section-title {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.section-index {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.form-section-title strong {
  display: block;
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
}

.form-section-title p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.form-section-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-field.span-2 {
  grid-column: span 2;
}

.form-field span {
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.form-field small {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.form-field input,
.form-field select,
.operating-control select {
  width: 100%;
  height: 42px;
  border: 1px solid #d7e0ea;
  border-radius: 12px;
  padding: 0 12px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
}

.operating-control {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) minmax(110px, 0.8fr) auto minmax(110px, 0.8fr);
  gap: 10px;
  align-items: center;
}

.operating-control select:first-child:last-child {
  grid-column: 1 / -1;
}

.time-separator {
  color: #64748b;
  font-size: 13px;
  font-weight: 900;
}

.form-error,
.message-card {
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.7;
}

.form-error,
.message-card.error {
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #dc2626;
}

.message-card.success {
  border: 1px solid #bbf7d0;
  background: #ecfdf5;
  color: #15803d;
}

.message-card.info {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
}

.form-error {
  margin-top: 14px;
}

.form-actions {
  justify-content: flex-end;
  margin-top: 18px;
}

.btn {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 11px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}

button.btn,
label.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  white-space: nowrap;
}

.btn-sm {
  min-height: 32px;
  padding: 0 10px;
  font-size: 12px;
}

.btn-primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.btn-danger {
  border-color: #fecaca;
  color: #dc2626;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.file-action {
  position: relative;
}

.file-action input {
  display: none;
}

.file-action.disabled {
  pointer-events: none;
  cursor: not-allowed;
  opacity: 0.6;
}

.permission-card {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 28px;
}

.permission-icon {
  width: 56px;
  height: 56px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 28px;
  font-weight: 900;
  margin-bottom: 14px;
}

.permission-title {
  font-size: 22px;
  font-weight: 900;
  color: #0f172a;
  margin-bottom: 8px;
}

.permission-desc {
  color: #64748b;
  font-size: 14px;
}

@media (max-width: 1200px) {
  .filter-bar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .form-section-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
