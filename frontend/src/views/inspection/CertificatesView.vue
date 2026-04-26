<template>
    <div v-if="hasPermission" class="page-shell">
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
        <div v-if="actionMessage" class="message-card success-card">{{ actionMessage }}</div>

        <div class="stats-grid">
            <div v-for="card in statCards" :key="card.label" class="card-surface stat-card">
                <div class="stat-label">{{ card.label }}</div>
                <div :class="['stat-value', card.valueClass]">{{ card.value }}</div>
                <div class="stat-desc">{{ card.desc }}</div>
            </div>
        </div>

        <div class="content-grid">
            <div class="left-column">
                <div class="card-surface section-card">
                    <div class="section-head">
                        <div>
                            <div class="section-kicker">证照台账</div>
                            <h3>{{ canEdit ? '全部站点证照有效期' : '本站证照有效期' }}</h3>
                        </div>
                        <div class="inline-tags">
                            <span class="tag neutral">共 {{ filteredCertificateRows.length }} 条</span>
                            <span v-if="reminderRows.length" class="tag warning">提醒 {{ reminderRows.length }}</span>
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
                                <option value="attention">提醒中</option>
                                <option value="expired">已过期</option>
                                <option value="expiring">即将到期</option>
                                <option value="normal">正常</option>
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
                                            <span class="status-chip neutral">提前 {{ getReminderDays(row) }} 天</span>
                                        </td>
                                        <td>
                                            <span :class="['status-chip', getStatusMeta(row).className]">
                                                {{ getStatusMeta(row).label }}
                                            </span>
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
                                <span :class="{ danger: item.expired > 0 }">过期 {{ item.expired }}</span>
                                <span :class="{ warning: item.expiring > 0 }">提醒 {{ item.expiring }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="right-column">
                <div v-if="canEdit" class="card-surface section-card">
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
                        当前没有进入提醒期或已过期的证照。
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
                                    有效期至 {{ row.expiry_date }}，{{ getStatusMeta(row).label }}。
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="card-surface section-card rule-card">
                    <div class="section-kicker">提醒规则</div>
                    <h3>到期前自动进入提醒</h3>
                    <div class="rule-list">
                        <div class="rule-item">
                            <span class="rule-mark danger">90</span>
                            <div>
                                <div class="rule-title">危险化学品经营许可证</div>
                                <div class="rule-desc">提前三个月进入提醒期，便于预留换证办理时间。</div>
                            </div>
                        </div>
                        <div class="rule-item">
                            <span class="rule-mark warning">30</span>
                            <div>
                                <div class="rule-title">其他证照</div>
                                <div class="rule-desc">默认提前 30 天提醒，已过期证照会置顶展示。</div>
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
import { computed, onMounted, reactive, ref } from 'vue'

const DEFAULT_CERTIFICATE_TYPES = [
    { code: 'business_license', name: '工商营业执照', note: '站点主体基础证照', reminder_days: 30 },
    { code: 'oil_retail_permit', name: '成品油零售经营许可证', note: '加油站核心经营许可', reminder_days: 30 },
    { code: 'dangerous_chemicals_permit', name: '危险化学品经营许可证', note: '危化经营相关许可，提前三个月提醒', reminder_days: 90 },
    { code: 'pollutant_discharge_permit', name: '排污许可证', note: '环保相关证照', reminder_days: 30 },
    { code: 'lightning_protection_report', name: '防雷检测报告', note: '检测报告类材料', reminder_days: 30 },
    { code: 'tax_registration_certificate', name: '税务登记证', note: '历史台账类证照', reminder_days: 30 },
    { code: 'tobacco_monopoly_permit', name: '烟草专卖许可证', note: '便利店涉烟业务证件', reminder_days: 30 }
]

const currentRole = ref(localStorage.getItem('user_role') || '')
const currentUserId = ref(localStorage.getItem('user_id') || '')
const currentStationName = ref(localStorage.getItem('station_name') || '')

const loading = ref(false)
const saving = ref(false)
const pageError = ref('')
const actionMessage = ref('')
const certificateTypes = ref(DEFAULT_CERTIFICATE_TYPES)
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
    return getTypeMeta(certificateForm.certificate_type).note
})

const getTypeMeta = (typeCode) => {
    return typeMap.value[typeCode] || {
        code: typeCode,
        name: typeCode || '-',
        note: '自定义证照类型',
        reminder_days: 30
    }
}

const getReminderDays = (rowOrTypeCode) => {
    if (typeof rowOrTypeCode === 'string') {
        return Number(getTypeMeta(rowOrTypeCode).reminder_days || 30)
    }
    return Number(rowOrTypeCode?.reminder_days || getTypeMeta(rowOrTypeCode?.certificate_type).reminder_days || 30)
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
            label: `已过期 ${Math.abs(daysLeft)} 天`,
            className: 'danger',
            tone: 'expired',
            daysLeft
        }
    }

    if (daysLeft <= getReminderDays(row)) {
        return {
            label: daysLeft === 0 ? '今天到期' : `${daysLeft} 天后到期`,
            className: 'warning',
            tone: 'warning',
            daysLeft
        }
    }

    return { label: '正常', className: 'success', tone: 'normal', daysLeft }
}

const statusRank = (row) => {
    const tone = getStatusMeta(row).tone
    if (tone === 'expired') return 0
    if (tone === 'warning') return 1
    if (tone === 'missing') return 2
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
            (filters.status === 'attention' && ['expired', 'warning'].includes(statusTone)) ||
            (filters.status === 'expired' && statusTone === 'expired') ||
            (filters.status === 'expiring' && statusTone === 'warning') ||
            (filters.status === 'normal' && statusTone === 'normal')
        const matchedKeyword = !keyword ||
            String(row.station_name || '').toLowerCase().includes(keyword) ||
            String(row.certificate_name || '').toLowerCase().includes(keyword) ||
            String(row.region || '').toLowerCase().includes(keyword)
        return matchedStation && matchedType && matchedStatus && matchedKeyword
    })
})

const reminderRows = computed(() => {
    return sortedCertificateRows.value.filter((row) => ['expired', 'warning'].includes(getStatusMeta(row).tone))
})

const urgentReminderRows = computed(() => reminderRows.value.slice(0, 8))
const expiredRows = computed(() => sortedCertificateRows.value.filter((row) => getStatusMeta(row).tone === 'expired'))

const statCards = computed(() => [
    {
        label: canEdit.value ? '管理站点数' : '当前站点',
        value: canEdit.value ? stations.value.length : (currentStationName.value || '本站'),
        desc: canEdit.value ? '可维护证照台账的站点数量' : '本账号仅展示所属站点证照',
        valueClass: canEdit.value ? '' : 'small'
    },
    {
        label: '已录入证照',
        value: certificateRows.value.length,
        desc: '仅统计实际已录入的证照记录',
        valueClass: ''
    },
    {
        label: '提醒中',
        value: reminderRows.value.length,
        desc: '包含即将到期和已过期证照',
        valueClass: reminderRows.value.length ? 'warning' : ''
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
        const expiring = rows.filter((row) => getStatusMeta(row).tone === 'warning').length
        return {
            ...type,
            recorded: rows.length,
            expired,
            expiring
        }
    })
})

const setActionMessage = (message) => {
    actionMessage.value = message
    if (!message) return
    window.setTimeout(() => {
        actionMessage.value = ''
    }, 2600)
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
        certificateTypes.value = response.data?.certificate_types?.length
            ? response.data.certificate_types
            : DEFAULT_CERTIFICATE_TYPES
        stations.value = response.data?.stations || []
        certificateRows.value = response.data?.records || []

        if (canEdit.value && (!certificateForm.station_id || !certificateForm.certificate_type)) {
            resetCertificateForm()
        }
    } catch (error) {
        pageError.value = error?.response?.data?.error || '证照台账加载失败，请稍后重试。'
    } finally {
        loading.value = false
    }
}

const saveCertificate = async () => {
    if (!canEdit.value) return

    if (!certificateForm.station_id || !certificateForm.certificate_type || !certificateForm.expiry_date) {
        pageError.value = '请完整填写站点、证照类型和到期时间。'
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
        setActionMessage('证照有效期已保存。')
        resetCertificateForm()
        await fetchCertificateData()
    } catch (error) {
        pageError.value = error?.response?.data?.error || '证照保存失败，请稍后重试。'
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
        setActionMessage('证照记录已删除。')
        if (certificateForm.id === row.id) resetCertificateForm()
        await fetchCertificateData()
    } catch (error) {
        pageError.value = error?.response?.data?.error || '证照删除失败，请稍后重试。'
    }
}

onMounted(() => {
    fetchCertificateData()
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

.summary-meta .danger {
    color: #dc2626;
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
}
</style>
