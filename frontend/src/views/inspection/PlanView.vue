<template>
    <div class="page-shell">
        <div class="page-header card-surface">
            <div>
                <div class="page-kicker">巡检计划</div>
                <h2>月度巡检计划样板页面</h2>
                <p class="page-desc">
                    围绕“每张检查表 × 全部站点”的月度任务量展示计划、完成、未完成情况，并预留站点勾选计划与出发前路线规划入口。
                </p>
            </div>
            <div class="header-actions">
                <button class="ghost-btn" type="button">导出计划台账</button>
                <button class="primary-btn" type="button" :disabled="!canEditPlan">
                    {{ canEditPlan ? '编辑本月计划' : '仅督导组测试账号可编辑计划' }}
                </button>
            </div>
        </div>

        <div v-if="hasPermission" class="page-content">
            <div class="stats-grid">
                <div v-for="card in statCards" :key="card.label" class="card-surface stat-card">
                    <div class="stat-label">{{ card.label }}</div>
                    <div class="stat-value">{{ card.value }}</div>
                    <div class="stat-desc">{{ card.desc }}</div>
                </div>
            </div>

            <div class="content-grid">
                <div class="left-column">
                    <div class="card-surface section-card">
                        <div class="section-head">
                            <div>
                                <div class="section-kicker">任务总览</div>
                                <h3>检查表月度计划完成情况</h3>
                            </div>
                            <button class="ghost-btn" type="button">查看历史月份</button>
                        </div>

                        <div class="table-wrap">
                            <table class="plan-table">
                                <thead>
                                    <tr>
                                        <th>检查表</th>
                                        <th>覆盖要求</th>
                                        <th>本月计划</th>
                                        <th>本月已完成</th>
                                        <th>未完成</th>
                                        <th>完成率</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="item in planRows" :key="item.name">
                                        <td>
                                            <div class="table-title">{{ item.name }}</div>
                                            <div class="table-sub">{{ item.scope }}</div>
                                        </td>
                                        <td>{{ item.coverage }}</td>
                                        <td>{{ item.plan }}</td>
                                        <td>{{ item.done }}</td>
                                        <td>
                                            <span
                                                :class="item.remaining > 0 ? 'status-chip warning' : 'status-chip success'">
                                                {{ item.remaining }}
                                            </span>
                                        </td>
                                        <td>
                                            <div class="progress-cell">
                                                <div class="progress-bar">
                                                    <div class="progress-fill" :style="{ width: item.rate + '%' }">
                                                    </div>
                                                </div>
                                                <span>{{ item.rate }}%</span>
                                            </div>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div class="card-surface section-card">
                        <div class="section-head">
                            <div>
                                <div class="section-kicker">站点勾选计划</div>
                                <h3>按检查表设定本月要去的站点</h3>
                            </div>
                            <div class="inline-tags">
                                <span class="tag info">样板交互</span>
                                <span class="tag" :class="canEditPlan ? 'editable' : 'locked'">
                                    {{ canEditPlan ? '当前账号可编辑' : '当前账号只读查看' }}
                                </span>
                            </div>
                        </div>

                        <div class="planner-layout">
                            <div class="planner-left">
                                <div class="planner-select-card">
                                    <label class="field-label">选择检查表</label>
                                    <div class="fake-select">{{ selectedTemplate.name }}</div>
                                </div>

                                <div class="planner-hint">
                                    本月计划站点由具备权限的账号勾选。已完成过本月该检查表的站点仍会展示，并带有“本月已完成”提示，避免重复安排。
                                </div>
                            </div>

                            <div class="planner-right">
                                <div class="station-list">
                                    <div v-for="station in stationChoices" :key="station.name" class="station-item">
                                        <div class="station-main">
                                            <div class="station-name">{{ station.name }}</div>
                                            <div class="station-meta">{{ station.area }}</div>
                                        </div>

                                        <div class="station-state">
                                            <span v-if="station.done" class="tag success">本月已完成</span>
                                            <span v-else-if="station.planned" class="tag info">已纳入计划</span>
                                            <span v-else class="tag neutral">未纳入计划</span>
                                        </div>

                                        <button class="mini-btn" type="button" :disabled="!canEditPlan || station.done">
                                            {{ station.done ? '已完成' : station.planned ? '取消勾选' : '勾选站点' }}
                                        </button>
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
                                <div class="section-kicker">路线规划</div>
                                <h3>今日出发前路线建议</h3>
                            </div>
                            <button class="ghost-btn" type="button">重新生成</button>
                        </div>

                        <div class="route-desc">
                            选择今天准备出发的若干站点后，系统可优先补入“本月该检查表尚未完成”的邻近站点，形成建议巡检路线。当前仅为样板展示，不执行真实地图导航。
                        </div>

                        <div class="route-picks">
                            <div class="pick-title">今日已选站点</div>
                            <div class="pick-list">
                                <span v-for="item in selectedRouteStops" :key="item" class="tag dark">{{ item }}</span>
                            </div>
                        </div>

                        <div class="route-suggest">
                            <div class="pick-title">系统补充建议站点（本月未完成）</div>
                            <div class="pick-list">
                                <span v-for="item in suggestedStops" :key="item" class="tag warning">{{ item }}</span>
                            </div>
                        </div>

                        <div class="route-line">
                            <div v-for="(item, index) in routePreview" :key="item.name" class="route-step">
                                <div class="route-index">{{ index + 1 }}</div>
                                <div class="route-content">
                                    <div class="route-name">{{ item.name }}</div>
                                    <div class="route-note">{{ item.note }}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="card-surface section-card">
                        <div class="section-head compact">
                            <div>
                                <div class="section-kicker">权限说明</div>
                                <h3>计划管理权限样板</h3>
                            </div>
                        </div>

                        <div class="rule-list">
                            <div class="rule-item">
                                <div class="rule-title">查看权限</div>
                                <div class="rule-desc">督导组成员可查看每张检查表的本月计划、本月已完成与未完成数量。</div>
                            </div>
                            <div class="rule-item">
                                <div class="rule-title">编辑权限</div>
                                <div class="rule-desc">当前样板暂定仅“督导组测试账号”可勾选本月计划站点，后续可单独配置权限账号。</div>
                            </div>
                            <div class="rule-item">
                                <div class="rule-title">完成提示</div>
                                <div class="rule-desc">某站点本月对应检查表已经完成时，站点列表中仍可见，但会以“本月已完成”标识提示。</div>
                            </div>
                            <div class="rule-item">
                                <div class="rule-title">路线规划</div>
                                <div class="rule-desc">出发前可基于已选站点与本月未完成站点，自动生成建议路线顺序，作为巡检导航参考。</div>
                            </div>
                        </div>
                    </div>

                    <div class="card-surface section-card highlight-card">
                        <div class="section-kicker highlight-kicker">页面定位</div>
                        <h3>巡检计划页面样板</h3>
                        <p>
                            本页面主要回答两类问题：一是“每张检查表本月计划做多少、完成多少”；二是“今天出发前去哪些站、还可以顺路补哪些未完成站点”。
                            当前仅展示前端样板效果，未接真实计划写入、历史数据、地图服务与自动导航功能。
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <div v-else class="card-surface section-card permission-card">
            <div class="permission-icon">!</div>
            <div class="permission-title">无权限访问</div>
            <div class="permission-desc">当前账号无权访问巡检计划页面，请使用督导组账号登录后操作。</div>
        </div>
    </div>
</template>

<script setup>
const currentRole = localStorage.getItem('user_role') || ''
const currentUsername = localStorage.getItem('username') || ''
const hasPermission = currentRole === 'supervisor'
const canEditPlan = currentUsername === '督导组测试账号'

const statCards = [
    { label: '检查表总数', value: '8', desc: '覆盖现场巡检、远程巡检与专项检查' },
    { label: '本月总站点任务量', value: '245', desc: '按各检查表应覆盖站点数汇总' },
    { label: '本月已完成', value: '168', desc: '已完成检查表 × 站点数量' },
    { label: '本月未完成', value: '77', desc: '可用于补站与路线规划' }
]

const planRows = [
    { name: '充电站安全检查', scope: '充电站', coverage: '半年覆盖', plan: 12, done: 7, remaining: 5, rate: 58 },
    { name: '质量健康安全检查', scope: '加油站现场巡检', coverage: '半年覆盖', plan: 35, done: 22, remaining: 13, rate: 63 },
    { name: '加油站财务巡检', scope: '加油站现场巡检', coverage: '季度覆盖', plan: 35, done: 25, remaining: 10, rate: 71 },
    { name: '设备巡检', scope: '加油站现场巡检', coverage: '年度覆盖', plan: 35, done: 19, remaining: 16, rate: 54 },
    { name: '加油站现场', scope: '远程巡检', coverage: '每月全覆盖', plan: 43, done: 36, remaining: 7, rate: 84 },
    { name: '安全检查', scope: '远程巡检', coverage: '每月全覆盖', plan: 43, done: 29, remaining: 14, rate: 67 },
    { name: '手工比对', scope: '远程巡检', coverage: '每月全覆盖', plan: 43, done: 18, remaining: 25, rate: 42 }
]

const selectedTemplate = {
    name: '加油站财务巡检'
}

const stationChoices = [
    { name: '华辉加油站', area: '城区片区', planned: true, done: false },
    { name: '龙吴路加油站', area: '城区片区', planned: true, done: true },
    { name: '锦秋加油站', area: '北区片区', planned: false, done: false },
    { name: '宝杨第一加油站', area: '宝山片区', planned: true, done: false },
    { name: '宝杨第二加油站', area: '宝山片区', planned: false, done: true },
    { name: '凯燕加油站', area: '城区片区', planned: false, done: false }
]

const selectedRouteStops = ['华辉加油站', '锦秋加油站']
const suggestedStops = ['凯燕加油站', '龙吴路加油站']

const routePreview = [
    { name: '华辉加油站', note: '今日手动选择起点站' },
    { name: '凯燕加油站', note: '同片区且本月该检查表未完成，建议顺路补站' },
    { name: '龙吴路加油站', note: '已完成站点，显示提示便于统筹判断是否重复前往' },
    { name: '锦秋加油站', note: '今日手动选择终点站' }
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

.page-desc {
    margin: 10px 0 0;
    max-width: 760px;
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
.mini-btn {
    border: 1px solid #cbd5e1;
    background: #fff;
    color: #334155;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
}

.ghost-btn {
    height: 38px;
    padding: 0 14px;
}

.primary-btn {
    height: 40px;
    padding: 0 16px;
    background: #2563eb;
    border-color: #2563eb;
    color: #fff;
}

.primary-btn:disabled,
.mini-btn:disabled {
    cursor: not-allowed;
    opacity: 0.55;
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

.inline-tags,
.pick-list {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.table-wrap {
    overflow-x: auto;
}

.plan-table {
    width: 100%;
    border-collapse: collapse;
}

.plan-table th,
.plan-table td {
    padding: 14px 12px;
    border-bottom: 1px solid #e2e8f0;
    text-align: left;
    vertical-align: middle;
    font-size: 14px;
    color: #0f172a;
}

.plan-table th {
    font-size: 13px;
    color: #64748b;
    font-weight: 700;
}

.table-title,
.rule-title,
.route-name {
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
}

.table-sub,
.rule-desc,
.route-note,
.planner-hint,
.route-desc,
.highlight-card p,
.station-meta {
    margin-top: 6px;
    font-size: 13px;
    line-height: 1.8;
    color: #64748b;
}

.progress-cell {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 140px;
}

.progress-bar {
    flex: 1;
    height: 10px;
    border-radius: 999px;
    background: #e2e8f0;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #2563eb 0%, #60a5fa 100%);
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

.tag.neutral {
    background: #f1f5f9;
    color: #475569;
}

.tag.dark {
    background: #0f172a;
    color: #fff;
}

.tag.editable {
    background: #ecfdf5;
    color: #15803d;
}

.tag.locked {
    background: #fef2f2;
    color: #dc2626;
}

.planner-layout {
    display: grid;
    grid-template-columns: 280px minmax(0, 1fr);
    gap: 18px;
}

.planner-select-card {
    padding: 16px;
    border-radius: 18px;
    background: #f8fafc;
    border: 1px solid #dbe4ee;
}

.field-label,
.pick-title {
    font-size: 13px;
    font-weight: 700;
    color: #64748b;
    margin-bottom: 10px;
}

.fake-select {
    min-height: 44px;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    display: flex;
    align-items: center;
    padding: 0 14px;
    font-size: 14px;
    font-weight: 700;
    color: #0f172a;
    background: #fff;
}

.station-list,
.rule-list,
.route-line {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.station-item,
.rule-item,
.route-step {
    padding: 14px 16px;
    border-radius: 16px;
    border: 1px solid #dbe4ee;
    background: #f8fafc;
}

.station-item {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: 14px;
    align-items: center;
}

.station-name {
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
}

.mini-btn {
    min-width: 90px;
    height: 34px;
    padding: 0 12px;
}

.route-index {
    width: 30px;
    height: 30px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 13px;
    font-weight: 800;
    flex-shrink: 0;
}

.route-step {
    display: flex;
    gap: 12px;
    align-items: flex-start;
}

.highlight-card {
    background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
}

.highlight-kicker {
    background: #dbeafe;
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
    max-width: 520px;
}

@media (max-width: 1200px) {
    .stats-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .content-grid,
    .planner-layout {
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

    .stats-grid {
        grid-template-columns: 1fr;
    }

    .station-item {
        grid-template-columns: 1fr;
    }

    .section-head,
    .header-actions {
        flex-direction: column;
        align-items: stretch;
    }
}
</style>