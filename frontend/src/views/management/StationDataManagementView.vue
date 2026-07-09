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
        <button class="btn btn-secondary" type="button" :disabled="exportingData" @click="openStationExportDialog">
          {{ exportingData ? '导出中...' : '导出数据' }}
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
      <div class="permission-desc">当前账号无权访问站点数据管理页面。</div>
    </div>

    <template v-else>
      <transition name="toast-fade">
        <div v-if="message.text" :class="['message-toast', message.type]">{{ message.text }}</div>
      </transition>

      <div v-if="stationExportDialog.visible" class="station-export-backdrop">
        <div class="station-export-modal card-surface">
          <div class="station-export-header">
            <div>
              <div class="section-kicker">站点数据导出</div>
              <h3>选择需要导出的字段</h3>
            </div>
            <button class="close-btn" type="button" :disabled="exportingData" @click="closeStationExportDialog">×</button>
          </div>

          <div class="station-export-body">
            <div class="export-notice">
              <div>
                <strong>导出说明</strong>
                <p>这里导出的是当前筛选后的站点数据，文件格式为 Excel。完整灾备恢复请继续使用“导出备份 / 导入备份”。</p>
              </div>
              <span>Excel</span>
            </div>

            <div class="export-summary-grid">
              <div class="export-summary-card primary">
                <span>准备导出</span>
                <strong>{{ filteredStations.length }}</strong>
                <em>个站点</em>
              </div>
              <div class="export-summary-card">
                <span>已选字段</span>
                <strong>{{ selectedStationExportFieldCount }}</strong>
                <em>项字段</em>
              </div>
              <div class="export-summary-card">
                <span>默认字段</span>
                <strong>3</strong>
                <em>站点名 / 用户名 / 片区</em>
              </div>
            </div>

            <div class="export-field-panel">
              <div class="export-field-panel-head">
                <div>
                  <div class="export-section-title">导出字段</div>
                  <p>默认只勾选“站点名称”“站点登录用户名”“所属片区/归属地”，也可以按需要自由选择。</p>
                </div>
                <div class="export-field-actions">
                  <span>已选 {{ selectedStationExportFieldCount }} 项</span>
                  <button class="btn btn-secondary btn-sm" type="button" :disabled="exportingData"
                    @click="setAllStationExportFields(true)">一键全选</button>
                  <button class="btn btn-secondary btn-sm" type="button" :disabled="exportingData"
                    @click="invertStationExportFields">一键反选</button>
                </div>
              </div>

              <div class="export-field-groups">
                <section v-for="group in stationExportFieldGroups" :key="group.title" class="export-field-group">
                  <h4>{{ group.title }}</h4>
                  <div class="export-field-options">
                    <label v-for="option in group.options" :key="option.key" class="export-field-option">
                      <input v-model="stationExportSelection[option.key]" type="checkbox" :disabled="exportingData" />
                      <span>{{ option.label }}</span>
                      <em>{{ option.help }}</em>
                    </label>
                  </div>
                </section>
              </div>
            </div>

            <div v-if="stationExportDialog.error" class="form-error">{{ stationExportDialog.error }}</div>
          </div>

          <div class="station-export-actions">
            <button class="btn btn-secondary" type="button" :disabled="exportingData" @click="closeStationExportDialog">
              关闭
            </button>
            <button class="btn btn-primary" type="button" :disabled="exportingData" @click="exportStationData">
              {{ exportingData ? '生成中...' : '生成并下载 Excel' }}
            </button>
          </div>
        </div>
      </div>

      <div class="management-stack">
        <section ref="formCardRef" class="card-surface form-card" :class="{ editing: editingId }">
          <div class="section-head compact">
            <div>
              <div class="section-kicker">{{ editingId ? '编辑站点' : '新增站点' }}</div>
              <h3>{{ editingId ? '维护站点主数据' : '录入新站点' }}</h3>
              <p v-if="editingId" class="editing-target">
                <span>正在编辑</span>
                <strong>{{ form.station_name }}</strong>
              </p>
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
                  <span>HOS编码</span>
                  <input v-model.trim="form.hos_station_code" type="text" placeholder="例如：PQ04" />
                  <small>站点唯一标识，用于防止重复添加。</small>
                </label>

                <label class="form-field">
                  <span>站点类型</span>
                  <select v-model="form.station_type">
                    <option value="油站">油站</option>
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
                  <span>监控状态</span>
                  <select v-model="form.monitoring_status">
                    <option value="运行中">运行中</option>
                    <option value="未运行">未运行</option>
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
            <button class="btn btn-secondary" type="button" @click="resetForm({ scrollToForm: true })">
              {{ editingId ? '放弃修改' : '清空' }}
            </button>
            <button class="btn btn-primary" type="button" :disabled="saving" @click="saveStation">
              {{ saving ? '保存中...' : editingId ? '保存修改' : '保存站点' }}
            </button>
          </div>
        </section>

        <section ref="tableCardRef" class="card-surface table-card">
          <div class="section-head">
            <div>
              <div class="section-kicker">站点清单</div>
              <h3>共 {{ filteredStations.length }} 个站点</h3>
            </div>
          </div>

          <div class="filter-bar">
            <label class="filter-field keyword-field">
              <span>关键词</span>
              <input v-model.trim="filters.keyword" type="text" placeholder="站点名称、地址、负责人、HOS编码、登录用户名" />
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
                <option value="油站">油站</option>
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

            <label class="filter-field">
              <span>监控状态</span>
              <select v-model="filters.monitoring_status">
                <option value="">全部监控</option>
                <option value="运行中">运行中</option>
                <option value="未运行">未运行</option>
              </select>
            </label>

            <button class="btn btn-secondary" type="button" @click="resetFilters">重置筛选</button>
          </div>

          <div class="table-wrap">
            <table class="station-table">
              <thead>
                <tr>
                  <th>站点名称</th>
                  <th>站点登录用户名</th>
                  <th>所属片区/归属地</th>
                  <th>站点类型</th>
                  <th>资产类型</th>
                  <th>是否并表</th>
                  <th>是否上线3.0</th>
                  <th>监控状态</th>
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
                  <td colspan="16" class="empty-cell">正在加载站点数据...</td>
                </tr>
                <tr v-else-if="!filteredStations.length">
                  <td colspan="16" class="empty-cell">暂无匹配的站点数据。</td>
                </tr>
                <tr v-for="station in pagedStations" :key="station.id" :class="{ active: editingId === station.id }">
                  <td>
                    <div class="table-title">{{ station.station_name }}</div>
                    <div class="table-sub">{{ station.address || '-' }}</div>
                  </td>
                  <td>
                    <div v-if="getStationUsernames(station).length" class="username-chip-list">
                      <span v-for="username in getStationUsernames(station)" :key="`${station.id}-${username}`" class="username-chip">
                        {{ username }}
                      </span>
                    </div>
                    <span v-else class="table-sub muted">未绑定</span>
                  </td>
                  <td>{{ station.region || '-' }}</td>
                  <td>{{ station.station_type || '-' }}</td>
                  <td>{{ normalizeAssetType(station.asset_type) }}</td>
                  <td>{{ station.is_consolidated || '否' }}</td>
                  <td>{{ station.online_3_status || '未上线' }}</td>
                  <td>
                    <span class="status-pill monitor" :class="{ offline: station.monitoring_status === '未运行' }">
                      {{ station.monitoring_status || '运行中' }}
                    </span>
                  </td>
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
                      <button v-if="canResetStationPassword" class="btn btn-warning btn-sm" type="button"
                        :disabled="resettingStationId === station.id || !getStationUsernames(station).length"
                        @click="resetStationPassword(station)">
                        {{ resettingStationId === station.id ? '重置中' : getStationUsernames(station).length ? '重置密码' : '无账号' }}
                      </button>
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

          <div class="mobile-station-list">
            <div v-if="loading" class="mobile-empty-card">正在加载站点数据...</div>
            <div v-else-if="!filteredStations.length" class="mobile-empty-card">暂无匹配的站点数据。</div>
            <template v-else>
              <article v-for="station in pagedStations" :key="`mobile-${station.id}`" class="mobile-station-card"
                :class="{ active: editingId === station.id }">
                <div class="mobile-card-head">
                  <div>
                    <h4>{{ station.station_name }}</h4>
                    <p>{{ station.region || '未设置片区' }} · {{ station.station_type || '未设置类型' }}</p>
                  </div>
                  <span class="status-pill" :class="{ closed: station.status === '停业' }">{{ station.status || '-' }}</span>
                </div>

                <div class="mobile-account-block">
                  <span>站点登录用户名</span>
                  <div v-if="getStationUsernames(station).length" class="username-chip-list">
                    <span v-for="username in getStationUsernames(station)" :key="`mobile-user-${station.id}-${username}`" class="username-chip">
                      {{ username }}
                    </span>
                  </div>
                  <strong v-else>未绑定站点账号</strong>
                </div>

                <div class="mobile-info-grid">
                  <div>
                    <span>HOS编码</span>
                    <strong>{{ station.hos_station_code || '-' }}</strong>
                  </div>
                  <div>
                    <span>资产类型</span>
                    <strong>{{ normalizeAssetType(station.asset_type) }}</strong>
                  </div>
                  <div>
                    <span>是否并表</span>
                    <strong>{{ station.is_consolidated || '否' }}</strong>
                  </div>
                  <div>
                    <span>上线3.0</span>
                    <strong>{{ station.online_3_status || '未上线' }}</strong>
                  </div>
                  <div>
                    <span>监控状态</span>
                    <strong>{{ station.monitoring_status || '运行中' }}</strong>
                  </div>
                  <div>
                    <span>营运时间</span>
                    <strong>{{ station.operating_hours || '-' }}</strong>
                  </div>
                  <div>
                    <span>固定电话</span>
                    <strong>{{ station.landline_phone || '-' }}</strong>
                  </div>
                </div>

                <div class="mobile-contact-row">
                  <span>负责人</span>
                  <strong>{{ station.station_manager_name || '-' }}</strong>
                  <em>{{ station.station_manager_phone || '-' }}</em>
                </div>

                <p class="mobile-address">{{ station.address || '未填写站点地址' }}</p>

                <div class="mobile-meta-row">
                  <span>创建 {{ station.created_at || '-' }}</span>
                  <span>更新 {{ station.updated_at || '-' }}</span>
                </div>

                <div class="mobile-card-actions">
                  <button class="btn btn-secondary btn-sm" type="button" @click="startEdit(station)">编辑</button>
                  <button v-if="canResetStationPassword" class="btn btn-warning btn-sm" type="button"
                    :disabled="resettingStationId === station.id || !getStationUsernames(station).length"
                    @click="resetStationPassword(station)">
                    {{ resettingStationId === station.id ? '重置中' : getStationUsernames(station).length ? '重置密码' : '无账号' }}
                  </button>
                  <button class="btn btn-danger btn-sm" type="button" :disabled="deletingId === station.id"
                    @click="deleteStation(station)">
                    {{ deletingId === station.id ? '删除中' : '删除' }}
                  </button>
                </div>
              </article>
            </template>
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
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

const currentUserId = localStorage.getItem('user_id') || ''
const currentRole = localStorage.getItem('user_role') || ''
let localPermissions = {}
try {
  localPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch (error) {
  localPermissions = {}
}
const hasPermission = currentRole === 'root' || Boolean(localPermissions.manage_stations)
const canResetStationPassword = currentRole === 'root' || Boolean(localPermissions.reset_station_account_password)

const stations = ref([])
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const exportingData = ref(false)
const importing = ref(false)
const deletingId = ref(null)
const resettingStationId = ref(null)
const editingId = ref(null)
const formError = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const formCardRef = ref(null)
const tableCardRef = ref(null)
const operatingMode = ref('24小时')
const operatingStart = ref('06:00')
const operatingEnd = ref('22:00')
const message = reactive({
  text: '',
  type: 'info'
})
const stationExportDialog = reactive({
  visible: false,
  error: ''
})
let messageTimer = null
const filters = reactive({
  keyword: '',
  region: '',
  station_type: '',
  status: '',
  monitoring_status: ''
})

const createEmptyForm = () => ({
  station_name: '',
  region: '',
  address: '',
  longitude: '',
  latitude: '',
  station_manager_name: '',
  station_manager_phone: '',
  station_type: '油站',
  asset_type: '全资',
  is_consolidated: '否',
  online_3_status: '未上线',
  monitoring_status: '运行中',
  hos_station_code: '',
  landline_phone: '',
  status: '营业中',
  operating_hours: '24小时'
})

const stationExportFieldGroups = [
  {
    title: '基础档案',
    options: [
      { key: 'station_name', label: '站点名称', help: '站点主数据名称' },
      { key: 'station_usernames', label: '站点登录用户名', help: '绑定本站的站点账号' },
      { key: 'region', label: '所属片区/归属地', help: '站点所属片区或归属地' },
      { key: 'address', label: '站点地址', help: '站点详细地址' },
      { key: 'hos_station_code', label: 'HOS编码', help: '站点唯一业务编码' }
    ]
  },
  {
    title: '联系方式',
    options: [
      { key: 'station_manager_name', label: '站点负责人姓名', help: '站点负责人' },
      { key: 'station_manager_phone', label: '站点负责人手机号', help: '负责人联系电话' },
      { key: 'landline_phone', label: '固定电话', help: '站点固定电话' },
      { key: 'longitude', label: '经度', help: '地图经度坐标' },
      { key: 'latitude', label: '纬度', help: '地图纬度坐标' }
    ]
  },
  {
    title: '经营属性',
    options: [
      { key: 'station_type', label: '站点类型', help: '油站或充电站' },
      { key: 'asset_type', label: '资产类型', help: '全资或股权' },
      { key: 'is_consolidated', label: '是否并表', help: '是否纳入并表范围' },
      { key: 'online_3_status', label: '是否上线3.0', help: '3.0 系统上线状态' },
      { key: 'monitoring_status', label: '监控状态', help: '站点视频监控是否运行' },
      { key: 'status', label: '站点状态', help: '营业中或停业' },
      { key: 'operating_hours', label: '营运时间', help: '统一格式的营业时间' }
    ]
  },
  {
    title: '系统时间',
    options: [
      { key: 'created_at', label: '创建时间', help: '站点数据创建时间' },
      { key: 'updated_at', label: '更新时间', help: '站点数据最后更新时间' }
    ]
  }
]
const stationExportFieldOptions = stationExportFieldGroups.flatMap((group) => group.options)
const defaultStationExportFieldKeys = new Set(['station_name', 'station_usernames', 'region'])
const createDefaultStationExportSelection = () => Object.fromEntries(
  stationExportFieldOptions.map((option) => [option.key, defaultStationExportFieldKeys.has(option.key)])
)
const stationExportSelection = reactive(createDefaultStationExportSelection())

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

const getStationUsernames = (station) => {
  return String(station?.station_usernames || '')
    .split(/\s+/)
    .map((item) => item.trim())
    .filter(Boolean)
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
      station.landline_phone,
      station.station_usernames
    ].join(' ').toLowerCase()
    const matchesKeyword = !keyword || text.includes(keyword)
    const matchesRegion = !filters.region || station.region === filters.region
    const matchesType = !filters.station_type || station.station_type === filters.station_type
    const matchesStatus = !filters.status || station.status === filters.status
    const matchesMonitoring = !filters.monitoring_status || (station.monitoring_status || '运行中') === filters.monitoring_status
    return matchesKeyword && matchesRegion && matchesType && matchesStatus && matchesMonitoring
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
const selectedStationExportFieldKeys = computed(() => (
  stationExportFieldOptions
    .filter((option) => Boolean(stationExportSelection[option.key]))
    .map((option) => option.key)
))
const selectedStationExportFieldCount = computed(() => selectedStationExportFieldKeys.value.length)

const setMessage = (text, type = 'info') => {
  if (messageTimer) {
    clearTimeout(messageTimer)
    messageTimer = null
  }

  message.text = text
  message.type = type
  if (!text) return

  messageTimer = setTimeout(() => {
    message.text = ''
    messageTimer = null
  }, 2400)
}

const resetForm = (options = {}) => {
  Object.assign(form, createEmptyForm())
  applyOperatingHoursToControls(form.operating_hours)
  editingId.value = null
  formError.value = ''
  if (!options.keepMessage) setMessage('')
  if (options.scrollToForm) {
    nextTick(() => {
      formCardRef.value?.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      })
    })
  }
}

const resetFilters = () => {
  Object.assign(filters, {
    keyword: '',
    region: '',
    station_type: '',
    status: '',
    monitoring_status: ''
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
  station_type: station.station_type || '油站',
  asset_type: normalizeAssetType(station.asset_type) === '股权' ? '股权' : '全资',
  is_consolidated: station.is_consolidated || '否',
  online_3_status: station.online_3_status || '未上线',
  monitoring_status: station.monitoring_status || '运行中',
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
  setMessage(`已进入【${station.station_name}】编辑状态，请在维护站点主数据模块修改后保存。`, 'info')
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
  const utf8Matched = value.match(/filename\*=UTF-8''([^;]+)/i)
  const fallbackMatched = value.match(/filename="?([^";]+)"?/i)
  const filename = decodeURIComponent(utf8Matched?.[1] || fallbackMatched?.[1] || '')
  return filename || `ywddzx_stations_backup_${new Date().toISOString().slice(0, 10)}.json`
}

const getExcelDownloadFileName = (disposition) => {
  const value = String(disposition || '')
  const utf8Matched = value.match(/filename\*=UTF-8''([^;]+)/i)
  const fallbackMatched = value.match(/filename="?([^";]+)"?/i)
  const filename = decodeURIComponent(utf8Matched?.[1] || fallbackMatched?.[1] || '')
  return filename || `站点数据导出_${new Date().toISOString().slice(0, 10)}.xlsx`
}

const getResponseErrorMessage = async (error, fallback) => {
  const data = error?.response?.data
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      const payload = JSON.parse(text || '{}')
      return payload.error || payload.message || fallback
    } catch (_error) {
      return fallback
    }
  }
  return data?.error || data?.message || fallback
}

const openStationExportDialog = () => {
  if (!filteredStations.value.length) {
    setMessage('当前筛选结果为空，不能导出。', 'error')
    return
  }
  Object.assign(stationExportSelection, createDefaultStationExportSelection())
  stationExportDialog.error = ''
  stationExportDialog.visible = true
}

const closeStationExportDialog = () => {
  if (exportingData.value) return
  stationExportDialog.visible = false
  stationExportDialog.error = ''
}

const setAllStationExportFields = (checked) => {
  stationExportFieldOptions.forEach((option) => {
    stationExportSelection[option.key] = checked
  })
}

const invertStationExportFields = () => {
  stationExportFieldOptions.forEach((option) => {
    stationExportSelection[option.key] = !stationExportSelection[option.key]
  })
}

const exportStationData = async () => {
  if (!selectedStationExportFieldCount.value) {
    stationExportDialog.error = '请至少选择一个导出字段。'
    return
  }
  if (!filteredStations.value.length) {
    stationExportDialog.error = '当前筛选结果为空，不能导出。'
    return
  }

  try {
    exportingData.value = true
    stationExportDialog.error = ''
    setMessage('')
    const response = await axios.post('/api/management/stations/export-data', {
      user_id: currentUserId,
      station_ids: filteredStations.value.map((station) => station.id),
      field_keys: selectedStationExportFieldKeys.value
    }, {
      responseType: 'blob'
    })
    const blobUrl = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = getExcelDownloadFileName(response.headers['content-disposition'])
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(blobUrl)
    stationExportDialog.visible = false
    setMessage('站点数据 Excel 已生成。', 'success')
  } catch (error) {
    stationExportDialog.error = await getResponseErrorMessage(error, '站点数据导出失败，请稍后重试。')
  } finally {
    exportingData.value = false
  }
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
    setMessage(await getResponseErrorMessage(error, '站点数据导出失败，请稍后重试。'), 'error')
  } finally {
    exporting.value = false
  }
}

const resetStationPassword = async (station) => {
  if (!canResetStationPassword) return
  const usernames = getStationUsernames(station)
  if (!usernames.length) {
    setMessage('该站点暂无绑定站点账号。', 'error')
    return
  }
  const confirmed = window.confirm(`确定将【${station.station_name}】绑定站点账号密码重置为 123456 吗？该账号下次登录需要重新设置密码。`)
  if (!confirmed) return

  try {
    resettingStationId.value = station.id
    const response = await axios.post(`/api/management/stations/${station.id}/reset-password`, {
      user_id: currentUserId
    })
    setMessage(response.data?.message || '站点账号密码已重置。', 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || '站点账号密码重置失败。', 'error')
  } finally {
    resettingStationId.value = null
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
    resetForm({ keepMessage: true })
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
  if (!form.hos_station_code) return '请填写 HOS编码。'
  if (!form.station_type) return '请选择站点类型。'
  if (!form.asset_type) return '请选择资产类型。'
  if (!form.is_consolidated) return '请选择是否并表。'
  if (!form.online_3_status) return '请选择是否上线3.0。'
  if (!form.monitoring_status) return '请选择监控状态。'
  if (!form.status) return '请选择站点状态。'
  if (operatingMode.value === 'custom' && operatingStart.value === operatingEnd.value) return '营运时间的开始时间和结束时间不能相同。'
  return ''
}

const saveStation = async () => {
  formError.value = validateForm()
  if (formError.value) return

  try {
    saving.value = true
    const isEditing = Boolean(editingId.value)
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
    if (isEditing) {
      nextTick(() => {
        tableCardRef.value?.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        })
      })
      return
    }
    if (savedId) {
      const savedRow = stations.value.find((item) => String(item.id) === String(savedId))
      if (savedRow) startEdit(savedRow)
    } else {
      resetForm({ keepMessage: true })
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
    if (editingId.value === station.id) resetForm({ keepMessage: true })
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

onBeforeUnmount(() => {
  if (messageTimer) {
    clearTimeout(messageTimer)
    messageTimer = null
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

.row-actions {
  flex-wrap: wrap;
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

.form-card.editing {
  border-color: #bfdbfe;
  box-shadow: 0 18px 40px rgba(37, 99, 235, 0.12);
}

.editing-target {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin: 8px 0 0;
}

.editing-target > span {
  color: #64748b;
  font-size: 14px;
  font-weight: 900;
}

.editing-target > strong {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 6px 14px;
  border-radius: 999px;
  background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%);
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.12);
  font-size: 15px;
  font-weight: 950;
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
  min-width: 1780px;
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

.table-sub.muted {
  display: inline-flex;
  margin-top: 0;
  color: #94a3b8;
  font-weight: 800;
}

.username-chip-list {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.username-chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
  line-height: 1;
}

.mobile-station-list {
  display: none;
}

.mobile-empty-card,
.mobile-station-card {
  border: 1px solid #dbe4ee;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.06);
}

.mobile-empty-card {
  padding: 22px 16px;
  text-align: center;
  color: #64748b;
  font-size: 14px;
  font-weight: 800;
}

.mobile-station-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.mobile-station-card.active {
  border-color: #93c5fd;
  background: linear-gradient(135deg, #eff6ff 0%, #ffffff 72%);
}

.mobile-card-head,
.mobile-contact-row,
.mobile-meta-row,
.mobile-card-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mobile-card-head {
  justify-content: space-between;
}

.mobile-card-head h4 {
  margin: 0;
  color: #0f172a;
  font-size: 17px;
  font-weight: 950;
}

.mobile-card-head p,
.mobile-address,
.mobile-meta-row {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.status-pill {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 5px 10px;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
  font-size: 12px;
  font-weight: 900;
}

.status-pill.closed {
  background: #fee2e2;
  color: #b91c1c;
}

.status-pill.monitor {
  background: #ecfdf5;
  color: #047857;
}

.status-pill.monitor.offline {
  background: #fff7ed;
  color: #c2410c;
}

.mobile-account-block {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.mobile-account-block > span,
.mobile-info-grid span,
.mobile-contact-row span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.mobile-account-block > strong {
  color: #94a3b8;
  font-size: 13px;
  font-weight: 900;
}

.mobile-info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.mobile-info-grid > div {
  display: grid;
  gap: 5px;
  padding: 10px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.mobile-info-grid strong,
.mobile-contact-row strong {
  color: #0f172a;
  font-size: 13px;
  font-weight: 900;
  line-height: 1.45;
}

.mobile-contact-row {
  flex-wrap: wrap;
  padding: 10px 12px;
  border-radius: 14px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
}

.mobile-contact-row em {
  color: #9a3412;
  font-size: 12px;
  font-style: normal;
  font-weight: 900;
}

.mobile-address {
  padding: 0 2px;
}

.mobile-meta-row {
  justify-content: space-between;
  flex-wrap: wrap;
  margin-top: 0;
}

.mobile-card-actions {
  justify-content: flex-end;
  padding-top: 2px;
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

.message-toast {
  position: fixed;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: min(calc(100vw - 32px), 440px);
  z-index: 1500;
  padding: 12px 14px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 900;
  line-height: 1.7;
  text-align: center;
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.18);
  backdrop-filter: blur(10px);
  animation: toast-pulse 1.2s ease-in-out infinite;
}

.message-toast.error {
  border: 1px solid #fecaca;
  background: rgba(254, 242, 242, 0.98);
  color: #b91c1c;
}

.message-toast.success {
  border: 1px solid #bbf7d0;
  background: rgba(236, 253, 245, 0.98);
  color: #166534;
}

.message-toast.info {
  border: 1px solid #bfdbfe;
  background: rgba(239, 246, 255, 0.98);
  color: #1d4ed8;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, calc(-50% + 12px));
}

@keyframes toast-pulse {
  0%,
  100% {
    box-shadow: 0 18px 36px rgba(15, 23, 42, 0.16);
  }

  50% {
    box-shadow: 0 22px 44px rgba(37, 99, 235, 0.22);
  }
}

.form-error {
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.7;
}

.form-error {
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #dc2626;
}

.form-error {
  margin-top: 14px;
}

.form-actions {
  justify-content: flex-end;
  margin-top: 18px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  min-height: 38px;
  padding: 0 14px;
  border-radius: 11px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  font-size: 13px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
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

.btn-warning {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #c2410c;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.file-action {
  position: relative;
  height: 38px;
}

.file-action input {
  display: none;
}

.file-action span {
  pointer-events: none;
}

.file-action.disabled {
  pointer-events: none;
  cursor: not-allowed;
  opacity: 0.6;
}

.close-btn {
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
}

.close-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.station-export-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1400;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 22px;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(8px);
}

.station-export-modal {
  width: min(860px, 100%);
  max-height: min(88vh, 880px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.station-export-header,
.station-export-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 20px;
}

.station-export-header {
  border-bottom: 1px solid #e2e8f0;
}

.station-export-header h3 {
  margin: 0;
  color: #0f172a;
  font-size: 22px;
}

.station-export-body {
  overflow: auto;
  padding: 20px;
  background:
    radial-gradient(circle at 100% 0%, rgba(37, 99, 235, 0.10), transparent 32%),
    linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.station-export-actions {
  justify-content: flex-end;
  border-top: 1px solid #e2e8f0;
  background: #fff;
}

.export-notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border: 1px solid #bfdbfe;
  border-radius: 18px;
  background: #eff6ff;
}

.export-notice strong,
.export-section-title {
  display: block;
  color: #0f172a;
  font-size: 14px;
  font-weight: 950;
}

.export-notice p {
  margin: 6px 0 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.8;
}

.export-notice > span {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 68px;
  height: 36px;
  border-radius: 999px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 950;
}

.export-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.export-summary-card {
  min-width: 0;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: #fff;
}

.export-summary-card.primary {
  border-color: #bfdbfe;
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
}

.export-summary-card span,
.export-summary-card em {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.export-summary-card strong {
  display: block;
  margin: 6px 0 4px;
  color: #0f172a;
  font-size: 28px;
  font-weight: 950;
}

.export-field-panel {
  margin-top: 14px;
  padding: 16px;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.94);
}

.export-field-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.export-field-panel p {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.8;
}

.export-field-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.export-field-actions span {
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.export-field-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}

.export-field-group {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #f8fafc;
}

.export-field-group h4 {
  margin: 0 0 10px;
  color: #0f172a;
  font-size: 13px;
  font-weight: 950;
}

.export-field-options {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.export-field-option {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  grid-template-areas:
    "check title"
    "check help";
  align-items: start;
  column-gap: 9px;
  row-gap: 4px;
  min-height: 76px;
  padding: 12px;
  border: 1px solid #dbe4ee;
  border-radius: 16px;
  background: #fff;
  cursor: pointer;
}

.export-field-option input {
  grid-area: check;
  width: 16px;
  height: 16px;
  margin-top: 2px;
  accent-color: #2563eb;
}

.export-field-option span {
  grid-area: title;
  color: #0f172a;
  font-size: 13px;
  font-weight: 950;
}

.export-field-option em {
  grid-area: help;
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
  line-height: 1.6;
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

@media (max-width: 760px) {
  .page-shell {
    gap: 14px;
  }

  .page-header {
    flex-direction: column;
    padding: 18px;
    border-radius: 20px;
  }

  .page-header h2 {
    font-size: 28px;
  }

  .header-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
    justify-content: stretch;
  }

  .header-actions .btn,
  .header-actions .file-action {
    width: 100%;
  }

  .table-card,
  .form-card {
    padding: 16px;
    border-radius: 20px;
  }

  .section-head,
  .form-section-title,
  .pagination-bar,
  .pagination-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-bar,
  .form-section-grid,
  .export-summary-grid,
  .export-field-options {
    grid-template-columns: 1fr;
  }

  .filter-bar {
    padding: 12px;
    border-radius: 16px;
  }

  .form-section {
    padding: 14px;
    border-radius: 16px;
  }

  .form-field.span-2 {
    grid-column: auto;
  }

  .operating-control {
    grid-template-columns: 1fr;
  }

  .time-separator {
    text-align: center;
  }

  .table-wrap {
    display: none;
  }

  .mobile-station-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .pagination-actions {
    gap: 8px;
  }

  .page-size-field {
    justify-content: space-between;
  }

  .pagination-actions .btn,
  .pagination-actions .page-size-field,
  .pagination-actions .page-indicator {
    width: 100%;
  }

  .form-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .station-export-backdrop {
    align-items: flex-end;
    padding: 10px;
  }

  .station-export-modal {
    max-height: 92vh;
    border-radius: 22px;
  }

  .station-export-header,
  .station-export-actions,
  .export-field-panel-head,
  .export-notice {
    flex-direction: column;
    align-items: stretch;
  }

  .station-export-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .export-field-actions {
    justify-content: stretch;
  }

  .export-field-actions span,
  .export-field-actions .btn {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .header-actions,
  .mobile-info-grid {
    grid-template-columns: 1fr;
  }

  .mobile-card-head {
    align-items: flex-start;
  }
}
</style>
