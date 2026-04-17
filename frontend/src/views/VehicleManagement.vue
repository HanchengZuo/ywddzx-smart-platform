<template>
    <div class="page-shell">
        <div class="page-header card-surface">
            <div>
                <div class="page-kicker">车辆管理系统</div>
                <h2>公务车辆管理样板页面</h2>
                <p class="page-desc">
                    用于统一管理借车申请、审批流转、车辆使用记录、归还确认及申请单模板导出。当前页面仅为前端样板展示，未接入真实审批与导出功能。
                </p>
            </div>
            <div class="header-actions">
                <button class="ghost-btn" type="button">导出借车审批单模板</button>
                <button class="primary-btn" type="button">发起借车申请</button>
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
                                <div class="section-kicker">车辆总览</div>
                                <h3>公务车辆状态示例</h3>
                            </div>
                            <button class="ghost-btn" type="button">查看全部车辆</button>
                        </div>

                        <div class="vehicle-list">
                            <div v-for="car in vehicles" :key="car.plate" class="vehicle-card">
                                <div class="vehicle-top">
                                    <div>
                                        <div class="vehicle-plate">{{ car.plate }}</div>
                                        <div class="vehicle-meta">{{ car.model }} · {{ car.owner }}</div>
                                    </div>
                                    <span :class="['status-chip', car.statusClass]">{{ car.status }}</span>
                                </div>

                                <div class="vehicle-info-grid">
                                    <div class="info-item">
                                        <span class="info-label">当前位置</span>
                                        <span class="info-value">{{ car.location }}</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">当前使用人</span>
                                        <span class="info-value">{{ car.user }}</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">下次保养</span>
                                        <span class="info-value">{{ car.maintenance }}</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">年检状态</span>
                                        <span class="info-value">{{ car.inspection }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="card-surface section-card">
                        <div class="section-head">
                            <div>
                                <div class="section-kicker">借车申请</div>
                                <h3>当前申请流转示例</h3>
                            </div>
                            <div class="inline-tags">
                                <span class="tag info">样板流程</span>
                                <span class="tag neutral">借车 → 主任审批 → 车辆管理员确认 → 出车</span>
                            </div>
                        </div>

                        <div class="application-list">
                            <div v-for="item in applications" :key="item.code" class="application-card">
                                <div class="application-top">
                                    <div>
                                        <div class="application-title">{{ item.code }}</div>
                                        <div class="application-meta">{{ item.department }} · {{ item.user }}</div>
                                    </div>
                                    <span :class="['status-chip', item.statusClass]">{{ item.status }}</span>
                                </div>

                                <div class="application-grid">
                                    <div class="info-item">
                                        <span class="info-label">用车事由</span>
                                        <span class="info-value">{{ item.reason }}</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">用车日期</span>
                                        <span class="info-value">{{ item.useDate }}</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">出车地点</span>
                                        <span class="info-value">{{ item.start }}</span>
                                    </div>
                                    <div class="info-item">
                                        <span class="info-label">到达地点</span>
                                        <span class="info-value">{{ item.end }}</span>
                                    </div>
                                </div>

                                <div class="flow-line">
                                    <div v-for="(step, index) in item.flow" :key="step.name" class="flow-step">
                                        <div :class="['flow-dot', step.done ? 'done' : 'pending']">{{ index + 1 }}</div>
                                        <div class="flow-content">
                                            <div class="flow-name">{{ step.name }}</div>
                                            <div class="flow-desc">{{ step.desc }}</div>
                                        </div>
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
                                <div class="section-kicker">审批提醒</div>
                                <h3>待处理事项</h3>
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
                        <h3>车辆管理系统样板</h3>
                        <p>
                            本页面主要服务于公务车辆借用与审批管理，后续可继续扩展接入电子审批、车辆调度、归还确认、停车费登记、出车台账、模板导出与流程留痕等功能。
                        </p>
                    </div>
                    <div class="card-surface section-card compact-template-card">
                        <div class="section-head compact">
                            <div>
                                <div class="section-kicker">申请单模板</div>
                                <h3>公务车辆使用申请单字段示例</h3>
                            </div>
                            <button class="ghost-btn" type="button">预览模板</button>
                        </div>

                        <div class="template-grid compact-template-grid">
                            <div v-for="field in formFields" :key="field" class="template-field compact-template-field">
                                {{ field }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="card-surface section-card full-width-form-preview">
            <div class="section-head compact">
                <div>
                    <div class="section-kicker">模板示例</div>
                    <h3>公务车辆使用申请单预览</h3>
                </div>
                <button class="ghost-btn" type="button">打印预览</button>
            </div>

            <div class="paper-preview">
                <div class="paper-attachment">附件 2：</div>
                <div class="paper-title">公务车辆使用申请单</div>

                <table class="paper-form-table">
                    <tr>
                        <td class="label-cell">用车部门</td>
                        <td class="value-cell">业务督导中心</td>
                        <td class="label-cell">车牌号</td>
                        <td class="value-cell">沪A·12345</td>
                        <td class="label-cell">使用人</td>
                        <td class="value-cell">左翰承</td>
                    </tr>
                    <tr>
                        <td class="label-cell">用车事由</td>
                        <td colspan="5" class="textarea-cell">赴站点开展现场巡检及问题复查工作。</td>
                    </tr>
                    <tr>
                        <td class="label-cell">用车日期</td>
                        <td colspan="2" class="value-cell">2026-04-20</td>
                        <td class="label-cell">归还日期</td>
                        <td colspan="2" class="value-cell">2026-04-20</td>
                    </tr>
                    <tr>
                        <td class="label-cell">出车地点</td>
                        <td colspan="2" class="value-cell">分公司本部</td>
                        <td class="label-cell">到达地点</td>
                        <td colspan="2" class="value-cell">华辉加油站、龙吴路加油站</td>
                    </tr>
                    <tr>
                        <td class="label-cell tall-cell">用车部门<br />负责人签字</td>
                        <td colspan="2" class="signature-cell">张三</td>
                        <td class="label-cell tall-cell">办公室车辆<br />负责人签字</td>
                        <td colspan="2" class="signature-cell">李四</td>
                    </tr>
                    <tr>
                        <td class="label-cell tall-cell">路桥停车费<br />金额</td>
                        <td colspan="2" class="value-cell">0 元</td>
                        <td class="label-cell">审核人签字</td>
                        <td colspan="2" class="signature-cell">王主任</td>
                    </tr>
                    <tr>
                        <td class="label-cell">备注</td>
                        <td colspan="5" class="textarea-cell">本示例为系统自动生成的借车审批单预览效果。</td>
                    </tr>
                </table>

                <div class="paper-note">
                    说明：用车人归还车辆时，如发生路桥停车费，应填写发生金额并同时将发票交车辆管理人员，并由办公室车辆负责人签字确认。
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
const statCards = [
    { label: '在管车辆数', value: '6', desc: '纳入统一借车管理', descClass: '' },
    { label: '待主任审批', value: '2', desc: '需尽快完成审批', descClass: 'warning-text' },
    { label: '当前出车中', value: '3', desc: '已借出未归还', descClass: '' },
    { label: '本月申请单', value: '18', desc: '含已完成与流转中申请', descClass: '' }
]

const vehicles = [
    {
        plate: '沪A·12345',
        model: '别克 GL8',
        owner: '办公室车辆',
        status: '出车中',
        statusClass: 'warning',
        location: '外出办事',
        user: '张三',
        maintenance: '2026-05-20',
        inspection: '正常'
    },
    {
        plate: '沪B·56321',
        model: '大众帕萨特',
        owner: '办公室车辆',
        status: '空闲',
        statusClass: 'success',
        location: '公司停车点',
        user: '暂无',
        maintenance: '2026-06-18',
        inspection: '正常'
    },
    {
        plate: '沪C·90876',
        model: '丰田凯美瑞',
        owner: '办公室车辆',
        status: '审批预留',
        statusClass: 'neutral',
        location: '公司停车点',
        user: '待分配',
        maintenance: '2026-04-28',
        inspection: '即将到期'
    }
]

const applications = [
    {
        code: 'CAR-2026-001',
        department: '业务督导中心',
        user: '左翰承',
        reason: '赴站点巡检',
        useDate: '2026-04-20',
        start: '分公司本部',
        end: '华辉加油站、龙吴路加油站',
        status: '主任审批中',
        statusClass: 'warning',
        flow: [
            { name: '提交申请', desc: '申请单已提交', done: true },
            { name: '主任审批', desc: '待主任审批', done: false },
            { name: '车辆管理员确认', desc: '待分配车辆', done: false },
            { name: '出车登记', desc: '待出车', done: false }
        ]
    },
    {
        code: 'CAR-2026-002',
        department: '业务督导中心',
        user: '李四',
        reason: '现场陪同检查',
        useDate: '2026-04-19',
        start: '分公司本部',
        end: '锦秋加油站',
        status: '出车中',
        statusClass: 'info',
        flow: [
            { name: '提交申请', desc: '申请单已提交', done: true },
            { name: '主任审批', desc: '审批通过', done: true },
            { name: '车辆管理员确认', desc: '车辆已分配', done: true },
            { name: '出车登记', desc: '车辆已出车', done: true }
        ]
    }
]

const formFields = [
    '用车部门',
    '车牌号',
    '使用人',
    '用车事由',
    '用车日期',
    '归还日期',
    '出车地点',
    '到达地点',
    '用车部门负责人签字',
    '办公室车辆负责人签字',
    '路桥停车费金额',
    '审核人签字',
    '备注'
]

const alerts = [
    {
        title: '2 条借车申请待主任审批',
        desc: '建议今日内完成审核，避免影响出车安排。',
        dotClass: 'warning'
    },
    {
        title: '沪C·90876 年检时间临近',
        desc: '建议提前安排车辆年检，避免影响正常调度。',
        dotClass: 'info'
    },
    {
        title: '1 条出车记录尚未归还确认',
        desc: '建议联系使用人补充归还时间与费用信息。',
        dotClass: 'danger'
    }
]

const quickEntries = [
    { icon: '借', title: '发起借车', desc: '创建新的公务车辆使用申请' },
    { icon: '审', title: '主任审批', desc: '查看并处理待审批申请单' },
    { icon: '车', title: '车辆台账', desc: '查看车辆状态与使用记录' },
    { icon: '单', title: '模板导出', desc: '导出公务车辆使用申请单' }
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
.vehicle-meta,
.alert-desc,
.quick-desc,
.highlight-card p,
.table-sub,
.flow-desc,
.info-label,
.info-value,
.ledger-desc {
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

.content-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.55fr) minmax(360px, 0.9fr);
    gap: 20px;
    align-items: start;
}

.left-column,
.right-column {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.right-column {
    align-self: stretch;
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
}

.tag.info,
.status-chip.info {
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

.vehicle-list,
.application-list,
.alert-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.vehicle-card,
.application-card,
.alert-item {
    padding: 16px;
    border-radius: 18px;
    background: #f8fafc;
    border: 1px solid #dbe4ee;
}

.vehicle-top,
.application-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 14px;
}

.vehicle-plate,
.application-title,
.alert-title,
.quick-title,
.table-title,
.flow-name {
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
}

.vehicle-info-grid,
.application-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
}

.flow-line {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 14px;
}

.flow-step {
    display: flex;
    gap: 12px;
    align-items: flex-start;
}

.flow-dot {
    width: 28px;
    height: 28px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 800;
    flex-shrink: 0;
}

.flow-dot.done {
    background: #ecfdf5;
    color: #15803d;
}

.flow-dot.pending {
    background: #f1f5f9;
    color: #475569;
}

.template-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
}

.template-field {
    min-height: 44px;
    display: flex;
    align-items: center;
    padding: 0 14px;
    border-radius: 12px;
    border: 1px solid #dbe4ee;
    background: #f8fafc;
    font-size: 14px;
    color: #0f172a;
    font-weight: 600;
}

.compact-template-card {
    flex: 1;
}

.compact-template-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
}

.compact-template-field {
    min-height: 40px;
    font-size: 13px;
    padding: 0 12px;
}

.full-width-form-preview {
    width: 100%;
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

.form-preview-card {
    overflow: hidden;
}

.paper-preview {
    margin-top: 8px;
    padding: 20px;
    border: 1px dashed #cbd5e1;
    border-radius: 20px;
    background: #fff;
}

.paper-attachment {
    font-size: 16px;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 18px;
}

.paper-title {
    text-align: center;
    font-size: 34px;
    font-weight: 800;
    color: #000;
    margin-bottom: 22px;
    letter-spacing: 1px;
}

.paper-form-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    margin-bottom: 16px;
}

.paper-form-table td {
    border: 1px solid #111827;
    padding: 14px 10px;
    font-size: 14px;
    line-height: 1.7;
    color: #111827;
    vertical-align: middle;
    word-break: break-word;
}

.label-cell {
    width: 12%;
    text-align: center;
    font-weight: 700;
    background: #fafafa;
}

.value-cell {
    text-align: center;
}

.textarea-cell {
    min-height: 88px;
}

.tall-cell {
    min-height: 78px;
}

.signature-cell {
    text-align: center;
    font-weight: 700;
    color: #1f2937;
}

.paper-note {
    font-size: 14px;
    line-height: 2;
    color: #111827;
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
    .quick-grid,
    .template-grid,
    .compact-template-grid {
        grid-template-columns: 1fr;
    }

    .vehicle-top,
    .application-top,
    .section-head,
    .header-actions {
        flex-direction: column;
        align-items: stretch;
    }

    .vehicle-info-grid,
    .application-grid {
        grid-template-columns: 1fr;
    }

    .paper-preview {
        padding: 14px;
    }

    .paper-title {
        font-size: 24px;
        margin-bottom: 16px;
    }

    .paper-form-table td {
        padding: 10px 6px;
        font-size: 12px;
    }

    .paper-note {
        font-size: 12px;
        line-height: 1.8;
    }
}
</style>