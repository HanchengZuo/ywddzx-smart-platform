<template>
    <div v-if="hasPermission" class="page-shell" :class="{ 'edit-mode': canEdit }">
        <div class="page-header card-surface">
            <div>
                <div class="page-kicker">证照管理</div>
                <h2>{{ pageTitle }}</h2>
                <p class="page-desc">{{ pageDesc }}</p>
            </div>
            <div class="header-actions">
                <span :class="['role-chip', canEdit ? 'supervisor' : 'station']">
                    {{ canEdit ? '督导维护视角' : '站点查看视角' }}
                </span>
                <button class="ghost-btn" type="button" @click="fetchCertificateData" :disabled="loading">
                    {{ loading ? '刷新中...' : '刷新数据' }}
                </button>
            </div>
        </div>

        <div v-if="pageError" class="message-card error-card">{{ pageError }}</div>

        <transition name="toast-fade">
            <div v-if="actionMessage" class="submit-toast" :class="actionMessageType">{{ actionMessage }}</div>
        </transition>

        <div class="stats-grid">
            <div v-for="card in statCards" :key="card.label" class="card-surface stat-card">
                <div class="stat-label">{{ card.label }}</div>
                <div :class="['stat-value', card.valueClass]">{{ card.value }}</div>
                <div class="stat-desc">{{ card.desc }}</div>
            </div>
        </div>

        <div class="content-grid" :class="{ 'edit-first': canEdit }">
            <div class="left-column">
                <div class="card-surface section-card">
                    <div class="section-head">
                        <div>
                            <div class="section-kicker">证照台账</div>
                            <h3>{{ canEdit ? '全部站点证照有效期' : '本站证照有效期' }}</h3>
                        </div>
                        <div class="inline-tags">
                            <span class="tag neutral">共 {{ filteredCertificateRows.length }} 条</span>
                            <span v-if="recommendedRows.length" class="tag recommended">推荐 {{ recommendedRows.length
                                }}</span>
                            <span v-if="legalRows.length" class="tag legal">法定 {{ legalRows.length }}</span>
                            <span v-if="expiredRows.length" class="tag danger">过期 {{ expiredRows.length }}</span>
                        </div>
                    </div>

                    <div class="filter-grid">
                        <div v-if="canEdit" class="filter-field">
                            <label>站点</label>
                            <select v-model="filters.stationId">
                                <option value="all">全部站点</option>
                                <option v-for="station in stations" :key="station.id" :value="String(station.id)">
                                    {{ station.station_name }}
                                </option>
                            </select>
                        </div>
                        <div class="filter-field">
                            <label>证照类型</label>
                            <select v-model="filters.certificateType">
                                <option value="all">全部证照</option>
                                <option v-for="type in certificateTypes" :key="type.code" :value="type.code">
                                    {{ type.name }}
                                </option>
                            </select>
                        </div>
                        <div class="filter-field">
                            <label>到期状态</label>
                            <select v-model="filters.status">
                                <option value="all">全部状态</option>
                                <option value="normal">正常</option>
                                <option value="recommended">推荐提醒期</option>
                                <option value="legal">法定提醒期</option>
                                <option value="expired">已过期</option>
                            </select>
                        </div>
                        <div class="filter-field">
                            <label>关键词</label>
                            <input v-model.trim="filters.keyword" type="text" placeholder="搜索站点或证照名称" />
                        </div>
                    </div>

                    <div class="table-wrap">
                        <table class="cert-table ledger-table">
                            <thead>
                                <tr>
                                    <th>站点</th>
                                    <th>证照类型</th>
                                    <th>起始日期</th>
                                    <th>到期时间</th>
                                    <th>提醒规则</th>
                                    <th>状态</th>
                                    <th v-if="canEdit">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-if="loading">
                                    <td :colspan="canEdit ? 7 : 6" class="empty-cell">证照台账加载中...</td>
                                </tr>
                                <tr v-else-if="!filteredCertificateRows.length">
                                    <td :colspan="canEdit ? 7 : 6" class="empty-cell">
                                        当前筛选条件下暂无证照记录。
                                    </td>
                                </tr>
                                <template v-else>
                                    <tr v-for="row in filteredCertificateRows" :key="row.id">
                                        <td>
                                            <div class="table-title">{{ row.station_name || '-' }}</div>
                                            <div class="table-sub">{{ row.region || '暂无片区' }}</div>
                                        </td>
                                        <td>
                                            <div class="table-title">{{ row.certificate_name }}</div>
                                            <div class="table-sub">{{ getTypeMeta(row.certificate_type).note }}</div>
                                        </td>
                                        <td>{{ row.start_date || '未录入' }}</td>
                                        <td>
                                            <div class="expire-date">{{ row.expiry_date || '-' }}</div>
                                            <div class="table-sub">更新 {{ row.updated_at || '-' }}</div>
                                        </td>
                                        <td>
                                            <div class="rule-mini">推荐：{{ getRecommendedLabel(row) }}</div>
                                            <div class="table-sub">法定：{{ getLegalLabel(row) }}</div>
                                        </td>
                                        <td>
                                            <div class="status-cell">
                                                <span :class="['status-chip', getStatusMeta(row).className]">
                                                    {{ getStatusMeta(row).label }}
                                                </span>
                                                <div class="table-sub">{{ getStatusMeta(row).desc }}</div>
                                            </div>
                                        </td>
                                        <td v-if="canEdit">
                                            <div class="row-actions">
                                                <button class="ghost-btn mini-btn" type="button"
                                                    @click="editCertificate(row)">
                                                    编辑
                                                </button>
                                                <button class="ghost-btn mini-btn danger-btn" type="button"
                                                    @click="deleteCertificate(row)">
                                                    删除
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                </template>
                            </tbody>
                        </table>
                    </div>

                    <div class="mobile-cert-list">
                        <div v-if="loading" class="mobile-empty card-surface">证照台账加载中...</div>
                        <div v-else-if="!filteredCertificateRows.length" class="mobile-empty card-surface">
                            当前筛选条件下暂无证照记录。
                        </div>
                        <div v-else class="mobile-cert-cards">
                            <div v-for="row in filteredCertificateRows" :key="row.id" class="mobile-cert-card card-surface">
                                <div class="mobile-card-head">
                                    <div>
                                        <div class="mobile-card-category">{{ row.certificate_name }}</div>
                                        <div class="mobile-card-code">{{ row.station_name || '-' }}</div>
                                    </div>
                                    <span :class="['status-chip', getStatusMeta(row).className]">
                                        {{ getStatusMeta(row).label }}
                                    </span>
                                </div>

                                <div class="mobile-card-body">
                                    <div class="mobile-card-row">
                                        <span>所属片区</span>
                                        <strong>{{ row.region || '暂无片区' }}</strong>
                                    </div>
                                    <div class="mobile-card-row">
                                        <span>起始日期</span>
                                        <strong>{{ row.start_date || '未录入' }}</strong>
                                    </div>
                                    <div class="mobile-card-row">
                                        <span>到期时间</span>
                                        <strong>{{ row.expiry_date || '-' }}</strong>
                                    </div>
                                    <div class="mobile-card-row">
                                        <span>推荐提醒</span>
                                        <strong>{{ getRecommendedLabel(row) }}</strong>
                                    </div>
                                    <div class="mobile-card-row">
                                        <span>法定提醒</span>
                                        <strong>{{ getLegalLabel(row) }}</strong>
                                    </div>
                                    <div class="mobile-card-row mobile-card-row-top">
                                        <span>状态说明</span>
                                        <div class="mobile-card-text">{{ getStatusMeta(row).desc }}</div>
                                    </div>
                                </div>

                                <div v-if="canEdit" class="mobile-card-actions">
                                    <button class="ghost-btn" type="button" @click="editCertificate(row)">编辑</button>
                                    <button class="ghost-btn danger-btn" type="button" @click="deleteCertificate(row)">
                                        删除
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="card-surface section-card">
                    <div class="section-head">
                        <div>
                            <div class="section-kicker">证件类型</div>
                            <h3>证照录入与提醒覆盖</h3>
                        </div>
                    </div>

                    <div class="summary-grid">
                        <div v-for="item in certificateSummary" :key="item.code" class="summary-card">
                            <div class="summary-title">{{ item.name }}</div>
                            <div class="summary-note">{{ item.note }}</div>
                            <div class="summary-meta">
                                <span>已录入 {{ item.recorded }} 条</span>
                                <span :class="{ recommended: item.recommended > 0 }">推荐 {{ item.recommended }}</span>
                                <span :class="{ legal: item.legal > 0 }">法定 {{ item.legal }}</span>
                                <span :class="{ danger: item.expired > 0 }">过期 {{ item.expired }}</span>
                            </div>
                            <div class="summary-rule">{{ item.rule }}</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="right-column">
                <div v-if="canEdit" class="card-surface section-card entry-card">
                    <div class="section-head compact">
                        <div>
                            <div class="section-kicker">维护证照</div>
                            <h3>{{ formTitle }}</h3>
                        </div>
                    </div>

                    <form class="certificate-form" @submit.prevent="saveCertificate">
                        <div class="form-field">
                            <label>站点</label>
                            <select v-model.number="certificateForm.station_id" :disabled="isEditing" required>
                                <option disabled value="">请选择站点</option>
                                <option v-for="station in stations" :key="station.id" :value="station.id">
                                    {{ station.station_name }}
                                </option>
                            </select>
                        </div>

                        <div class="form-field">
                            <label>证照类型</label>
                            <select v-model="certificateForm.certificate_type" :disabled="isEditing" required>
                                <option disabled value="">请选择证照类型</option>
                                <option v-for="type in certificateTypes" :key="type.code" :value="type.code">
                                    {{ type.name }}
                                </option>
                            </select>
                            <div class="form-tip">{{ selectedTypeNote }}</div>
                        </div>

                        <div class="form-field">
                            <label>起始日期（可选）</label>
                            <input v-model="certificateForm.start_date" type="date" />
                        </div>

                        <div class="form-field">
                            <label>到期时间（必填）</label>
                            <input v-model="certificateForm.expiry_date" type="date" required />
                        </div>

                        <div class="form-field">
                            <label>备注（可选）</label>
                            <textarea v-model.trim="certificateForm.remark" rows="3"
                                placeholder="可填写证件编号、换证进度或其他说明"></textarea>
                        </div>

                        <div class="form-actions">
                            <button class="ghost-btn" type="button" @click="resetCertificateForm">
                                {{ isEditing ? '取消编辑' : '清空' }}
                            </button>
                            <button class="primary-btn" type="submit" :disabled="saving">
                                {{ saving ? '保存中...' : '保存证照' }}
                            </button>
                        </div>
                    </form>
                </div>

                <div v-else class="card-surface section-card readonly-card">
                    <div class="section-kicker">查看权限</div>
                    <h3>站点账号仅可查看</h3>
                    <p>
                        当前页面展示本账号所属站点已录入的证照有效期和到期提醒。如需调整有效期，请联系督导组账号维护。
                    </p>
                </div>

                <div class="card-surface section-card">
                    <div class="section-head compact">
                        <div>
                            <div class="section-kicker">到期提醒</div>
                            <h3>{{ canEdit ? '全部站点重点提醒' : '本站重点提醒' }}</h3>
                        </div>
                    </div>

                    <div v-if="!urgentReminderRows.length" class="empty-alert">
                        当前没有进入推荐提醒期、法定提醒期或已过期的证照。
                    </div>
                    <div v-else class="alert-list">
                        <div v-for="row in urgentReminderRows" :key="row.id" class="alert-item"
                            :class="getStatusMeta(row).tone">
                            <div class="alert-dot"></div>
                            <div class="alert-content">
                                <div class="alert-title">
                                    {{ row.station_name }} · {{ row.certificate_name }}
                                </div>
                                <div class="alert-desc">
                                    有效期至 {{ row.expiry_date }}，{{ getStatusMeta(row).desc }}。
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="card-surface section-card rule-card">
                    <div class="section-kicker">提醒规则</div>
                    <h3>到期前自动进入提醒</h3>
                    <div class="rule-list">
                        <div v-for="type in certificateTypes" :key="type.code" class="rule-item">
                            <span class="rule-mark"
                                :class="type.code === 'dangerous_chemicals_permit' ? 'danger' : 'warning'">
                                {{ getLegalDays(type) }}
                            </span>
                            <div>
                                <div class="rule-title">{{ type.name }}</div>
                                <div class="rule-desc">
                                    推荐：{{ getRecommendedLabel(type) }}；法定：{{ getLegalLabel(type) }}。
                                </div>
                                <div class="rule-desc">{{ type.rule }}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div v-else class="card-surface section-card permission-card">
        <div class="permission-icon">!</div>
        <div class="permission-title">无权限访问</div>
        <div class="permission-desc">当前账号无权访问证照管理页面。</div>
    </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const currentRole = ref(localStorage.getItem('user_role') || '')
const currentUserId = ref(localStorage.getItem('user_id') || '')
const currentStationName = ref(localStorage.getItem('station_name') || '')

const loading = ref(false)
const saving = ref(false)
const pageError = ref('')
const actionMessage = ref('')
const actionMessageType = ref('info')
let actionMessageTimer = null
const certificateTypes = ref([])
const stations = ref([])
const certificateRows = ref([])

const filters = reactive({
    stationId: 'all',
    certificateType: 'all',
    status: 'all',
    keyword: ''
})

const certificateForm = reactive({
    id: null,
    station_id: '',
    certificate_type: '',
    start_date: '',
    expiry_date: '',
    remark: ''
})

const hasPermission = computed(() => ['supervisor', 'station_manager'].includes(currentRole.value))
const canEdit = computed(() => currentRole.value === 'supervisor')
const isEditing = computed(() => Boolean(certificateForm.id))

const pageTitle = computed(() => {
    return canEdit.value ? '站点证照有效期管理' : `${currentStationName.value || '本站'}证照有效期`
})

const pageDesc = computed(() => {
    if (canEdit.value) {
        return '督导组可维护任一站点实际拥有的证照有效期，并统一查看即将到期和已过期提醒。'
    }
    return '站点账号可查看本账号所属站点的证照有效期和到期提醒，证照有效期由督导组统一维护。'
})

const formTitle = computed(() => {
    return isEditing.value ? '编辑证照有效期' : '录入证照有效期'
})

const typeMap = computed(() => {
    return certificateTypes.value.reduce((result, item) => {
        result[item.code] = item
        return result
    }, {})
})

const selectedTypeNote = computed(() => {
    if (!certificateForm.certificate_type) return '到期时间必填，起始日期可按实际情况补充。'
    return getTypeMeta(certificateForm.certificate_type).rule
})

const getTypeMeta = (typeCode) => {
    return typeMap.value[typeCode] || {
        code: typeCode,
        name: typeCode || '-',
        note: '自定义证照类型',
        recommended_reminder_days: 30,
        legal_reminder_days: 7,
        recommended_label: '到期前 30天',
        legal_label: '到期前 7天',
        rule: '未配置专门提醒规则，默认30天进入推荐提醒，7天内进入法定提醒。'
    }
}

const getRecommendedDays = (rowOrTypeCode) => {
    if (typeof rowOrTypeCode === 'string') {
        return Number(getTypeMeta(rowOrTypeCode).recommended_reminder_days || 30)
    }
    return Number(rowOrTypeCode?.recommended_reminder_days ||
        getTypeMeta(rowOrTypeCode?.certificate_type).recommended_reminder_days ||
        30)
}

const getLegalDays = (rowOrTypeCode) => {
    if (typeof rowOrTypeCode === 'string') {
        return Number(getTypeMeta(rowOrTypeCode).legal_reminder_days || 7)
    }
    return Number(rowOrTypeCode?.legal_reminder_days ||
        getTypeMeta(rowOrTypeCode?.certificate_type).legal_reminder_days ||
        7)
}

const getRecommendedLabel = (rowOrTypeCode) => {
    const meta = typeof rowOrTypeCode === 'string'
        ? getTypeMeta(rowOrTypeCode)
        : getTypeMeta(rowOrTypeCode?.certificate_type)
    return rowOrTypeCode?.recommended_label || meta.recommended_label || `到期前 ${getRecommendedDays(rowOrTypeCode)}天`
}

const getLegalLabel = (rowOrTypeCode) => {
    const meta = typeof rowOrTypeCode === 'string'
        ? getTypeMeta(rowOrTypeCode)
        : getTypeMeta(rowOrTypeCode?.certificate_type)
    return rowOrTypeCode?.legal_label || meta.legal_label || `到期前 ${getLegalDays(rowOrTypeCode)}天`
}

const parseDate = (value) => {
    if (!value) return null
    const [year, month, day] = String(value).split('-').map((item) => Number(item))
    if (!year || !month || !day) return null
    return new Date(year, month - 1, day)
}

const getTodayStart = () => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

const getDaysUntil = (dateText) => {
    const target = parseDate(dateText)
    if (!target) return null
    const diff = target.getTime() - getTodayStart().getTime()
    return Math.ceil(diff / 86400000)
}

const getStatusMeta = (row) => {
    const daysLeft = getDaysUntil(row?.expiry_date)
    if (daysLeft === null) {
        return { label: '待补录', className: 'neutral', tone: 'missing', daysLeft: null }
    }

    if (daysLeft < 0) {
        return {
            label: '已过期',
            desc: `已过期 ${Math.abs(daysLeft)} 天`,
            className: 'danger',
            tone: 'expired',
            daysLeft
        }
    }

    if (daysLeft <= getLegalDays(row)) {
        return {
            label: '法定提醒期',
            desc: daysLeft === 0 ? '今天到期' : `${daysLeft} 天后到期，已进入法定提醒节点`,
            className: 'legal',
            tone: 'legal',
            daysLeft
        }
    }

    if (daysLeft <= getRecommendedDays(row)) {
        return {
            label: '推荐提醒期',
            desc: `${daysLeft} 天后到期，建议提前启动办理`,
            className: 'recommended',
            tone: 'recommended',
            daysLeft
        }
    }

    return { label: '正常', desc: `${daysLeft} 天后到期`, className: 'success', tone: 'normal', daysLeft }
}

const statusRank = (row) => {
    const tone = getStatusMeta(row).tone
    if (tone === 'expired') return 0
    if (tone === 'legal') return 1
    if (tone === 'recommended') return 2
    if (tone === 'missing') return 4
    return 3
}

const sortedCertificateRows = computed(() => {
    return [...certificateRows.value].sort((a, b) => {
        const rankDiff = statusRank(a) - statusRank(b)
        if (rankDiff !== 0) return rankDiff
        const dayA = getStatusMeta(a).daysLeft ?? 99999
        const dayB = getStatusMeta(b).daysLeft ?? 99999
        if (dayA !== dayB) return dayA - dayB
        return String(a.station_name || '').localeCompare(String(b.station_name || ''), 'zh-Hans-CN')
    })
})

const filteredCertificateRows = computed(() => {
    const keyword = filters.keyword.trim().toLowerCase()
    return sortedCertificateRows.value.filter((row) => {
        const statusTone = getStatusMeta(row).tone
        const matchedStation = filters.stationId === 'all' || String(row.station_id) === filters.stationId
        const matchedType = filters.certificateType === 'all' || row.certificate_type === filters.certificateType
        const matchedStatus = filters.status === 'all' ||
            (filters.status === 'recommended' && statusTone === 'recommended') ||
            (filters.status === 'legal' && statusTone === 'legal') ||
            (filters.status === 'expired' && statusTone === 'expired') ||
            (filters.status === 'normal' && statusTone === 'normal')
        const matchedKeyword = !keyword ||
            String(row.station_name || '').toLowerCase().includes(keyword) ||
            String(row.certificate_name || '').toLowerCase().includes(keyword) ||
            String(row.region || '').toLowerCase().includes(keyword)
        return matchedStation && matchedType && matchedStatus && matchedKeyword
    })
})

const reminderRows = computed(() => {
    return sortedCertificateRows.value.filter((row) => ['expired', 'legal', 'recommended'].includes(getStatusMeta(row).tone))
})

const urgentReminderRows = computed(() => reminderRows.value.slice(0, 8))
const expiredRows = computed(() => sortedCertificateRows.value.filter((row) => getStatusMeta(row).tone === 'expired'))
const legalRows = computed(() => sortedCertificateRows.value.filter((row) => getStatusMeta(row).tone === 'legal'))
const recommendedRows = computed(() => sortedCertificateRows.value.filter((row) => getStatusMeta(row).tone === 'recommended'))
const normalRows = computed(() => sortedCertificateRows.value.filter((row) => getStatusMeta(row).tone === 'normal'))

const statCards = computed(() => [
    {
        label: '正常',
        value: normalRows.value.length,
        desc: '未进入任何提醒节点',
        valueClass: ''
    },
    {
        label: '推荐提醒期',
        value: recommendedRows.value.length,
        desc: '建议提前启动换证办理',
        valueClass: recommendedRows.value.length ? 'recommended' : ''
    },
    {
        label: '法定提醒期',
        value: legalRows.value.length,
        desc: '已进入法规要求的办理节点',
        valueClass: legalRows.value.length ? 'legal' : ''
    },
    {
        label: '已过期',
        value: expiredRows.value.length,
        desc: '需优先跟进换证或状态核实',
        valueClass: expiredRows.value.length ? 'danger' : ''
    }
])

const certificateSummary = computed(() => {
    return certificateTypes.value.map((type) => {
        const rows = certificateRows.value.filter((row) => row.certificate_type === type.code)
        const expired = rows.filter((row) => getStatusMeta(row).tone === 'expired').length
        const legal = rows.filter((row) => getStatusMeta(row).tone === 'legal').length
        const recommended = rows.filter((row) => getStatusMeta(row).tone === 'recommended').length
        return {
            ...type,
            recorded: rows.length,
            expired,
            legal,
            recommended
        }
    })
})

const setActionMessage = (message, type = 'info') => {
    if (actionMessageTimer) {
        window.clearTimeout(actionMessageTimer)
        actionMessageTimer = null
    }

    actionMessageType.value = type
    actionMessage.value = message
    if (!message) return

    actionMessageTimer = window.setTimeout(() => {
        actionMessage.value = ''
        actionMessageTimer = null
    }, 2400)
}

const resetCertificateForm = () => {
    certificateForm.id = null
    certificateForm.station_id = stations.value[0]?.id || ''
    certificateForm.certificate_type = certificateTypes.value[0]?.code || ''
    certificateForm.start_date = ''
    certificateForm.expiry_date = ''
    certificateForm.remark = ''
}

const editCertificate = (row) => {
    certificateForm.id = row.id
    certificateForm.station_id = row.station_id
    certificateForm.certificate_type = row.certificate_type
    certificateForm.start_date = row.start_date || ''
    certificateForm.expiry_date = row.expiry_date || ''
    certificateForm.remark = row.remark || ''
    setActionMessage('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
}

const fetchCertificateData = async () => {
    if (!currentUserId.value) {
        pageError.value = '缺少当前用户信息，请重新登录。'
        return
    }

    try {
        loading.value = true
        pageError.value = ''
        const response = await axios.get('/api/station-certificates', {
            params: {
                user_id: currentUserId.value,
                _ts: Date.now()
            }
        })
        certificateTypes.value = response.data?.certificate_types || []
        stations.value = response.data?.stations || []
        certificateRows.value = response.data?.records || []

        if (canEdit.value && (!certificateForm.station_id || !certificateForm.certificate_type)) {
            resetCertificateForm()
        }
    } catch (error) {
        pageError.value = error?.response?.data?.error || '证照台账加载失败，请稍后重试。'
        setActionMessage(pageError.value, 'error')
    } finally {
        loading.value = false
    }
}

const saveCertificate = async () => {
    if (!canEdit.value) return

    if (!certificateForm.station_id || !certificateForm.certificate_type || !certificateForm.expiry_date) {
        pageError.value = '请完整填写站点、证照类型和到期时间。'
        setActionMessage(pageError.value, 'error')
        return
    }

    try {
        saving.value = true
        pageError.value = ''
        await axios.post('/api/station-certificates', {
            user_id: currentUserId.value,
            station_id: certificateForm.station_id,
            certificate_type: certificateForm.certificate_type,
            start_date: certificateForm.start_date || '',
            expiry_date: certificateForm.expiry_date,
            remark: certificateForm.remark || ''
        })
        setActionMessage('证照有效期已保存。', 'success')
        resetCertificateForm()
        await fetchCertificateData()
    } catch (error) {
        pageError.value = error?.response?.data?.error || '证照保存失败，请稍后重试。'
        setActionMessage(pageError.value, 'error')
    } finally {
        saving.value = false
    }
}

const deleteCertificate = async (row) => {
    if (!canEdit.value) return
    const confirmed = window.confirm(`确认删除“${row.station_name} · ${row.certificate_name}”这条证照记录吗？`)
    if (!confirmed) return

    try {
        pageError.value = ''
        await axios.delete(`/api/station-certificates/${row.id}`, {
            data: { user_id: currentUserId.value }
        })
        setActionMessage('证照记录已删除。', 'success')
        if (certificateForm.id === row.id) resetCertificateForm()
        await fetchCertificateData()
    } catch (error) {
        pageError.value = error?.response?.data?.error || '证照删除失败，请稍后重试。'
        setActionMessage(pageError.value, 'error')
    }
}

onMounted(() => {
    fetchCertificateData()
})

onBeforeUnmount(() => {
    if (actionMessageTimer) {
        window.clearTimeout(actionMessageTimer)
        actionMessageTimer = null
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
    font-weight: 700;
    margin-bottom: 12px;
}

.page-header h2,
.section-head h3,
.readonly-card h3,
.rule-card h3 {
    margin: 0;
    color: #0f172a;
}

.page-header h2 {
    font-size: 34px;
}

.page-desc,
.table-sub,
.summary-note,
.alert-desc,
.rule-desc,
.readonly-card p,
.form-tip {
    margin-top: 8px;
    font-size: 14px;
    line-height: 1.8;
    color: #64748b;
}

.header-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
}

.role-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 34px;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 800;
}

.role-chip.supervisor {
    color: #1d4ed8;
    background: #eff6ff;
}

.role-chip.station {
    color: #15803d;
    background: #ecfdf5;
}

.ghost-btn,
.primary-btn {
    border-radius: 10px;
    font-size: 13px;
    font-weight: 700;
    border: 1px solid #cbd5e1;
    cursor: pointer;
}

.ghost-btn {
    height: 38px;
    padding: 0 14px;
    background: #fff;
    color: #334155;
}

.primary-btn {
    height: 40px;
    padding: 0 16px;
    background: #2563eb;
    border-color: #2563eb;
    color: #fff;
}

.ghost-btn:disabled,
.primary-btn:disabled {
    opacity: 0.62;
    cursor: not-allowed;
}

.message-card {
    padding: 14px 16px;
    border-radius: 16px;
    font-size: 14px;
    font-weight: 700;
}

.error-card {
    color: #dc2626;
    background: #fef2f2;
    border: 1px solid #fecaca;
}

.success-card {
    color: #15803d;
    background: #ecfdf5;
    border: 1px solid #bbf7d0;
}

.submit-toast {
    position: fixed;
    left: 50%;
    top: 50%;
    z-index: 1600;
    width: min(calc(100vw - 32px), 420px);
    transform: translate(-50%, -50%);
    padding: 12px 14px;
    border: 1px solid #bfdbfe;
    border-radius: 14px;
    background: rgba(239, 246, 255, 0.98);
    color: #2563eb;
    box-shadow: 0 14px 28px rgba(15, 23, 42, 0.16);
    backdrop-filter: blur(8px);
    font-size: 14px;
    font-weight: 800;
    line-height: 1.7;
    text-align: center;
}

.submit-toast.success {
    color: #166534;
    background: rgba(236, 253, 245, 0.98);
    border-color: #bbf7d0;
}

.submit-toast.error {
    color: #b91c1c;
    background: rgba(254, 242, 242, 0.98);
    border-color: #fecaca;
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

.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 18px;
}

.stat-card,
.section-card {
    padding: 24px;
}

.stat-label {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 10px;
}

.stat-value {
    font-size: 34px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
}

.stat-value.small {
    font-size: 22px;
    line-height: 1.3;
}

.stat-value.warning {
    color: #c2410c;
}

.stat-value.recommended {
    color: #b45309;
}

.stat-value.legal {
    color: #c2410c;
}

.stat-value.danger {
    color: #dc2626;
}

.stat-desc {
    margin-top: 10px;
    font-size: 13px;
    line-height: 1.7;
    color: #64748b;
}

.content-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.55fr) minmax(330px, 1fr);
    gap: 20px;
}

.left-column,
.right-column {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.section-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 18px;
}

.section-head.compact {
    margin-bottom: 16px;
}

.inline-tags {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.tag,
.status-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 28px;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    white-space: nowrap;
}

.tag.neutral,
.status-chip.neutral {
    background: #f1f5f9;
    color: #475569;
}

.tag.warning,
.status-chip.warning {
    background: #fff7ed;
    color: #c2410c;
}

.tag.recommended,
.status-chip.recommended {
    background: #fffbeb;
    color: #b45309;
}

.tag.legal,
.status-chip.legal {
    background: #fff7ed;
    color: #c2410c;
}

.tag.danger,
.status-chip.danger {
    background: #fef2f2;
    color: #dc2626;
}

.status-chip.success {
    background: #ecfdf5;
    color: #15803d;
}

.filter-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin-bottom: 18px;
}

.filter-field,
.form-field {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.filter-field label,
.form-field label {
    font-size: 13px;
    font-weight: 700;
    color: #64748b;
}

.filter-field select,
.filter-field input,
.form-field select,
.form-field input,
.form-field textarea {
    width: 100%;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    background: #fff;
    color: #0f172a;
    font-size: 14px;
}

.filter-field select,
.filter-field input,
.form-field select,
.form-field input {
    height: 38px;
    padding: 0 12px;
}

.form-field textarea {
    padding: 10px 12px;
    resize: vertical;
}

.form-field select:disabled {
    color: #64748b;
    background: #f8fafc;
    cursor: not-allowed;
}

.table-wrap {
    overflow-x: auto;
}

.cert-table {
    width: 100%;
    border-collapse: collapse;
}

.ledger-table {
    min-width: 980px;
}

.cert-table th,
.cert-table td {
    padding: 14px 12px;
    border-bottom: 1px solid #e2e8f0;
    text-align: left;
    vertical-align: middle;
    font-size: 14px;
    color: #0f172a;
}

.cert-table th {
    font-size: 13px;
    color: #64748b;
    font-weight: 700;
    white-space: nowrap;
}

.table-title,
.summary-title,
.alert-title,
.rule-title {
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
}

.expire-date {
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
}

.empty-cell {
    text-align: center;
    color: #64748b;
    padding: 28px 12px;
}

.row-actions,
.form-actions {
    display: flex;
    align-items: center;
    gap: 8px;
}

.mini-btn {
    min-width: 70px;
    height: 34px;
    padding: 0 10px;
}

.danger-btn {
    color: #dc2626;
    border-color: #fecaca;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}

.summary-card {
    padding: 16px;
    border-radius: 18px;
    border: 1px solid #dbe4ee;
    background: #f8fafc;
}

.summary-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 12px;
    color: #64748b;
    font-size: 12px;
    font-weight: 700;
}

.summary-meta .warning {
    color: #c2410c;
}

.summary-meta .recommended {
    color: #b45309;
}

.summary-meta .legal {
    color: #c2410c;
}

.summary-meta .danger {
    color: #dc2626;
}

.summary-rule {
    margin-top: 10px;
    color: #64748b;
    font-size: 13px;
    line-height: 1.7;
}

.certificate-form {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.form-actions {
    justify-content: flex-end;
    padding-top: 4px;
}

.entry-card {
    border-color: #bfdbfe;
    background:
        linear-gradient(135deg, rgba(239, 246, 255, 0.92) 0%, rgba(255, 255, 255, 0.98) 62%, rgba(255, 251, 235, 0.8) 100%);
}

.readonly-card {
    background: linear-gradient(135deg, #ecfdf5 0%, #f8fafc 100%);
}

.alert-list,
.rule-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.alert-item,
.rule-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 14px 16px;
    border-radius: 16px;
    border: 1px solid #dbe4ee;
    background: #f8fafc;
}

.alert-item.expired {
    border-color: #fecaca;
    background: #fff7f7;
}

.alert-item.warning {
    border-color: #fed7aa;
    background: #fffaf2;
}

.alert-item.legal {
    border-color: #fed7aa;
    background: #fffaf2;
}

.alert-item.recommended {
    border-color: #fde68a;
    background: #fffdf4;
}

.alert-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    margin-top: 8px;
    flex-shrink: 0;
    background: #f59e0b;
}

.alert-item.expired .alert-dot {
    background: #ef4444;
}

.alert-item.legal .alert-dot {
    background: #f97316;
}

.alert-item.recommended .alert-dot {
    background: #f59e0b;
}

.empty-alert {
    padding: 16px;
    border-radius: 16px;
    background: #f8fafc;
    border: 1px dashed #cbd5e1;
    color: #64748b;
    font-size: 14px;
    line-height: 1.8;
}

.rule-card {
    background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
}

.rule-mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 14px;
    flex-shrink: 0;
    font-size: 15px;
    font-weight: 800;
}

.rule-mark.danger {
    color: #dc2626;
    background: #fef2f2;
}

.rule-mark.warning {
    color: #c2410c;
    background: #fff7ed;
}

.rule-mini {
    font-size: 13px;
    font-weight: 800;
    color: #0f172a;
    white-space: nowrap;
}

.status-cell {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
}

.mobile-cert-list {
    display: none;
}

.mobile-cert-cards {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.mobile-cert-card {
    padding: 16px;
    border-radius: 18px;
}

.mobile-card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding-bottom: 14px;
    border-bottom: 1px solid #e2e8f0;
}

.mobile-card-category {
    display: inline-flex;
    align-items: center;
    min-height: 28px;
    padding: 4px 10px;
    border-radius: 999px;
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 12px;
    font-weight: 800;
}

.mobile-card-code {
    margin-top: 8px;
    color: #0f172a;
    font-size: 17px;
    font-weight: 800;
    line-height: 1.35;
}

.mobile-card-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-top: 14px;
}

.mobile-card-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
    padding: 10px 0;
    border-bottom: 1px solid #e2e8f0;
}

.mobile-card-row:last-child {
    border-bottom: none;
}

.mobile-card-row span {
    flex: 0 0 82px;
    color: #64748b;
    font-size: 13px;
    line-height: 1.6;
}

.mobile-card-row strong {
    flex: 1;
    color: #0f172a;
    font-size: 14px;
    line-height: 1.6;
    text-align: right;
}

.mobile-card-row-top {
    flex-direction: column;
    gap: 6px;
}

.mobile-card-text {
    width: 100%;
    padding: 10px 12px;
    border-radius: 14px;
    background: #f8fafc;
    color: #334155;
    font-size: 14px;
    line-height: 1.7;
}

.mobile-card-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin-top: 14px;
}

.mobile-card-actions .ghost-btn {
    width: 100%;
    min-height: 40px;
}

.mobile-empty {
    padding: 18px;
    color: #64748b;
    font-size: 14px;
    line-height: 1.8;
    text-align: center;
}

.permission-card {
    min-height: 280px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
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
    font-weight: 800;
    margin-bottom: 14px;
}

.permission-title {
    font-size: 22px;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 8px;
}

.permission-desc {
    font-size: 14px;
    line-height: 1.8;
    color: #64748b;
}

@media (max-width: 1200px) {

    .stats-grid,
    .filter-grid,
    .content-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .content-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 768px) {

    .page-header,
    .stat-card,
    .section-card {
        padding: 20px;
    }

    .page-shell.edit-mode .content-grid {
        order: 1;
    }

    .page-shell.edit-mode .stats-grid {
        order: 2;
    }

    .page-header {
        flex-direction: column;
    }

    .page-header h2 {
        font-size: 28px;
    }

    .header-actions,
    .section-head,
    .row-actions,
    .form-actions {
        flex-direction: column;
        align-items: stretch;
    }

    .stats-grid,
    .filter-grid,
    .summary-grid {
        grid-template-columns: 1fr;
    }

    .stats-grid {
        gap: 12px;
    }

    .table-wrap {
        display: none;
    }

    .mobile-cert-list {
        display: block;
    }

    .mobile-cert-card {
        box-shadow: 0 12px 26px rgba(15, 23, 42, 0.07);
    }

    .mobile-card-head {
        flex-direction: column;
        align-items: stretch;
    }

    .mobile-card-head .status-chip {
        align-self: flex-start;
    }

    .content-grid.edit-first .right-column {
        order: -1;
    }

    .entry-card {
        padding: 18px;
        border-radius: 24px;
        box-shadow: 0 18px 42px rgba(37, 99, 235, 0.12);
    }

    .entry-card .section-head {
        margin-bottom: 12px;
    }

    .certificate-form {
        gap: 12px;
    }

    .form-field select,
    .form-field input {
        height: 46px;
        border-radius: 14px;
        font-size: 15px;
    }

    .form-field textarea {
        min-height: 88px;
        border-radius: 14px;
        font-size: 15px;
    }

    .form-actions {
        position: static;
        padding: 0;
        border: none;
        background: transparent;
        backdrop-filter: none;
        gap: 10px;
    }

    .form-actions .ghost-btn,
    .form-actions .primary-btn {
        width: 100%;
        height: 44px;
    }

    .submit-toast {
        width: min(calc(100vw - 24px), 420px);
        font-size: 13px;
    }
}
</style>
