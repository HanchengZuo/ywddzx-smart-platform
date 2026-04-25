<template>
    <div class="page-shell">
        <div class="page-header card-surface">
            <div>
                <div class="page-kicker">巡检计划</div>
                <h2>巡检计划样板页面</h2>
            </div>
            <div class="header-actions"></div>
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
                                <h3>检查表计划完成进度实时看板</h3>
                            </div>
                            <div class="inline-tags">
                                <span class="tag info">实时进度</span>
                            </div>
                        </div>

                        <div class="table-wrap">
                            <table class="plan-table">
                                <thead>
                                    <tr>
                                        <th>检查表</th>
                                        <th>覆盖要求</th>
                                        <th>时间配置</th>
                                        <th>纳入站点数</th>
                                        <th>计划完成情况</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-if="!planRows.length && !isLoadingTaskBoard">
                                        <td colspan="5" class="table-empty-cell">当前暂无检查表目录数据。</td>
                                    </tr>

                                    <tr v-if="isLoadingTaskBoard">
                                        <td colspan="5" class="table-empty-cell">任务总览加载中...</td>
                                    </tr>

                                    <tr v-for="item in planRows" :key="item.name">
                                        <td>
                                            <div class="table-title">{{ item.name }}</div>
                                            <div class="table-sub">{{ item.scope }}</div>
                                        </td>
                                        <td>
                                            <span class="plan-status-chip neutral">
                                                {{ coverageTypeLabelMap[item.coverageType] || '-' }}
                                            </span>
                                        </td>
                                        <td>
                                            <div class="table-sub">{{ getCoverageConfigLabel(item) }}</div>
                                        </td>
                                        <td>{{ getIncludedStationCount(item) }}</td>
                                        <td>
                                            <div class="progress-cell progress-cell-wide">
                                                <div class="progress-bar">
                                                    <div class="progress-fill" :style="{ width: item.rate + '%' }">
                                                    </div>
                                                </div>
                                                <span>{{ item.done }}/{{ item.plan }}（{{ item.rate }}%）</span>
                                            </div>
                                            <div class="table-sub">未完成 {{ item.remaining }} 个站点</div>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div class="card-surface section-card">
                        <div class="section-head">
                            <div>
                                <div class="section-kicker">数据总览</div>
                                <h3>检查表计划数据总览</h3>
                            </div>


                            <button v-if="isPlanManager" class="primary-btn" type="button"
                                @click="openOverviewPlanDetail">
                                配置计划
                            </button>

                        </div>

                        <div class="overview-toolbar">
                            <div class="overview-field">
                                <div class="overview-field-head">
                                    <label class="field-label">选择检查表</label>
                                    <span class="overview-inline-tag info">{{ overviewSelectedTable?.name || '-'
                                    }}</span>
                                </div>
                                <select class="month-picker-select planner-table-select"
                                    v-model="overviewSelectedTableName">
                                    <option v-for="item in inspectionTablesCatalog" :key="item.id"
                                        :value="item.table_name">
                                        {{ item.table_name }}
                                    </option>
                                </select>
                            </div>

                            <div class="overview-field">
                                <div class="overview-field-head">
                                    <label class="field-label">选择时间范围</label>
                                    <span class="overview-inline-tag neutral">{{ overviewTimeLabel }}</span>
                                </div>
                                <select class="month-picker-select planner-table-select"
                                    v-model="overviewSelectedPeriod">
                                    <option v-for="option in overviewConfiguredPeriodOptions" :key="option"
                                        :value="option">
                                        {{ option }}
                                    </option>
                                </select>
                            </div>
                        </div>

                        <div class="overview-summary-bar">
                            <span class="plan-status-chip neutral">
                                覆盖要求：{{ coverageTypeLabelMap[overviewSelectedTable?.coverageType] || '-' }}
                            </span>
                            <span class="plan-status-chip info">纳入站点：{{ overviewIncludedCount }}</span>
                            <span class="plan-status-chip editable">已完成：{{ overviewDoneCount }}</span>
                            <span class="plan-status-chip readonly">未完成：{{ overviewPendingCount }}</span>
                            <span class="plan-status-chip neutral">{{ overviewCompletionRateLabel }}：{{
                                overviewCompletionRate }}%</span>
                        </div>

                        <div class="table-wrap">
                            <table class="plan-detail-table">
                                <thead>
                                    <tr>
                                        <th>
                                            <div class="table-header-inline">
                                                <span class="table-header-title">站点名称</span>
                                            </div>
                                        </th>
                                        <th>
                                            <div class="table-header-inline table-header-inline-filterable">
                                                <span class="table-header-title">片区</span>
                                                <button class="table-filter-mini-btn" type="button"
                                                    @click.stop="toggleOverviewFilterMenu('area', $event)"
                                                    aria-label="筛选片区">
                                                    <span class="table-filter-icon-line line-1"></span>
                                                    <span class="table-filter-icon-line line-2"></span>
                                                    <span class="table-filter-icon-line line-3"></span>
                                                </button>
                                            </div>
                                        </th>
                                        <th>
                                            <div class="table-header-inline table-header-inline-filterable">
                                                <span class="table-header-title">是否纳入该检查表计划</span>
                                                <button class="table-filter-mini-btn" type="button"
                                                    @click.stop="toggleOverviewFilterMenu('planned', $event)"
                                                    aria-label="筛选是否纳入该检查表计划">
                                                    <span class="table-filter-icon-line line-1"></span>
                                                    <span class="table-filter-icon-line line-2"></span>
                                                    <span class="table-filter-icon-line line-3"></span>
                                                </button>
                                            </div>
                                        </th>
                                        <th>
                                            <div class="table-header-inline table-header-inline-filterable">
                                                <span class="table-header-title">{{ overviewTimeLabel }}完成情况</span>
                                                <button class="table-filter-mini-btn" type="button"
                                                    @click.stop="toggleOverviewFilterMenu('done', $event)"
                                                    aria-label="筛选完成情况">
                                                    <span class="table-filter-icon-line line-1"></span>
                                                    <span class="table-filter-icon-line line-2"></span>
                                                    <span class="table-filter-icon-line line-3"></span>
                                                </button>
                                            </div>
                                        </th>
                                        <th>
                                            <div class="table-header-inline">
                                                <span class="table-header-title">状态说明</span>
                                            </div>
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="station in pagedOverviewRows" :key="station.station_id || station.name">
                                        <td>{{ station.name }}</td>
                                        <td>{{ station.area }}</td>
                                        <td>
                                            <span
                                                :class="station.planned ? 'status-chip success' : 'status-chip neutral'">
                                                {{ station.planned ? '已纳入' : '未纳入' }}
                                            </span>
                                        </td>
                                        <td>
                                            <span :class="station.done ? 'status-chip success' : 'status-chip warning'">
                                                {{ station.done ? '已完成' : '未完成' }}
                                            </span>
                                        </td>
                                        <td>
                                            {{ station.done ? `${overviewTimeLabel}已完成该检查表` :
                                                `${overviewTimeLabel}尚未完成该检查表` }}
                                        </td>
                                    </tr>
                                    <tr v-if="!overviewRows.length && !isLoadingOverview">
                                        <td colspan="5" class="table-empty-cell">当前时间范围下暂无计划明细数据。</td>
                                    </tr>
                                    <tr v-if="isLoadingOverview">
                                        <td colspan="5" class="table-empty-cell">数据加载中...</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <div v-if="overviewTotalPages > 1" class="table-pagination-bar">
                            <div class="table-pagination-info">
                                共 {{ overviewRows.length }} 个站点，第 {{ overviewCurrentPage }} / {{ overviewTotalPages }} 页
                            </div>
                            <div class="table-pagination-actions">
                                <button class="ghost-btn" type="button" :disabled="overviewCurrentPage <= 1"
                                    @click="overviewCurrentPage--">
                                    上一页
                                </button>
                                <button class="ghost-btn" type="button"
                                    :disabled="overviewCurrentPage >= overviewTotalPages"
                                    @click="overviewCurrentPage++">
                                    下一页
                                </button>
                            </div>
                        </div>
                        <teleport to="body">
                            <div v-if="activeOverviewFilterMenu"
                                class="table-filter-popover table-filter-popover-teleported"
                                :style="overviewFilterPopoverStyle" @click.stop>
                                <template v-if="activeOverviewFilterMenu === 'area'">
                                    <label class="table-filter-option">
                                        <input type="checkbox" :checked="overviewAreaFilter === 'all'"
                                            @change="setOverviewAreaFilterAll" />
                                        <span>全部片区</span>
                                    </label>
                                    <label v-for="area in overviewAreaOptions" :key="area" class="table-filter-option">
                                        <input type="checkbox" :checked="overviewAreaFilterSet.includes(area)"
                                            @change="toggleOverviewAreaFilter(area)" />
                                        <span>{{ area }}</span>
                                    </label>
                                </template>

                                <template v-else-if="activeOverviewFilterMenu === 'planned'">
                                    <label class="table-filter-option">
                                        <input type="checkbox" :checked="overviewPlannedFilter === 'all'"
                                            @change="setOverviewPlannedFilterAll" />
                                        <span>全部</span>
                                    </label>
                                    <label class="table-filter-option">
                                        <input type="checkbox" :checked="overviewPlannedFilterSet.includes('planned')"
                                            @change="toggleOverviewPlannedFilter('planned')" />
                                        <span>已纳入</span>
                                    </label>
                                    <label class="table-filter-option">
                                        <input type="checkbox" :checked="overviewPlannedFilterSet.includes('unplanned')"
                                            @change="toggleOverviewPlannedFilter('unplanned')" />
                                        <span>未纳入</span>
                                    </label>
                                </template>

                                <template v-else-if="activeOverviewFilterMenu === 'done'">
                                    <label class="table-filter-option">
                                        <input type="checkbox" :checked="overviewDoneFilter === 'all'"
                                            @change="setOverviewDoneFilterAll" />
                                        <span>全部</span>
                                    </label>
                                    <label class="table-filter-option">
                                        <input type="checkbox" :checked="overviewDoneFilterSet.includes('done')"
                                            @change="toggleOverviewDoneFilter('done')" />
                                        <span>已完成</span>
                                    </label>
                                    <label class="table-filter-option">
                                        <input type="checkbox" :checked="overviewDoneFilterSet.includes('pending')"
                                            @change="toggleOverviewDoneFilter('pending')" />
                                        <span>未完成</span>
                                    </label>
                                </template>
                            </div>
                        </teleport>
                    </div>
                </div>

                <div class="right-column">
                    <div class="card-surface section-card">
                        <div class="section-head compact">
                            <div>
                                <div class="section-kicker">路线建议</div>
                                <h3>今日出发前路线建议</h3>
                            </div>
                            <button class="ghost-btn" type="button" @click="regenerateRouteBatches">重新生成</button>
                        </div>

                        <div class="route-desc">
                            当前按照“{{ getCoverageConfigLabel(selectedTemplate) }} / {{ selectedTemplate?.name || '-'
                            }}”生成今日出发建议。
                            出发点固定为世纪大道1200号（经纬度 121.531347,
                            31.225426），系统优先从该检查表当前配置周期内已纳入计划且尚未完成的站点中，组合出若干批最适合当天出发的顺路站点方案。
                        </div>

                        <div class="route-control-panel">
                            <div class="route-control-card">
                                <div class="pick-title">今日计划出发站点数量</div>
                                <select class="month-picker-select route-count-select"
                                    v-model.number="routeStationCount">
                                    <option :value="2">2 个站</option>
                                    <option :value="3">3 个站</option>
                                    <option :value="4">4 个站</option>
                                    <option :value="5">5 个站</option>
                                </select>
                            </div>

                            <div class="route-control-card">
                                <div class="pick-title">固定出发点</div>
                                <div class="route-origin-box">
                                    <div class="route-origin-name">业务督导中心</div>
                                    <div class="route-origin-coord">经纬度：121.531347, 31.225426</div>
                                </div>
                            </div>
                        </div>

                        <div class="route-suggest">
                            <div class="pick-title">当前检查表计划内未完成站点</div>
                            <div class="pick-list">
                                <span v-for="item in suggestedStops" :key="item" class="tag warning">{{ item }}</span>
                                <span v-if="suggestedStops.length === 0" class="tag success">当前计划内站点已全部完成</span>
                            </div>
                            <div class="route-helper-text">
                                当前按“{{ routeStationCount }}
                                个站点为一组”生成推荐方案；系统仅从该检查表当前配置周期内“已纳入计划且尚未完成”的站点中生成出发建议，不再补入“已纳入计划但已完成”或“未纳入计划”的站点。
                            </div>
                            <div v-if="suggestedStops.length > 0 && suggestedStops.length < routeStationCount"
                                class="route-helper-warning">
                                当前计划内未完成站点仅 {{ suggestedStops.length }} 个，少于你设定的 {{ routeStationCount }}
                                个站点，暂无法凑满一组完整出发方案。
                            </div>
                        </div>

                        <div class="route-batch-list">
                            <div v-for="(batch, batchIndex) in routeBatches" :key="batchIndex" class="route-batch-card">
                                <div class="route-batch-head">
                                    <div class="route-batch-title">推荐方案 {{ batchIndex + 1 }}</div>
                                    <div class="route-batch-meta">共 {{ batch.stations.length }} 个站点 · 预计路线长度最优样板</div>
                                </div>

                                <div class="route-line">
                                    <div v-for="(item, index) in batch.stations"
                                        :key="(item.station_id || item.name) + '-' + index" class="route-step">
                                        <div class="route-index">{{ index + 1 }}</div>
                                        <div class="route-content">
                                            <div class="route-name">{{ item.name }}</div>
                                            <div class="route-note">{{ item.note }}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div v-if="routeBatches.length === 0" class="route-empty-state">
                            当前选中检查表暂无可展示的路线建议，请先配置当前检查表计划站点。
                        </div>
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

    <div v-if="detailDialog.visible" class="plan-dialog-overlay" @click.self="closePlanDetail">
        <div class="card-surface plan-dialog">
            <div class="plan-dialog-header">
                <div>
                    <div class="section-kicker">计划详情</div>
                    <h3>{{ detailDialogTitle }}</h3>
                    <div class="plan-dialog-meta">
                        <span>配置周期：{{ getCoverageConfigLabel(detailDialog.row) }}</span>
                        <span>覆盖要求：{{ coverageTypeLabelMap[detailDialog.row?.coverageType] || '-' }}</span>
                        <span>计划站点数：{{ detailDialogPlanCount }}</span>
                        <span>当前周期已完成：{{ detailDialogDoneCount }}</span>
                    </div>
                </div>
                <button class="ghost-btn" type="button" @click="closePlanDetail">关闭</button>
            </div>

            <div class="plan-dialog-body">
                <div class="plan-dialog-tip">
                    <strong>
                        {{ isPlanManager ? '当前账号为计划管理员，可编辑当前检查表计划。' : '当前账号为普通督导组账号，仅可查看计划详情。' }}
                    </strong>
                    <div class="plan-dialog-tip-text">
                        当前计划以“检查表配置周期 + 检查表 + 站点”为单位配置。已完成站点会保留显示，便于统筹安排与补站。
                    </div>
                    <div class="plan-dialog-summary-row">
                        <span class="plan-status-chip neutral">计划站点：{{ detailDialogPlanCount }}</span>
                        <span class="plan-status-chip editable">已完成：{{ detailDialogDoneCount }}</span>
                        <span class="plan-status-chip readonly">未完成：{{ detailDialogPendingCount }}</span>
                        <span class="plan-status-chip info">当前列表：{{ filteredDetailRows.length }}</span>
                    </div>
                </div>

                <div class="plan-config-panel">
                    <div class="plan-config-field">
                        <label class="field-label">覆盖要求</label>
                        <select class="coverage-select detail-coverage-select" v-model="detailDialog.row.coverageType"
                            :disabled="!isPlanManager" @change="handleCoverageTypeChange(detailDialog.row)">
                            <option value="monthly">月度覆盖</option>
                            <option value="quarterly">季度覆盖</option>
                            <option value="yearly">年度覆盖</option>
                        </select>
                    </div>

                    <div class="plan-config-field">
                        <label class="field-label">时间配置</label>

                        <div class="detail-period-flex" :class="{
                            'two-columns': detailDialog.row?.coverageType === 'monthly' || detailDialog.row?.coverageType === 'quarterly',
                            'one-column': detailDialog.row?.coverageType === 'yearly'
                        }">
                            <select class="month-picker-select detail-period-select" :disabled="!isPlanManager"
                                :value="getDetailPeriodYear(detailDialog.row)"
                                @change="setDetailPeriodYear(detailDialog.row, $event.target.value)">
                                <option v-for="year in detailPeriodYearOptions" :key="year" :value="year">
                                    {{ year }}年
                                </option>
                            </select>

                            <select v-if="detailDialog.row?.coverageType === 'monthly'"
                                class="month-picker-select detail-period-select" :disabled="!isPlanManager"
                                :value="getDetailPeriodMonth(detailDialog.row)"
                                @change="setDetailPeriodMonth(detailDialog.row, $event.target.value)">
                                <option v-for="month in detailPeriodMonthOptions" :key="month" :value="month">
                                    {{ month }}月
                                </option>
                            </select>

                            <select v-if="detailDialog.row?.coverageType === 'quarterly'"
                                class="month-picker-select detail-period-select" :disabled="!isPlanManager"
                                :value="getDetailPeriodQuarter(detailDialog.row)"
                                @change="setDetailPeriodQuarter(detailDialog.row, $event.target.value)">
                                <option v-for="quarter in detailPeriodQuarterOptions" :key="quarter.value"
                                    :value="quarter.value">
                                    {{ quarter.label }}
                                </option>
                            </select>
                        </div>

                    </div>
                </div>

                <div class="table-wrap">
                    <table class="plan-detail-table">
                        <thead>

                            <tr>
                                <th>
                                    <div class="table-header-inline">
                                        <span class="table-header-title">站点名称</span>
                                    </div>
                                </th>

                                <th>
                                    <div class="table-header-inline table-header-inline-filterable">
                                        <span class="table-header-title">片区</span>
                                        <button class="table-filter-mini-btn" type="button"
                                            @click.stop="toggleFilterMenu('area', $event)" aria-label="筛选片区">
                                            <span class="table-filter-icon-line line-1"></span>
                                            <span class="table-filter-icon-line line-2"></span>
                                            <span class="table-filter-icon-line line-3"></span>
                                        </button>
                                    </div>
                                </th>

                                <th>
                                    <div class="table-header-inline table-header-inline-filterable">
                                        <span class="table-header-title">纳入计划</span>
                                        <button class="table-filter-mini-btn" type="button"
                                            @click.stop="toggleFilterMenu('planned', $event)" aria-label="筛选纳入计划">
                                            <span class="table-filter-icon-line line-1"></span>
                                            <span class="table-filter-icon-line line-2"></span>
                                            <span class="table-filter-icon-line line-3"></span>
                                        </button>
                                    </div>
                                </th>

                                <th>
                                    <div class="table-header-inline table-header-inline-filterable">
                                        <span class="table-header-title">当前周期是否完成</span>
                                        <button class="table-filter-mini-btn" type="button"
                                            @click.stop="toggleFilterMenu('done', $event)" aria-label="筛选当前周期是否完成">
                                            <span class="table-filter-icon-line line-1"></span>
                                            <span class="table-filter-icon-line line-2"></span>
                                            <span class="table-filter-icon-line line-3"></span>
                                        </button>
                                    </div>
                                </th>

                                <th>
                                    <div class="table-header-inline">
                                        <span class="table-header-title">完成日期</span>
                                    </div>
                                </th>
                            </tr>

                        </thead>
                        <tbody>
                            <tr v-for="station in pagedDetailRows" :key="station.station_id || station.name">
                                <td>{{ station.name }}</td>
                                <td>{{ station.area }}</td>
                                <td>
                                    <label class="plan-checkbox-wrap"
                                        :class="{ disabled: !isPlanManager || station.done }">
                                        <input type="checkbox" :checked="station.planned"
                                            :disabled="!isPlanManager || station.done"
                                            @change="toggleStationPlan(station)" />
                                        <span>{{ station.planned ? '已纳入' : '未纳入' }}</span>
                                    </label>
                                </td>
                                <td>
                                    <span :class="station.done ? 'status-chip success' : 'status-chip warning'">
                                        {{ station.done ? '已完成' : '未完成' }}
                                    </span>
                                </td>
                                <td>{{ station.doneDate || '-' }}</td>
                            </tr>
                            <tr v-if="!filteredDetailRows.length">
                                <td colspan="5" class="table-empty-cell">当前计划下暂无站点明细数据。</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div v-if="detailTotalPages > 1" class="table-pagination-bar">
                    <div class="table-pagination-info">
                        共 {{ filteredDetailRows.length }} 个站点，第 {{ detailCurrentPage }} / {{ detailTotalPages }} 页
                    </div>
                    <div class="table-pagination-actions">
                        <button class="ghost-btn" type="button" :disabled="detailCurrentPage <= 1"
                            @click="detailCurrentPage--">
                            上一页
                        </button>
                        <button class="ghost-btn" type="button" :disabled="detailCurrentPage >= detailTotalPages"
                            @click="detailCurrentPage++">
                            下一页
                        </button>
                    </div>
                </div>

                <div class="plan-dialog-actions">
                    <button class="ghost-btn" type="button" :disabled="!isPlanManager" @click="markAllPlanned">
                        自动纳入未完成站点
                    </button>
                    <button class="primary-btn" type="button" :disabled="!isPlanManager" @click="savePlanDetail">
                        {{ isPlanManager ? '保存本检查表计划' : '当前账号不可编辑' }}
                    </button>
                </div>
                <teleport to="body">
                    <div v-if="activeFilterMenu" class="table-filter-popover table-filter-popover-teleported"
                        :style="filterPopoverStyle" @click.stop>
                        <template v-if="activeFilterMenu === 'area'">
                            <label class="table-filter-option">
                                <input type="checkbox" :checked="detailAreaFilter === 'all'"
                                    @change="setAreaFilterAll" />
                                <span>全部片区</span>
                            </label>
                            <label v-for="area in detailAreaOptions" :key="area" class="table-filter-option">
                                <input type="checkbox" :checked="detailAreaFilterSet.includes(area)"
                                    @change="toggleAreaFilter(area)" />
                                <span>{{ area }}</span>
                            </label>
                        </template>

                        <template v-else-if="activeFilterMenu === 'planned'">
                            <label class="table-filter-option">
                                <input type="checkbox" :checked="detailPlannedFilter === 'all'"
                                    @change="setPlannedFilterAll" />
                                <span>全部</span>
                            </label>
                            <label class="table-filter-option">
                                <input type="checkbox" :checked="detailPlannedFilterSet.includes('planned')"
                                    @change="togglePlannedFilter('planned')" />
                                <span>已纳入</span>
                            </label>
                            <label class="table-filter-option">
                                <input type="checkbox" :checked="detailPlannedFilterSet.includes('unplanned')"
                                    @change="togglePlannedFilter('unplanned')" />
                                <span>未纳入</span>
                            </label>
                        </template>

                        <template v-else-if="activeFilterMenu === 'done'">
                            <label class="table-filter-option">
                                <input type="checkbox" :checked="detailDoneFilter === 'all'"
                                    @change="setDoneFilterAll" />
                                <span>全部</span>
                            </label>
                            <label class="table-filter-option">
                                <input type="checkbox" :checked="detailDoneFilterSet.includes('done')"
                                    @change="toggleDoneFilter('done')" />
                                <span>已完成</span>
                            </label>
                            <label class="table-filter-option">
                                <input type="checkbox" :checked="detailDoneFilterSet.includes('pending')"
                                    @change="toggleDoneFilter('pending')" />
                                <span>未完成</span>
                            </label>
                        </template>
                    </div>
                </teleport>

            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

const currentRole = localStorage.getItem('user_role') || ''
const currentUsername = localStorage.getItem('username') || ''
const currentUserId = localStorage.getItem('user_id') || ''

const hasPermission = currentRole === 'supervisor'
const isPlanManager = ['kongdechen', 'supervisor1'].includes(currentUsername)

const coverageTypeLabelMap = {
    monthly: '月度覆盖',
    quarterly: '季度覆盖',
    yearly: '年度覆盖'
}

const inferScopeByName = (tableName) => {
    const name = String(tableName || '')
    if (name.includes('充电站')) return '充电站'
    if (name.includes('远程')) return '远程巡检'
    return '加油站现场巡检'
}

const createPlanRowFromTable = (table) => ({
    inspectionTableId: table?.id ?? null,
    planConfigId: null,
    status: 'draft',
    name: table?.table_name || table?.name || '未命名检查表',
    scope: inferScopeByName(table?.table_name || table?.name),
    coverageType: 'monthly',
    periodConfig: { month: '2026年4月', quarter: '2026年第二季度', year: '2026年' },
    plan: 0,
    done: 0,
    remaining: 0,
    rate: 0
})
const inspectionTablesCatalog = ref([])
const planRows = ref([])
const planConfigList = ref([])
const allStationsCatalog = ref([])
const overviewRowsState = ref([])
const selectedTemplateStationsState = ref([])
const isLoadingOverview = ref(false)
const isLoadingTaskBoard = ref(false)

const parsePeriodConfig = (coverageType, periodKey) => {
    if (coverageType === 'quarterly') {
        return { month: '2026年4月', quarter: periodKey || '2026年第二季度', year: '2026年' }
    }
    if (coverageType === 'yearly') {
        return { month: '2026年4月', quarter: '2026年第二季度', year: periodKey || '2026年' }
    }
    return { month: periodKey || '2026年4月', quarter: '2026年第二季度', year: '2026年' }
}

const getCoverageConfigLabel = (row) => {
    if (!row) return '-'
    if (row.coverageType === 'quarterly') return row.periodConfig?.quarter || '2026年第二季度'
    if (row.coverageType === 'yearly') return row.periodConfig?.year || '2026年'
    return row.periodConfig?.month || '2026年4月'
}

const getPeriodKeyByCoverage = (coverageType, periodConfig = {}) => {
    if (coverageType === 'quarterly') return periodConfig.quarter || '2026年第二季度'
    if (coverageType === 'yearly') return periodConfig.year || '2026年'
    return periodConfig.month || '2026年4月'
}

const getPeriodKey = (row) => {
    if (!row) return ''
    return getPeriodKeyByCoverage(row.coverageType, row.periodConfig)
}

const getRealtimePeriodKey = (coverageType) => {
    const now = new Date()
    const year = now.getFullYear()
    const month = now.getMonth() + 1

    if (coverageType === 'quarterly') {
        const quarter = Math.ceil(month / 3)
        const quarterMap = {
            1: '第一季度',
            2: '第二季度',
            3: '第三季度',
            4: '第四季度'
        }
        return `${year}年${quarterMap[quarter]}`
    }

    if (coverageType === 'yearly') {
        return `${year}年`
    }

    return `${year}年${month}月`
}

const statCards = computed(() => {
    const rows = planRows.value
    const totalTables = inspectionTablesCatalog.value.length > 0
        ? inspectionTablesCatalog.value.length
        : rows.filter((item) => item.inspectionTableId).length || rows.length

    const configuredRows = rows.filter((item) => item.planConfigId)
    const monthlyTables = configuredRows.filter((item) => item.coverageType === 'monthly').length
    const quarterlyTables = configuredRows.filter((item) => item.coverageType === 'quarterly').length
    const yearlyTables = configuredRows.filter((item) => item.coverageType === 'yearly').length
    const totalIncludedStations = rows.reduce((sum, item) => sum + Number(item.plan || 0), 0)
    const totalDoneStations = rows.reduce((sum, item) => sum + Number(item.done || 0), 0)
    const averageCompletion = totalIncludedStations
        ? Math.round((totalDoneStations / totalIncludedStations) * 100)
        : 0

    return [
        { label: '检查表总数', value: String(totalTables), desc: '当前检查表目录中的检查表总数' },
        {
            label: '覆盖要求分布',
            value: `月度 ${monthlyTables} · 季度 ${quarterlyTables} · 年度 ${yearlyTables}`,
            desc: '当前已加载计划配置中，不同覆盖要求对应的检查表数量'
        },
        { label: '已纳入站点总数', value: String(totalIncludedStations), desc: '所有检查表当前纳入计划的站点累计数' },
        { label: '整体完成率', value: `${averageCompletion}%`, desc: `已完成 ${totalDoneStations} 个站点任务` }
    ]
})

const overviewSelectedTableName = ref('')
const overviewSelectedTable = computed(() => {
    return planRows.value.find((item) => item.name === overviewSelectedTableName.value) || planRows.value[0] || null
})


const overviewConfiguredPeriodOptions = computed(() => {
    const row = overviewSelectedTable.value
    if (!row) return []

    const matchedConfigs = planConfigList.value.filter(
        (item) =>
            item.inspection_table_id === row.inspectionTableId &&
            item.coverage_type === row.coverageType
    )

    const uniquePeriods = Array.from(
        new Set(matchedConfigs.map((item) => item.period_key).filter(Boolean))
    )

    return uniquePeriods.length > 0 ? uniquePeriods : [getRealtimePeriodKey(row.coverageType)]
})

const overviewSelectedPeriod = ref('2026年第二季度')

const overviewTimeLabel = computed(() => {
    if (overviewSelectedTable.value?.coverageType === 'quarterly') return '所选季度'
    if (overviewSelectedTable.value?.coverageType === 'yearly') return '所选年度'
    return '所选月份'
})

const overviewAreaFilter = ref('all')
const overviewPlannedFilter = ref('all')
const overviewDoneFilter = ref('all')
const overviewAreaFilterSet = ref([])
const overviewPlannedFilterSet = ref([])
const overviewDoneFilterSet = ref([])
const activeOverviewFilterMenu = ref(null)
const overviewFilterPopoverStyle = ref({})

const overviewRows = computed(() => {
    let rows = overviewRowsState.value || []

    if (overviewAreaFilter.value !== 'all' && overviewAreaFilterSet.value.length > 0) {
        rows = rows.filter((item) => overviewAreaFilterSet.value.includes(item.area))
    }

    if (overviewPlannedFilter.value !== 'all' && overviewPlannedFilterSet.value.length > 0) {
        rows = rows.filter((item) => {
            if (item.planned && overviewPlannedFilterSet.value.includes('planned')) return true
            if (!item.planned && overviewPlannedFilterSet.value.includes('unplanned')) return true
            return false
        })
    }

    if (overviewDoneFilter.value !== 'all' && overviewDoneFilterSet.value.length > 0) {
        rows = rows.filter((item) => {
            if (item.done && overviewDoneFilterSet.value.includes('done')) return true
            if (!item.done && overviewDoneFilterSet.value.includes('pending')) return true
            return false
        })
    }

    return rows
})
const overviewIncludedCount = computed(() => overviewRows.value.filter((item) => item.planned).length)
const overviewDoneCount = computed(() => overviewRows.value.filter((item) => item.done).length)
const overviewPendingCount = computed(() => overviewRows.value.filter((item) => item.planned && !item.done).length)
const overviewCompletionRate = computed(() => {
    return overviewIncludedCount.value
        ? Math.round((overviewDoneCount.value / overviewIncludedCount.value) * 100)
        : 0
})

const overviewCompletionRateLabel = computed(() => {
    if (overviewSelectedTable.value?.coverageType === 'quarterly') return '本季度计划完成率'
    if (overviewSelectedTable.value?.coverageType === 'yearly') return '本年度计划完成率'
    return '本月计划完成率'
})

const overviewPageSize = 10
const overviewCurrentPage = ref(1)
const overviewTotalPages = computed(() => {
    return Math.max(1, Math.ceil(overviewRows.value.length / overviewPageSize))
})
const pagedOverviewRows = computed(() => {
    const start = (overviewCurrentPage.value - 1) * overviewPageSize
    return overviewRows.value.slice(start, start + overviewPageSize)
})

const overviewAreaOptions = computed(() => {
    const rows = overviewRowsState.value || []
    return Array.from(new Set(rows.map((item) => item.area).filter(Boolean)))
})

const toggleOverviewFilterMenu = async (menuName, event) => {
    if (activeOverviewFilterMenu.value === menuName) {
        activeOverviewFilterMenu.value = null
        overviewFilterPopoverStyle.value = {}
        return
    }

    const buttonRect = event.currentTarget.getBoundingClientRect()
    activeOverviewFilterMenu.value = menuName
    await nextTick()

    const panelWidth = 240
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight
    const estimatedHeight = 260

    let left = buttonRect.right - panelWidth
    if (left < 12) left = 12
    if (left + panelWidth > viewportWidth - 12) {
        left = viewportWidth - panelWidth - 12
    }

    let top = buttonRect.bottom + 8
    if (top + estimatedHeight > viewportHeight - 12) {
        top = Math.max(12, buttonRect.top - estimatedHeight - 8)
    }

    overviewFilterPopoverStyle.value = {
        position: 'fixed',
        top: `${top}px`,
        left: `${left}px`
    }
}

const setOverviewAreaFilterAll = () => {
    overviewAreaFilter.value = 'all'
    overviewAreaFilterSet.value = []
}

const toggleOverviewAreaFilter = (area) => {
    if (overviewAreaFilter.value === 'all') {
        overviewAreaFilter.value = 'custom'
        overviewAreaFilterSet.value = [area]
        return
    }

    if (overviewAreaFilterSet.value.includes(area)) {
        overviewAreaFilterSet.value = overviewAreaFilterSet.value.filter((item) => item !== area)
    } else {
        overviewAreaFilterSet.value = [...overviewAreaFilterSet.value, area]
    }

    if (overviewAreaFilterSet.value.length === 0) {
        overviewAreaFilter.value = 'all'
    } else {
        overviewAreaFilter.value = 'custom'
    }
}

const setOverviewPlannedFilterAll = () => {
    overviewPlannedFilter.value = 'all'
    overviewPlannedFilterSet.value = []
}

const toggleOverviewPlannedFilter = (value) => {
    if (overviewPlannedFilter.value === 'all') {
        overviewPlannedFilter.value = 'custom'
        overviewPlannedFilterSet.value = [value]
        return
    }

    if (overviewPlannedFilterSet.value.includes(value)) {
        overviewPlannedFilterSet.value = overviewPlannedFilterSet.value.filter((item) => item !== value)
    } else {
        overviewPlannedFilterSet.value = [...overviewPlannedFilterSet.value, value]
    }

    if (overviewPlannedFilterSet.value.length === 0) {
        overviewPlannedFilter.value = 'all'
    } else {
        overviewPlannedFilter.value = 'custom'
    }
}

const setOverviewDoneFilterAll = () => {
    overviewDoneFilter.value = 'all'
    overviewDoneFilterSet.value = []
}

const toggleOverviewDoneFilter = (value) => {
    if (overviewDoneFilter.value === 'all') {
        overviewDoneFilter.value = 'custom'
        overviewDoneFilterSet.value = [value]
        return
    }

    if (overviewDoneFilterSet.value.includes(value)) {
        overviewDoneFilterSet.value = overviewDoneFilterSet.value.filter((item) => item !== value)
    } else {
        overviewDoneFilterSet.value = [...overviewDoneFilterSet.value, value]
    }

    if (overviewDoneFilterSet.value.length === 0) {
        overviewDoneFilter.value = 'all'
    } else {
        overviewDoneFilter.value = 'custom'
    }
}

const handleCoverageTypeChange = (row) => {
    if (!row) return
    if (!row.periodConfig) {
        row.periodConfig = { month: '2026年4月', quarter: '2026年第二季度', year: '2026年' }
    }
    if (row.coverageType === 'quarterly') {
        row.periodConfig.quarter = row.periodConfig?.quarter || '2026年第二季度'
    } else if (row.coverageType === 'yearly') {
        row.periodConfig.year = row.periodConfig?.year || '2026年'
    } else {
        row.periodConfig.month = row.periodConfig?.month || '2026年4月'
    }
}

const currentYear = new Date().getFullYear()
const detailPeriodYearOptions = Array.from({ length: 11 }, (_, index) => currentYear - 5 + index)
const detailPeriodMonthOptions = Array.from({ length: 12 }, (_, index) => index + 1)
const detailPeriodQuarterOptions = [
    { value: 1, label: '第一季度' },
    { value: 2, label: '第二季度' },
    { value: 3, label: '第三季度' },
    { value: 4, label: '第四季度' }
]

const getDetailPeriodYear = (row) => {
    if (!row) return 2026
    const source = row.coverageType === 'quarterly'
        ? row.periodConfig?.quarter
        : row.coverageType === 'yearly'
            ? row.periodConfig?.year
            : row.periodConfig?.month
    const matched = String(source || '').match(/(\d{4})年/)
    return matched ? Number(matched[1]) : 2026
}

const getDetailPeriodMonth = (row) => {
    if (!row) return 1
    const matched = String(row.periodConfig?.month || '').match(/年(\d{1,2})月/)
    return matched ? Number(matched[1]) : 1
}

const getDetailPeriodQuarter = (row) => {
    if (!row) return 1
    const value = String(row.periodConfig?.quarter || '')
    if (value.includes('第一')) return 1
    if (value.includes('第二')) return 2
    if (value.includes('第三')) return 3
    if (value.includes('第四')) return 4
    const matched = value.match(/第(\d)季度/)
    return matched ? Number(matched[1]) : 1
}

const setDetailPeriodYear = (row, yearValue) => {
    if (!row) return
    if (!row.periodConfig) {
        row.periodConfig = { month: '2026年4月', quarter: '2026年第二季度', year: '2026年' }
    }
    const year = Number(yearValue)
    if (row.coverageType === 'quarterly') {
        const quarterNumber = getDetailPeriodQuarter(row)
        const quarterLabelMap = {
            1: '第一季度',
            2: '第二季度',
            3: '第三季度',
            4: '第四季度'
        }
        row.periodConfig.quarter = `${year}年${quarterLabelMap[quarterNumber]}`
    } else if (row.coverageType === 'yearly') {
        row.periodConfig.year = `${year}年`
    } else {
        const month = getDetailPeriodMonth(row)
        row.periodConfig.month = `${year}年${month}月`
    }
}

const setDetailPeriodMonth = (row, monthValue) => {
    if (!row) return
    if (!row.periodConfig) {
        row.periodConfig = { month: '2026年4月', quarter: '2026年第二季度', year: '2026年' }
    }
    const year = getDetailPeriodYear(row)
    const month = Number(monthValue)
    row.periodConfig.month = `${year}年${month}月`
}

const setDetailPeriodQuarter = (row, quarterValue) => {
    if (!row) return
    if (!row.periodConfig) {
        row.periodConfig = { month: '2026年4月', quarter: '2026年第二季度', year: '2026年' }
    }
    const year = getDetailPeriodYear(row)
    const quarterNumber = Number(quarterValue)
    const quarterLabelMap = {
        1: '第一季度',
        2: '第二季度',
        3: '第三季度',
        4: '第四季度'
    }
    row.periodConfig.quarter = `${year}年${quarterLabelMap[quarterNumber]}`
}

const getIncludedStationCount = (row) => Number(row?.plan || 0)

const selectedTemplateName = ref('')
const selectedTemplate = computed(() => {
    return planRows.value.find((item) => item.name === selectedTemplateName.value) || planRows.value[0] || {
        name: '检查表计划详情',
        coverageType: 'monthly',
        periodConfig: { month: '2026年4月', quarter: '2026年第二季度', year: '2026年' }
    }
})

watch(overviewSelectedTableName, (value) => {
    if (value) {
        selectedTemplateName.value = value
    }
}, { immediate: false })

watch(overviewSelectedTableName, () => {
    if (!overviewSelectedTable.value) return
    const options = overviewConfiguredPeriodOptions.value
    overviewSelectedPeriod.value = options[0] || getRealtimePeriodKey(overviewSelectedTable.value.coverageType)
}, { immediate: false })

watch(
    () => [overviewSelectedTable.value?.inspectionTableId, overviewSelectedTable.value?.coverageType, overviewConfiguredPeriodOptions.value.join('|')],
    () => {
        if (!overviewSelectedTable.value) return
        const configuredOptions = overviewConfiguredPeriodOptions.value
        if (!configuredOptions.length) {
            overviewSelectedPeriod.value = getRealtimePeriodKey(overviewSelectedTable.value.coverageType)
            return
        }
        if (!configuredOptions.includes(overviewSelectedPeriod.value)) {
            overviewSelectedPeriod.value = configuredOptions[0]
        }
    },
    { immediate: false }
)

const selectedTemplateStations = computed(() => selectedTemplateStationsState.value)

const routeStationCount = ref(3)
const routeOrigin = {
    lng: 121.531347,
    lat: 31.225426
}

const detailDialogTitle = computed(() => {
    return detailDialog.value.row?.name || selectedTemplate.value?.name || '检查表计划详情'
})

const suggestedStops = computed(() => {
    return selectedTemplateStations.value
        .filter((item) => item.planned && !item.done)
        .map((item) => item.name)
})

const buildRouteBatch = (stations, batchIndex) => {
    return {
        stations: stations.map((item, index) => ({
            ...item,
            note: `方案 ${batchIndex + 1} · 第 ${index + 1} 站：从固定出发点（${routeOrigin.lng}, ${routeOrigin.lat}）出发后，优先安排该站，因其属于${getCoverageConfigLabel(selectedTemplate.value)}【${selectedTemplate.value.name}】计划内未完成站点。`
        }))
    }
}

const routeBatches = computed(() => {
    const batchSize = Math.max(Number(routeStationCount.value || 0), 1)
    const pendingStations = (selectedTemplateStations.value || []).filter((item) => item.planned && !item.done)
    if (pendingStations.length === 0) return []

    const batches = []
    const maxBatches = 3

    for (let i = 0; i < pendingStations.length && batches.length < maxBatches; i += batchSize) {
        const slice = pendingStations.slice(i, i + batchSize)
        if (slice.length === batchSize) {
            batches.push(buildRouteBatch(slice, batches.length))
        }
    }

    return batches
})

const planDetailDialog = {
    visible: false,
    row: null,
    rows: []
}

const detailDialog = ref({ ...planDetailDialog })
const detailPageSize = 12
const detailCurrentPage = ref(1)

const detailAreaFilter = ref('all')
const detailPlannedFilter = ref('all')
const detailDoneFilter = ref('all')

const detailAreaFilterSet = ref([])
const detailPlannedFilterSet = ref([])
const detailDoneFilterSet = ref([])
const activeFilterMenu = ref(null)
const filterPopoverStyle = ref({})
const handleGlobalClickCloseFilterMenu = () => {
    activeFilterMenu.value = null
    filterPopoverStyle.value = {}
    activeOverviewFilterMenu.value = null
    overviewFilterPopoverStyle.value = {}
}

const detailDialogPlanCount = computed(() => detailDialog.value.rows.filter((item) => item.planned).length)
const detailDialogDoneCount = computed(() => detailDialog.value.rows.filter((item) => item.done).length)
const detailDialogPendingCount = computed(() => detailDialog.value.rows.filter((item) => item.planned && !item.done).length)

const filteredDetailRows = computed(() => {
    let rows = detailDialog.value.rows || []

    if (detailAreaFilter.value !== 'all' && detailAreaFilterSet.value.length > 0) {
        rows = rows.filter((item) => detailAreaFilterSet.value.includes(item.area))
    }

    if (detailPlannedFilter.value !== 'all' && detailPlannedFilterSet.value.length > 0) {
        rows = rows.filter((item) => {
            if (item.planned && detailPlannedFilterSet.value.includes('planned')) return true
            if (!item.planned && detailPlannedFilterSet.value.includes('unplanned')) return true
            return false
        })
    }

    if (detailDoneFilter.value !== 'all' && detailDoneFilterSet.value.length > 0) {
        rows = rows.filter((item) => {
            if (item.done && detailDoneFilterSet.value.includes('done')) return true
            if (!item.done && detailDoneFilterSet.value.includes('pending')) return true
            return false
        })
    }

    return rows
})

const detailTotalPages = computed(() => {
    return Math.max(1, Math.ceil(filteredDetailRows.value.length / detailPageSize))
})

const pagedDetailRows = computed(() => {
    const start = (detailCurrentPage.value - 1) * detailPageSize
    return filteredDetailRows.value.slice(start, start + detailPageSize)
})

const detailAreaOptions = computed(() => {
    const rows = detailDialog.value.rows || []
    return Array.from(new Set(rows.map((item) => item.area).filter(Boolean)))
})

const toggleFilterMenu = async (menuName, event) => {
    if (activeFilterMenu.value === menuName) {
        activeFilterMenu.value = null
        filterPopoverStyle.value = {}
        return
    }

    const buttonRect = event.currentTarget.getBoundingClientRect()
    activeFilterMenu.value = menuName
    await nextTick()

    const panelWidth = 240
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight
    const estimatedHeight = 260

    let left = buttonRect.right - panelWidth
    if (left < 12) left = 12
    if (left + panelWidth > viewportWidth - 12) {
        left = viewportWidth - panelWidth - 12
    }

    let top = buttonRect.bottom + 8
    if (top + estimatedHeight > viewportHeight - 12) {
        top = Math.max(12, buttonRect.top - estimatedHeight - 8)
    }

    filterPopoverStyle.value = {
        position: 'fixed',
        top: `${top}px`,
        left: `${left}px`
    }
}

const setAreaFilterAll = () => {
    detailAreaFilter.value = 'all'
    detailAreaFilterSet.value = []
}

const toggleAreaFilter = (area) => {
    if (detailAreaFilter.value === 'all') {
        detailAreaFilter.value = 'custom'
        detailAreaFilterSet.value = [area]
        return
    }

    if (detailAreaFilterSet.value.includes(area)) {
        detailAreaFilterSet.value = detailAreaFilterSet.value.filter((item) => item !== area)
    } else {
        detailAreaFilterSet.value = [...detailAreaFilterSet.value, area]
    }

    if (detailAreaFilterSet.value.length === 0) {
        detailAreaFilter.value = 'all'
    } else {
        detailAreaFilter.value = 'custom'
    }
}

const setPlannedFilterAll = () => {
    detailPlannedFilter.value = 'all'
    detailPlannedFilterSet.value = []
}

const togglePlannedFilter = (value) => {
    if (detailPlannedFilter.value === 'all') {
        detailPlannedFilter.value = 'custom'
        detailPlannedFilterSet.value = [value]
        return
    }

    if (detailPlannedFilterSet.value.includes(value)) {
        detailPlannedFilterSet.value = detailPlannedFilterSet.value.filter((item) => item !== value)
    } else {
        detailPlannedFilterSet.value = [...detailPlannedFilterSet.value, value]
    }

    if (detailPlannedFilterSet.value.length === 0) {
        detailPlannedFilter.value = 'all'
    } else {
        detailPlannedFilter.value = 'custom'
    }
}

const setDoneFilterAll = () => {
    detailDoneFilter.value = 'all'
    detailDoneFilterSet.value = []
}

const toggleDoneFilter = (value) => {
    if (detailDoneFilter.value === 'all') {
        detailDoneFilter.value = 'custom'
        detailDoneFilterSet.value = [value]
        return
    }

    if (detailDoneFilterSet.value.includes(value)) {
        detailDoneFilterSet.value = detailDoneFilterSet.value.filter((item) => item !== value)
    } else {
        detailDoneFilterSet.value = [...detailDoneFilterSet.value, value]
    }

    if (detailDoneFilterSet.value.length === 0) {
        detailDoneFilter.value = 'all'
    } else {
        detailDoneFilter.value = 'custom'
    }
}

const toggleStationPlan = (station) => {
    if (!isPlanManager || station.done) return
    station.planned = !station.planned
}

const markAllPlanned = () => {
    if (!isPlanManager) return
    detailDialog.value.rows = detailDialog.value.rows.map((item) => {
        if (item.done) return { ...item }
        return { ...item, planned: true }
    })
}

const normalizeResponseList = (payload) => {
    if (!payload) return []
    if (Array.isArray(payload)) return payload
    if (Array.isArray(payload.items)) return payload.items
    if (Array.isArray(payload.data)) return payload.data
    if (Array.isArray(payload.tables)) return payload.tables
    if (Array.isArray(payload.stations)) return payload.stations
    return []
}

const requestJson = async (url, options = {}) => {
    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        },
        ...options
    })

    let payload = null
    try {
        payload = await response.json()
    } catch {
        payload = null
    }

    if (!response.ok || payload?.success === false) {
        const message = payload?.error || payload?.message || `请求失败：${response.status}`
        const error = new Error(message)
        error.payload = payload
        error.status = response.status
        if (payload?.existing_id) {
            error.existing_id = payload.existing_id
        }
        throw error
    }

    return payload
}

const applyPlanConfigToRow = (row, item) => {
    row.planConfigId = item.id || null
    row.inspectionTableId = item.inspection_table_id || row.inspectionTableId || null
    row.coverageType = item.coverage_type || row.coverageType
    row.periodConfig = parsePeriodConfig(item.coverage_type || row.coverageType, item.period_key)
    row.status = item.status || row.status
    row.plan = Number(item.included_station_count || 0)
    row.done = Number(item.completed_station_count || 0)
    row.remaining = Number(item.pending_station_count || 0)
    row.rate = Number(item.completion_rate || 0)
}

const normalizeTaskBoardRowsToRealtimePeriod = () => {
    planRows.value.forEach((row) => {
        row.periodConfig = parsePeriodConfig(row.coverageType, getRealtimePeriodKey(row.coverageType))
    })
}

const fetchInspectionTablesCatalog = async () => {
    try {
        const payload = await requestJson('/api/inspection-tables')
        const items = normalizeResponseList(payload)
        inspectionTablesCatalog.value = items
            .map((item) => ({
                id: item.id,
                table_name: item.table_name || item.name,
                is_active: item.is_active
            }))
            .filter((item) => item.id && item.table_name && item.is_active !== false)

        planRows.value = inspectionTablesCatalog.value.map((item) => createPlanRowFromTable(item))

        if (!overviewSelectedTableName.value && planRows.value.length > 0) {
            overviewSelectedTableName.value = planRows.value[0].name
        }
        if (!selectedTemplateName.value && planRows.value.length > 0) {
            selectedTemplateName.value = planRows.value[0].name
        }
    } catch {
        inspectionTablesCatalog.value = []
        planRows.value = []
    }
}

const fetchAllStationsCatalog = async () => {
    try {
        const payload = await requestJson('/api/stations')
        const items = normalizeResponseList(payload)
        allStationsCatalog.value = items
            .map((item) => ({
                station_id: item.id ?? item.station_id,
                name: item.station_name || item.name,
                area: item.region || item.area || '-',
                planned: false,
                done: false,
                doneDate: '-',
                note: null
            }))
            .filter((item) => item.station_id && item.name)
    } catch {
        allStationsCatalog.value = []
    }
}

const fetchPlanConfigs = async () => {
    isLoadingTaskBoard.value = true
    try {
        const query = currentUserId ? `?user_id=${encodeURIComponent(currentUserId)}` : ''
        const payload = await requestJson(`/api/inspection-plan-configs${query}`)
        const items = normalizeResponseList(payload)
        planConfigList.value = items

        const baseRows = inspectionTablesCatalog.value.length > 0
            ? inspectionTablesCatalog.value.map((item) => createPlanRowFromTable(item))
            : planRows.value.map((item) => ({ ...item, periodConfig: { ...(item.periodConfig || {}) } }))

        const groupedPlanMap = new Map()
        items.forEach((item) => {
            const key = item.inspection_table_name
            if (!groupedPlanMap.has(key)) {
                groupedPlanMap.set(key, [])
            }
            groupedPlanMap.get(key).push(item)
        })

        baseRows.forEach((row) => {
            const tableConfigs = groupedPlanMap.get(row.name) || []
            if (tableConfigs.length === 0) {
                row.planConfigId = null
                row.plan = 0
                row.done = 0
                row.remaining = 0
                row.rate = 0
                row.periodConfig = parsePeriodConfig(row.coverageType, getRealtimePeriodKey(row.coverageType))
                return
            }

            const latestConfig = tableConfigs[0]
            row.inspectionTableId = latestConfig.inspection_table_id || row.inspectionTableId
            row.coverageType = latestConfig.coverage_type || row.coverageType
            row.status = latestConfig.status || row.status

            const realtimePeriodKey = getRealtimePeriodKey(row.coverageType)
            const realtimeConfig = tableConfigs.find(
                (item) => item.coverage_type === row.coverageType && item.period_key === realtimePeriodKey
            )

            if (realtimeConfig) {
                applyPlanConfigToRow(row, realtimeConfig)
            } else {
                row.planConfigId = null
                row.plan = 0
                row.done = 0
                row.remaining = 0
                row.rate = 0
                row.periodConfig = parsePeriodConfig(row.coverageType, realtimePeriodKey)
            }
        })

        planRows.value = baseRows
        normalizeTaskBoardRowsToRealtimePeriod()

        if (!overviewSelectedTableName.value && planRows.value.length > 0) {
            overviewSelectedTableName.value = planRows.value[0].name
        }

        if (!selectedTemplateName.value && planRows.value.length > 0) {
            selectedTemplateName.value = planRows.value[0].name
        }
    } finally {
        isLoadingTaskBoard.value = false
    }
}

const mapOverviewStationRow = (item) => ({
    station_id: item.station_id,
    name: item.station_name,
    area: item.region || '-',
    planned: Boolean(item.is_included),
    done: item.completion_status === 'completed',
    doneDate: item.completed_at || '-',
    note: item.note || null
})

const mergePlanStationsWithCatalog = (catalogRows, planStationRows) => {
    const planMap = new Map(
        (planStationRows || []).map((item) => [
            item.station_id,
            mapOverviewStationRow(item)
        ])
    )

    return (catalogRows || []).map((catalogItem) => {
        const matched = planMap.get(catalogItem.station_id)
        if (matched) return matched
        return {
            ...catalogItem,
            planned: false,
            done: false,
            doneDate: '-',
            note: null
        }
    })
}

const loadOverviewData = async () => {
    const row = overviewSelectedTable.value
    if (!row?.inspectionTableId) {
        overviewRowsState.value = []
        return
    }

    isLoadingOverview.value = true
    activeOverviewFilterMenu.value = null
    overviewFilterPopoverStyle.value = {}
    overviewAreaFilter.value = 'all'
    overviewPlannedFilter.value = 'all'
    overviewDoneFilter.value = 'all'
    overviewAreaFilterSet.value = []
    overviewPlannedFilterSet.value = []
    overviewDoneFilterSet.value = []
    try {
        const targetPeriodKey = overviewSelectedPeriod.value || getCoverageConfigLabel(row)
        const params = new URLSearchParams({
            inspection_table_id: String(row.inspectionTableId),
            coverage_type: row.coverageType,
            period_key: targetPeriodKey
        })
        if (currentUserId) {
            params.set('user_id', currentUserId)
        }
        const payload = await requestJson(`/api/inspection-plan-overview?${params.toString()}`)
        overviewRowsState.value = (payload.item?.stations || []).map(mapOverviewStationRow)
    } catch {
        overviewRowsState.value = []
    } finally {
        isLoadingOverview.value = false
    }
}

const loadSelectedTemplateStations = async () => {
    const row = selectedTemplate.value
    if (!row?.inspectionTableId) {
        selectedTemplateStationsState.value = []
        return
    }

    try {
        const params = new URLSearchParams({
            inspection_table_id: String(row.inspectionTableId),
            coverage_type: row.coverageType,
            period_key: getCoverageConfigLabel(row)
        })
        if (currentUserId) {
            params.set('user_id', currentUserId)
        }
        const payload = await requestJson(`/api/inspection-plan-overview?${params.toString()}`)
        selectedTemplateStationsState.value = (payload.item?.stations || []).map(mapOverviewStationRow)
    } catch {
        selectedTemplateStationsState.value = []
    }
}

const openPlanDetail = async (row) => {
    detailCurrentPage.value = 1
    detailAreaFilter.value = 'all'
    detailPlannedFilter.value = 'all'
    detailDoneFilter.value = 'all'
    detailAreaFilterSet.value = []
    detailPlannedFilterSet.value = []
    detailDoneFilterSet.value = []
    activeFilterMenu.value = null
    filterPopoverStyle.value = {}
    const dialogRow = {
        ...row,
        periodConfig: { ...(row.periodConfig || {}) }
    }

    if (row.planConfigId) {
        try {
            const query = currentUserId ? `?user_id=${encodeURIComponent(currentUserId)}` : ''
            const payload = await requestJson(`/api/inspection-plan-configs/${row.planConfigId}${query}`)
            const item = payload.item || {}
            dialogRow.planConfigId = item.id || row.planConfigId
            dialogRow.inspectionTableId = item.inspection_table_id || row.inspectionTableId
            dialogRow.coverageType = item.coverage_type || row.coverageType
            dialogRow.periodConfig = parsePeriodConfig(item.coverage_type || row.coverageType, item.period_key)
            dialogRow.status = item.status || row.status

            detailDialog.value = {
                visible: true,
                row: dialogRow,
                rows: mergePlanStationsWithCatalog(allStationsCatalog.value, item.stations || [])
            }
            return
        } catch (error) {
            window.alert(error.message || '获取计划详情失败。')
        }
    }

    if (allStationsCatalog.value.length === 0) {
        window.alert('当前无法获取站点目录，请先确认后端站点接口是否可用。')
    }

    detailDialog.value = {
        visible: true,
        row: dialogRow,
        rows: allStationsCatalog.value.map((item) => ({ ...item }))
    }
}

const closePlanDetail = () => {
    detailCurrentPage.value = 1
    detailAreaFilter.value = 'all'
    detailPlannedFilter.value = 'all'
    detailDoneFilter.value = 'all'
    detailAreaFilterSet.value = []
    detailPlannedFilterSet.value = []
    detailDoneFilterSet.value = []
    activeFilterMenu.value = null
    filterPopoverStyle.value = {}
    detailDialog.value = {
        visible: false,
        row: null,
        rows: []
    }
}

const savePlanDetail = async () => {
    if (!isPlanManager) return
    const row = detailDialog.value.row
    if (!row?.inspectionTableId) {
        window.alert('当前检查表缺少 inspection_table_id，无法保存计划。')
        return
    }

    try {
        const periodKey = getPeriodKey(row)
        let planConfigId = row.planConfigId

        if (planConfigId) {
            await requestJson(`/api/inspection-plan-configs/${planConfigId}`, {
                method: 'PUT',
                body: JSON.stringify({
                    user_id: currentUserId,
                    coverage_type: row.coverageType,
                    period_key: periodKey,
                    status: row.status || 'draft',
                    remark: row.remark || ''
                })
            })
        } else {
            try {
                const payload = await requestJson('/api/inspection-plan-configs', {
                    method: 'POST',
                    body: JSON.stringify({
                        user_id: currentUserId,
                        inspection_table_id: row.inspectionTableId,
                        coverage_type: row.coverageType,
                        period_key: periodKey,
                        status: row.status || 'draft',
                        remark: row.remark || ''
                    })
                })
                planConfigId = payload.plan_config_id
            } catch (error) {
                const existingId = error?.existing_id || error?.payload?.existing_id
                if (existingId) {
                    planConfigId = existingId
                } else {
                    throw error
                }
            }
        }

        if (!planConfigId) {
            throw new Error('未能获取计划配置ID，无法保存站点明细。')
        }

        await requestJson(`/api/inspection-plan-configs/${planConfigId}/stations`, {
            method: 'PUT',
            body: JSON.stringify({
                user_id: currentUserId,
                stations: detailDialog.value.rows.map((item) => ({
                    station_id: item.station_id,
                    is_included: Boolean(item.planned),
                    note: item.note || ''
                }))
            })
        })

        await fetchPlanConfigs()
        const targetRow = planRows.value.find((item) => item.name === row.name)
        if (targetRow) {
            overviewSelectedTableName.value = targetRow.name
        }
        await Promise.all([loadOverviewData(), loadSelectedTemplateStations()])
        window.alert(`已保存【${row.name || '当前检查表'}】的计划配置。`)
        closePlanDetail()
    } catch (error) {
        window.alert(error.message || '保存计划配置失败。')
    }
}

const regenerateRouteBatches = () => {
    window.alert(`已按 ${getCoverageConfigLabel(selectedTemplate.value)} / ${selectedTemplate.value.name} 重新生成 ${routeStationCount.value} 站一组的出发建议样板。`)
}

watch(
    () => [overviewSelectedTable.value?.inspectionTableId, overviewSelectedTable.value?.coverageType, overviewSelectedPeriod.value],
    () => {
        loadOverviewData()
    }
)

watch(
    () => [selectedTemplate.value?.inspectionTableId, selectedTemplate.value?.coverageType, getCoverageConfigLabel(selectedTemplate.value)],
    () => {
        loadSelectedTemplateStations()
    }
)

watch(overviewRows, () => {
    overviewCurrentPage.value = 1
})

watch(filteredDetailRows, () => {
    detailCurrentPage.value = 1
})

onMounted(async () => {
    document.addEventListener('click', handleGlobalClickCloseFilterMenu)
    try {
        await Promise.all([fetchInspectionTablesCatalog(), fetchAllStationsCatalog()])
        await fetchPlanConfigs()
        if (overviewSelectedTable.value) {
            const options = overviewConfiguredPeriodOptions.value
            overviewSelectedPeriod.value = options[0] || getRealtimePeriodKey(overviewSelectedTable.value.coverageType)
        }
        await Promise.all([loadOverviewData(), loadSelectedTemplateStations()])
    } catch (error) {
        console.error('加载巡检计划页面失败：', error)
    }
})

onBeforeUnmount(() => {
    document.removeEventListener('click', handleGlobalClickCloseFilterMenu)
})

const openOverviewPlanDetail = () => {
    if (!overviewSelectedTable.value) return

    const row = {
        ...overviewSelectedTable.value,
        periodConfig: parsePeriodConfig(
            overviewSelectedTable.value.coverageType,
            overviewSelectedPeriod.value
        )
    }

    const matchedConfig = planConfigList.value.find(
        (item) =>
            item.inspection_table_id === row.inspectionTableId &&
            item.coverage_type === row.coverageType &&
            item.period_key === overviewSelectedPeriod.value
    )

    if (matchedConfig) {
        row.planConfigId = matchedConfig.id
        row.status = matchedConfig.status || row.status
    } else {
        row.planConfigId = null
    }

    openPlanDetail(row)
}

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

.month-picker-label {
    font-size: 13px;
    color: #64748b;
    font-weight: 700;
}

.month-picker-select {
    min-width: 140px;
    height: 38px;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 0 12px;
    background: #fff;
    color: #0f172a;
    font-size: 14px;
}

.plan-status-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 32px;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
}

.plan-status-chip.editable {
    background: #ecfdf5;
    color: #15803d;
}

.plan-status-chip.readonly {
    background: #fff7ed;
    color: #c2410c;
}

.plan-status-chip.published {
    background: #ecfdf5;
    color: #15803d;
}

.plan-status-chip.neutral {
    background: #eff6ff;
    color: #1d4ed8;
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
    overflow-y: visible;
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
    white-space: nowrap;
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

.route-helper-text {
    margin-top: 10px;
    font-size: 13px;
    line-height: 1.8;
    color: #64748b;
}

.route-helper-warning {
    margin-top: 10px;
    padding: 10px 12px;
    border-radius: 12px;
    background: #fff7ed;
    border: 1px solid #fed7aa;
    color: #c2410c;
    font-size: 13px;
    line-height: 1.8;
}

.table-sub {
    white-space: normal;
}

.coverage-select {
    min-width: 120px;
    height: 36px;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 0 10px;
    background: #fff;
    color: #0f172a;
    font-size: 13px;
}

.overview-toolbar {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
    margin-bottom: 16px;
}

.overview-field {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.overview-field-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: nowrap;
    min-height: 28px;
}

.overview-inline-tag {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 24px;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    line-height: 1.2;
    white-space: nowrap;
    margin-top: -1px;
}

.overview-inline-tag.info {
    background: #eff6ff;
    color: #1d4ed8;
}

.overview-inline-tag.neutral {
    background: #f1f5f9;
    color: #475569;
}

.overview-summary-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 16px;
}

.progress-cell {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 140px;
}

.progress-cell-wide {
    min-width: 180px;
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

.planner-table-select {
    width: 100%;
}

.field-label,
.pick-title {
    font-size: 13px;
    font-weight: 700;
    color: #64748b;
    margin-bottom: 10px;
    line-height: 1.2;
}

.route-control-panel {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}

.route-control-card {
    padding: 14px 16px;
    border-radius: 16px;
    border: 1px solid #dbe4ee;
    background: #f8fafc;
}

.route-count-select {
    width: 100%;
}

.route-origin-box {
    margin-top: 10px;
}

.route-origin-name {
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
}

.route-origin-coord {
    margin-top: 6px;
    font-size: 13px;
    line-height: 1.8;
    color: #64748b;
}

.route-batch-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.route-batch-card {
    padding: 14px 16px;
    border-radius: 16px;
    border: 1px solid #dbe4ee;
    background: #f8fafc;
}

.route-batch-head {
    margin-bottom: 12px;
}

.route-batch-title {
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
}

.route-batch-meta {
    margin-top: 6px;
    font-size: 13px;
    line-height: 1.8;
    color: #64748b;
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
    padding: 14px 16px;
    border-radius: 16px;
    border: 1px solid #dbe4ee;
    background: #f8fafc;
    display: flex;
    gap: 12px;
    align-items: flex-start;
}

.route-empty-state {
    padding: 14px 16px;
    border-radius: 16px;
    border: 1px dashed #cbd5e1;
    background: #f8fafc;
    color: #64748b;
    font-size: 13px;
    line-height: 1.8;
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

.plan-dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.46);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    z-index: 1200;
}

.plan-dialog {
    width: min(1100px, 100%);
    max-height: 88vh;
    overflow-x: visible;
    overflow-y: auto;
    padding: 24px;
}

.plan-dialog-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 18px;
    padding-bottom: 16px;
    border-bottom: 1px solid #e2e8f0;
}

.plan-dialog-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 10px 12px;
    margin-top: 12px;
}

.plan-dialog-meta span {
    display: inline-flex;
    align-items: center;
    min-height: 32px;
    padding: 6px 12px;
    border-radius: 999px;
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 12px;
    font-weight: 700;
}

.plan-dialog-body {
    display: flex;
    flex-direction: column;
    gap: 18px;
}

.plan-dialog-tip {
    padding: 14px 16px;
    border-radius: 16px;
    background: #f8fafc;
    border: 1px solid #dbe4ee;
    color: #0f172a;
    font-size: 14px;
    line-height: 1.8;
}

.plan-dialog-tip-text {
    margin-top: 6px;
    color: #64748b;
    font-size: 13px;
}

.plan-dialog-summary-row {
    margin-top: 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.plan-config-panel {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    padding: 14px 16px;
    border-radius: 16px;
    background: #f8fafc;
    border: 1px solid #dbe4ee;
}

.plan-config-field {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.detail-coverage-select,
.detail-period-select {
    width: 100%;
    min-width: 0;
}

.detail-period-flex {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
}

.detail-period-flex.two-columns {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
}

.detail-period-flex.one-column {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
}


.plan-status-chip.info {
    background: #eef4ff;
    color: #1d4ed8;
}

.plan-detail-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
}

.plan-detail-table th,
.plan-detail-table td {
    padding: 14px 12px;
    border-bottom: 1px solid #e2e8f0;
    text-align: left;
    vertical-align: middle;
    font-size: 14px;
    color: #0f172a;
}

.plan-detail-table th {
    font-size: 13px;
    color: #64748b;
    font-weight: 700;
    white-space: nowrap;
}

.plan-dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    flex-wrap: wrap;
}

.table-empty-cell {
    text-align: center;
    color: #64748b;
    font-size: 13px;
    padding: 18px 12px;
}

.table-pagination-bar {
    margin-top: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
}

.table-pagination-info {
    font-size: 13px;
    color: #64748b;
}

.table-pagination-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.plan-checkbox-wrap {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #0f172a;
    font-weight: 600;
}

.plan-checkbox-wrap.disabled {
    color: #94a3b8;
}

.plan-checkbox-wrap input[type="checkbox"] {
    width: 16px;
    height: 16px;
    cursor: pointer;
}

.plan-checkbox-wrap.disabled input[type="checkbox"] {
    cursor: not-allowed;
}

.table-header-inline {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 24px;
    white-space: nowrap;
}


.table-header-title {
    font-size: 13px;
    font-weight: 700;
    color: #64748b;
    line-height: 1.2;
}

.table-filter-mini-btn {
    position: absolute;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 18px;
    height: 18px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: 2px;
    cursor: pointer;
    padding: 0;
}

.table-filter-mini-btn:hover {
    background: #eff6ff;
}

.table-filter-popover {
    width: 240px;
    max-height: min(320px, 40vh);
    padding: 10px 0;
    border: 1px solid #dbe4ee;
    border-radius: 12px;
    background: #fff;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.16);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    overflow-x: hidden;
}

.table-filter-popover-teleported {
    position: fixed;
    z-index: 3000;
}

.table-header-inline-filterable {
    position: relative;
    display: inline-flex;
    align-items: center;
    padding-right: 26px;
}

.table-filter-option {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #0f172a;
    line-height: 1.4;
    cursor: pointer;
    padding: 8px 12px;
}

.table-filter-option input[type="checkbox"] {
    width: 14px;
    height: 14px;
}

.table-filter-popover::-webkit-scrollbar {
    width: 8px;
}

.table-filter-popover::-webkit-scrollbar-track {
    background: transparent;
}

.table-filter-popover::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 999px;
}

.table-filter-popover::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
}

.table-filter-icon-line {
    display: block;
    height: 2px;
    border-radius: 999px;
    background: #2563eb;
    opacity: 0.9;
}

.table-filter-icon-line.line-1 {
    width: 12px;
}

.table-filter-icon-line.line-2 {
    width: 8px;
}

.table-filter-icon-line.line-3 {
    width: 3px;
    height: 7px;
}


@media (max-width: 1200px) {
    .stats-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .content-grid {
        grid-template-columns: 1fr;
    }

    .route-control-panel {
        grid-template-columns: 1fr;
    }

    .overview-toolbar {
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

    .section-head,
    .header-actions {
        flex-direction: column;
        align-items: stretch;
    }


    .plan-config-panel {
        grid-template-columns: 1fr;
    }

    .detail-period-flex,
    .detail-period-flex.two-columns,
    .detail-period-flex.one-column {
        display: grid;
        grid-template-columns: 1fr;
    }

    .overview-field-head {
        align-items: flex-start;
        flex-direction: column;
        gap: 6px;
    }

    .month-picker-select,
    .table-filter-select {
        width: 100%;
        min-width: 0;
    }

    .plan-dialog-overlay {
        padding: 12px;
    }

    .plan-dialog {
        padding: 16px;
        max-height: 92vh;
    }

    .plan-dialog-header,
    .plan-dialog-actions {
        flex-direction: column;
        align-items: stretch;
    }

    .plan-detail-table th,
    .plan-detail-table td {
        white-space: nowrap;
    }

    .plan-dialog-summary-row {
        flex-direction: column;
        align-items: stretch;
    }

    .table-pagination-bar,
    .table-pagination-actions {
        flex-direction: column;
        align-items: stretch;
    }
}
</style>