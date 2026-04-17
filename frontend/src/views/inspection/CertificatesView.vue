<template>
    <div class="page-shell">
        <div class="page-header card-surface">
            <div>
                <div class="page-kicker">证照管理</div>
                <h2>站点证照有效期管理样板页面</h2>
                <p class="page-desc">
                    用于统一管理各站点证照有效期限，支持按证件类型查看本月到期、30 天内到期、已过期等情况，并预留批量录入与提醒功能入口。
                </p>
            </div>
            <div class="header-actions">
                <button class="ghost-btn" type="button">导出证照台账</button>
                <button class="primary-btn" type="button">批量录入证照</button>
            </div>
        </div>

        <div class="page-content">
            <div class="stats-grid">
                <div v-for="card in statCards" :key="card.label" class="card-surface stat-card">
                    <div class="stat-label">{{ card.label }}</div>
                    <div class="stat-value">{{ card.value }}</div>
                    <div class="stat-desc" :class="card.descClass">{{ card.desc }}</div>
                </div>
            </div>

            <div class="content-grid">
                <div class="left-column">
                    <div class="card-surface section-card">
                        <div class="section-head">
                            <div>
                                <div class="section-kicker">证件总览</div>
                                <h3>各类证照到期情况示例</h3>
                            </div>
                            <div class="inline-tags">
                                <span class="tag info">样板数据</span>
                                <span class="tag neutral">可扩展筛选</span>
                            </div>
                        </div>

                        <div class="table-wrap">
                            <table class="cert-table">
                                <thead>
                                    <tr>
                                        <th>证件名称</th>
                                        <th>应管理站点数</th>
                                        <th>已录入</th>
                                        <th>30天内到期</th>
                                        <th>已过期</th>
                                        <th>管理状态</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="item in certificateSummary" :key="item.name">
                                        <td>
                                            <div class="table-title">{{ item.name }}</div>
                                            <div class="table-sub">{{ item.note }}</div>
                                        </td>
                                        <td>{{ item.total }}</td>
                                        <td>{{ item.recorded }}</td>
                                        <td>
                                            <span class="status-chip warning">{{ item.expiringSoon }}</span>
                                        </td>
                                        <td>
                                            <span class="status-chip danger">{{ item.expired }}</span>
                                        </td>
                                        <td>
                                            <span :class="['status-chip', item.statusClass]">{{ item.status }}</span>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div class="card-surface section-card">
                        <div class="section-head">
                            <div>
                                <div class="section-kicker">站点台账</div>
                                <h3>站点证照清单示例</h3>
                            </div>
                            <button class="ghost-btn" type="button">查看全部站点</button>
                        </div>

                        <div class="ledger-list">
                            <div v-for="station in stationLedger" :key="station.name" class="ledger-card">
                                <div class="ledger-top">
                                    <div>
                                        <div class="ledger-title">{{ station.name }}</div>
                                        <div class="ledger-meta">{{ station.area }} · {{ station.ownerType }}</div>
                                    </div>
                                    <span :class="['tag', station.riskClass]">{{ station.riskText }}</span>
                                </div>

                                <div class="ledger-items">
                                    <div v-for="doc in station.documents" :key="doc.name" class="ledger-item">
                                        <div class="ledger-doc-main">
                                            <div class="ledger-doc-name">{{ doc.name }}</div>
                                            <div class="ledger-doc-date">有效期至：{{ doc.expireDate }}</div>
                                        </div>
                                        <span :class="['status-chip', doc.statusClass]">{{ doc.status }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="right-column">
                    <div class="card-surface section-card">
                        <div class="section-head compact">
                            <div>
                                <div class="section-kicker">到期提醒</div>
                                <h3>重点提醒示例</h3>
                            </div>
                        </div>

                        <div class="alert-list">
                            <div v-for="alert in alerts" :key="alert.title" class="alert-item">
                                <div class="alert-dot" :class="alert.dotClass"></div>
                                <div class="alert-content">
                                    <div class="alert-title">{{ alert.title }}</div>
                                    <div class="alert-desc">{{ alert.desc }}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="card-surface section-card">
                        <div class="section-head compact">
                            <div>
                                <div class="section-kicker">快捷入口</div>
                                <h3>常用操作</h3>
                            </div>
                        </div>

                        <div class="quick-grid">
                            <button v-for="entry in quickEntries" :key="entry.title" class="quick-entry" type="button">
                                <div class="quick-icon">{{ entry.icon }}</div>
                                <div class="quick-title">{{ entry.title }}</div>
                                <div class="quick-desc">{{ entry.desc }}</div>
                            </button>
                        </div>
                    </div>

                    <div class="card-surface section-card highlight-card">
                        <div class="section-kicker highlight-kicker">页面定位</div>
                        <h3>证照有效期管理样板</h3>
                        <p>
                            本页面主要用于统一管理各站点证照有效期限，后续可继续扩展接入站点维度台账、批量录入、到期预警、消息提醒、按证件类型筛选及导出等功能。
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
const statCards = [
    { label: '管理站点数', value: '43', desc: '纳入证照台账统一管理', descClass: '' },
    { label: '证件种类数', value: '7', desc: '营业执照、零售许可、危化证等', descClass: '' },
    { label: '30天内到期', value: '12', desc: '建议尽快跟进换证', descClass: 'warning-text' },
    { label: '已过期证件', value: '3', desc: '需立即处置并重点提醒', descClass: 'danger-text' }
]

const certificateSummary = [
    {
        name: '工商营业执照',
        note: '站点主体基础证照',
        total: 43,
        recorded: 43,
        expiringSoon: 2,
        expired: 0,
        status: '正常',
        statusClass: 'success'
    },
    {
        name: '成品油零售经营许可证',
        note: '加油站核心经营许可',
        total: 43,
        recorded: 43,
        expiringSoon: 4,
        expired: 1,
        status: '重点关注',
        statusClass: 'warning'
    },
    {
        name: '危险化学品经营许可证',
        note: '危化经营相关许可',
        total: 43,
        recorded: 42,
        expiringSoon: 3,
        expired: 1,
        status: '重点关注',
        statusClass: 'warning'
    },
    {
        name: '排污许可证',
        note: '环保相关证照',
        total: 43,
        recorded: 39,
        expiringSoon: 1,
        expired: 0,
        status: '部分缺失',
        statusClass: 'neutral'
    },
    {
        name: '防雷检测报告',
        note: '年度检测材料',
        total: 43,
        recorded: 41,
        expiringSoon: 2,
        expired: 1,
        status: '需补录',
        statusClass: 'neutral'
    },
    {
        name: '税务登记证',
        note: '历史台账类证照',
        total: 43,
        recorded: 35,
        expiringSoon: 0,
        expired: 0,
        status: '待梳理',
        statusClass: 'neutral'
    },
    {
        name: '烟草专卖许可证',
        note: '便利店涉烟业务证件',
        total: 18,
        recorded: 16,
        expiringSoon: 0,
        expired: 0,
        status: '正常',
        statusClass: 'success'
    }
]

const stationLedger = [
    {
        name: '华辉加油站',
        area: '城区片区',
        ownerType: '自有站',
        riskText: '30天内到期',
        riskClass: 'warning',
        documents: [
            { name: '成品油零售经营许可证', expireDate: '2026-05-12', status: '即将到期', statusClass: 'warning' },
            { name: '危险化学品经营许可证', expireDate: '2026-08-30', status: '正常', statusClass: 'success' },
            { name: '防雷检测报告', expireDate: '2026-04-25', status: '即将到期', statusClass: 'warning' }
        ]
    },
    {
        name: '龙吴路加油站',
        area: '城区片区',
        ownerType: '自有站',
        riskText: '存在过期',
        riskClass: 'danger',
        documents: [
            { name: '成品油零售经营许可证', expireDate: '2025-12-30', status: '已过期', statusClass: 'danger' },
            { name: '排污许可证', expireDate: '2026-09-18', status: '正常', statusClass: 'success' },
            { name: '工商营业执照', expireDate: '2027-02-20', status: '正常', statusClass: 'success' }
        ]
    },
    {
        name: '锦秋加油站',
        area: '北区片区',
        ownerType: '控股站',
        riskText: '台账待补录',
        riskClass: 'neutral',
        documents: [
            { name: '危险化学品经营许可证', expireDate: '未录入', status: '待补录', statusClass: 'neutral' },
            { name: '防雷检测报告', expireDate: '2026-10-15', status: '正常', statusClass: 'success' },
            { name: '烟草专卖许可证', expireDate: '2026-12-08', status: '正常', statusClass: 'success' }
        ]
    }
]

const alerts = [
    {
        title: '龙吴路加油站成品油零售经营许可证已过期',
        desc: '建议立即核实证件状态，并纳入重点跟踪。',
        dotClass: 'danger'
    },
    {
        title: '华辉加油站防雷检测报告 30 天内到期',
        desc: '建议提前安排检测并更新台账。',
        dotClass: 'warning'
    },
    {
        title: '锦秋加油站危险化学品经营许可证尚未录入',
        desc: '建议尽快补录证照有效期信息。',
        dotClass: 'info'
    }
]

const quickEntries = [
    { icon: '录', title: '批量录入', desc: '导入各站点证照有效期台账' },
    { icon: '筛', title: '到期筛选', desc: '按 30 天内到期 / 已过期查看' },
    { icon: '提', title: '提醒管理', desc: '查看即将到期站点提醒' },
    { icon: '档', title: '台账导出', desc: '导出证照有效期管理清单' }
]
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
.highlight-card h3 {
    margin: 0;
    color: #0f172a;
}

.page-header h2 {
    font-size: 34px;
}

.page-desc,
.table-sub,
.alert-desc,
.quick-desc,
.highlight-card p,
.ledger-meta,
.ledger-doc-date {
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

.ghost-btn,
.primary-btn,
.quick-entry {
    border-radius: 10px;
    font-size: 13px;
    font-weight: 700;
}

.ghost-btn,
.primary-btn {
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

.page-content {
    display: flex;
    flex-direction: column;
    gap: 20px;
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

.stat-desc {
    margin-top: 10px;
    font-size: 13px;
    line-height: 1.7;
    color: #64748b;
}

.warning-text {
    color: #c2410c;
}

.danger-text {
    color: #dc2626;
}

.content-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.55fr) minmax(320px, 1fr);
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

.table-wrap {
    overflow-x: auto;
}

.cert-table {
    width: 100%;
    border-collapse: collapse;
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
}

.table-title,
.ledger-title,
.alert-title,
.quick-title {
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
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
}

.tag.info {
    background: #eff6ff;
    color: #1d4ed8;
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

.tag.success,
.status-chip.success {
    background: #ecfdf5;
    color: #15803d;
}

.status-chip.danger {
    background: #fef2f2;
    color: #dc2626;
}

.ledger-list,
.alert-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.ledger-card,
.alert-item {
    padding: 16px;
    border-radius: 18px;
    background: #f8fafc;
    border: 1px solid #dbe4ee;
}

.ledger-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 14px;
}

.ledger-items {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.ledger-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 0;
    border-bottom: 1px solid #e2e8f0;
}

.ledger-item:last-child {
    border-bottom: none;
    padding-bottom: 0;
}

.ledger-doc-name {
    font-size: 14px;
    font-weight: 700;
    color: #0f172a;
}

.alert-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
}

.alert-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    margin-top: 8px;
    flex-shrink: 0;
}

.alert-dot.info {
    background: #3b82f6;
}

.alert-dot.warning {
    background: #f59e0b;
}

.alert-dot.danger {
    background: #ef4444;
}

.quick-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}

.quick-entry {
    padding: 18px 16px;
    border: 1px solid #dbe4ee;
    background: #f8fafc;
    text-align: left;
    cursor: pointer;
}

.quick-icon {
    width: 42px;
    height: 42px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #eff6ff;
    color: #2563eb;
    font-size: 18px;
    font-weight: 800;
    margin-bottom: 12px;
}

.highlight-card {
    background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
}

.highlight-kicker {
    background: #dbeafe;
}

@media (max-width: 1200px) {
    .stats-grid {
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

    .stats-grid,
    .quick-grid {
        grid-template-columns: 1fr;
    }

    .section-head,
    .header-actions,
    .ledger-top,
    .ledger-item {
        flex-direction: column;
        align-items: stretch;
    }
}
</style>