<template>
  <div class="report-page">
    <section class="report-hero card-surface">
      <div>
        <div class="page-kicker">AI REPORT STUDIO</div>
        <h2>AI报告生成</h2>
        <p>选择报告类型和月份，由后台汇总巡检数据并调用 AI 完成报告分析。</p>
      </div>
      <div class="report-month-control">
        <label>
          <span>报告月份</span>
          <input v-model="selectedMonth" type="month" @change="handleReportContextChange" />
        </label>
        <button
          type="button"
          class="regenerate-report-btn"
          :disabled="loading || templateUnavailable || !canGenerateReports"
          :title="!canGenerateReports ? '当前账号只有查看权限' : ''"
          @click="startGeneration({ force: true })"
        >
          {{ templateUnavailable ? '模板待配置' : (canGenerateReports ? (hasReport ? '重新生成' : '生成报告') : '只读查看') }}
        </button>
        <button
          type="button"
          class="export-ppt-btn"
          :disabled="!hasReport || loading || templateUnavailable"
          :title="!hasReport ? '请先生成当前月份的报告' : '导出当前保存的报告快照'"
          @click="openExportDialog"
        >
          <span class="ppt-file-mark">P</span>
          {{ exportBusy ? `PPT生成中 ${exportTask?.progress || 0}%` : '导出PPT' }}
        </button>
        <small v-if="!canGenerateReports" class="report-readonly-note">
          当前账号可查看已有报告，生成权限需由管理员分配。
        </small>
      </div>
    </section>

    <section class="report-type-panel card-surface">
      <div class="report-type-panel-head">
        <div>
          <span>报告类型</span>
          <h3>选择本次需要生成的报告</h3>
        </div>
        <small>不同报告独立关联检查表和报告模板</small>
      </div>
      <div class="report-type-grid">
        <button
          v-for="item in reportTypes"
          :key="item.key"
          type="button"
          :class="['report-type-card', { active: selectedReportType === item.key, pending: !item.template_ready }]"
          @click="selectReportType(item.key)"
        >
          <span class="report-type-status">{{ item.template_ready ? '模板已配置' : '模板待配置' }}</span>
          <strong>{{ item.name }}</strong>
          <p>{{ item.description }}</p>
          <div class="report-type-sources">
            <span>关联检查表</span>
            <em v-for="tableName in item.target_tables" :key="`${item.key}-${tableName}`">{{ tableName }}</em>
          </div>
        </button>
      </div>
    </section>

    <section v-if="!templateUnavailable" class="report-source-panel card-surface">
      <div class="report-source-main">
        <div class="report-source-icon" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="report-source-copy">
          <span class="source-panel-kicker">DATA SOURCE</span>
          <div class="source-panel-title-row">
            <h3>本次报告数据来源</h3>
            <span :class="['source-mode-badge', sourceSelectionMode]">
              {{ sourceSelectionMode === 'custom' ? '自定义范围' : '全部可用站点' }}
            </span>
          </div>
          <p v-if="sourceLoading">正在核对当前月份可用于报告的站点数据...</p>
          <p v-else-if="sourceError" class="source-inline-error">{{ sourceError }}</p>
          <p v-else>
            {{ sourceSelectionDescription }}
          </p>
          <div v-if="sourceSelectionMode === 'custom' && selectedSourceStations.length" class="source-station-preview">
            <span
              v-for="station in selectedSourceStations.slice(0, 6)"
              :key="`source-preview-${station.station_id}`"
            >
              {{ station.station_name }}
            </span>
            <em v-if="selectedSourceStations.length > 6">
              另有 {{ selectedSourceStations.length - 6 }} 个
            </em>
          </div>
          <div v-if="sourceSelectionDirty" class="source-dirty-note">
            数据范围已调整，重新生成报告后生效。
          </div>
        </div>
      </div>
      <div class="report-source-actions">
        <div class="source-summary-grid">
          <div>
            <span>站点</span>
            <strong>{{ effectiveSourceSummary.station_count }}</strong>
          </div>
          <div>
            <span>片区</span>
            <strong>{{ effectiveSourceSummary.region_count }}</strong>
          </div>
          <div>
            <span>问题</span>
            <strong>{{ effectiveSourceSummary.issue_count }}</strong>
          </div>
        </div>
        <button
          type="button"
          class="source-configure-btn"
          :disabled="sourceLoading"
          @click="openSourceDialog"
        >
          {{ canGenerateReports ? '设置数据来源' : '查看数据来源' }}
        </button>
        <button
          v-if="canGenerateReports && sourceSelectionDirty"
          type="button"
          class="source-apply-generate-btn"
          :disabled="loading || sourceLoading"
          @click="startGeneration({ force: true })"
        >
          按此范围生成
        </button>
      </div>
    </section>

    <div v-if="error" class="state-card error">{{ error }}</div>

    <section v-if="templateUnavailable" class="template-placeholder card-surface">
      <div class="template-placeholder-mark">AI</div>
      <div>
        <span>模板预留</span>
        <h3>{{ currentReportType.name }}</h3>
        <p>关联检查表已经预留，报告章节和分析模板暂未配置，当前不会发起生成任务。</p>
      </div>
    </section>

    <section v-else-if="loading" class="ai-generation-state card-surface">
      <div class="ai-generation-visual" aria-hidden="true">
        <span class="ai-orbit orbit-one"></span>
        <span class="ai-orbit orbit-two"></span>
        <span class="ai-spark spark-one"></span>
        <span class="ai-spark spark-two"></span>
        <span class="ai-core">AI</span>
      </div>
      <div class="ai-generation-content">
        <div class="ai-generation-kicker">
          <span class="live-dot"></span>
          后台 AI 生成任务
        </div>
        <h3>{{ generationStageMessage }}</h3>
        <p>系统正在汇总真实巡检数据并调用 DeepSeek 生成分析内容。可以放心切换页面，后台任务不会中断。</p>
        <div class="ai-progress-head">
          <span>{{ currentReportType.name }}</span>
          <strong>{{ generationProgress }}%</strong>
        </div>
        <div class="ai-progress-track">
          <span :style="{ width: `${generationProgress}%` }"></span>
        </div>
        <div class="ai-stage-list">
          <span :class="{ done: generationProgress >= 12 }">读取数据</span>
          <span :class="{ done: generationProgress >= 38 }">汇总统计</span>
          <span :class="{ done: generationProgress >= 52 }">AI分析</span>
          <span :class="{ done: generationProgress >= 84 }">编排报告</span>
        </div>
      </div>
    </section>

    <section v-else-if="hasReport" class="report-document card-surface">
      <div class="report-document-head">
        <div class="report-title-block">
          <span class="doc-eyebrow">{{ report.month_label || '-' }}</span>
          <h1>{{ report.title || reportTitleFallback }}</h1>
        </div>
        <div class="report-context-grid" :class="{ 'single-context': !dataScopeNote }">
          <div v-if="dataScopeNote" class="report-data-scope-note">
            <div class="report-context-label">
              <span>01</span>
              <b>统计口径</b>
            </div>
            <p>{{ dataScopeNote }}</p>
          </div>
          <div class="doc-meta">
            <div class="report-context-label">
              <span>{{ dataScopeNote ? '02' : '01' }}</span>
              <b>数据来源</b>
            </div>
            <strong>{{ targetTableText }}</strong>
            <div class="report-generated-meta">
              <small>上次生成：{{ reportGeneratedAt }}</small>
              <small v-if="reportSnapshot.cached" class="snapshot-hint">当前展示上次生成结果</small>
            </div>
          </div>
        </div>
      </div>

      <template v-if="isQualityMeasurementReport">
      <div class="summary-cards">
        <article v-for="card in summaryCards" :key="card.label" class="summary-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.desc }}</small>
        </article>
      </div>

      <article class="chapter-card">
        <div class="chapter-banner">第一章　总体情况</div>
        <p class="chapter-lead">{{ report.overview_text || emptyOverviewText }}</p>

        <div class="report-table-wrap">
          <table class="report-table">
            <thead>
              <tr>
                <th rowspan="2">二级单位</th>
                <th rowspan="2">检查站点数量</th>
                <th colspan="2">发现问题数量</th>
                <th rowspan="2">单库、车、站问题数量</th>
              </tr>
              <tr>
                <th>一般性问题</th>
                <th>涉及禁止项问题</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!reportRows.length">
                <td colspan="5" class="empty-cell">当前月份暂无计量稽查问题数据。</td>
              </tr>
              <tr v-for="row in reportRows" :key="`${row.unit_type}-${row.unit_name}`">
                <td>
                  <div class="unit-cell">
                    <span :class="['unit-type-pill', row.unit_type]">{{ row.unit_type_label }}</span>
                    <strong>{{ row.unit_name }}</strong>
                  </div>
                </td>
                <td>{{ row.station_count }}</td>
                <td>{{ row.general_issue_count }}</td>
                <td>{{ row.prohibited_issue_count }}</td>
                <td>{{ row.total_issue_count }}</td>
              </tr>
              <tr class="total-row">
                <td>{{ totalRow.unit_name || '合计' }}</td>
                <td>{{ totalRow.station_count || 0 }}</td>
                <td>{{ totalRow.general_issue_count || 0 }}</td>
                <td>{{ totalRow.prohibited_issue_count || 0 }}</td>
                <td>{{ totalRow.total_issue_count || 0 }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="chapter-card">
        <div class="chapter-banner">第二章　检查发现-发现问题</div>
        <p class="chapter-lead">{{ chapterTwoText }}</p>
        <div class="finding-distribution-chart">
          <div class="finding-chart-head">
            <div>
              <span>问题板块分布</span>
              <strong>按业务流程统计</strong>
            </div>
            <div class="finding-chart-total">
              <strong>{{ findingSummary.total_issue_count || 0 }}</strong>
              <span>问题总数</span>
            </div>
          </div>

          <div v-if="businessFlowRows.length" class="finding-flow-list">
            <div
              v-for="(item, index) in businessFlowRows"
              :key="`finding-flow-${item.name}`"
              class="finding-flow-row"
              :style="{
                '--flow-color': getFindingFlowColor(index),
                '--flow-width': `${getFindingFlowWidth(item.count)}%`
              }"
            >
              <div class="finding-flow-label">
                <span>{{ String(index + 1).padStart(2, '0') }}</span>
                <strong>{{ item.name }}</strong>
              </div>
              <div class="finding-flow-track" aria-hidden="true">
                <span></span>
              </div>
              <div class="finding-flow-value">
                <strong>{{ item.count }}项</strong>
                <span>{{ formatPercent(item.percentage) }}</span>
              </div>
            </div>
          </div>
          <div v-else class="finding-chart-empty">当前月份暂无业务流程分布数据。</div>
        </div>
      </article>

      <article class="chapter-card">
        <div class="chapter-banner">第三章　检查发现-禁止项问题</div>
        <p class="chapter-note">
          系统从禁止项问题中优先按片区或控（参）股单位去重选取典型问题，最多展示 10 项。
        </p>
        <div class="report-table-wrap">
          <table class="report-table typical-table">
            <thead>
              <tr>
                <th>所属单位（片区/控参股单位）</th>
                <th>禁止项管理规定（具体问题描述）</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!prohibitedExamples.length">
                <td colspan="2" class="empty-cell">当前月份暂无可提取的禁止项典型问题。</td>
              </tr>
              <tr v-for="item in prohibitedExamples" :key="`prohibited-${item.issue_id}-${item.unit_name}`">
                <td>
                  <div class="unit-cell">
                    <span :class="['unit-type-pill', item.unit_type]">{{ item.unit_type_label }}</span>
                    <strong>{{ item.unit_name }}</strong>
                  </div>
                </td>
                <td class="text-cell">{{ item.description }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="chapter-card station-link-chapter">
        <div class="chapter-banner">第四章　检查发现-加油站环节</div>
        <p class="chapter-lead strong-lead">{{ stationLinkText }}</p>
        <h4 class="chart-title">分布条形图</h4>
        <div class="bar-chart" :style="{ '--chart-max': chartMax }">
          <div class="chart-grid">
            <span v-for="tick in chartTicks" :key="`tick-${tick}`" :style="{ bottom: `${(tick / chartMax) * 100}%` }">
              {{ tick }}
            </span>
          </div>
          <div class="chart-bars">
            <div v-for="item in businessFlowRows" :key="`flow-${item.name}`" class="chart-bar-item">
              <div class="bar-value">{{ item.count }}</div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ height: `${getBarHeight(item.count)}%` }"></div>
              </div>
              <div class="bar-label">{{ item.name }}</div>
              <div class="bar-percent">{{ formatPercent(item.percentage) }}</div>
            </div>
            <div v-if="!businessFlowRows.length" class="chart-empty">当前月份暂无业务流程分布数据。</div>
          </div>
        </div>
      </article>

      <article class="chapter-card">
        <div class="chapter-banner">第五章　各环节突出问题</div>
        <div class="content-source-row">
          <span>突出问题的筛选和概括会明确标注内容来源</span>
        </div>
        <section v-for="flow in flowHighlights" :key="`highlight-${flow.flow_name}`" class="flow-highlight-section">
          <div class="flow-highlight-head">
            <div class="flow-highlight-title">
              <h4>{{ flow.flow_name }}</h4>
              <AiContentBadge
                :generated="Boolean(flow.ai_generated)"
                ai-label="AI辅助筛选"
                fallback-label="规则筛选"
                compact
              />
            </div>
            <p>发现问题{{ flow.count || 0 }}项，突出问题{{ flow.highlight_count || 0 }}项：</p>
          </div>
          <p v-if="flow.summary" class="flow-highlight-summary">{{ flow.summary }}</p>
          <div v-if="flow.highlighted_issues?.length" class="highlight-issue-grid">
            <article v-for="issue in flow.highlighted_issues" :key="`highlight-issue-${flow.flow_name}-${issue.issue_id}`"
              class="highlight-issue-card">
              <div class="highlight-issue-text">
                <span>{{ issue.unit_name || '未设置单位' }}</span>
                <strong>{{ issue.station_name || '未命名站点' }}</strong>
                <p>{{ issue.description || '暂无问题描述' }}</p>
              </div>
              <button
                v-if="issue.issue_photo"
                type="button"
                class="highlight-photo is-clickable"
                @click="openImagePreview(issue.issue_photo, `${issue.station_name || '问题'}照片`)"
              >
                <img :src="resolveImage(issue.issue_photo)" alt="问题照片" />
              </button>
              <div v-else class="highlight-photo">
                <span>暂无照片</span>
              </div>
            </article>
          </div>
          <div v-else class="empty-highlight">当前环节暂无可展示的突出问题。</div>
        </section>
      </article>

      <article class="chapter-card trace-chapter">
        <div class="chapter-banner">第六章　管理追溯</div>
        <div class="content-source-row">
          <span>典型问题分析、结论和改进措施</span>
          <AiContentBadge
            :generated="Boolean(managementTrace.ai_generated)"
            ai-label="AI参与生成"
            fallback-label="规则生成"
          />
        </div>
        <div v-if="managementTrace.typical_issue" class="trace-problem-card">
          <span>典型问题</span>
          <strong>{{ formatStationIssue(managementTrace.typical_issue) }}</strong>
        </div>
        <div v-else class="trace-problem-card muted">
          <span>典型问题</span>
          <strong>当前月份暂无可追溯的典型问题。</strong>
        </div>

        <div class="trace-analysis-grid">
          <article>
            <span>（1）执行层面</span>
            <p>{{ managementTrace.execution_analysis || '-' }}</p>
          </article>
          <article>
            <span>（2）监督层面</span>
            <p>{{ managementTrace.supervision_analysis || '-' }}</p>
          </article>
          <article>
            <span>（3）管理层面</span>
            <p>{{ managementTrace.management_analysis || '-' }}</p>
          </article>
        </div>

        <div class="trace-conclusion-card">
          <h4>典型问题分析</h4>
          <p>{{ managementTrace.conclusion || '综上所述：当前月份暂无可分析的典型问题。' }}</p>
          <h4>改进措施</h4>
          <ol v-if="managementTrace.improvement_measures?.length">
            <li v-for="item in managementTrace.improvement_measures" :key="`${item.level}-${item.content}`">
              <strong>{{ item.level }}：</strong>{{ item.content }}
            </li>
          </ol>
          <p v-else>暂无改进措施。</p>
        </div>
      </article>

      <article class="chapter-card">
        <div class="chapter-banner">第七章　工作计划</div>
        <div class="content-source-row">
          <span>以本月问题分布与管理分析为依据生成</span>
          <AiContentBadge
            :generated="Boolean(deepAnalysis.work_plan_ai_generated)"
            ai-label="AI生成"
            fallback-label="规则生成"
          />
        </div>
        <div class="work-plan-list">
          <article v-for="(item, index) in workPlan" :key="`work-plan-${index}`" class="work-plan-card">
            <span>{{ index + 1 }}</span>
            <div>
              <div class="work-plan-title-row">
                <h4>{{ item.title }}</h4>
                <AiContentBadge
                  :generated="Boolean(item.ai_generated)"
                  ai-label="AI生成"
                  fallback-label="规则生成"
                  compact
                />
              </div>
              <p>{{ item.content }}</p>
            </div>
          </article>
        </div>
      </article>
      </template>

      <template v-else-if="isSafetyQualityReport">
        <div class="summary-cards safety-summary-cards">
          <article v-for="card in summaryCards" :key="card.label" class="summary-card">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.desc }}</small>
          </article>
        </div>

        <article class="chapter-card">
          <div class="chapter-banner">第一章　总体情况</div>
          <section
            v-for="section in safetySections"
            :key="`scope-${section.mode}`"
            class="safety-scope-section"
          >
            <div class="safety-section-head">
              <div>
                <span>{{ section.mode === 'video' ? 'VIDEO' : 'ON-SITE' }}</span>
                <h3>{{ section.label }}</h3>
              </div>
              <div class="safety-section-metrics">
                <span><b>{{ section.station_count || 0 }}</b>座站点</span>
                <span><b>{{ section.total_issue_count || 0 }}</b>项问题</span>
              </div>
            </div>
            <p class="chapter-lead safety-narrative">{{ section.narrative }}</p>

            <div class="safety-unit-chart-shell">
              <div class="safety-chart-legend">
                <span><i class="issue-series"></i>问题数量</span>
                <span><i class="station-series"></i>检查站点数量</span>
              </div>
              <div v-if="section.units?.length" class="safety-unit-chart-scroll">
                <div
                  class="safety-unit-chart"
                  :style="{ minWidth: getSafetyChartMinWidth(section) }"
                >
                  <div class="safety-unit-y-axis">
                    <span
                      v-for="tick in getSafetyUnitChartTicks(section)"
                      :key="`${section.mode}-unit-tick-${tick}`"
                    >{{ tick }}</span>
                  </div>
                  <div class="safety-unit-plot">
                    <span
                      v-for="tick in getSafetyUnitChartTicks(section)"
                      :key="`${section.mode}-grid-${tick}`"
                      class="safety-unit-grid-line"
                      :style="{ bottom: `${getSafetyUnitTickPosition(section, tick)}%` }"
                    ></span>
                    <div
                      v-for="unit in section.units"
                      :key="`${section.mode}-${unit.unit_type}-${unit.unit_name}`"
                      class="safety-unit-bar-group"
                    >
                      <div class="safety-unit-bars">
                        <div
                          class="safety-unit-bar issue-series"
                          :style="{ height: `${getSafetyUnitBarHeight(section, unit.issue_count)}%` }"
                        >
                          <span>{{ unit.issue_count }}</span>
                        </div>
                        <div
                          class="safety-unit-bar station-series"
                          :style="{ height: `${getSafetyUnitBarHeight(section, unit.station_count)}%` }"
                        >
                          <span>{{ unit.station_count }}</span>
                        </div>
                      </div>
                      <strong>{{ unit.unit_name }}</strong>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="safety-chart-empty">当前月份暂无可展示的单位统计数据。</div>
            </div>
          </section>
        </article>

        <article class="chapter-card">
          <div class="chapter-banner">第二章　检查发现-典型问题</div>
          <div class="content-source-row">
            <span>分别从视频和现场问题中识别高频、具有共性的典型问题</span>
            <AiContentBadge
              :generated="Boolean(safetyDeepAnalysis.ai_generated)"
              ai-label="AI辅助识别"
              fallback-label="规则筛选"
            />
          </div>
          <div class="safety-typical-grid">
            <article
              v-for="item in safetyTypicalFindings"
              :key="`safety-typical-${item.mode}`"
              class="safety-typical-card"
            >
              <div class="safety-typical-copy">
                <div class="safety-typical-title">
                  <span>{{ item.label }}</span>
                  <AiContentBadge
                    :generated="Boolean(item.ai_generated)"
                    ai-label="AI选取"
                    fallback-label="规则选取"
                    compact
                  />
                </div>
                <h3>{{ item.title }}</h3>
                <p>{{ buildSafetyTypicalText(item) }}</p>
                <small v-if="item.summary">{{ item.summary }}</small>
                <div v-if="item.representative_issue" class="safety-typical-example">
                  <b>{{ item.representative_issue.station_name || '未命名站点' }}</b>
                  <span>{{ item.representative_issue.description || '暂无问题描述' }}</span>
                </div>
              </div>
              <button
                v-if="item.representative_issue?.issue_photo"
                type="button"
                class="safety-typical-photo"
                @click="openImagePreview(
                  item.representative_issue.issue_photo,
                  `${item.representative_issue.station_name || item.title}问题照片`
                )"
              >
                <img :src="resolveImage(item.representative_issue.issue_photo)" alt="典型问题照片" />
                <span>点击查看完整照片</span>
              </button>
              <div v-else class="safety-typical-photo empty">
                <span>暂无问题照片</span>
              </div>
            </article>
          </div>
        </article>

        <article class="chapter-card">
          <div class="chapter-banner">第三章　问题数据统计分析</div>
          <section
            v-for="section in safetySections"
            :key="`category-${section.mode}`"
            class="safety-category-section"
          >
            <div class="safety-category-heading">
              <div>
                <span>{{ section.label }}</span>
                <h3>按“{{ section.category_field }}”分类</h3>
              </div>
              <strong>{{ section.total_issue_count || 0 }}项</strong>
            </div>
            <p class="chapter-lead safety-narrative">{{ section.category_text }}</p>
            <div v-if="section.category_distribution?.length" class="safety-category-list">
              <div
                v-for="(item, index) in section.category_distribution"
                :key="`${section.mode}-category-${item.name}`"
                class="safety-category-row"
                :style="{
                  '--category-color': getFindingFlowColor(index),
                  '--category-width': `${getSafetyCategoryWidth(section, item.count)}%`
                }"
              >
                <strong>{{ item.name }}</strong>
                <div class="safety-category-track"><span></span></div>
                <div>
                  <b>{{ item.count }}项</b>
                  <span>{{ formatPercent(item.percentage) }}</span>
                </div>
              </div>
            </div>
            <div v-else class="safety-chart-empty">当前分类暂无审核通过的问题数据。</div>
          </section>
        </article>

        <article class="chapter-card">
          <div class="chapter-banner">第四章　分类重点问题</div>
          <div class="content-source-row">
            <span>按视频“检查内容”和现场“检查主题”分别展示重点问题</span>
          </div>
          <section
            v-for="group in safetyHighlightGroups"
            :key="`highlight-group-${group.mode}`"
            class="safety-highlight-group"
          >
            <div class="safety-highlight-group-head">
              <span>{{ group.label }}</span>
              <strong>{{ group.items.length }}个分类</strong>
            </div>
            <div class="safety-highlight-list">
              <article
                v-for="item in group.items"
                :key="`${group.mode}-${item.category_name}`"
                class="safety-highlight-card"
              >
                <div class="safety-highlight-card-head">
                  <div>
                    <span>{{ item.category_count }}项问题</span>
                    <h4>{{ item.category_name }}</h4>
                  </div>
                  <AiContentBadge
                    :generated="Boolean(item.ai_generated)"
                    ai-label="AI选取"
                    fallback-label="规则选取"
                    compact
                  />
                </div>
                <p>{{ item.summary }}</p>
                <div class="safety-highlight-issues">
                  <div
                    v-for="issue in item.issues"
                    :key="`${item.mode}-${item.category_name}-${issue.issue_id}`"
                    class="safety-highlight-issue"
                  >
                    <div>
                      <b>{{ issue.station_name || '未命名站点' }}</b>
                      <span>{{ issue.description || '暂无问题描述' }}</span>
                    </div>
                    <button
                      v-if="issue.issue_photo"
                      type="button"
                      @click="openImagePreview(issue.issue_photo, `${issue.station_name || '重点问题'}照片`)"
                    >
                      <img :src="resolveImage(issue.issue_photo)" alt="重点问题照片" />
                    </button>
                  </div>
                </div>
              </article>
            </div>
          </section>
        </article>

        <article class="chapter-card">
          <div class="chapter-banner">第五章　问题分析</div>
          <div class="content-source-row">
            <span>结合视频扫站与四不两直现场检查数据综合分析</span>
            <AiContentBadge
              :generated="safetyProblemAnalysis.some((item) => item.ai_generated)"
              ai-label="AI生成"
              fallback-label="规则生成"
            />
          </div>
          <div class="safety-analysis-list">
            <article
              v-for="(item, index) in safetyProblemAnalysis"
              :key="`safety-analysis-${index}-${item.title}`"
            >
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <div>
                <h4>{{ item.title }}</h4>
                <p>{{ item.content }}</p>
              </div>
            </article>
          </div>
        </article>

        <article class="chapter-card">
          <div class="chapter-banner">第六章　工作建议</div>
          <div class="content-source-row">
            <span>依据本月高频问题、分类分布和原因分析形成</span>
            <AiContentBadge
              :generated="safetyWorkSuggestions.some((item) => item.ai_generated)"
              ai-label="AI生成"
              fallback-label="规则生成"
            />
          </div>
          <div class="work-plan-list safety-work-list">
            <article
              v-for="(item, index) in safetyWorkSuggestions"
              :key="`safety-work-${index}-${item.title}`"
              class="work-plan-card"
            >
              <span>{{ index + 1 }}</span>
              <div>
                <div class="work-plan-title-row">
                  <h4>{{ item.title }}</h4>
                  <AiContentBadge
                    :generated="Boolean(item.ai_generated)"
                    ai-label="AI生成"
                    fallback-label="规则生成"
                    compact
                  />
                </div>
                <p>{{ item.content }}</p>
              </div>
            </article>
          </div>
        </article>
      </template>

      <template v-else-if="isFinanceReport">
        <div class="summary-cards finance-summary-cards">
          <article v-for="card in summaryCards" :key="card.label" class="summary-card">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.desc }}</small>
          </article>
        </div>

        <article class="chapter-card">
          <div class="chapter-banner">第一章　总体情况</div>
          <p class="chapter-lead">{{ report.overview_text }}</p>
          <div class="finance-scope-strip">
            <div>
              <span>巡检时间范围</span>
              <strong>{{ financeSummary.date_range || '-' }}</strong>
            </div>
            <div>
              <span>巡检范围</span>
              <strong>{{ financeUnitRows.length }}个二级单位</strong>
            </div>
          </div>
          <p class="finance-scope-text">{{ report.scope_text }}</p>

          <div class="report-table-wrap finance-overview-table">
            <table class="report-table">
              <thead>
                <tr>
                  <th>二级单位</th>
                  <th>单位类型</th>
                  <th>检查站点</th>
                  <th>发现问题</th>
                  <th>各站问题数量</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!financeUnitRows.length">
                  <td colspan="5" class="empty-cell">当前月份暂无财务检查审核通过问题。</td>
                </tr>
                <tr v-for="unit in financeUnitRows" :key="`finance-unit-${unit.unit_type}-${unit.unit_name}`">
                  <td><strong>{{ unit.unit_name }}</strong></td>
                  <td>
                    <span :class="['unit-type-pill', unit.unit_type]">{{ unit.unit_type_label }}</span>
                  </td>
                  <td>{{ unit.station_count }}座</td>
                  <td>{{ unit.issue_count }}项</td>
                  <td class="finance-station-breakdown-cell">
                    <span
                      v-for="station in unit.station_breakdown"
                      :key="`${unit.unit_name}-${station.station_id || station.station_name}`"
                    >
                      {{ station.station_name }} {{ station.issue_count }}项
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <section class="finance-chart-section">
            <div class="finance-subsection-head">
              <div>
                <span>UNIT OVERVIEW</span>
                <h3>片区与控（参）股单位检查情况</h3>
              </div>
              <div class="safety-chart-legend">
                <span><i class="issue-series"></i>问题数量</span>
                <span><i class="station-series"></i>检查站点数量</span>
              </div>
            </div>
            <div v-if="financeUnitRows.length" class="safety-unit-chart-scroll">
              <div
                class="safety-unit-chart"
                :style="{ minWidth: getSafetyChartMinWidth(financeOverviewSection) }"
              >
                <div class="safety-unit-y-axis">
                  <span
                    v-for="tick in getSafetyUnitChartTicks(financeOverviewSection)"
                    :key="`finance-unit-tick-${tick}`"
                  >{{ tick }}</span>
                </div>
                <div class="safety-unit-plot">
                  <span
                    v-for="tick in getSafetyUnitChartTicks(financeOverviewSection)"
                    :key="`finance-unit-grid-${tick}`"
                    class="safety-unit-grid-line"
                    :style="{ bottom: `${getSafetyUnitTickPosition(financeOverviewSection, tick)}%` }"
                  ></span>
                  <div
                    v-for="unit in financeUnitRows"
                    :key="`finance-bar-${unit.unit_type}-${unit.unit_name}`"
                    class="safety-unit-bar-group"
                  >
                    <div class="safety-unit-bars">
                      <div
                        class="safety-unit-bar issue-series"
                        :style="{ height: `${getSafetyUnitBarHeight(financeOverviewSection, unit.issue_count)}%` }"
                      ><span>{{ unit.issue_count }}</span></div>
                      <div
                        class="safety-unit-bar station-series"
                        :style="{ height: `${getSafetyUnitBarHeight(financeOverviewSection, unit.station_count)}%` }"
                      ><span>{{ unit.station_count }}</span></div>
                    </div>
                    <strong>{{ unit.unit_name }}</strong>
                    <small>{{ unit.percentage }}%</small>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="safety-chart-empty">当前月份暂无单位分布数据。</div>
          </section>

          <div class="finance-distribution-grid">
            <section
              v-for="distribution in financeDistributions"
              :key="distribution.key"
              class="finance-distribution-card"
            >
              <div class="finance-subsection-head">
                <div>
                  <span>{{ distribution.eyebrow }}</span>
                  <h3>{{ distribution.title }}</h3>
                </div>
                <strong>{{ distribution.items.length }}类</strong>
              </div>
              <p>{{ distribution.text }}</p>
              <div v-if="distribution.items.length" class="safety-category-list">
                <div
                  v-for="item in distribution.items"
                  :key="`${distribution.key}-${item.name}`"
                  class="safety-category-row"
                >
                  <strong>{{ item.name }}</strong>
                  <div class="safety-category-track">
                    <span :style="{ width: `${getFinanceCategoryWidth(distribution.items, item.count)}%` }"></span>
                  </div>
                  <div><b>{{ item.count }}项</b><span>{{ formatPercent(item.percentage) }}</span></div>
                </div>
              </div>
              <div v-else class="safety-chart-empty">当前分类暂无审核通过的问题数据。</div>
            </section>
          </div>
        </article>

        <article class="chapter-card">
          <div class="chapter-banner">第二章　各站结果通报</div>
          <p class="chapter-note">按所属单位和站点归纳全部审核通过问题，检查时间、项目和关键环节均取自巡检原始记录。</p>
          <div class="finance-station-report-list">
            <section
              v-for="(station, stationIndex) in financeStationReports"
              :key="`finance-station-${station.station_id || station.station_name}`"
              class="finance-station-report"
            >
              <div class="finance-station-report-head">
                <div>
                  <span>{{ String(stationIndex + 1).padStart(2, '0') }}</span>
                  <div>
                    <h3>{{ station.station_name }}</h3>
                    <p>{{ station.unit_name }} · {{ station.date_range }}</p>
                  </div>
                </div>
                <strong>{{ station.issue_count }}项问题</strong>
              </div>
              <div class="report-table-wrap">
                <table class="report-table finance-issue-table">
                  <thead>
                    <tr>
                      <th>检查时间</th>
                      <th>项目</th>
                      <th>关键环节</th>
                      <th>管理规范</th>
                      <th>问题描述</th>
                      <th>问题照片</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="issue in station.issues" :key="`finance-station-issue-${issue.issue_id}`">
                      <td>{{ issue.report_date || '-' }}</td>
                      <td>{{ issue.project || '-' }}</td>
                      <td>{{ issue.key_link || '-' }}</td>
                      <td class="text-cell">{{ issue.management_standard || '-' }}</td>
                      <td class="text-cell">{{ issue.description || '-' }}</td>
                      <td>
                        <button
                          v-if="issue.issue_photo"
                          type="button"
                          class="finance-photo-button"
                          @click="openImagePreview(issue.issue_photo, `${station.station_name}问题照片`)"
                        >
                          <img :src="resolveImage(issue.issue_photo)" alt="问题照片" loading="lazy" />
                        </button>
                        <span v-else>-</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
            <div v-if="!financeStationReports.length" class="safety-chart-empty">当前月份暂无可通报的站点问题。</div>
          </div>
        </article>

        <article class="chapter-card">
          <div class="chapter-banner">第三章　检查结果分析与检查内容建议</div>
          <div class="content-source-row">
            <span>围绕检查项目、关键环节和审核通过问题综合生成</span>
            <AiContentBadge
              :generated="Boolean(financeDeepAnalysis.ai_generated)"
              ai-label="AI生成"
              fallback-label="规则生成"
            />
          </div>
          <div class="finance-ai-grid">
            <section class="finance-ai-panel">
              <div class="finance-ai-panel-head">
                <span>01</span>
                <div><small>RESULT ANALYSIS</small><h3>检查结果分析</h3></div>
              </div>
              <article
                v-for="(item, index) in financeResultAnalysis"
                :key="`finance-analysis-${index}-${item.title}`"
                class="finance-ai-item"
              >
                <div class="finance-ai-item-title">
                  <h4>{{ item.title }}</h4>
                  <AiContentBadge :generated="Boolean(item.ai_generated)" ai-label="AI生成" fallback-label="规则生成" compact />
                </div>
                <p>{{ item.content }}</p>
                <div v-if="item.related_issues?.length" class="finance-related-issues">
                  <span
                    v-for="issue in item.related_issues"
                    :key="`finance-related-${index}-${issue.issue_id}`"
                  >{{ issue.station_name }} · {{ issue.description }}</span>
                </div>
              </article>
            </section>
            <section class="finance-ai-panel suggestion">
              <div class="finance-ai-panel-head">
                <span>02</span>
                <div><small>CHECK SUGGESTIONS</small><h3>检查内容建议</h3></div>
              </div>
              <article
                v-for="(item, index) in financeContentSuggestions"
                :key="`finance-suggestion-${index}-${item.title}`"
                class="finance-ai-item"
              >
                <div class="finance-ai-item-title">
                  <h4>{{ item.title }}</h4>
                  <AiContentBadge :generated="Boolean(item.ai_generated)" ai-label="AI生成" fallback-label="规则生成" compact />
                </div>
                <p>{{ item.content }}</p>
                <div class="finance-focus-tags">
                  <span v-for="name in item.focus_projects" :key="`focus-project-${index}-${name}`">{{ name }}</span>
                  <span v-for="name in item.focus_key_links" :key="`focus-link-${index}-${name}`">{{ name }}</span>
                </div>
              </article>
            </section>
          </div>
        </article>
      </template>

      <template v-else-if="isOnSiteServiceReport">
        <div class="summary-cards service-summary-cards">
          <article v-for="card in summaryCards" :key="card.label" class="summary-card">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.desc }}</small>
          </article>
        </div>

        <article class="chapter-card service-chapter">
          <div class="chapter-banner">第一章　{{ reportMonthNumber }}月检查基本情况</div>
          <p class="chapter-lead">{{ report.overview_text }}</p>
          <div class="service-mode-overview-grid">
            <article v-for="mode in serviceModeSummaries" :key="`service-overview-${mode.mode}`">
              <div :class="['service-mode-mark', mode.mode]">{{ mode.mode === 'video' ? 'VIDEO' : 'ON SITE' }}</div>
              <div>
                <span>{{ mode.label }}</span>
                <strong>{{ mode.station_count }}座站点</strong>
                <p>{{ mode.issue_count }}项问题 · 站均{{ Number(mode.average_issue_count || 0).toFixed(1) }}项</p>
              </div>
            </article>
          </div>
        </article>

        <article class="chapter-card service-chapter">
          <div class="chapter-banner">第二章　{{ reportMonthNumber }}月检查基本情况-单位问题对比</div>
          <div class="service-section-intro">
            <div>
              <span>UNIT COMPARISON</span>
              <h3>各片区及股权单位问题数量与站均问题数量</h3>
            </div>
            <strong>{{ serviceUnitRows.length }}个单位</strong>
          </div>
          <div v-if="serviceUnitRows.length" class="service-unit-comparison">
            <article v-for="unit in serviceUnitRows" :key="`service-unit-${unit.unit_type}-${unit.unit_name}`">
              <div class="service-unit-name">
                <small>{{ unit.unit_type_label }}</small>
                <strong>{{ unit.unit_name }}</strong>
                <span>{{ unit.station_count }}座站点</span>
              </div>
              <div class="service-unit-bars">
                <div>
                  <span>问题总数</span>
                  <div><i class="issue" :style="{ width: `${getServiceUnitBarWidth('issue_count', unit.issue_count)}%` }"></i></div>
                  <b>{{ unit.issue_count }}</b>
                </div>
                <div>
                  <span>站均问题</span>
                  <div><i class="average" :style="{ width: `${getServiceUnitBarWidth('average_issue_count', unit.average_issue_count)}%` }"></i></div>
                  <b>{{ Number(unit.average_issue_count || 0).toFixed(1) }}</b>
                </div>
              </div>
            </article>
          </div>
          <div v-else class="safety-chart-empty">当前月份暂无可用于单位对比的巡检数据。</div>
        </article>

        <article class="chapter-card service-chapter">
          <div class="chapter-banner">第三章　{{ reportMonthNumber }}月检查基本情况-上月整改情况</div>
          <p class="chapter-lead">{{ servicePreviousRectification.narrative }}</p>
          <div class="service-rectification-legend">
            <span><i class="unreceived"></i>未签收</span>
            <span><i class="pending"></i>未整改</span>
            <span><i class="rectified"></i>已整改</span>
          </div>
          <div v-if="serviceRectificationRows.length" class="service-rectification-grid">
            <article v-for="unit in serviceRectificationRows" :key="`service-rectification-${unit.unit_type}-${unit.unit_name}`">
              <div>
                <small>{{ unit.unit_type_label }}</small>
                <strong>{{ unit.unit_name }}</strong>
                <span>共{{ unit.total_count }}项</span>
              </div>
              <div class="service-rectification-counts">
                <span class="unreceived"><b>{{ unit.unreceived_count }}</b>未签收</span>
                <span class="pending"><b>{{ unit.pending_count }}</b>未整改</span>
                <span class="rectified"><b>{{ unit.rectified_count }}</b>已整改</span>
              </div>
              <div class="service-stacked-track" aria-hidden="true">
                <i class="unreceived" :style="{ width: `${getRectificationWidth(unit, 'unreceived_count')}%` }"></i>
                <i class="pending" :style="{ width: `${getRectificationWidth(unit, 'pending_count')}%` }"></i>
                <i class="rectified" :style="{ width: `${getRectificationWidth(unit, 'rectified_count')}%` }"></i>
              </div>
            </article>
          </div>
          <div v-else class="safety-chart-empty">上月暂无可统计的整改数据。</div>
        </article>

        <article class="chapter-card service-chapter">
          <div class="chapter-banner">第四章　{{ reportMonthNumber }}月检查基本情况-片区汇总</div>
          <section v-for="mode in serviceModeSummaries" :key="`service-mode-${mode.mode}`" class="service-mode-section">
            <div class="service-section-intro">
              <div>
                <span>{{ mode.mode === 'video' ? 'VIDEO INSPECTION' : 'ON-SITE INSPECTION' }}</span>
                <h3>{{ mode.label }}片区汇总</h3>
              </div>
              <strong>站均{{ Number(mode.average_issue_count || 0).toFixed(1) }}项</strong>
            </div>
            <p>{{ mode.narrative }}</p>
            <div v-if="mode.units?.length" class="service-average-chart">
              <article v-for="unit in mode.units" :key="`service-mode-unit-${mode.mode}-${unit.unit_name}`">
                <strong>{{ unit.unit_name }}</strong>
                <div><span :style="{ width: `${getServiceModeAverageWidth(mode, unit.average_issue_count)}%` }"></span></div>
                <b>{{ Number(unit.average_issue_count || 0).toFixed(1) }}</b>
              </article>
            </div>
            <div v-else class="safety-chart-empty">当前模式暂无片区汇总数据。</div>
          </section>
        </article>

        <article class="chapter-card service-chapter">
          <div class="chapter-banner">第五章　{{ reportMonthNumber }}月检查基本情况-分环节汇总</div>
          <section v-for="section in serviceCategorySections" :key="`service-category-${section.mode}`" class="service-category-section">
            <div class="service-section-intro">
              <div>
                <span>{{ section.mode === 'video' ? 'VIDEO CATEGORY' : 'ON-SITE CATEGORY' }}</span>
                <h3>{{ section.label }}分环节统计</h3>
              </div>
              <strong>{{ section.total_issue_count }}项问题</strong>
            </div>
            <p>{{ section.narrative }}</p>
            <div v-if="section.items?.length" class="service-category-grid">
              <article v-for="item in section.items" :key="`service-category-${section.mode}-${item.name}`">
                <div class="service-category-head">
                  <strong>{{ item.name }}</strong>
                  <span>{{ item.count }}项 · {{ formatPercent(item.percentage) }}</span>
                </div>
                <div class="service-category-track">
                  <i :style="{ width: `${getServiceCategoryWidth(section, item.count)}%` }"></i>
                </div>
                <div class="service-category-children">
                  <span v-for="child in item.children" :key="`service-child-${section.mode}-${item.name}-${child.name}`">
                    <b>{{ child.name }}</b>
                    <em>{{ child.count }}</em>
                  </span>
                </div>
              </article>
            </div>
            <div v-else class="safety-chart-empty">当前模式暂无分类问题。</div>
          </section>
        </article>

        <article class="chapter-card service-chapter">
          <div class="chapter-banner">第六章　各片区问题分析</div>
          <div class="content-source-row">
            <span>按单位与四大服务板块筛选突出问题，原始描述和照片均来自巡检问题</span>
            <AiContentBadge
              :generated="Boolean(serviceDeepAnalysis.ai_generated)"
              ai-label="AI生成"
              fallback-label="规则生成"
            />
          </div>
          <div class="service-region-analysis-list">
            <article v-for="unit in serviceUnitAnalyses" :key="`service-analysis-${unit.unit_type}-${unit.unit_name}`" class="service-region-analysis">
              <header>
                <div>
                  <small>{{ unit.unit_type_label }}</small>
                  <h3>{{ unit.unit_name }}</h3>
                  <p>涉及{{ unit.station_names?.length || 0 }}座站点，共{{ unit.issue_count }}项问题</p>
                </div>
                <span>{{ unit.service_areas?.length || 0 }}个板块</span>
              </header>
              <section v-for="area in unit.service_areas" :key="`service-area-${unit.unit_name}-${area.service_area}`" class="service-area-analysis">
                <div class="service-area-head">
                  <div>
                    <span>{{ area.service_area }}</span>
                    <strong>发现问题{{ area.issue_count }}项</strong>
                  </div>
                  <AiContentBadge :generated="Boolean(area.ai_generated)" ai-label="AI筛选" fallback-label="规则筛选" compact />
                </div>
                <p>{{ area.summary }}</p>
                <div class="service-highlight-grid">
                  <article v-for="(highlight, highlightIndex) in area.highlights" :key="`service-highlight-${unit.unit_name}-${area.service_area}-${highlightIndex}`">
                    <div class="service-highlight-title">
                      <span>{{ highlightIndex + 1 }}</span>
                      <div>
                        <h4>{{ highlight.title }}</h4>
                        <p>{{ highlight.analysis }}</p>
                      </div>
                    </div>
                    <div class="service-highlight-issues">
                      <div v-for="issue in highlight.issues" :key="`service-highlight-issue-${issue.issue_id}`">
                        <div>
                          <strong>{{ issue.station_name }}</strong>
                          <span>{{ issue.description }}</span>
                        </div>
                        <button
                          v-if="issue.issue_photo"
                          type="button"
                          @click="openImagePreview(issue.issue_photo, `${issue.station_name}问题照片`)"
                        >
                          <img :src="resolveImage(issue.issue_photo)" :alt="`${issue.station_name}问题照片`" />
                        </button>
                      </div>
                    </div>
                  </article>
                </div>
              </section>
            </article>
            <div v-if="!serviceUnitAnalyses.length" class="safety-chart-empty">当前月份暂无可用于片区问题分析的数据。</div>
          </div>
        </article>

        <article class="chapter-card service-chapter">
          <div class="chapter-banner">第七章　问题总结</div>
          <div class="content-source-row">
            <span>结合视频、现场、单位分布与高频问题综合分析</span>
            <AiContentBadge
              :generated="serviceProblemSummary.some((item) => item.ai_generated)"
              ai-label="AI生成"
              fallback-label="规则生成"
            />
          </div>
          <div class="service-summary-list">
            <article v-for="(item, index) in serviceProblemSummary" :key="`service-summary-${index}-${item.title}`">
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <div>
                <div class="service-ai-title">
                  <h4>{{ item.title }}</h4>
                  <AiContentBadge :generated="Boolean(item.ai_generated)" ai-label="AI生成" fallback-label="规则生成" compact />
                </div>
                <p>{{ item.content }}</p>
              </div>
            </article>
          </div>
        </article>

        <article class="chapter-card service-chapter">
          <div class="chapter-banner">第八章　下一步建议</div>
          <div class="content-source-row">
            <span>依据本月问题分布、突出问题和整改情况生成</span>
            <AiContentBadge
              :generated="serviceNextSteps.some((item) => item.ai_generated)"
              ai-label="AI生成"
              fallback-label="规则生成"
            />
          </div>
          <div class="work-plan-list service-work-list">
            <article v-for="(item, index) in serviceNextSteps" :key="`service-next-${index}-${item.title}`" class="work-plan-card">
              <span>{{ index + 1 }}</span>
              <div>
                <div class="work-plan-title-row">
                  <h4>{{ item.title }}</h4>
                  <AiContentBadge :generated="Boolean(item.ai_generated)" ai-label="AI生成" fallback-label="规则生成" compact />
                </div>
                <p>{{ item.content }}</p>
              </div>
            </article>
          </div>
        </article>
      </template>

      <template v-else-if="isEquipmentFacilitiesReport">
        <div class="summary-cards equipment-summary-cards">
          <article v-for="card in summaryCards" :key="card.label" class="summary-card">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.desc }}</small>
          </article>
        </div>

        <article class="chapter-card">
          <div class="chapter-banner">第一章　总体情况</div>
          <p class="chapter-lead">{{ report.overview_text }}</p>

          <section class="equipment-overview-section">
            <div class="equipment-subsection-head">
              <div>
                <span>01 · REGION VIEW</span>
                <h3>按片区划分</h3>
              </div>
              <strong>{{ equipmentRegionRows.length }}个片区及管理单位</strong>
            </div>
            <p class="equipment-section-text">{{ report.region_text }}</p>
            <div class="equipment-chart-legend">
              <span><i class="station"></i>受检站点数量</span>
              <span><i class="issue"></i>发现问题数量</span>
              <span><i class="average"></i>平均问题数量</span>
            </div>
            <div v-if="equipmentRegionRows.length" class="equipment-region-chart">
              <article
                v-for="row in equipmentRegionRows"
                :key="`equipment-region-${row.unit_type}-${row.unit_name}`"
                class="equipment-region-row"
              >
                <div class="equipment-region-name">
                  <span :class="['unit-type-pill', row.unit_type]">
                    {{ row.unit_type === 'holding' ? '控（参）股单位' : '管理片区' }}
                  </span>
                  <strong>{{ row.unit_name }}</strong>
                </div>
                <div class="equipment-region-bars">
                  <div>
                    <span class="station" :style="{ width: `${getEquipmentRegionBarWidth('station_count', row.station_count)}%` }"></span>
                    <b>{{ row.station_count }}座</b>
                  </div>
                  <div>
                    <span class="issue" :style="{ width: `${getEquipmentRegionBarWidth('issue_count', row.issue_count)}%` }"></span>
                    <b>{{ row.issue_count }}项</b>
                  </div>
                </div>
                <div class="equipment-average-value">
                  <strong>{{ Number(row.average_issue_count || 0).toFixed(1) }}</strong>
                  <span>项/站</span>
                </div>
              </article>
            </div>
            <div v-else class="safety-chart-empty">当前月份暂无片区统计数据。</div>
          </section>

          <section class="equipment-overview-section station-view">
            <div class="equipment-subsection-head">
              <div>
                <span>02 · STATION RANKING</span>
                <h3>按站点划分</h3>
              </div>
              <strong>按问题数量由高到低</strong>
            </div>
            <div v-if="equipmentStationRanking.length" class="equipment-station-ranking">
              <article
                v-for="station in equipmentStationRanking"
                :key="`equipment-station-${station.station_id || station.station_name}`"
                :class="{ 'top-rank': station.rank <= 3 }"
              >
                <span class="equipment-rank-number">{{ String(station.rank).padStart(2, '0') }}</span>
                <div class="equipment-station-copy">
                  <strong>{{ station.station_name }}</strong>
                  <small>{{ station.management_unit }} · {{ station.date_range }}</small>
                </div>
                <div class="equipment-station-track">
                  <span :style="{ width: `${getEquipmentStationBarWidth(station.issue_count)}%` }"></span>
                </div>
                <b>{{ station.issue_count }}项</b>
              </article>
            </div>
            <div v-else class="safety-chart-empty">当前月份暂无已完成受检站点。</div>
          </section>
        </article>

        <article class="chapter-card">
          <div class="chapter-banner">第二章　问题数据统计分析</div>
          <div class="equipment-distribution-grid">
            <section
              v-for="distribution in equipmentDistributions"
              :key="distribution.key"
              class="equipment-distribution-card"
            >
              <div class="equipment-subsection-head">
                <div>
                  <span>{{ distribution.eyebrow }}</span>
                  <h3>{{ distribution.title }}</h3>
                </div>
                <strong>{{ distribution.items.length }}类</strong>
              </div>
              <p>{{ distribution.text }}</p>
              <div v-if="distribution.items.length" class="safety-category-list">
                <div
                  v-for="item in distribution.items"
                  :key="`${distribution.key}-${item.name}`"
                  class="safety-category-row equipment-category-row"
                >
                  <strong>{{ item.name }}</strong>
                  <div class="safety-category-track">
                    <span :style="{ width: `${getFinanceCategoryWidth(distribution.items, item.count)}%` }"></span>
                  </div>
                  <div><b>{{ item.count }}项</b><span>{{ formatPercent(item.percentage) }}</span></div>
                </div>
              </div>
              <div v-else class="safety-chart-empty">当前分类暂无审核通过的问题数据。</div>
            </section>
          </div>
        </article>

        <article class="chapter-card">
          <div class="chapter-banner">第三章　检查发现-典型问题</div>
          <div class="content-source-row">
            <span>从跨站重复出现的高频问题中选择代表性问题</span>
            <AiContentBadge
              :generated="Boolean(equipmentTypicalFinding.ai_generated)"
              ai-label="AI筛选"
              fallback-label="规则筛选"
            />
          </div>
          <div v-if="equipmentTypicalFinding.issue_count" class="equipment-typical-card">
            <div class="equipment-typical-copy">
              <div class="equipment-typical-title">
                <span>高频典型问题</span>
                <h3>{{ equipmentTypicalFinding.title }}</h3>
              </div>
              <p>{{ buildEquipmentTypicalText(equipmentTypicalFinding) }}</p>
              <blockquote v-if="equipmentTypicalFinding.summary">{{ equipmentTypicalFinding.summary }}</blockquote>
              <div v-if="equipmentTypicalFinding.representative_issue" class="equipment-typical-example">
                <span>代表问题</span>
                <strong>{{ equipmentTypicalFinding.representative_issue.station_name }}</strong>
                <p>{{ equipmentTypicalFinding.representative_issue.description }}</p>
                <small>
                  {{ equipmentTypicalFinding.representative_issue.area_name }} ·
                  {{ equipmentTypicalFinding.representative_issue.inspection_item }}
                </small>
              </div>
            </div>
            <button
              v-if="equipmentTypicalFinding.representative_issue?.issue_photo"
              type="button"
              class="equipment-typical-photo"
              @click="openImagePreview(
                equipmentTypicalFinding.representative_issue.issue_photo,
                `${equipmentTypicalFinding.representative_issue.station_name || '典型问题'}照片`
              )"
            >
              <img
                :src="resolveImage(equipmentTypicalFinding.representative_issue.issue_photo)"
                alt="典型问题照片"
                loading="lazy"
              />
              <span>点击查看原图</span>
            </button>
            <div v-else class="equipment-typical-photo empty">暂无问题照片</div>
          </div>
          <div v-else class="safety-chart-empty">当前月份暂无可用于典型问题分析的数据。</div>
        </article>

        <article class="chapter-card">
          <div class="chapter-banner">第四章　问题分析</div>
          <div class="content-source-row">
            <span>结合所属区域、检查事项和高频问题综合分析</span>
            <AiContentBadge
              :generated="equipmentProblemAnalysis.some((item) => item.ai_generated)"
              ai-label="AI生成"
              fallback-label="规则生成"
            />
          </div>
          <div class="safety-analysis-list equipment-analysis-list">
            <article
              v-for="(item, index) in equipmentProblemAnalysis"
              :key="`equipment-analysis-${index}-${item.title}`"
            >
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <div>
                <div class="equipment-analysis-title">
                  <h4>{{ item.title }}</h4>
                  <AiContentBadge :generated="Boolean(item.ai_generated)" ai-label="AI生成" fallback-label="规则生成" compact />
                </div>
                <p>{{ item.content }}</p>
              </div>
            </article>
          </div>
        </article>

        <article class="chapter-card">
          <div class="chapter-banner">第五章　工作建议</div>
          <div class="content-source-row">
            <span>依据问题分布、典型问题和原因分析形成</span>
            <AiContentBadge
              :generated="equipmentWorkSuggestions.some((item) => item.ai_generated)"
              ai-label="AI生成"
              fallback-label="规则生成"
            />
          </div>
          <div class="work-plan-list equipment-work-list">
            <article
              v-for="(item, index) in equipmentWorkSuggestions"
              :key="`equipment-work-${index}-${item.title}`"
              class="work-plan-card"
            >
              <span>{{ index + 1 }}</span>
              <div>
                <div class="work-plan-title-row">
                  <h4>{{ item.title }}</h4>
                  <AiContentBadge :generated="Boolean(item.ai_generated)" ai-label="AI生成" fallback-label="规则生成" compact />
                </div>
                <p>{{ item.content }}</p>
              </div>
            </article>
          </div>
        </article>
      </template>
    </section>

    <section v-else class="state-card card-surface">
      <div class="state-orb"></div>
      <h3>暂未生成报告</h3>
      <p v-if="canGenerateReports">点击重新生成，后台会开始整理当前月份的巡检数据。</p>
      <p v-else>当前月份暂无已生成报告，请等待有生成权限的账号完成生成。</p>
    </section>

    <teleport to="body">
      <div v-if="sourceDialogVisible" class="report-source-dialog-layer">
        <section class="report-source-dialog" role="dialog" aria-modal="true" aria-label="设置报告数据来源">
          <button type="button" class="source-dialog-close" aria-label="关闭" @click="closeSourceDialog">×</button>
          <header class="source-dialog-head">
            <div>
              <span>REPORT DATA SCOPE</span>
              <h3>{{ canGenerateReports ? '设置报告数据来源' : '查看报告数据来源' }}</h3>
              <p>候选站点已按报告模板、月份和当前账号权限自动筛选。</p>
            </div>
            <div class="source-dialog-total">
              <strong>{{ sourceStations.length }}</strong>
              <span>个可用站点</span>
            </div>
          </header>

          <div class="source-mode-switch">
            <button
              type="button"
              :class="{ active: sourceDraftMode === 'all' }"
              :disabled="!canGenerateReports"
              @click="setSourceDraftMode('all')"
            >
              <strong>全部可用站点</strong>
              <span>自动包含当前月份全部可统计站点</span>
            </button>
            <button
              type="button"
              :class="{ active: sourceDraftMode === 'custom' }"
              :disabled="!canGenerateReports"
              @click="setSourceDraftMode('custom')"
            >
              <strong>自定义选择</strong>
              <span>按片区或站点精确控制报告数据</span>
            </button>
          </div>

          <div class="source-dialog-toolbar">
            <label class="source-search-box">
              <span aria-hidden="true"></span>
              <input v-model.trim="sourceKeyword" type="search" placeholder="搜索站点名称或片区" />
            </label>
            <select v-model="sourceRegionFilter">
              <option value="">全部片区</option>
              <option v-for="region in sourceRegions" :key="region" :value="region">{{ region }}</option>
            </select>
            <label class="source-selected-toggle">
              <input v-model="sourceOnlySelected" type="checkbox" />
              <span>只看已选</span>
            </label>
          </div>

          <div class="source-dialog-batch">
            <div>
              <strong>
                {{ sourceDraftMode === 'all' ? sourceStations.length : sourceDraftIds.length }}
              </strong>
              <span>个站点将纳入报告</span>
            </div>
            <div v-if="canGenerateReports && sourceDraftMode === 'custom'">
              <button type="button" @click="selectVisibleSourceStations">全选当前结果</button>
              <button type="button" @click="invertVisibleSourceStations">反选当前结果</button>
              <button type="button" class="danger" @click="sourceDraftIds = []">清空</button>
            </div>
          </div>

          <div class="source-station-list">
            <div v-if="!filteredSourceStations.length" class="source-list-empty">
              当前筛选条件下没有站点。
            </div>
            <section
              v-for="group in groupedSourceStations"
              :key="`source-region-${group.region}`"
              class="source-region-group"
            >
              <div class="source-region-head">
                <strong>{{ group.region }}</strong>
                <span>{{ group.stations.length }} 个站点</span>
              </div>
              <div class="source-station-grid">
                <label
                  v-for="station in group.stations"
                  :key="`source-station-${station.station_id}`"
                  :class="[
                    'source-station-option',
                    {
                      selected: isDraftSourceStationSelected(station.station_id),
                      readonly: !canGenerateReports || sourceDraftMode === 'all'
                    }
                  ]"
                >
                  <input
                    type="checkbox"
                    :checked="isDraftSourceStationSelected(station.station_id)"
                    :disabled="!canGenerateReports || sourceDraftMode === 'all'"
                    @change="toggleDraftSourceStation(station.station_id)"
                  />
                  <span class="source-checkbox-mark"></span>
                  <span class="source-station-info">
                    <strong>{{ station.station_name }}</strong>
                    <small>
                      {{ station.inspection_count }} 条巡检记录 · {{ station.issue_count }} 项问题
                    </small>
                  </span>
                </label>
              </div>
            </section>
          </div>

          <footer class="source-dialog-footer">
            <p v-if="sourceDraftMode === 'custom' && !sourceDraftIds.length">
              自定义范围至少保留一个站点。
            </p>
            <p v-else>
              当前选择不会修改原始巡检数据，只影响下一次报告生成。
            </p>
            <div>
              <button type="button" class="source-cancel-btn" @click="closeSourceDialog">
                {{ canGenerateReports ? '取消' : '关闭' }}
              </button>
              <button
                v-if="canGenerateReports"
                type="button"
                class="source-confirm-btn"
                :disabled="sourceDraftMode === 'custom' && !sourceDraftIds.length"
                @click="applySourceSelection"
              >
                应用选择
              </button>
            </div>
          </footer>
        </section>
      </div>
      <div v-if="exportDialogVisible" class="report-export-dialog-layer">
        <section class="report-export-dialog" role="dialog" aria-modal="true" aria-label="导出报告PPT">
          <button type="button" class="export-dialog-close" aria-label="关闭" @click="closeExportDialog">×</button>
          <header class="export-dialog-head">
            <div class="export-dialog-icon" aria-hidden="true">
              <span>P</span>
            </div>
            <div>
              <span>PRESENTATION EXPORT</span>
              <h3>导出报告PPT</h3>
              <p>系统会在后台把当前报告编排为专业的 16:9 演示文稿。</p>
            </div>
          </header>

          <div class="export-dialog-body">
            <div class="export-snapshot-card">
              <div>
                <span>导出内容</span>
                <strong>{{ report.title || currentReportType.name }}</strong>
                <small>{{ selectedMonth }} · 报告生成于 {{ reportGeneratedAt }}</small>
              </div>
              <div class="export-snapshot-status">已保存快照</div>
            </div>

            <div class="export-feature-grid">
              <div><span class="feature-dot chart"></span><strong>原生图表</strong><small>可继续编辑</small></div>
              <div><span class="feature-dot table"></span><strong>分页表格</strong><small>自动控制版面</small></div>
              <div><span class="feature-dot photo"></span><strong>问题照片</strong><small>固定完整导出</small></div>
              <div><span class="feature-dot ai"></span><strong>AI标识</strong><small>来源清楚可见</small></div>
            </div>

            <div v-if="exportTask" :class="['export-task-panel', exportTask.status]">
              <div class="export-task-head">
                <div>
                  <span>{{ exportStatusLabel }}</span>
                  <strong>{{ exportTask.stage_message || '正在准备演示文稿' }}</strong>
                </div>
                <b>{{ exportTask.progress || 0 }}%</b>
              </div>
              <div class="export-progress-track">
                <span :style="{ width: `${exportTask.progress || 0}%` }"></span>
              </div>
              <div v-if="exportTask.status === 'completed'" class="export-result-meta">
                <span>{{ exportTask.slide_count || 0 }} 页幻灯片</span>
                <span>{{ exportTask.file_size_text || '文件已就绪' }}</span>
                <span>保留至 {{ exportTask.expires_at || '7天后' }}</span>
              </div>
            </div>

            <p v-if="exportError" class="export-error-message">{{ exportError }}</p>
            <p class="export-dialog-note">PPT固定包含报告中的问题照片，并根据当前已保存报告生成；不会重新调用AI，也不会修改报告数据。</p>
          </div>

          <footer class="export-dialog-footer">
            <button type="button" class="export-secondary-btn" @click="closeExportDialog">稍后处理</button>
            <button
              v-if="exportTask?.status === 'completed'"
              type="button"
              class="export-secondary-btn"
              :disabled="exportSubmitting"
              @click="startPptExport"
            >
              重新创建
            </button>
            <button
              v-if="exportTask?.status === 'completed'"
              type="button"
              class="export-primary-btn download"
              :disabled="exportDownloading"
              @click="downloadExportPpt"
            >
              {{ exportDownloading ? '正在下载...' : '下载PPT' }}
            </button>
            <button
              v-else
              type="button"
              class="export-primary-btn"
              :disabled="exportBusy || exportSubmitting"
              @click="startPptExport"
            >
              {{ exportBusy || exportSubmitting ? '后台生成中...' : '创建PPT' }}
            </button>
          </footer>
        </section>
      </div>
      <div v-if="imagePreview.visible" class="report-image-preview" @click.self="closeImagePreview">
        <img :src="imagePreview.src" :alt="imagePreview.title || '问题照片预览'" />
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import axios from 'axios'
import AiContentBadge from '@/components/AiContentBadge.vue'

const currentRole = localStorage.getItem('user_role') || ''
let storedPermissions = {}
try {
  storedPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch {
  // Keep the safe empty permission map when local data is malformed.
}

const DEFAULT_REPORT_TYPES = [
  {
    key: 'quality_measurement',
    name: '质量计量监督检查报告',
    description: '以计量稽查现场检查涉及站点为范围，合并同站视频检查数据。',
    target_tables: ['计量稽查检查表（现场）', '计量稽查检查表（视频）'],
    data_scope_note: '以“计量稽查检查表（现场）”中审核通过问题涉及站点为统计范围，同时合并这些站点在“计量稽查检查表（视频）”中的审核通过问题。',
    template_ready: true
  },
  {
    key: 'safety_quality',
    name: '安全质量检查报告',
    description: '汇总质量安全环保现场与视频检查数据。',
    target_tables: ['质量安全环保检查表（视频）', '质量安全环保检查表（现场）'],
    data_scope_note: '仅统计所选月份内审核通过的问题；视频扫站与四不两直现场检查分别汇总、分别分析。',
    template_ready: true
  },
  {
    key: 'finance',
    name: '财务检查报告',
    description: '汇总财务现场检查数据。',
    target_tables: ['财务检查表（现场）'],
    data_scope_note: '仅统计所选月份内“财务检查表（现场）”中审核通过的问题，按项目、关键环节、所属单位和站点进行汇总分析。',
    template_ready: true
  },
  {
    key: 'on_site_service',
    name: '现场服务检查报告',
    description: '汇总现场服务视频与现场检查数据。',
    target_tables: ['现场检查明细表（视频）', '现场检查明细表（现场）'],
    data_scope_note: '站点覆盖按所选月份内已确认完成的视频与现场巡检记录统计；问题数量、分类、上月整改对比和AI分析仅使用审核通过的问题。',
    template_ready: true
  },
  {
    key: 'equipment_facilities',
    name: '设备设施检查报告',
    description: '汇总设备设施现场检查数据。',
    target_tables: ['设备设施检查表（现场）'],
    data_scope_note: '受检站点按所选月份内已确认完成的巡检记录统计；问题数量、分类、典型问题和AI分析仅使用审核通过的问题。',
    template_ready: true
  },
  {
    key: 'non_oil',
    name: '非油检查报告',
    description: '汇总非油团购合规与现场检查数据。',
    target_tables: ['非油合规性检查（团购）', '非油检查表（现场）'],
    template_ready: false
  }
]

const createEmptyReport = () => ({
  month: '',
  month_label: '',
  title: '',
  target_tables: [],
  data_scope_note: '',
  source_selection: {},
  summary: {},
  overview_text: '',
  finding_summary: {},
  prohibited_examples: [],
  deep_analysis: {},
  sections: [],
  units: [],
  project_distribution: [],
  key_link_distribution: [],
  station_reports: [],
  region_rows: [],
  station_ranking: [],
  area_distribution: [],
  item_distribution: [],
  unit_comparison: [],
  previous_month_rectification: {},
  mode_summaries: [],
  category_sections: [],
  rows: [],
  total_row: {}
})

const getDefaultReportMonth = () => {
  const now = new Date()
  const previousMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1)
  const year = previousMonth.getFullYear()
  const month = String(previousMonth.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

const selectedMonth = ref(getDefaultReportMonth())
const selectedReportType = ref('quality_measurement')
const reportTypes = ref(DEFAULT_REPORT_TYPES)
const loading = ref(false)
const error = ref('')
const activeJob = ref(null)
const canGenerateReports = ref(
  currentRole === 'root' || Boolean(storedPermissions.generate_inspection_reports)
)
const imagePreview = ref({
  visible: false,
  src: '',
  title: ''
})
const report = ref(createEmptyReport())
const sourceStations = ref([])
const sourceLoading = ref(false)
const sourceError = ref('')
const sourceSelectionMode = ref('all')
const selectedSourceStationIds = ref([])
const sourceDialogVisible = ref(false)
const sourceDraftMode = ref('all')
const sourceDraftIds = ref([])
const sourceKeyword = ref('')
const sourceRegionFilter = ref('')
const sourceOnlySelected = ref(false)
const exportDialogVisible = ref(false)
const exportTask = ref(null)
const exportError = ref('')
const exportSubmitting = ref(false)
const exportDownloading = ref(false)
let pollTimer = null
let exportPollTimer = null
let contextRequestId = 0

const currentReportType = computed(() => (
  reportTypes.value.find((item) => item.key === selectedReportType.value)
  || DEFAULT_REPORT_TYPES[0]
))
const templateUnavailable = computed(() => currentReportType.value.template_ready === false)
const isQualityMeasurementReport = computed(() => selectedReportType.value === 'quality_measurement')
const isSafetyQualityReport = computed(() => selectedReportType.value === 'safety_quality')
const isFinanceReport = computed(() => selectedReportType.value === 'finance')
const isOnSiteServiceReport = computed(() => selectedReportType.value === 'on_site_service')
const isEquipmentFacilitiesReport = computed(() => selectedReportType.value === 'equipment_facilities')
const hasReport = computed(() => Boolean(report.value?.month))
const exportBusy = computed(() => ['queued', 'running'].includes(exportTask.value?.status))
const exportStatusLabel = computed(() => {
  const labels = {
    queued: '等待后台处理',
    running: '正在生成演示文稿',
    completed: '演示文稿已就绪',
    failed: '生成未完成'
  }
  return labels[exportTask.value?.status] || '导出准备'
})
const reportTitleFallback = computed(() => {
  const monthNumber = Number.parseInt(String(selectedMonth.value || '').split('-')[1] || '', 10)
  const monthPrefix = Number.isFinite(monthNumber) ? `${monthNumber}月` : ''
  return `${monthPrefix}${currentReportType.value.name}`
})
const generationProgress = computed(() => {
  const value = Number(activeJob.value?.progress)
  if (Number.isFinite(value)) return Math.max(3, Math.min(100, Math.round(value)))
  return 3
})
const generationStageMessage = computed(() => (
  activeJob.value?.stage_message || '正在连接后台 AI 生成服务'
))

const reportSnapshot = computed(() => report.value.snapshot || {})
const reportSourceSelection = computed(() => report.value.source_selection || {})
const sourceRegions = computed(() => (
  [...new Set(sourceStations.value.map((item) => item.region).filter(Boolean))]
))
const selectedSourceStations = computed(() => {
  if (sourceSelectionMode.value === 'all') return sourceStations.value
  const selectedIds = new Set(selectedSourceStationIds.value.map(Number))
  return sourceStations.value.filter((item) => selectedIds.has(Number(item.station_id)))
})
const effectiveSourceSummary = computed(() => {
  const stations = selectedSourceStations.value
  return {
    station_count: stations.length,
    region_count: new Set(stations.map((item) => item.region).filter(Boolean)).size,
    issue_count: stations.reduce((total, item) => total + Number(item.issue_count || 0), 0),
    inspection_count: stations.reduce((total, item) => total + Number(item.inspection_count || 0), 0)
  }
})
const sourceSelectionDescription = computed(() => {
  const summary = effectiveSourceSummary.value
  if (!sourceStations.value.length) return '当前月份暂无符合报告口径的可用站点数据。'
  if (sourceSelectionMode.value === 'custom') {
    return `已选择 ${summary.station_count} 个站点，覆盖 ${summary.region_count} 个片区；下一次生成只统计这些站点。`
  }
  return `使用当前月份全部 ${summary.station_count} 个可用站点，覆盖 ${summary.region_count} 个片区。`
})
const sourceSelectionDirty = computed(() => {
  if (!hasReport.value) return false
  const savedMode = reportSourceSelection.value.mode === 'custom' ? 'custom' : 'all'
  if (savedMode !== sourceSelectionMode.value) return true
  if (savedMode !== 'custom') return false
  const savedIds = [...(reportSourceSelection.value.station_ids || [])].map(Number).sort((a, b) => a - b)
  const currentIds = [...selectedSourceStationIds.value].map(Number).sort((a, b) => a - b)
  return JSON.stringify(savedIds) !== JSON.stringify(currentIds)
})
const filteredSourceStations = computed(() => {
  const keyword = sourceKeyword.value.toLowerCase()
  const selectedIds = new Set(sourceDraftIds.value.map(Number))
  return sourceStations.value.filter((item) => {
    if (sourceRegionFilter.value && item.region !== sourceRegionFilter.value) return false
    if (sourceOnlySelected.value && sourceDraftMode.value === 'custom' && !selectedIds.has(Number(item.station_id))) {
      return false
    }
    if (!keyword) return true
    return `${item.station_name} ${item.region}`.toLowerCase().includes(keyword)
  })
})
const groupedSourceStations = computed(() => {
  const groups = []
  filteredSourceStations.value.forEach((station) => {
    let group = groups.find((item) => item.region === station.region)
    if (!group) {
      group = { region: station.region || '未设置片区', stations: [] }
      groups.push(group)
    }
    group.stations.push(station)
  })
  return groups
})
const reportGeneratedAt = computed(() => (
  reportSnapshot.value.generated_at
  || report.value.summary?.generated_at
  || '-'
))
const reportRows = computed(() => Array.isArray(report.value.rows) ? report.value.rows : [])
const totalRow = computed(() => report.value.total_row || {})
const findingSummary = computed(() => report.value.finding_summary || {})
const businessFlowRows = computed(() => (
  Array.isArray(findingSummary.value.business_flow_distribution)
    ? findingSummary.value.business_flow_distribution
    : []
))
const prohibitedExamples = computed(() => (
  Array.isArray(report.value.prohibited_examples) ? report.value.prohibited_examples : []
))
const deepAnalysis = computed(() => report.value.deep_analysis || {})
const flowHighlights = computed(() => (
  Array.isArray(deepAnalysis.value.flow_highlights) ? deepAnalysis.value.flow_highlights : []
))
const managementTrace = computed(() => deepAnalysis.value.management_trace || {})
const workPlan = computed(() => (
  Array.isArray(deepAnalysis.value.work_plan) ? deepAnalysis.value.work_plan : []
))
const safetySections = computed(() => (
  Array.isArray(report.value.sections) ? report.value.sections : []
))
const safetyDeepAnalysis = computed(() => report.value.deep_analysis || {})
const safetyTypicalFindings = computed(() => (
  Array.isArray(safetyDeepAnalysis.value.typical_findings)
    ? safetyDeepAnalysis.value.typical_findings
    : []
))
const safetyCategoryHighlights = computed(() => (
  Array.isArray(safetyDeepAnalysis.value.category_highlights)
    ? safetyDeepAnalysis.value.category_highlights
    : []
))
const safetyHighlightGroups = computed(() => (
  safetySections.value.map((section) => ({
    mode: section.mode,
    label: section.label,
    items: safetyCategoryHighlights.value.filter((item) => item.mode === section.mode)
  }))
))
const safetyProblemAnalysis = computed(() => (
  Array.isArray(safetyDeepAnalysis.value.problem_analysis)
    ? safetyDeepAnalysis.value.problem_analysis
    : []
))
const safetyWorkSuggestions = computed(() => (
  Array.isArray(safetyDeepAnalysis.value.work_suggestions)
    ? safetyDeepAnalysis.value.work_suggestions
    : []
))
const financeSummary = computed(() => report.value.summary || {})
const financeUnitRows = computed(() => (
  Array.isArray(report.value.units) ? report.value.units : []
))
const financeOverviewSection = computed(() => ({
  units: financeUnitRows.value
}))
const financeDistributions = computed(() => [
  {
    key: 'project',
    eyebrow: 'PROJECT',
    title: '按检查项目分类',
    text: report.value.project_distribution_text || '',
    items: Array.isArray(report.value.project_distribution) ? report.value.project_distribution : []
  },
  {
    key: 'key-link',
    eyebrow: 'KEY LINK',
    title: '按关键环节分类',
    text: report.value.key_link_distribution_text || '',
    items: Array.isArray(report.value.key_link_distribution) ? report.value.key_link_distribution : []
  }
])
const financeStationReports = computed(() => (
  Array.isArray(report.value.station_reports) ? report.value.station_reports : []
))
const financeDeepAnalysis = computed(() => report.value.deep_analysis || {})
const financeResultAnalysis = computed(() => (
  Array.isArray(financeDeepAnalysis.value.result_analysis)
    ? financeDeepAnalysis.value.result_analysis
    : []
))
const financeContentSuggestions = computed(() => (
  Array.isArray(financeDeepAnalysis.value.content_suggestions)
    ? financeDeepAnalysis.value.content_suggestions
    : []
))
const equipmentRegionRows = computed(() => (
  Array.isArray(report.value.region_rows) ? report.value.region_rows : []
))
const equipmentStationRanking = computed(() => (
  Array.isArray(report.value.station_ranking) ? report.value.station_ranking : []
))
const equipmentDistributions = computed(() => [
  {
    key: 'area',
    eyebrow: 'AREA DISTRIBUTION',
    title: '按所属区域分类',
    text: report.value.area_distribution_text || '',
    items: Array.isArray(report.value.area_distribution) ? report.value.area_distribution : []
  },
  {
    key: 'inspection-item',
    eyebrow: 'INSPECTION ITEM',
    title: '按检查事项分类',
    text: report.value.item_distribution_text || '',
    items: Array.isArray(report.value.item_distribution) ? report.value.item_distribution : []
  }
])
const equipmentDeepAnalysis = computed(() => report.value.deep_analysis || {})
const equipmentTypicalFinding = computed(() => (
  equipmentDeepAnalysis.value.typical_finding || {}
))
const equipmentProblemAnalysis = computed(() => (
  Array.isArray(equipmentDeepAnalysis.value.problem_analysis)
    ? equipmentDeepAnalysis.value.problem_analysis
    : []
))
const equipmentWorkSuggestions = computed(() => (
  Array.isArray(equipmentDeepAnalysis.value.work_suggestions)
    ? equipmentDeepAnalysis.value.work_suggestions
    : []
))
const reportMonthNumber = computed(() => {
  const monthValue = String(report.value.month || selectedMonth.value || '').split('-')[1]
  return Number.parseInt(monthValue || '', 10) || '-'
})
const serviceUnitRows = computed(() => (
  Array.isArray(report.value.unit_comparison) ? report.value.unit_comparison : []
))
const servicePreviousRectification = computed(() => (
  report.value.previous_month_rectification || {}
))
const serviceRectificationRows = computed(() => (
  Array.isArray(servicePreviousRectification.value.units)
    ? servicePreviousRectification.value.units
    : []
))
const serviceModeSummaries = computed(() => (
  Array.isArray(report.value.mode_summaries) ? report.value.mode_summaries : []
))
const serviceCategorySections = computed(() => (
  Array.isArray(report.value.category_sections) ? report.value.category_sections : []
))
const serviceDeepAnalysis = computed(() => report.value.deep_analysis || {})
const serviceUnitAnalyses = computed(() => (
  Array.isArray(serviceDeepAnalysis.value.unit_analyses)
    ? serviceDeepAnalysis.value.unit_analyses
    : []
))
const serviceProblemSummary = computed(() => (
  Array.isArray(serviceDeepAnalysis.value.problem_summary)
    ? serviceDeepAnalysis.value.problem_summary
    : []
))
const serviceNextSteps = computed(() => (
  Array.isArray(serviceDeepAnalysis.value.next_steps)
    ? serviceDeepAnalysis.value.next_steps
    : []
))
const targetTableText = computed(() => {
  const tables = Array.isArray(report.value.target_tables) ? report.value.target_tables : []
  const fallbackTables = Array.isArray(currentReportType.value.target_tables) ? currentReportType.value.target_tables : []
  return (tables.length ? tables : fallbackTables).join('、') || '-'
})
const dataScopeNote = computed(() => (
  report.value.data_scope_note || currentReportType.value.data_scope_note || ''
))

const summaryCards = computed(() => {
  const summary = report.value.summary || {}
  if (isSafetyQualityReport.value) {
    return [
      {
        label: '视频检查站点',
        value: summary.video_station_count ?? 0,
        desc: `发现问题 ${summary.video_issue_count ?? 0} 项`
      },
      {
        label: '现场检查站点',
        value: summary.onsite_station_count ?? 0,
        desc: `发现问题 ${summary.onsite_issue_count ?? 0} 项`
      },
      {
        label: '涉及站点',
        value: summary.station_count ?? 0,
        desc: '视频与现场合并去重'
      },
      {
        label: '问题总数',
        value: summary.total_issue_count ?? 0,
        desc: '仅统计审核通过问题'
      }
    ]
  }
  if (isFinanceReport.value) {
    return [
      {
        label: '巡检时间',
        value: summary.date_from && summary.date_to ? `${summary.date_from.slice(5)}—${summary.date_to.slice(5)}` : '-',
        desc: summary.date_range || '当前月份暂无巡检记录'
      },
      {
        label: '管理片区',
        value: summary.region_count ?? 0,
        desc: '实际涉及片区'
      },
      {
        label: '控（参）股单位',
        value: summary.holding_unit_count ?? 0,
        desc: '中油单位去重统计'
      },
      {
        label: '检查站点',
        value: summary.station_count ?? 0,
        desc: '去重统计站点数'
      },
      {
        label: '发现问题',
        value: summary.total_issue_count ?? 0,
        desc: '仅统计审核通过问题'
      }
    ]
  }
  if (isEquipmentFacilitiesReport.value) {
    return [
      {
        label: '受检站点',
        value: summary.station_count ?? 0,
        desc: '已确认完成的巡检记录'
      },
      {
        label: '片区及单位',
        value: summary.unit_count ?? 0,
        desc: '按站点主数据归类'
      },
      {
        label: '发现问题',
        value: summary.total_issue_count ?? 0,
        desc: '仅统计审核通过问题'
      },
      {
        label: '平均问题',
        value: Number(summary.average_issue_count || 0).toFixed(1),
        desc: '平均每座受检站点'
      }
    ]
  }
  if (isOnSiteServiceReport.value) {
    return [
      {
        label: '检查站次',
        value: summary.station_visit_count ?? 0,
        desc: '视频与现场分别统计'
      },
      {
        label: '视频巡检',
        value: summary.video_station_count ?? 0,
        desc: `${summary.video_issue_count ?? 0}项问题 · 站均${Number(summary.video_average_issue_count || 0).toFixed(1)}`
      },
      {
        label: '现场巡检',
        value: summary.onsite_station_count ?? 0,
        desc: `${summary.onsite_issue_count ?? 0}项问题 · 站均${Number(summary.onsite_average_issue_count || 0).toFixed(1)}`
      },
      {
        label: '发现问题',
        value: summary.total_issue_count ?? 0,
        desc: '仅统计审核通过问题'
      }
    ]
  }
  return [
    {
      label: '管理片区',
      value: summary.region_count ?? 0,
      desc: '本月问题涉及片区'
    },
    {
      label: '控（参）股单位',
      value: summary.holding_unit_count ?? 0,
      desc: '按站点主数据识别'
    },
    {
      label: '检查站点',
      value: summary.station_count ?? 0,
      desc: '去重统计站点数'
    },
    {
      label: '发现问题',
      value: summary.total_issue_count ?? 0,
      desc: `禁止项 ${summary.prohibited_issue_count ?? 0} 项`
    }
  ]
})

const emptyOverviewText = computed(() => {
  const month = report.value.month_label || '当前月份'
  return `${month}暂无计量稽查现场与视频检查问题数据，暂不能形成总体情况统计。`
})

const joinChineseList = (items) => {
  const values = items.map((item) => String(item || '').trim()).filter(Boolean)
  if (!values.length) return ''
  if (values.length === 1) return values[0]
  if (values.length === 2) return values.join('和')
  return `${values.slice(0, -1).join('、')}和${values[values.length - 1]}`
}

const formatPercent = (value) => `${Number(value || 0).toFixed(1)}%`

const buildFlowText = (prefix, includePercent = false) => {
  const total = Number(findingSummary.value.total_issue_count ?? report.value.summary?.total_issue_count ?? 0)
  if (!total || !businessFlowRows.value.length) return `${prefix}0项。`
  const names = businessFlowRows.value.map((item) => item.name)
  const counts = businessFlowRows.value.map((item) => `${item.count}项`)
  const percentText = includePercent
    ? `，占比${joinChineseList(businessFlowRows.value.map((item) => formatPercent(item.percentage)))}`
    : ''
  return `${prefix}${total}项，涉及${joinChineseList(names)}问题，问题数量分别为${joinChineseList(counts)}${percentText}。`
}

const chapterTwoText = computed(() => buildFlowText('本次检查发现问题'))
const stationLinkText = computed(() => buildFlowText('检查发现加油站环节问题', true))

const chartMax = computed(() => {
  const max = Math.max(...businessFlowRows.value.map((item) => Number(item.count || 0)), 0)
  if (max <= 0) return 5
  return Math.ceil(max / chartTickStep.value) * chartTickStep.value
})

const chartTickStep = computed(() => {
  const max = Math.max(...businessFlowRows.value.map((item) => Number(item.count || 0)), 0)
  if (max <= 0) return 1
  const rawStep = max / 7
  const magnitude = 10 ** Math.floor(Math.log10(rawStep))
  const niceMultipliers = [1, 2, 5, 10]
  const multiplier = niceMultipliers.find((item) => item * magnitude >= rawStep) || 10
  return multiplier * magnitude
})

const chartTicks = computed(() => {
  const max = chartMax.value || 5
  const step = chartTickStep.value || 1
  const ticks = []
  for (let value = max; value >= 0; value -= step) {
    ticks.push(Math.round(value * 10) / 10)
  }
  if (ticks[ticks.length - 1] !== 0) ticks.push(0)
  return ticks
})

const getBarHeight = (count) => {
  const max = chartMax.value || 1
  return Math.max(2, Math.min(100, (Number(count || 0) / max) * 100))
}

const findingFlowColors = ['#167fb3', '#20a0a0', '#e8993f', '#5479c9', '#7b61b3', '#d76565', '#4b9b68', '#8b6f47']

const getFindingFlowColor = (index) => findingFlowColors[index % findingFlowColors.length]

const getFindingFlowWidth = (count) => {
  const max = Math.max(...businessFlowRows.value.map((item) => Number(item.count) || 0), 1)
  return Math.max(3, Math.min(100, ((Number(count) || 0) / max) * 100))
}

const getSafetyUnitChartStep = (section) => {
  const values = (section?.units || []).flatMap((item) => [
    Number(item.issue_count || 0),
    Number(item.station_count || 0)
  ])
  const max = Math.max(...values, 0)
  if (max <= 4) return 1
  const rawStep = max / 4
  const magnitude = 10 ** Math.floor(Math.log10(rawStep))
  return ([1, 2, 5, 10].find((item) => item * magnitude >= rawStep) || 10) * magnitude
}

const getSafetyUnitChartMax = (section) => {
  const values = (section?.units || []).flatMap((item) => [
    Number(item.issue_count || 0),
    Number(item.station_count || 0)
  ])
  const max = Math.max(...values, 0)
  const step = getSafetyUnitChartStep(section)
  return Math.max(step * 4, Math.ceil(max / step) * step)
}

const getSafetyUnitChartTicks = (section) => {
  const max = getSafetyUnitChartMax(section)
  const step = getSafetyUnitChartStep(section)
  const ticks = []
  for (let value = max; value >= 0; value -= step) ticks.push(value)
  if (ticks[ticks.length - 1] !== 0) ticks.push(0)
  return ticks
}

const getSafetyUnitTickPosition = (section, tick) => {
  const max = getSafetyUnitChartMax(section)
  return max ? (Number(tick || 0) / max) * 100 : 0
}

const getSafetyUnitBarHeight = (section, value) => {
  const max = getSafetyUnitChartMax(section)
  if (!Number(value || 0)) return 0
  return Math.max(3, Math.min(100, (Number(value || 0) / max) * 100))
}

const getSafetyChartMinWidth = (section) => {
  const unitCount = Array.isArray(section?.units) ? section.units.length : 0
  return `${Math.max(640, unitCount * 98 + 70)}px`
}

const getSafetyCategoryWidth = (section, count) => {
  const max = Math.max(
    ...(section?.category_distribution || []).map((item) => Number(item.count || 0)),
    1
  )
  return Math.max(3, Math.min(100, (Number(count || 0) / max) * 100))
}

const getFinanceCategoryWidth = (items, count) => {
  const max = Math.max(...(items || []).map((item) => Number(item.count || 0)), 1)
  return Math.max(3, Math.min(100, (Number(count || 0) / max) * 100))
}

const getEquipmentRegionBarWidth = (field, value) => {
  const max = Math.max(
    ...equipmentRegionRows.value.map((item) => Number(item?.[field] || 0)),
    1
  )
  return Number(value || 0) > 0
    ? Math.max(3, Math.min(100, Number(value || 0) / max * 100))
    : 0
}

const getEquipmentStationBarWidth = (value) => {
  const max = Math.max(
    ...equipmentStationRanking.value.map((item) => Number(item.issue_count || 0)),
    1
  )
  return Number(value || 0) > 0
    ? Math.max(2, Math.min(100, Number(value || 0) / max * 100))
    : 0
}

const getServiceUnitBarWidth = (field, value) => {
  const max = Math.max(
    ...serviceUnitRows.value.map((item) => Number(item?.[field] || 0)),
    1
  )
  return Number(value || 0) > 0
    ? Math.max(3, Math.min(100, Number(value || 0) / max * 100))
    : 0
}

const getRectificationWidth = (unit, field) => {
  const total = Number(unit?.total_count || 0)
  return total > 0 ? Math.max(0, Number(unit?.[field] || 0) / total * 100) : 0
}

const getServiceModeAverageWidth = (mode, value) => {
  const max = Math.max(
    ...(mode?.units || []).map((item) => Number(item.average_issue_count || 0)),
    1
  )
  return Number(value || 0) > 0
    ? Math.max(3, Math.min(100, Number(value || 0) / max * 100))
    : 0
}

const getServiceCategoryWidth = (section, value) => {
  const max = Math.max(
    ...(section?.items || []).map((item) => Number(item.count || 0)),
    1
  )
  return Number(value || 0) > 0
    ? Math.max(3, Math.min(100, Number(value || 0) / max * 100))
    : 0
}

const buildEquipmentTypicalText = (item) => {
  if (!item?.issue_count) return '当前月份暂无可用于典型问题分析的数据。'
  const areas = joinChineseList(Array.isArray(item.area_names) ? item.area_names : [])
  const units = joinChineseList(Array.isArray(item.management_units) ? item.management_units : [])
  const areaText = areas ? `属于${areas}相关问题，` : ''
  const unitText = units ? `涉及${units}，` : ''
  return `${item.title}${areaText}${unitText}在${item.station_count || 0}座站点出现${item.issue_count || 0}项，占本月设备设施问题${formatPercent(item.percentage)}。`
}

const buildSafetyTypicalText = (item) => {
  if (!item?.issue_count) return '当前月份暂无可用于典型问题分析的数据。'
  const units = joinChineseList(Array.isArray(item.unit_names) ? item.unit_names : [])
  const unitText = units ? `涉及${units}，` : ''
  return `${item.title}属于${item.label}高频问题，${unitText}在${item.station_count || 0}座站点出现${item.issue_count || 0}项，占该类检查问题${formatPercent(item.percentage)}。`
}

const resolveImage = (path) => {
  if (!path) return ''
  const value = String(path || '').trim()
  if (!value) return ''
  if (value.startsWith('http://') || value.startsWith('https://') || value.startsWith('data:')) return value
  if (value.startsWith('/storage/')) return value
  if (value.startsWith('storage/')) return `/${value}`
  return `/storage/${value.replace(/^\/+/, '')}`
}

const formatStationIssue = (issue = {}) => {
  const station = String(issue.station_name || '').trim()
  const description = String(issue.description || '').trim()
  if (station && description) return `${station}${description}`
  return station || description || '暂无典型问题描述。'
}

const openImagePreview = (path, title = '问题照片预览') => {
  const src = resolveImage(path)
  if (!src) return
  imagePreview.value = {
    visible: true,
    src,
    title
  }
}

const closeImagePreview = () => {
  imagePreview.value = {
    visible: false,
    src: '',
    title: ''
  }
}

const normalizeSourceIds = (values) => (
  [...new Set((values || []).map(Number).filter((value) => Number.isInteger(value) && value > 0))]
    .sort((a, b) => a - b)
)

const syncSourceSelection = (savedSelection = {}, jobOptions = {}) => {
  const options = jobOptions && typeof jobOptions === 'object' ? jobOptions : {}
  const selection = savedSelection && typeof savedSelection === 'object' ? savedSelection : {}
  const hasActiveCustomSelection = Boolean(options.station_filter_enabled)
  const mode = hasActiveCustomSelection
    ? 'custom'
    : (selection.mode === 'custom' ? 'custom' : 'all')
  const candidateIds = hasActiveCustomSelection
    ? options.station_ids
    : selection.station_ids
  const availableIds = new Set(sourceStations.value.map((item) => Number(item.station_id)))
  const ids = normalizeSourceIds(candidateIds).filter((stationId) => availableIds.has(stationId))
  sourceSelectionMode.value = mode === 'custom' && ids.length ? 'custom' : 'all'
  selectedSourceStationIds.value = sourceSelectionMode.value === 'custom' ? ids : []
}

const loadSourceOptions = async (savedSelection = {}, jobOptions = {}, requestId = contextRequestId) => {
  sourceLoading.value = true
  sourceError.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/source-options', {
      params: {
        report_type: selectedReportType.value,
        month: selectedMonth.value
      }
    })
    if (requestId !== contextRequestId) return
    if (!response.data?.success) {
      throw new Error(response.data?.error || '读取报告数据来源失败。')
    }
    sourceStations.value = Array.isArray(response.data?.stations) ? response.data.stations : []
    syncSourceSelection(savedSelection, jobOptions)
  } catch (err) {
    if (requestId !== contextRequestId) return
    sourceStations.value = []
    sourceSelectionMode.value = 'all'
    selectedSourceStationIds.value = []
    sourceError.value = err?.response?.data?.error || err?.message || '读取报告数据来源失败。'
  } finally {
    if (requestId === contextRequestId) sourceLoading.value = false
  }
}

const openSourceDialog = () => {
  sourceDraftMode.value = sourceSelectionMode.value
  sourceDraftIds.value = sourceSelectionMode.value === 'custom'
    ? [...selectedSourceStationIds.value]
    : sourceStations.value.map((item) => Number(item.station_id))
  sourceKeyword.value = ''
  sourceRegionFilter.value = ''
  sourceOnlySelected.value = false
  sourceDialogVisible.value = true
}

const closeSourceDialog = () => {
  sourceDialogVisible.value = false
}

const setSourceDraftMode = (mode) => {
  if (!canGenerateReports.value) return
  sourceDraftMode.value = mode === 'custom' ? 'custom' : 'all'
  if (sourceDraftMode.value === 'custom' && !sourceDraftIds.value.length) {
    sourceDraftIds.value = sourceStations.value.map((item) => Number(item.station_id))
  }
}

const isDraftSourceStationSelected = (stationId) => (
  sourceDraftMode.value === 'all'
  || sourceDraftIds.value.map(Number).includes(Number(stationId))
)

const toggleDraftSourceStation = (stationId) => {
  if (!canGenerateReports.value || sourceDraftMode.value !== 'custom') return
  const targetId = Number(stationId)
  const selectedIds = new Set(sourceDraftIds.value.map(Number))
  if (selectedIds.has(targetId)) selectedIds.delete(targetId)
  else selectedIds.add(targetId)
  sourceDraftIds.value = [...selectedIds].sort((a, b) => a - b)
}

const selectVisibleSourceStations = () => {
  const selectedIds = new Set(sourceDraftIds.value.map(Number))
  filteredSourceStations.value.forEach((item) => selectedIds.add(Number(item.station_id)))
  sourceDraftIds.value = [...selectedIds].sort((a, b) => a - b)
}

const invertVisibleSourceStations = () => {
  const selectedIds = new Set(sourceDraftIds.value.map(Number))
  filteredSourceStations.value.forEach((item) => {
    const stationId = Number(item.station_id)
    if (selectedIds.has(stationId)) selectedIds.delete(stationId)
    else selectedIds.add(stationId)
  })
  sourceDraftIds.value = [...selectedIds].sort((a, b) => a - b)
}

const applySourceSelection = () => {
  if (!canGenerateReports.value) {
    closeSourceDialog()
    return
  }
  if (sourceDraftMode.value === 'custom' && !sourceDraftIds.value.length) return
  sourceSelectionMode.value = sourceDraftMode.value
  selectedSourceStationIds.value = sourceDraftMode.value === 'custom'
    ? normalizeSourceIds(sourceDraftIds.value)
    : []
  closeSourceDialog()
}

const clearExportPolling = () => {
  if (exportPollTimer) {
    window.clearTimeout(exportPollTimer)
    exportPollTimer = null
  }
}

const scheduleExportPoll = () => {
  clearExportPolling()
  if (!exportDialogVisible.value || !exportBusy.value) return
  exportPollTimer = window.setTimeout(pollPptExport, 1800)
}

const pollPptExport = async () => {
  const taskId = exportTask.value?.task_id
  if (!taskId || !exportDialogVisible.value) return
  try {
    const response = await axios.get(`/api/inspection-reports/exports/${taskId}`)
    if (exportTask.value?.task_id !== taskId) return
    if (!response.data?.success || !response.data?.task) {
      throw new Error(response.data?.error || '读取PPT生成进度失败。')
    }
    exportTask.value = response.data.task
    exportError.value = exportTask.value.status === 'failed'
      ? (exportTask.value.error_message || 'PPT生成失败，请稍后重试。')
      : ''
    if (exportBusy.value) scheduleExportPoll()
    else clearExportPolling()
  } catch (err) {
    exportError.value = err?.response?.data?.error || err?.message || '读取PPT生成进度失败，后台任务仍可能在继续。'
    scheduleExportPoll()
  }
}

const loadLatestPptExport = async () => {
  exportError.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/exports/latest', {
      params: {
        report_type: selectedReportType.value,
        month: selectedMonth.value
      }
    })
    if (!response.data?.success) {
      throw new Error(response.data?.error || '读取PPT导出状态失败。')
    }
    exportTask.value = response.data.task || null
    if (exportBusy.value) scheduleExportPoll()
  } catch (err) {
    exportTask.value = null
    exportError.value = err?.response?.data?.error || err?.message || '读取PPT导出状态失败。'
  }
}

const openExportDialog = async () => {
  if (!hasReport.value || loading.value || templateUnavailable.value) return
  exportDialogVisible.value = true
  await loadLatestPptExport()
}

const closeExportDialog = () => {
  exportDialogVisible.value = false
  clearExportPolling()
}

const startPptExport = async () => {
  if (!hasReport.value || exportBusy.value || exportSubmitting.value) return
  exportSubmitting.value = true
  exportError.value = ''
  try {
    const response = await axios.post('/api/inspection-reports/exports', {
      report_type: selectedReportType.value,
      month: selectedMonth.value
    })
    if (!response.data?.success || !response.data?.task) {
      throw new Error(response.data?.error || 'PPT导出任务提交失败。')
    }
    exportTask.value = response.data.task
    scheduleExportPoll()
  } catch (err) {
    exportError.value = err?.response?.data?.error || err?.message || 'PPT导出任务提交失败，请稍后重试。'
  } finally {
    exportSubmitting.value = false
  }
}

const downloadExportPpt = async () => {
  const taskId = exportTask.value?.task_id
  if (!taskId || exportTask.value?.status !== 'completed' || exportDownloading.value) return
  exportDownloading.value = true
  exportError.value = ''
  try {
    const response = await axios.get(`/api/inspection-reports/exports/${taskId}/download`, {
      responseType: 'blob'
    })
    const blob = new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    })
    const blobUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = exportTask.value.file_name || `${selectedMonth.value}_${currentReportType.value.name}.pptx`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => window.URL.revokeObjectURL(blobUrl), 1200)
  } catch (err) {
    exportError.value = err?.response?.data?.error || err?.message || 'PPT下载失败，请稍后重试。'
  } finally {
    exportDownloading.value = false
  }
}

const clearPolling = () => {
  if (pollTimer) {
    window.clearTimeout(pollTimer)
    pollTimer = null
  }
}

const scheduleJobPoll = () => {
  clearPolling()
  pollTimer = window.setTimeout(pollActiveJob, 2200)
}

const pollActiveJob = async () => {
  const taskId = activeJob.value?.task_id
  if (!taskId) return
  try {
    const response = await axios.get(`/api/inspection-reports/jobs/${taskId}`)
    if (activeJob.value?.task_id !== taskId) return
    const job = response.data?.job
    if (!response.data?.success || !job) {
      throw new Error(response.data?.error || '读取AI报告生成进度失败。')
    }
    activeJob.value = job
    if (job.status === 'completed') {
      clearPolling()
      if (response.data?.report) report.value = response.data.report
      loading.value = false
      error.value = ''
      return
    }
    if (job.status === 'failed') {
      clearPolling()
      if (response.data?.report) report.value = response.data.report
      loading.value = false
      error.value = job.error_message || 'AI报告生成失败，请稍后重试。'
      return
    }
    scheduleJobPoll()
  } catch (err) {
    error.value = err?.response?.data?.error || err?.message || '暂时无法读取生成进度，后台任务仍在继续。'
    scheduleJobPoll()
  }
}

const startGeneration = async (options = {}) => {
  if (!selectedMonth.value || templateUnavailable.value || !canGenerateReports.value) return
  const requestId = ++contextRequestId
  clearPolling()
  loading.value = true
  error.value = ''
  activeJob.value = {
    progress: 3,
    stage_message: '正在向后台提交 AI 报告生成任务'
  }
  try {
    const response = await axios.post('/api/inspection-reports/generate', {
      report_type: selectedReportType.value,
      month: selectedMonth.value,
      force: options?.force === true,
      generation_options: {
        station_filter_enabled: sourceSelectionMode.value === 'custom',
        station_ids: sourceSelectionMode.value === 'custom'
          ? selectedSourceStationIds.value
          : []
      }
    })
    if (requestId !== contextRequestId) return
    if (!response.data?.success) {
      throw new Error(response.data?.error || 'AI报告生成任务提交失败。')
    }
    if (response.data?.report && !response.data?.job) {
      report.value = response.data.report
      syncSourceSelection(report.value.source_selection || {}, {})
      activeJob.value = null
      loading.value = false
      return
    }
    if (!response.data?.job?.task_id) {
      throw new Error('后台没有返回有效的报告生成任务。')
    }
    activeJob.value = response.data.job
    scheduleJobPoll()
  } catch (err) {
    if (requestId !== contextRequestId) return
    activeJob.value = null
    loading.value = false
    error.value = err?.response?.data?.error || err?.message || 'AI报告生成任务提交失败。'
  }
}

const loadReportState = async () => {
  const requestId = ++contextRequestId
  clearPolling()
  activeJob.value = null
  error.value = ''
  if (templateUnavailable.value) {
    report.value = createEmptyReport()
    sourceStations.value = []
    sourceSelectionMode.value = 'all'
    selectedSourceStationIds.value = []
    loading.value = false
    return
  }
  loading.value = true
  try {
    const response = await axios.get('/api/inspection-reports/status', {
      params: {
        report_type: selectedReportType.value,
        month: selectedMonth.value
      }
    })
    if (requestId !== contextRequestId) return
    if (!response.data?.success) {
      throw new Error(response.data?.error || '读取报告状态失败。')
    }
    canGenerateReports.value = Boolean(response.data?.can_generate)
    report.value = response.data?.report || createEmptyReport()
    await loadSourceOptions(
      response.data?.report?.source_selection || {},
      response.data?.job?.generation_options || {},
      requestId
    )
    if (requestId !== contextRequestId) return
    if (response.data?.job?.task_id) {
      activeJob.value = response.data.job
      scheduleJobPoll()
      return
    }
    loading.value = false
  } catch (err) {
    if (requestId !== contextRequestId) return
    loading.value = false
    error.value = err?.response?.data?.error || err?.message || '读取报告状态失败，请稍后重试。'
  }
}

const selectReportType = async (reportType) => {
  if (selectedReportType.value === reportType) return
  closeExportDialog()
  exportTask.value = null
  exportError.value = ''
  selectedReportType.value = reportType
  report.value = createEmptyReport()
  sourceStations.value = []
  await loadReportState()
}

const handleReportContextChange = async () => {
  closeExportDialog()
  exportTask.value = null
  exportError.value = ''
  report.value = createEmptyReport()
  sourceStations.value = []
  await loadReportState()
}

const loadReportTypes = async () => {
  try {
    const response = await axios.get('/api/inspection-reports/types')
    if (response.data?.success && Array.isArray(response.data.report_types) && response.data.report_types.length) {
      reportTypes.value = response.data.report_types
      canGenerateReports.value = Boolean(response.data?.can_generate)
    }
  } catch {
    reportTypes.value = DEFAULT_REPORT_TYPES
  }
}

onMounted(async () => {
  await loadReportTypes()
  await loadReportState()
})

onBeforeUnmount(() => {
  contextRequestId += 1
  clearPolling()
  clearExportPolling()
})
</script>

<style scoped>
.report-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.card-surface {
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.22);
  box-shadow: 0 22px 54px rgba(15, 23, 42, 0.08);
}

.report-hero {
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: 24px;
  padding: 24px;
  border-radius: 24px;
  background:
    radial-gradient(circle at 8% 0%, rgba(14, 165, 233, 0.18), transparent 34%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(240, 249, 255, 0.94));
}

.page-kicker,
.doc-eyebrow {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.16em;
  color: #0284c7;
}

.report-hero h2,
.report-document h1 {
  margin: 8px 0;
  color: #0f172a;
}

.report-hero p {
  margin: 0;
  color: #64748b;
  line-height: 1.7;
}

.report-month-control {
  min-width: 230px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
  padding: 18px;
  border-radius: 20px;
  background: #0f172a;
  color: #e0f2fe;
}

.report-month-control label {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.report-month-control span {
  font-size: 13px;
  color: #bae6fd;
}

.report-month-control input {
  height: 44px;
  border: 0;
  border-radius: 14px;
  padding: 0 14px;
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}

.regenerate-report-btn {
  height: 42px;
  border: 1px solid rgba(186, 230, 253, 0.34);
  border-radius: 14px;
  color: #e0f2fe;
  background: rgba(14, 165, 233, 0.16);
  font-weight: 900;
  cursor: pointer;
  transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease;
}

.regenerate-report-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  background: rgba(14, 165, 233, 0.28);
  border-color: rgba(186, 230, 253, 0.62);
}

.regenerate-report-btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.export-ppt-btn {
  height: 42px;
  border: 1px solid rgba(94, 234, 212, 0.38);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #ccfbf1;
  background: rgba(13, 148, 136, 0.2);
  font-weight: 900;
  cursor: pointer;
  transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease;
}

.export-ppt-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: rgba(94, 234, 212, 0.7);
  background: rgba(13, 148, 136, 0.34);
}

.export-ppt-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.ppt-file-mark {
  width: 23px;
  height: 23px;
  border-radius: 7px;
  display: grid;
  place-items: center;
  color: #0f172a !important;
  background: #5eead4;
  font-size: 12px !important;
  font-weight: 950;
}

.report-readonly-note {
  display: block;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.55;
  text-align: center;
}

.report-type-panel {
  position: relative;
  padding: 22px;
  border-radius: 24px;
  border-color: rgba(125, 157, 177, 0.42);
  background:
    radial-gradient(circle at 92% 0%, rgba(14, 165, 233, 0.13), transparent 30%),
    linear-gradient(145deg, #e8f1f6 0%, #f2f7fa 50%, #e5eef4 100%);
  box-shadow:
    0 20px 46px rgba(15, 23, 42, 0.07),
    inset 0 1px 0 rgba(255, 255, 255, 0.82);
}

.report-type-panel-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 16px;
}

.report-type-panel-head span {
  color: #0284c7;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.12em;
}

.report-type-panel-head h3 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 18px;
}

.report-type-panel-head small {
  color: #64748b;
}

.report-type-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  padding: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.38);
  box-shadow: inset 0 1px 3px rgba(15, 23, 42, 0.035);
}

.report-type-card {
  position: relative;
  min-width: 0;
  padding: 18px;
  border: 1px solid rgba(184, 204, 216, 0.82);
  border-radius: 19px;
  background: rgba(255, 255, 255, 0.92);
  color: #334155;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
  box-shadow: 0 8px 18px rgba(30, 64, 82, 0.045);
}

.report-type-card:hover {
  transform: translateY(-2px);
  border-color: #7dd3fc;
  box-shadow: 0 14px 28px rgba(14, 116, 144, 0.1);
}

.report-type-card.active {
  border-color: #0284c7;
  background: linear-gradient(145deg, #f0f9ff, #ffffff 72%);
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.12), 0 16px 30px rgba(14, 116, 144, 0.1);
}

.report-type-card.pending.active {
  border-color: #d97706;
  background: linear-gradient(145deg, #fffbeb, #ffffff 72%);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.12), 0 16px 30px rgba(146, 64, 14, 0.08);
}

.report-type-card strong {
  display: block;
  padding-right: 96px;
  color: #0f172a;
  font-size: 18px;
  line-height: 1.45;
}

.report-type-card>p {
  margin: 8px 0 14px;
  color: #64748b;
  line-height: 1.65;
}

.report-type-status {
  position: absolute;
  top: 17px;
  right: 17px;
  padding: 5px 9px;
  border-radius: 999px;
  color: #0369a1;
  background: #e0f2fe;
  font-size: 12px;
  font-weight: 900;
}

.report-type-card.pending .report-type-status {
  color: #92400e;
  background: #fef3c7;
}

.report-type-sources {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
}

.report-type-sources span {
  margin-right: 2px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.report-type-sources em {
  padding: 5px 8px;
  border-radius: 8px;
  color: #334155;
  background: #eef2f7;
  font-size: 12px;
  font-style: normal;
  line-height: 1.4;
}

.report-source-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 24px;
  padding: 22px 24px;
  border-radius: 24px;
  border-color: rgba(20, 184, 166, 0.24);
  background:
    radial-gradient(circle at 6% 20%, rgba(20, 184, 166, 0.13), transparent 32%),
    linear-gradient(135deg, #f8fffd 0%, #ffffff 58%, #f0fdfa 100%);
}

.report-source-main {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.report-source-icon {
  width: 54px;
  height: 54px;
  flex: 0 0 54px;
  border-radius: 18px;
  display: grid;
  align-content: center;
  gap: 5px;
  padding: 0 13px;
  box-sizing: border-box;
  background: linear-gradient(145deg, #0f766e, #14b8a6);
  box-shadow: 0 12px 24px rgba(13, 148, 136, 0.2);
}

.report-source-icon span {
  height: 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
}

.report-source-icon span:nth-child(2) {
  width: 70%;
}

.report-source-icon span:nth-child(3) {
  width: 86%;
}

.report-source-copy {
  min-width: 0;
}

.source-panel-kicker {
  color: #0f766e;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.15em;
}

.source-panel-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 4px 0 5px;
}

.source-panel-title-row h3 {
  margin: 0;
  color: #0f172a;
  font-size: 19px;
}

.source-mode-badge {
  padding: 5px 9px;
  border-radius: 999px;
  color: #0369a1;
  background: #e0f2fe;
  font-size: 11px;
  font-weight: 900;
}

.source-mode-badge.custom {
  color: #0f766e;
  background: #ccfbf1;
}

.report-source-copy > p {
  margin: 0;
  color: #64748b;
  line-height: 1.6;
}

.report-source-copy .source-inline-error {
  color: #b91c1c;
}

.source-station-preview {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
}

.source-station-preview span {
  padding: 5px 8px;
  border-radius: 8px;
  color: #115e59;
  background: rgba(204, 251, 241, 0.74);
  font-size: 12px;
  font-weight: 800;
}

.source-station-preview em {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
}

.source-dirty-note {
  width: fit-content;
  margin-top: 10px;
  padding: 6px 10px;
  border-radius: 9px;
  color: #9a3412;
  background: #ffedd5;
  font-size: 12px;
  font-weight: 800;
}

.report-source-actions {
  display: grid;
  grid-template-columns: auto auto;
  align-items: center;
  gap: 9px;
}

.source-summary-grid {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(3, minmax(62px, 1fr));
  gap: 8px;
}

.source-summary-grid > div {
  padding: 9px 10px;
  border: 1px solid rgba(13, 148, 136, 0.14);
  border-radius: 12px;
  text-align: center;
  background: rgba(255, 255, 255, 0.72);
}

.source-summary-grid span {
  display: block;
  color: #64748b;
  font-size: 11px;
}

.source-summary-grid strong {
  display: block;
  margin-top: 2px;
  color: #0f172a;
  font-size: 18px;
}

.source-configure-btn,
.source-apply-generate-btn {
  min-height: 40px;
  padding: 0 15px;
  border-radius: 12px;
  font-weight: 900;
  cursor: pointer;
}

.source-configure-btn {
  border: 1px solid #99f6e4;
  color: #0f766e;
  background: #f0fdfa;
}

.source-apply-generate-btn {
  border: 1px solid #0f766e;
  color: #ffffff;
  background: #0f766e;
}

.source-configure-btn:disabled,
.source-apply-generate-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.report-source-dialog-layer {
  position: fixed;
  inset: 0;
  z-index: 15000;
  display: grid;
  place-items: center;
  padding: 34px;
  background: rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(8px);
}

.report-export-dialog-layer {
  position: fixed;
  inset: 0;
  z-index: 16000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(2, 6, 23, 0.64);
  backdrop-filter: blur(10px);
}

.report-export-dialog {
  position: relative;
  width: min(660px, calc(100vw - 48px));
  max-height: calc(100dvh - 48px);
  overflow-y: auto;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 28px;
  background: #f8fafc;
  box-shadow: 0 36px 110px rgba(2, 6, 23, 0.42);
}

.export-dialog-close {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 2;
  width: 42px;
  height: 42px;
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #dc2626;
  background: rgba(254, 226, 226, 0.9);
  font-size: 27px;
  line-height: 1;
  cursor: pointer;
}

.export-dialog-head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px 76px 21px 24px;
  border-bottom: 1px solid #e2e8f0;
  background:
    radial-gradient(circle at 18% 0%, rgba(20, 184, 166, 0.2), transparent 44%),
    #ffffff;
}

.export-dialog-icon {
  width: 54px;
  height: 62px;
  flex: 0 0 54px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  color: #ffffff;
  background: linear-gradient(145deg, #0f766e, #0e7490);
  box-shadow: 0 12px 26px rgba(13, 148, 136, 0.26);
}

.export-dialog-icon span {
  font-size: 23px;
  font-weight: 950;
}

.export-dialog-head > div:last-child > span {
  color: #0f766e;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.14em;
}

.export-dialog-head h3 {
  margin: 4px 0 5px;
  color: #0f172a;
  font-size: 23px;
}

.export-dialog-head p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.55;
}

.export-dialog-body {
  display: grid;
  gap: 14px;
  padding: 20px 24px 18px;
}

.export-snapshot-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 15px 16px;
  border: 1px solid #dbeafe;
  border-radius: 18px;
  background: #ffffff;
}

.export-snapshot-card > div:first-child,
.export-snapshot-card span,
.export-snapshot-card strong,
.export-snapshot-card small {
  display: block;
  min-width: 0;
}

.export-snapshot-card span {
  color: #64748b;
  font-size: 10px;
  font-weight: 850;
}

.export-snapshot-card strong {
  margin-top: 4px;
  overflow: hidden;
  color: #0f172a;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.export-snapshot-card small {
  margin-top: 5px;
  color: #94a3b8;
}

.export-snapshot-status {
  flex: 0 0 auto;
  padding: 7px 10px;
  border-radius: 999px;
  color: #0369a1;
  background: #e0f2fe;
  font-size: 11px;
  font-weight: 900;
}

.export-feature-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
}

.export-feature-grid > div {
  min-width: 0;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 15px;
  background: #ffffff;
}

.export-feature-grid strong,
.export-feature-grid small {
  display: block;
}

.export-feature-grid strong {
  margin-top: 8px;
  color: #334155;
  font-size: 12px;
}

.export-feature-grid small {
  margin-top: 3px;
  color: #94a3b8;
  font-size: 10px;
}

.feature-dot {
  width: 18px;
  height: 6px;
  border-radius: 999px;
  display: block;
}

.feature-dot.chart { background: #0e7490; }
.feature-dot.table { background: #14b8a6; }
.feature-dot.photo { background: #2563eb; }
.feature-dot.ai { background: #f59e0b; }

.export-task-panel {
  padding: 15px;
  border: 1px solid #bae6fd;
  border-radius: 17px;
  background: #f0f9ff;
}

.export-task-panel.completed {
  border-color: #99f6e4;
  background: #f0fdfa;
}

.export-task-panel.failed {
  border-color: #fecaca;
  background: #fef2f2;
}

.export-task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.export-task-head span,
.export-task-head strong {
  display: block;
}

.export-task-head span {
  color: #0284c7;
  font-size: 10px;
  font-weight: 900;
}

.export-task-head strong {
  margin-top: 4px;
  color: #0f172a;
  font-size: 13px;
}

.export-task-head b {
  color: #0e7490;
  font-size: 19px;
}

.export-progress-track {
  height: 8px;
  margin-top: 13px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.22);
}

.export-progress-track span {
  height: 100%;
  display: block;
  border-radius: inherit;
  background: linear-gradient(90deg, #0ea5e9, #14b8a6);
  transition: width 0.35s ease;
}

.export-result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 12px;
}

.export-result-meta span {
  padding: 5px 8px;
  border-radius: 999px;
  color: #0f766e;
  background: rgba(255, 255, 255, 0.8);
  font-size: 10px;
  font-weight: 800;
}

.export-error-message,
.export-dialog-note {
  margin: 0;
  line-height: 1.6;
}

.export-error-message {
  padding: 10px 12px;
  border-radius: 12px;
  color: #b91c1c;
  background: #fee2e2;
  font-size: 12px;
}

.export-dialog-note {
  color: #64748b;
  font-size: 11px;
}

.export-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 15px 24px 20px;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
}

.export-secondary-btn,
.export-primary-btn {
  min-width: 112px;
  height: 42px;
  border-radius: 13px;
  font-weight: 900;
  cursor: pointer;
}

.export-secondary-btn {
  border: 1px solid #cbd5e1;
  color: #475569;
  background: #ffffff;
}

.export-primary-btn {
  border: 1px solid #0f766e;
  color: #ffffff;
  background: #0f766e;
}

.export-primary-btn.download {
  border-color: #0369a1;
  background: #0369a1;
}

.export-primary-btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.report-source-dialog {
  position: relative;
  width: min(1120px, calc(100vw - 68px));
  max-height: min(860px, calc(100vh - 68px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 28px;
  background: #f8fafc;
  box-shadow: 0 36px 100px rgba(15, 23, 42, 0.3);
}

.source-dialog-close {
  position: absolute;
  top: 15px;
  right: 15px;
  z-index: 3;
  width: 42px;
  height: 42px;
  border: 1px solid rgba(239, 68, 68, 0.22);
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #dc2626;
  background: rgba(254, 226, 226, 0.9);
  font-size: 27px;
  line-height: 1;
  cursor: pointer;
}

.source-dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  padding: 24px 78px 20px 26px;
  border-bottom: 1px solid #e2e8f0;
  background:
    radial-gradient(circle at 12% 0%, rgba(20, 184, 166, 0.16), transparent 36%),
    #ffffff;
}

.source-dialog-head > div:first-child > span {
  color: #0f766e;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.15em;
}

.source-dialog-head h3 {
  margin: 5px 0;
  color: #0f172a;
  font-size: 23px;
}

.source-dialog-head p {
  margin: 0;
  color: #64748b;
}

.source-dialog-total {
  min-width: 100px;
  padding: 11px 14px;
  border-radius: 15px;
  text-align: center;
  color: #115e59;
  background: #ccfbf1;
}

.source-dialog-total strong,
.source-dialog-total span {
  display: block;
}

.source-dialog-total strong {
  font-size: 24px;
}

.source-dialog-total span {
  margin-top: 2px;
  font-size: 11px;
  font-weight: 800;
}

.source-mode-switch {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 18px 24px 12px;
}

.source-mode-switch button {
  min-width: 0;
  padding: 14px 16px;
  border: 1px solid #cbd5e1;
  border-radius: 16px;
  color: #475569;
  background: #ffffff;
  text-align: left;
  cursor: pointer;
}

.source-mode-switch button.active {
  border-color: #14b8a6;
  color: #115e59;
  background: #f0fdfa;
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.1);
}

.source-mode-switch button:disabled {
  cursor: default;
}

.source-mode-switch strong,
.source-mode-switch span {
  display: block;
}

.source-mode-switch strong {
  font-size: 15px;
}

.source-mode-switch span {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.source-dialog-toolbar {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) 190px auto;
  gap: 10px;
  padding: 0 24px 12px;
}

.source-search-box {
  position: relative;
}

.source-search-box > span {
  position: absolute;
  left: 14px;
  top: 50%;
  width: 13px;
  height: 13px;
  border: 2px solid #94a3b8;
  border-radius: 50%;
  transform: translateY(-58%);
}

.source-search-box > span::after {
  content: '';
  position: absolute;
  width: 6px;
  height: 2px;
  right: -5px;
  bottom: -2px;
  border-radius: 2px;
  background: #94a3b8;
  transform: rotate(45deg);
}

.source-search-box input,
.source-dialog-toolbar select {
  width: 100%;
  height: 42px;
  box-sizing: border-box;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  color: #0f172a;
  background: #ffffff;
  font-size: 14px;
}

.source-search-box input {
  padding: 0 14px 0 40px;
}

.source-dialog-toolbar select {
  padding: 0 12px;
}

.source-selected-toggle {
  height: 42px;
  padding: 0 13px;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #475569;
  background: #ffffff;
  font-size: 13px;
  font-weight: 800;
  white-space: nowrap;
}

.source-dialog-batch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin: 0 24px 12px;
  padding: 10px 13px;
  border-radius: 13px;
  color: #475569;
  background: #e8f2f2;
}

.source-dialog-batch > div {
  display: flex;
  align-items: center;
  gap: 8px;
}

.source-dialog-batch strong {
  color: #0f766e;
  font-size: 19px;
}

.source-dialog-batch button {
  padding: 6px 9px;
  border: 0;
  border-radius: 8px;
  color: #0f766e;
  background: #ffffff;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.source-dialog-batch button.danger {
  color: #b91c1c;
}

.source-station-list {
  min-height: 160px;
  flex: 1;
  overflow-y: auto;
  padding: 0 24px 20px;
}

.source-region-group + .source-region-group {
  margin-top: 16px;
}

.source-region-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding: 0 2px;
}

.source-region-head strong {
  color: #334155;
  font-size: 14px;
}

.source-region-head span {
  color: #94a3b8;
  font-size: 12px;
}

.source-station-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.source-station-option {
  position: relative;
  min-width: 0;
  padding: 12px 12px 12px 40px;
  border: 1px solid #e2e8f0;
  border-radius: 13px;
  color: #334155;
  background: #ffffff;
  cursor: pointer;
}

.source-station-option.selected {
  border-color: #5eead4;
  background: #f0fdfa;
}

.source-station-option.readonly {
  cursor: default;
}

.source-station-option input {
  position: absolute;
  opacity: 0;
}

.source-checkbox-mark {
  position: absolute;
  left: 13px;
  top: 50%;
  width: 17px;
  height: 17px;
  border: 1px solid #94a3b8;
  border-radius: 5px;
  background: #ffffff;
  transform: translateY(-50%);
}

.source-station-option.selected .source-checkbox-mark {
  border-color: #0d9488;
  background: #0d9488;
}

.source-station-option.selected .source-checkbox-mark::after {
  content: '';
  position: absolute;
  left: 5px;
  top: 2px;
  width: 4px;
  height: 8px;
  border: solid #ffffff;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.source-station-info,
.source-station-info strong,
.source-station-info small {
  display: block;
  min-width: 0;
}

.source-station-info strong {
  overflow: hidden;
  color: #0f172a;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-station-info small {
  margin-top: 4px;
  color: #64748b;
  font-size: 11px;
}

.source-list-empty {
  min-height: 150px;
  display: grid;
  place-items: center;
  color: #94a3b8;
}

.source-dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 24px;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
}

.source-dialog-footer p {
  margin: 0;
  color: #64748b;
  font-size: 12px;
}

.source-dialog-footer > div {
  display: flex;
  gap: 9px;
}

.source-cancel-btn,
.source-confirm-btn {
  min-width: 94px;
  height: 40px;
  border-radius: 12px;
  font-weight: 900;
  cursor: pointer;
}

.source-cancel-btn {
  border: 1px solid #cbd5e1;
  color: #475569;
  background: #ffffff;
}

.source-confirm-btn {
  border: 1px solid #0f766e;
  color: #ffffff;
  background: #0f766e;
}

.source-confirm-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.template-placeholder {
  min-height: 260px;
  padding: 34px;
  border-radius: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  background:
    radial-gradient(circle at 85% 18%, rgba(245, 158, 11, 0.13), transparent 30%),
    linear-gradient(145deg, #ffffff, #fffbeb);
}

.template-placeholder-mark {
  width: 82px;
  height: 82px;
  flex: 0 0 82px;
  border-radius: 24px;
  display: grid;
  place-items: center;
  color: #ffffff;
  background: linear-gradient(145deg, #d97706, #f59e0b);
  box-shadow: 0 18px 36px rgba(217, 119, 6, 0.22);
  font-size: 25px;
  font-weight: 950;
  letter-spacing: 0.08em;
}

.template-placeholder span {
  color: #b45309;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.12em;
}

.template-placeholder h3 {
  margin: 6px 0 8px;
  color: #0f172a;
  font-size: 24px;
}

.template-placeholder p {
  max-width: 660px;
  margin: 0;
  color: #64748b;
  line-height: 1.75;
}

.ai-generation-state {
  min-height: 330px;
  padding: 38px 42px;
  border-radius: 28px;
  display: grid;
  grid-template-columns: 210px minmax(0, 1fr);
  align-items: center;
  gap: 42px;
  overflow: hidden;
  color: #e0f2fe;
  border-color: rgba(56, 189, 248, 0.22);
  background:
    radial-gradient(circle at 13% 50%, rgba(34, 211, 238, 0.18), transparent 26%),
    radial-gradient(circle at 88% 0%, rgba(14, 165, 233, 0.16), transparent 30%),
    linear-gradient(130deg, #071827 0%, #0b2538 58%, #0c3445 100%);
  box-shadow: 0 26px 64px rgba(7, 24, 39, 0.24);
}

.ai-generation-visual {
  position: relative;
  width: 188px;
  height: 188px;
  display: grid;
  place-items: center;
}

.ai-core {
  position: relative;
  z-index: 3;
  width: 86px;
  height: 86px;
  border-radius: 28px;
  display: grid;
  place-items: center;
  color: #f0fdfa;
  background: linear-gradient(145deg, #0891b2, #0ea5e9);
  box-shadow: 0 0 0 10px rgba(34, 211, 238, 0.08), 0 0 46px rgba(56, 189, 248, 0.38);
  font-size: 27px;
  font-weight: 950;
  letter-spacing: 0.08em;
  animation: aiCorePulse 2.2s ease-in-out infinite;
}

.ai-orbit {
  position: absolute;
  inset: 18px;
  border: 1px solid rgba(125, 211, 252, 0.28);
  border-radius: 50%;
}

.ai-orbit::before {
  content: "";
  position: absolute;
  top: -5px;
  left: 50%;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #67e8f9;
  box-shadow: 0 0 16px #22d3ee;
}

.orbit-one {
  animation: aiOrbitSpin 5.4s linear infinite;
}

.orbit-two {
  inset: 2px;
  border-style: dashed;
  opacity: 0.55;
  animation: aiOrbitSpin 8s linear infinite reverse;
}

.ai-spark {
  position: absolute;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #bae6fd;
  box-shadow: 0 0 14px #7dd3fc;
  animation: aiSparkFloat 2.4s ease-in-out infinite;
}

.spark-one {
  top: 28px;
  right: 18px;
}

.spark-two {
  bottom: 23px;
  left: 20px;
  animation-delay: -1.1s;
}

.ai-generation-content {
  min-width: 0;
}

.ai-generation-kicker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid rgba(103, 232, 249, 0.22);
  border-radius: 999px;
  color: #a5f3fc;
  background: rgba(8, 145, 178, 0.12);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22d3ee;
  box-shadow: 0 0 10px #22d3ee;
  animation: liveDotPulse 1.2s ease-in-out infinite;
}

.ai-generation-content h3 {
  margin: 14px 0 8px;
  color: #f8fafc;
  font-size: clamp(22px, 3vw, 30px);
  line-height: 1.4;
}

.ai-generation-content>p {
  margin: 0 0 22px;
  color: #a9c4d5;
  line-height: 1.75;
}

.ai-progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 9px;
  color: #bae6fd;
  font-size: 13px;
}

.ai-progress-head strong {
  color: #67e8f9;
  font-size: 18px;
}

.ai-progress-track {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
}

.ai-progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0891b2, #22d3ee, #7dd3fc);
  box-shadow: 0 0 18px rgba(34, 211, 238, 0.45);
  transition: width 0.45s ease;
}

.ai-stage-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 13px;
}

.ai-stage-list span {
  padding-top: 10px;
  border-top: 2px solid rgba(148, 163, 184, 0.18);
  color: #68869a;
  font-size: 12px;
  text-align: center;
  transition: color 0.2s ease, border-color 0.2s ease;
}

.ai-stage-list span.done {
  color: #a5f3fc;
  border-color: #22d3ee;
}

.state-card {
  min-height: 220px;
  border-radius: 24px;
  padding: 36px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748b;
}

.state-card.error {
  min-height: auto;
  padding: 16px 18px;
  color: #b91c1c;
  background: #fff1f2;
  border: 1px solid #fecdd3;
}

.state-orb {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0ea5e9, #22c55e);
  margin-bottom: 14px;
}

.state-orb.loading {
  animation: pulseOrb 1.2s ease-in-out infinite;
}

.report-document {
  border-radius: 28px;
  padding: 28px;
}

.report-document-head {
  display: grid;
  grid-template-columns: minmax(250px, 0.72fr) minmax(520px, 1.28fr);
  gap: 24px;
  align-items: center;
  padding-bottom: 22px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.25);
}

.report-title-block {
  min-width: 0;
  padding: 4px 0;
}

.report-title-block h1 {
  max-width: 520px;
}

.report-context-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(220px, 0.85fr);
  gap: 8px;
  min-width: 0;
  padding: 7px;
  border: 1px solid #e2e8f0;
  border-radius: 22px;
  background: #f6f9fb;
}

.report-context-grid.single-context {
  grid-template-columns: minmax(280px, 420px);
  justify-content: end;
}

.report-data-scope-note,
.doc-meta {
  min-width: 0;
  min-height: 132px;
  box-sizing: border-box;
  padding: 15px 16px;
  border: 1px solid #e4edf4;
  border-radius: 16px;
  background: #ffffff;
}

.report-data-scope-note {
  background:
    radial-gradient(circle at 96% 4%, rgba(14, 165, 233, 0.11), transparent 40%),
    #ffffff;
}

.report-context-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 11px;
}

.report-context-label span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 27px;
  height: 22px;
  border-radius: 8px;
  color: #ffffff;
  background: #1686bd;
  font-size: 10px;
  font-weight: 900;
}

.report-context-label b {
  color: #0f5278;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.06em;
}

.report-data-scope-note p {
  margin: 0;
  color: #475569;
  font-size: 12.5px;
  line-height: 1.75;
}

.doc-meta {
  display: flex;
  flex-direction: column;
  color: #64748b;
}

.doc-meta strong {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.65;
}

.report-generated-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: auto;
  padding-top: 10px;
  color: #64748b;
}

.snapshot-hint {
  display: inline-flex;
  width: fit-content;
  padding: 3px 8px;
  border-radius: 999px;
  color: #0369a1;
  background: #e0f2fe;
  font-weight: 800;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin: 22px 0 0;
}

.summary-card {
  padding: 18px;
  border-radius: 20px;
  background: linear-gradient(180deg, #f8fafc, #ffffff);
  border: 1px solid rgba(203, 213, 225, 0.75);
}

.summary-card span {
  color: #64748b;
  font-size: 13px;
}

.summary-card strong {
  display: block;
  margin: 6px 0;
  font-size: 30px;
  color: #0f172a;
}

.summary-card small {
  color: #94a3b8;
}

.chapter-card {
  padding: 28px;
  margin-top: 34px;
  border-radius: 24px;
  background: #ffffff;
  border: 1px solid rgba(203, 213, 225, 0.72);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.055);
}

.chapter-lead {
  margin: 0 0 24px;
  color: #334155;
  line-height: 2;
  text-indent: 2em;
}

.strong-lead {
  font-size: 24px;
  font-weight: 900;
  color: #020617;
  text-indent: 2em;
}

.chapter-note {
  margin: 0 0 22px;
  padding: 12px 14px;
  border-radius: 14px;
  color: #475569;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  line-height: 1.7;
}

.chapter-banner {
  position: relative;
  overflow: hidden;
  min-height: 64px;
  margin: -28px -28px 28px;
  padding: 16px 24px;
  border-radius: 23px 23px 0 0;
  background: linear-gradient(105deg, #0b6f9f 0%, #1686bd 58%, #2b9dca 100%);
  color: #ffffff;
  display: flex;
  align-items: center;
  font-size: 22px;
  font-weight: 900;
  line-height: 1.45;
  letter-spacing: 0.02em;
  box-shadow: inset 0 -1px 0 rgba(255, 255, 255, 0.18);
}

.chapter-banner::after {
  content: "";
  position: absolute;
  right: -24px;
  top: 50%;
  width: 132px;
  height: 132px;
  border: 24px solid rgba(255, 255, 255, 0.08);
  border-radius: 50%;
  transform: translateY(-50%);
  pointer-events: none;
}

.report-table-wrap {
  overflow-x: auto;
  border-radius: 18px;
  border: 1px solid #cbd5e1;
}

.report-table {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
  background: #ffffff;
}

.report-table th,
.report-table td {
  border: 1px solid #cbd5e1;
  padding: 13px 12px;
  text-align: center;
  vertical-align: middle;
  color: #0f172a;
}

.report-table th {
  background: #eff6ff;
  font-weight: 800;
}

.typical-table th:first-child {
  width: 260px;
}

.text-cell {
  text-align: left !important;
  line-height: 1.8;
}

.unit-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.unit-type-pill {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  color: #0369a1;
  background: #e0f2fe;
}

.unit-type-pill.holding {
  color: #92400e;
  background: #fef3c7;
}

.total-row td {
  font-weight: 900;
  background: #f8fafc;
}

.empty-cell {
  height: 96px;
  color: #94a3b8;
}

.finding-distribution-chart {
  overflow: hidden;
  border: 1px solid #dbe7f0;
  border-radius: 20px;
  background:
    radial-gradient(circle at 92% 0%, rgba(14, 165, 233, 0.1), transparent 34%),
    linear-gradient(180deg, #fbfdff, #f8fbfd);
}

.finding-chart-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 18px 20px;
  border-bottom: 1px solid #e2e8f0;
}

.finding-chart-head>div:first-child span,
.finding-chart-head>div:first-child strong {
  display: block;
}

.finding-chart-head>div:first-child span {
  margin-bottom: 4px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.finding-chart-head>div:first-child strong {
  color: #0f172a;
  font-size: 19px;
}

.finding-chart-total {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex: 0 0 auto;
}

.finding-chart-total strong {
  color: #0b6f9f;
  font-size: 30px;
  line-height: 1;
}

.finding-chart-total span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.finding-flow-list {
  display: grid;
  gap: 14px;
  padding: 22px 20px 24px;
}

.finding-flow-row {
  display: grid;
  grid-template-columns: minmax(150px, 0.85fr) minmax(220px, 2.5fr) 92px;
  align-items: center;
  gap: 16px;
}

.finding-flow-label {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.finding-flow-label>span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 27px;
  height: 27px;
  flex: 0 0 auto;
  border-radius: 9px;
  color: var(--flow-color);
  background: #eef5f9;
  font-size: 10px;
  font-weight: 900;
}

.finding-flow-label strong {
  overflow: hidden;
  color: #1e293b;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.finding-flow-track {
  height: 13px;
  overflow: hidden;
  border-radius: 999px;
  background: #e9eff4;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.07);
}

.finding-flow-track span {
  display: block;
  width: var(--flow-width);
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #8cc6df, var(--flow-color));
  box-shadow: 0 4px 10px rgba(22, 127, 179, 0.18);
  transform-origin: left center;
  animation: findingBarReveal 0.65s ease both;
}

.finding-flow-value {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 7px;
  white-space: nowrap;
}

.finding-flow-value strong {
  color: #0f172a;
  font-size: 15px;
}

.finding-flow-value span {
  color: #64748b;
  font-size: 12px;
}

.finding-chart-empty {
  padding: 48px 20px;
  color: #94a3b8;
  text-align: center;
}

@keyframes findingBarReveal {
  from {
    transform: scaleX(0);
    opacity: 0.35;
  }
  to {
    transform: scaleX(1);
    opacity: 1;
  }
}

.chart-title {
  margin: 28px 0 8px 36px;
  font-size: 24px;
  color: #1f2937;
}

.bar-chart {
  position: relative;
  min-height: 360px;
  margin-top: 6px;
  padding: 18px 22px 12px 84px;
  overflow-x: auto;
}

.chart-grid {
  position: absolute;
  left: 18px;
  right: 22px;
  top: 18px;
  bottom: 66px;
  pointer-events: none;
}

.chart-grid::before {
  content: "";
  position: absolute;
  left: 62px;
  top: 0;
  width: 1px;
  bottom: 0;
  background: rgba(15, 23, 42, 0.38);
}

.chart-grid span {
  position: absolute;
  left: 0;
  transform: translateY(50%);
  min-width: 48px;
  text-align: right;
  font-size: 16px;
  color: #0f172a;
}

.chart-grid span::after {
  content: "";
  position: absolute;
  left: 62px;
  right: -100vw;
  top: 50%;
  height: 1px;
  background: rgba(148, 163, 184, 0.82);
}

.chart-bars {
  position: relative;
  z-index: 1;
  min-width: max(720px, 100%);
  height: 320px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 34px;
  padding-left: 52px;
}

.chart-bar-item {
  height: 100%;
  min-width: 104px;
  display: grid;
  grid-template-rows: 26px 1fr 36px 22px;
  justify-items: center;
  align-items: end;
}

.bar-value {
  font-size: 16px;
  color: #020617;
  align-self: end;
}

.bar-track {
  width: 54px;
  height: 100%;
  display: flex;
  align-items: flex-end;
}

.bar-fill {
  width: 100%;
  min-height: 4px;
  background: linear-gradient(180deg, #76b9ea, #4f9bd2);
  border-radius: 2px 2px 0 0;
}

.bar-label {
  align-self: start;
  padding-top: 10px;
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
  text-align: center;
  line-height: 1.25;
}

.bar-percent {
  align-self: start;
  color: #64748b;
  font-size: 13px;
}

.chart-empty {
  margin: auto;
  color: #94a3b8;
  font-weight: 700;
}

.content-source-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
  padding: 10px 12px 10px 15px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  color: #64748b;
  background: #f8fafc;
  font-size: 13px;
  line-height: 1.6;
}

.flow-highlight-section {
  margin-top: 18px;
  padding: 18px;
  border-radius: 20px;
  border: 1px solid #dbeafe;
  background: linear-gradient(180deg, #f8fbff, #ffffff);
}

.flow-highlight-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 12px;
}

.flow-highlight-head h4 {
  margin: 0;
  color: #0f172a;
  font-size: 22px;
}

.flow-highlight-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.work-plan-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.work-plan-title-row h4 {
  margin: 0;
}

.flow-highlight-head p {
  margin: 0;
  color: #0369a1;
  font-weight: 900;
}

.flow-highlight-summary {
  margin: 12px 0 0;
  color: #475569;
  line-height: 1.8;
}

.highlight-issue-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.highlight-issue-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 132px;
  gap: 14px;
  padding: 14px;
  border-radius: 18px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.06);
}

.highlight-issue-text span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.highlight-issue-text strong {
  display: block;
  margin: 4px 0 8px;
  color: #0f172a;
}

.highlight-issue-text p {
  margin: 0;
  color: #334155;
  line-height: 1.75;
}

.highlight-photo {
  width: 132px;
  height: 112px;
  border-radius: 14px;
  overflow: hidden;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 800;
}

.highlight-photo.is-clickable {
  border: 0;
  padding: 0;
  cursor: zoom-in;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.highlight-photo.is-clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 26px rgba(15, 23, 42, 0.18);
}

.highlight-photo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.safety-scope-section,
.safety-category-section,
.safety-highlight-group {
  padding: 22px;
  border: 1px solid #dbe7ef;
  border-radius: 20px;
  background:
    radial-gradient(circle at 96% 0%, rgba(14, 165, 233, 0.08), transparent 28%),
    linear-gradient(180deg, #fbfdff, #ffffff);
}

.safety-scope-section + .safety-scope-section,
.safety-category-section + .safety-category-section,
.safety-highlight-group + .safety-highlight-group {
  margin-top: 24px;
}

.safety-section-head,
.safety-category-heading,
.safety-highlight-group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.safety-section-head > div:first-child > span,
.safety-category-heading > div > span {
  color: #0284c7;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.12em;
}

.safety-section-head h3,
.safety-category-heading h3 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 21px;
}

.safety-section-metrics {
  display: flex;
  gap: 8px;
}

.safety-section-metrics span {
  padding: 8px 11px;
  border-radius: 12px;
  color: #475569;
  background: #f1f5f9;
  font-size: 12px;
}

.safety-section-metrics b {
  margin-right: 3px;
  color: #0369a1;
  font-size: 16px;
}

.safety-narrative {
  margin: 18px 0 20px;
}

.safety-unit-chart-shell {
  overflow: hidden;
  border: 1px solid #dbe7ef;
  border-radius: 18px;
  background: #ffffff;
}

.safety-chart-legend {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 18px;
  padding: 13px 16px;
  border-bottom: 1px solid #e8eef3;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.safety-chart-legend span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.safety-chart-legend i {
  width: 11px;
  height: 11px;
  border-radius: 3px;
}

.safety-chart-legend .issue-series,
.safety-unit-bar.issue-series {
  background: linear-gradient(180deg, #38bdf8, #167fb3);
}

.safety-chart-legend .station-series,
.safety-unit-bar.station-series {
  background: linear-gradient(180deg, #fbbf24, #d97706);
}

.safety-unit-chart-scroll {
  overflow-x: auto;
  padding: 18px 18px 8px;
  scrollbar-color: #b7c8d4 transparent;
  scrollbar-width: thin;
}

.safety-unit-chart {
  height: 350px;
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr);
}

.safety-unit-y-axis {
  height: 294px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding-right: 10px;
  color: #64748b;
  font-size: 11px;
  text-align: right;
}

.safety-unit-plot {
  position: relative;
  height: 320px;
  display: grid;
  grid-auto-columns: minmax(72px, 1fr);
  grid-auto-flow: column;
  align-items: stretch;
  gap: 12px;
  padding: 0 10px;
  border-left: 1px solid #94a3b8;
}

.safety-unit-grid-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: #e2e8f0;
  pointer-events: none;
}

.safety-unit-bar-group {
  position: relative;
  z-index: 1;
  min-width: 0;
  display: grid;
  grid-template-rows: 294px 1fr;
  gap: 8px;
}

.safety-unit-bars {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 6px;
  border-bottom: 1px solid #94a3b8;
}

.safety-unit-bar {
  position: relative;
  width: 24px;
  min-height: 0;
  border-radius: 6px 6px 0 0;
  transition: height 0.45s ease;
}

.safety-unit-bar span {
  position: absolute;
  top: -21px;
  left: 50%;
  transform: translateX(-50%);
  color: #334155;
  font-size: 11px;
  font-weight: 900;
}

.safety-unit-bar-group > strong {
  overflow: hidden;
  color: #334155;
  font-size: 11px;
  line-height: 1.25;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.safety-chart-empty {
  padding: 42px 18px;
  color: #94a3b8;
  text-align: center;
}

.safety-typical-grid {
  display: grid;
  gap: 18px;
}

.safety-typical-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 270px;
  gap: 20px;
  padding: 20px;
  border: 1px solid #dbe7ef;
  border-radius: 20px;
  background:
    radial-gradient(circle at 0% 0%, rgba(14, 165, 233, 0.08), transparent 30%),
    #ffffff;
}

.safety-typical-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.safety-typical-title > span {
  color: #0369a1;
  font-size: 12px;
  font-weight: 900;
}

.safety-typical-copy h3 {
  margin: 10px 0 8px;
  color: #0f172a;
  font-size: 22px;
}

.safety-typical-copy > p,
.safety-typical-copy > small {
  display: block;
  margin: 0;
  color: #475569;
  line-height: 1.8;
}

.safety-typical-copy > small {
  margin-top: 6px;
  color: #64748b;
}

.safety-typical-example {
  margin-top: 14px;
  padding: 13px 14px;
  border-radius: 14px;
  background: #f8fafc;
}

.safety-typical-example b,
.safety-typical-example span {
  display: block;
}

.safety-typical-example b {
  margin-bottom: 4px;
  color: #0f172a;
}

.safety-typical-example span {
  color: #475569;
  line-height: 1.65;
}

.safety-typical-photo {
  position: relative;
  width: 100%;
  min-height: 190px;
  overflow: hidden;
  padding: 0;
  border: 0;
  border-radius: 16px;
  background: #eaf1f5;
  cursor: zoom-in;
}

.safety-typical-photo img {
  width: 100%;
  height: 100%;
  min-height: 190px;
  object-fit: cover;
}

.safety-typical-photo span {
  position: absolute;
  right: 10px;
  bottom: 10px;
  padding: 5px 8px;
  border-radius: 999px;
  color: #ffffff;
  background: rgba(15, 23, 42, 0.72);
  font-size: 11px;
  font-weight: 800;
}

.safety-typical-photo.empty {
  display: grid;
  place-items: center;
  color: #94a3b8;
  cursor: default;
}

.safety-typical-photo.empty span {
  position: static;
  color: #94a3b8;
  background: transparent;
}

.safety-category-heading > strong {
  color: #0b6f9f;
  font-size: 26px;
}

.safety-category-list {
  display: grid;
  gap: 14px;
}

.safety-category-row {
  display: grid;
  grid-template-columns: minmax(150px, 0.8fr) minmax(240px, 2.3fr) 96px;
  align-items: center;
  gap: 16px;
}

.safety-category-row > strong {
  color: #334155;
  font-size: 14px;
}

.safety-category-track {
  height: 13px;
  overflow: hidden;
  border-radius: 999px;
  background: #e8eef3;
}

.safety-category-track span {
  display: block;
  width: var(--category-width);
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #9ac8dc, var(--category-color));
}

.safety-category-row > div:last-child {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 6px;
}

.safety-category-row b {
  color: #0f172a;
}

.safety-category-row > div:last-child span {
  color: #64748b;
  font-size: 12px;
}

.safety-highlight-group-head {
  padding-bottom: 14px;
  border-bottom: 1px solid #e2e8f0;
}

.safety-highlight-group-head > span {
  color: #0f172a;
  font-size: 19px;
  font-weight: 900;
}

.safety-highlight-group-head > strong {
  color: #0369a1;
  font-size: 13px;
}

.safety-highlight-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.safety-highlight-card {
  min-width: 0;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 17px;
  background: #ffffff;
}

.safety-highlight-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.safety-highlight-card-head span {
  color: #0284c7;
  font-size: 11px;
  font-weight: 900;
}

.safety-highlight-card-head h4 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 18px;
}

.safety-highlight-card > p {
  margin: 12px 0;
  color: #64748b;
  line-height: 1.7;
}

.safety-highlight-issues {
  display: grid;
  gap: 9px;
}

.safety-highlight-issue {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 72px;
  gap: 10px;
  padding: 10px;
  border-radius: 13px;
  background: #f8fafc;
}

.safety-highlight-issue b,
.safety-highlight-issue span {
  display: block;
}

.safety-highlight-issue b {
  margin-bottom: 3px;
  color: #0f172a;
}

.safety-highlight-issue span {
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.safety-highlight-issue button {
  width: 72px;
  height: 64px;
  overflow: hidden;
  padding: 0;
  border: 0;
  border-radius: 10px;
  cursor: zoom-in;
}

.safety-highlight-issue img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.safety-analysis-list {
  display: grid;
  gap: 12px;
}

.safety-analysis-list > article {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr);
  gap: 14px;
  padding: 17px;
  border: 1px solid #e2e8f0;
  border-radius: 17px;
  background: #fbfdff;
}

.safety-analysis-list > article > span {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  color: #ffffff;
  background: linear-gradient(145deg, #0b6f9f, #2b9dca);
  font-size: 12px;
  font-weight: 900;
}

.safety-analysis-list h4 {
  margin: 0 0 5px;
  color: #0f172a;
}

.safety-analysis-list p {
  margin: 0;
  color: #475569;
  line-height: 1.75;
}

.finance-summary-cards {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.finance-summary-cards .summary-card:first-child strong {
  font-size: 22px;
  letter-spacing: -0.04em;
}

.finance-scope-strip {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.7fr);
  gap: 12px;
  margin-bottom: 14px;
}

.finance-scope-strip > div {
  padding: 15px 17px;
  border: 1px solid #dce7ee;
  border-radius: 16px;
  background: linear-gradient(145deg, #f8fbfd, #ffffff);
}

.finance-scope-strip span,
.finance-scope-strip strong {
  display: block;
}

.finance-scope-strip span {
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.finance-scope-strip strong {
  color: #0f172a;
  line-height: 1.6;
}

.finance-scope-text {
  margin: 0 0 22px;
  color: #475569;
  line-height: 1.85;
}

.finance-overview-table {
  margin-bottom: 24px;
}

.finance-station-breakdown-cell {
  min-width: 270px;
}

.finance-station-breakdown-cell span {
  display: inline-flex;
  margin: 3px;
  padding: 5px 8px;
  border-radius: 9px;
  color: #475569;
  background: #f1f5f9;
  font-size: 12px;
}

.finance-chart-section,
.finance-distribution-card {
  overflow: hidden;
  border: 1px solid #dbe7ef;
  border-radius: 20px;
  background: #ffffff;
}

.finance-subsection-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  padding: 17px 18px;
  border-bottom: 1px solid #e5edf2;
  background: #f8fbfd;
}

.finance-subsection-head span {
  color: #0284c7;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.13em;
}

.finance-subsection-head h3 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 18px;
}

.finance-subsection-head > strong {
  color: #0369a1;
  font-size: 13px;
}

.finance-chart-section .safety-chart-legend {
  padding: 0;
  border-bottom: 0;
  background: transparent;
}

.finance-chart-section .safety-unit-bar-group > small {
  margin-top: -7px;
  color: #94a3b8;
  font-size: 10px;
  text-align: center;
}

.finance-distribution-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.finance-distribution-card > p {
  min-height: 74px;
  margin: 0;
  padding: 16px 18px 4px;
  color: #475569;
  line-height: 1.75;
}

.finance-distribution-card .safety-category-list {
  padding: 14px 18px 20px;
}

.finance-distribution-card .safety-category-row {
  grid-template-columns: minmax(105px, 0.9fr) minmax(120px, 1.5fr) 78px;
}

.finance-station-report-list {
  display: grid;
  gap: 20px;
}

.finance-station-report {
  overflow: hidden;
  border: 1px solid #dbe7ef;
  border-radius: 20px;
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.045);
}

.finance-station-report-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 18px;
  border-bottom: 1px solid #e5edf2;
  background:
    radial-gradient(circle at 0% 0%, rgba(14, 165, 233, 0.1), transparent 34%),
    #f8fbfd;
}

.finance-station-report-head > div {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.finance-station-report-head > div > span {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  color: #ffffff;
  background: linear-gradient(145deg, #0b6f9f, #2b9dca);
  font-size: 11px;
  font-weight: 900;
}

.finance-station-report-head h3,
.finance-station-report-head p {
  margin: 0;
}

.finance-station-report-head h3 {
  color: #0f172a;
  font-size: 18px;
}

.finance-station-report-head p {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.finance-station-report-head > strong {
  flex: 0 0 auto;
  padding: 7px 11px;
  border-radius: 11px;
  color: #0369a1;
  background: #e0f2fe;
  font-size: 13px;
}

.finance-station-report .report-table-wrap {
  border: 0;
  border-radius: 0;
}

.finance-issue-table {
  min-width: 1060px;
}

.finance-issue-table th:first-child {
  width: 110px;
}

.finance-issue-table th:nth-child(2),
.finance-issue-table th:nth-child(3) {
  width: 130px;
}

.finance-photo-button {
  width: 76px;
  height: 58px;
  overflow: hidden;
  padding: 0;
  border: 0;
  border-radius: 10px;
  background: #e2e8f0;
  cursor: zoom-in;
}

.finance-photo-button img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.finance-ai-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.finance-ai-panel {
  overflow: hidden;
  border: 1px solid #dbe7ef;
  border-radius: 21px;
  background: #fbfdff;
}

.finance-ai-panel.suggestion {
  border-color: #d9e7dd;
  background: #fbfefc;
}

.finance-ai-panel-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 17px 18px;
  border-bottom: 1px solid #e5edf2;
  background: #f1f7fa;
}

.finance-ai-panel.suggestion .finance-ai-panel-head {
  background: #f1f8f3;
}

.finance-ai-panel-head > span {
  width: 39px;
  height: 39px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  color: #ffffff;
  background: #167fb3;
  font-size: 12px;
  font-weight: 900;
}

.finance-ai-panel.suggestion .finance-ai-panel-head > span {
  background: #36885a;
}

.finance-ai-panel-head small {
  color: #64748b;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.12em;
}

.finance-ai-panel-head h3 {
  margin: 3px 0 0;
  color: #0f172a;
  font-size: 19px;
}

.finance-ai-item {
  margin: 14px;
  padding: 15px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #ffffff;
}

.finance-ai-item-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.finance-ai-item h4 {
  margin: 0;
  color: #0f172a;
}

.finance-ai-item > p {
  margin: 9px 0 0;
  color: #475569;
  line-height: 1.75;
}

.finance-related-issues,
.finance-focus-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 12px;
}

.finance-related-issues span {
  width: 100%;
  padding: 8px 10px;
  border-radius: 10px;
  color: #64748b;
  background: #f8fafc;
  font-size: 12px;
  line-height: 1.55;
}

.finance-focus-tags span {
  padding: 5px 8px;
  border-radius: 999px;
  color: #166534;
  background: #dcfce7;
  font-size: 11px;
  font-weight: 800;
}

.equipment-summary-cards .summary-card {
  position: relative;
  overflow: hidden;
}

.equipment-summary-cards .summary-card::after {
  content: "";
  position: absolute;
  right: -28px;
  bottom: -34px;
  width: 86px;
  height: 86px;
  border: 16px solid rgba(14, 116, 144, 0.055);
  border-radius: 50%;
}

.equipment-overview-section {
  overflow: hidden;
  margin-top: 18px;
  border: 1px solid #dbe7e5;
  border-radius: 21px;
  background: linear-gradient(145deg, #fbfefd, #ffffff);
}

.equipment-overview-section.station-view {
  margin-top: 22px;
  border-color: #dce5ee;
  background: linear-gradient(145deg, #fbfcfe, #ffffff);
}

.equipment-subsection-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border-bottom: 1px solid #e2ebe8;
  background:
    radial-gradient(circle at 100% 0%, rgba(13, 148, 136, 0.1), transparent 34%),
    #f4faf8;
}

.station-view .equipment-subsection-head {
  border-bottom-color: #e2e8f0;
  background:
    radial-gradient(circle at 100% 0%, rgba(14, 116, 144, 0.09), transparent 34%),
    #f6f9fb;
}

.equipment-subsection-head span {
  color: #0f766e;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.13em;
}

.station-view .equipment-subsection-head span {
  color: #0369a1;
}

.equipment-subsection-head h3 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 20px;
}

.equipment-subsection-head > strong {
  color: #0f766e;
  font-size: 13px;
}

.station-view .equipment-subsection-head > strong {
  color: #0369a1;
}

.equipment-section-text {
  margin: 0;
  padding: 18px 20px 8px;
  color: #475569;
  line-height: 1.8;
}

.equipment-chart-legend {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 16px;
  padding: 8px 20px 14px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.equipment-chart-legend span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.equipment-chart-legend i {
  width: 11px;
  height: 11px;
  border-radius: 3px;
}

.equipment-chart-legend i.station {
  background: #2a9d8f;
}

.equipment-chart-legend i.issue {
  background: #e07a5f;
}

.equipment-chart-legend i.average {
  background: #f2cc8f;
}

.equipment-region-chart {
  display: grid;
  gap: 1px;
  margin: 0 20px 20px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 17px;
  background: #e8eef2;
}

.equipment-region-row {
  display: grid;
  grid-template-columns: minmax(150px, 0.9fr) minmax(300px, 2fr) 86px;
  align-items: center;
  gap: 18px;
  padding: 14px 16px;
  background: #ffffff;
}

.equipment-region-name {
  min-width: 0;
}

.equipment-region-name strong {
  display: block;
  margin-top: 7px;
  overflow: hidden;
  color: #1e293b;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.equipment-region-bars {
  display: grid;
  gap: 8px;
}

.equipment-region-bars > div {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 48px;
  align-items: center;
  gap: 9px;
}

.equipment-region-bars > div::before {
  content: "";
  grid-column: 1;
  grid-row: 1;
  height: 9px;
  border-radius: 999px;
  background: #edf2f4;
}

.equipment-region-bars > div > span {
  position: relative;
  z-index: 1;
  grid-column: 1;
  grid-row: 1;
  height: 9px;
  border-radius: 999px;
  transition: width 0.4s ease;
}

.equipment-region-bars > div > span.station {
  background: linear-gradient(90deg, #8ed4ca, #2a9d8f);
}

.equipment-region-bars > div > span.issue {
  background: linear-gradient(90deg, #f3b7a7, #e07a5f);
}

.equipment-region-bars b {
  color: #334155;
  font-size: 12px;
  text-align: right;
}

.equipment-average-value {
  padding: 9px 7px;
  border-radius: 13px;
  color: #8a5a12;
  background: #fff7e5;
  text-align: center;
}

.equipment-average-value strong,
.equipment-average-value span {
  display: block;
}

.equipment-average-value strong {
  font-size: 20px;
}

.equipment-average-value span {
  margin-top: 2px;
  font-size: 10px;
  font-weight: 800;
}

.equipment-station-ranking {
  display: grid;
  gap: 1px;
  margin: 20px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 17px;
  background: #e8eef2;
}

.equipment-station-ranking > article {
  display: grid;
  grid-template-columns: 42px minmax(150px, 0.8fr) minmax(220px, 1.8fr) 52px;
  align-items: center;
  gap: 14px;
  padding: 12px 15px;
  background: #ffffff;
}

.equipment-station-ranking > article.top-rank {
  background: linear-gradient(90deg, #fffaf0, #ffffff 38%);
}

.equipment-rank-number {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  color: #0369a1;
  background: #e0f2fe;
  font-size: 11px;
  font-weight: 900;
}

.top-rank .equipment-rank-number {
  color: #ffffff;
  background: linear-gradient(145deg, #d97706, #f59e0b);
}

.equipment-station-copy {
  min-width: 0;
}

.equipment-station-copy strong,
.equipment-station-copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.equipment-station-copy strong {
  color: #1e293b;
}

.equipment-station-copy small {
  margin-top: 4px;
  color: #94a3b8;
  font-size: 11px;
}

.equipment-station-track {
  height: 11px;
  overflow: hidden;
  border-radius: 999px;
  background: #edf2f5;
}

.equipment-station-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #80c8df, #167fb3);
}

.equipment-station-ranking > article > b {
  color: #0f172a;
  text-align: right;
}

.equipment-distribution-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.equipment-distribution-card {
  overflow: hidden;
  border: 1px solid #dce7e5;
  border-radius: 21px;
  background: #ffffff;
}

.equipment-distribution-card > p {
  min-height: 88px;
  margin: 0;
  padding: 17px 20px 5px;
  color: #475569;
  line-height: 1.75;
}

.equipment-distribution-card .safety-category-list {
  padding: 15px 20px 22px;
}

.equipment-category-row {
  grid-template-columns: minmax(110px, 0.8fr) minmax(125px, 1.5fr) 80px;
}

.equipment-typical-card {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.75fr);
  gap: 22px;
  padding: 22px;
  border: 1px solid #dce7e5;
  border-radius: 22px;
  background:
    radial-gradient(circle at 0% 0%, rgba(13, 148, 136, 0.1), transparent 32%),
    linear-gradient(145deg, #f9fdfc, #ffffff);
}

.equipment-typical-title > span {
  color: #0f766e;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.12em;
}

.equipment-typical-title h3 {
  margin: 7px 0 0;
  color: #0f172a;
  font-size: 24px;
}

.equipment-typical-copy > p,
.equipment-typical-copy blockquote {
  color: #475569;
  line-height: 1.8;
}

.equipment-typical-copy blockquote {
  margin: 14px 0;
  padding: 13px 15px;
  border-left: 4px solid #2a9d8f;
  border-radius: 0 13px 13px 0;
  background: #eef8f5;
}

.equipment-typical-example {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 15px;
  background: #ffffff;
}

.equipment-typical-example span,
.equipment-typical-example strong,
.equipment-typical-example small {
  display: block;
}

.equipment-typical-example span {
  color: #0f766e;
  font-size: 11px;
  font-weight: 900;
}

.equipment-typical-example strong {
  margin-top: 5px;
  color: #0f172a;
}

.equipment-typical-example p {
  margin: 7px 0;
  color: #475569;
  line-height: 1.65;
}

.equipment-typical-example small {
  color: #94a3b8;
}

.equipment-typical-photo {
  position: relative;
  width: 100%;
  min-height: 280px;
  overflow: hidden;
  padding: 0;
  border: 0;
  border-radius: 18px;
  background: #e6efed;
  cursor: zoom-in;
}

.equipment-typical-photo img {
  width: 100%;
  height: 100%;
  min-height: 280px;
  object-fit: cover;
}

.equipment-typical-photo > span {
  position: absolute;
  right: 12px;
  bottom: 12px;
  padding: 6px 9px;
  border-radius: 999px;
  color: #ffffff;
  background: rgba(15, 23, 42, 0.74);
  font-size: 11px;
  font-weight: 800;
}

.equipment-typical-photo.empty {
  display: grid;
  place-items: center;
  color: #94a3b8;
  cursor: default;
}

.equipment-analysis-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.equipment-analysis-title h4 {
  margin: 0;
}

.report-image-preview {
  position: fixed;
  inset: 0;
  z-index: 90000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 26px;
  background: rgba(2, 6, 23, 0.82);
  backdrop-filter: blur(8px);
  cursor: zoom-out;
}

.report-image-preview img {
  max-width: min(1100px, 96vw);
  max-height: 92vh;
  object-fit: contain;
  border-radius: 18px;
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.42);
  cursor: default;
}

.empty-highlight {
  margin-top: 14px;
  padding: 18px;
  text-align: center;
  color: #94a3b8;
  background: #f8fafc;
  border-radius: 16px;
}

.trace-chapter {
  background:
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.12), transparent 35%),
    #ffffff;
}

.trace-problem-card {
  margin-top: 0;
  padding: 18px;
  border-radius: 20px;
  background: #0f172a;
  color: #e2e8f0;
}

.trace-problem-card.muted {
  background: #475569;
}

.trace-problem-card span {
  display: block;
  margin-bottom: 8px;
  color: #bae6fd;
  font-size: 13px;
  font-weight: 900;
}

.trace-problem-card strong {
  font-size: 20px;
  line-height: 1.7;
}

.trace-analysis-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.trace-analysis-grid article {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid #dbeafe;
  background: #f8fbff;
}

.trace-analysis-grid span {
  color: #0369a1;
  font-weight: 900;
}

.trace-analysis-grid p,
.trace-conclusion-card p,
.trace-conclusion-card li {
  color: #334155;
  line-height: 1.9;
}

.trace-conclusion-card {
  margin-top: 16px;
  padding: 18px;
  border-radius: 20px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.trace-conclusion-card h4 {
  margin: 0 0 10px;
  color: #0f172a;
}

.trace-conclusion-card ol {
  margin: 0;
  padding-left: 22px;
}

.work-plan-list {
  display: grid;
  gap: 14px;
  margin-top: 0;
}

.work-plan-card {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr);
  gap: 14px;
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, #f8fafc, #ffffff);
  border: 1px solid #e2e8f0;
}

.work-plan-card>span {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: #2488c7;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 900;
}

.work-plan-card h4 {
  margin: 0 0 8px;
  color: #0f172a;
}

.work-plan-card p {
  margin: 0;
  color: #475569;
  line-height: 1.9;
}

.service-summary-cards .summary-card {
  border-color: #dbe8e5;
  background:
    radial-gradient(circle at 100% 0%, rgba(15, 118, 110, 0.08), transparent 38%),
    #ffffff;
}

.service-chapter {
  border-color: #dce8e4;
}

.service-mode-overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 22px;
}

.service-mode-overview-grid > article {
  min-width: 0;
  display: grid;
  grid-template-columns: 78px minmax(0, 1fr);
  align-items: center;
  gap: 16px;
  padding: 18px;
  border: 1px solid #dce8e4;
  border-radius: 20px;
  background: linear-gradient(145deg, #f8fcfb, #ffffff);
}

.service-mode-mark {
  height: 62px;
  display: grid;
  place-items: center;
  border-radius: 17px;
  color: #ffffff;
  background: linear-gradient(145deg, #0e7490, #22a6b3);
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.service-mode-mark.onsite {
  background: linear-gradient(145deg, #b45309, #e99a3f);
}

.service-mode-overview-grid span,
.service-mode-overview-grid strong,
.service-mode-overview-grid p {
  display: block;
  margin: 0;
}

.service-mode-overview-grid span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.service-mode-overview-grid strong {
  margin-top: 4px;
  color: #0f172a;
  font-size: 22px;
}

.service-mode-overview-grid p {
  margin-top: 5px;
  color: #0f766e;
  font-size: 13px;
}

.service-section-intro {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.service-section-intro span {
  color: #0f766e;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.13em;
}

.service-section-intro h3 {
  margin: 5px 0 0;
  color: #0f172a;
  font-size: 20px;
}

.service-section-intro > strong {
  flex: 0 0 auto;
  padding: 8px 11px;
  border-radius: 12px;
  color: #0f766e;
  background: #e9f7f3;
  font-size: 13px;
}

.service-unit-comparison {
  display: grid;
  gap: 1px;
  overflow: hidden;
  border: 1px solid #dfe9e6;
  border-radius: 18px;
  background: #dfe9e6;
}

.service-unit-comparison > article {
  display: grid;
  grid-template-columns: minmax(150px, 0.8fr) minmax(360px, 2.2fr);
  align-items: center;
  gap: 20px;
  padding: 14px 17px;
  background: #ffffff;
}

.service-unit-name small,
.service-unit-name strong,
.service-unit-name span {
  display: block;
}

.service-unit-name small {
  color: #0f766e;
  font-size: 10px;
  font-weight: 900;
}

.service-unit-name strong {
  margin: 4px 0;
  color: #1e293b;
}

.service-unit-name span {
  color: #94a3b8;
  font-size: 11px;
}

.service-unit-bars {
  display: grid;
  gap: 9px;
}

.service-unit-bars > div {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) 42px;
  align-items: center;
  gap: 10px;
  color: #64748b;
  font-size: 11px;
}

.service-unit-bars > div > div {
  height: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: #edf3f1;
}

.service-unit-bars i {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.service-unit-bars i.issue {
  background: linear-gradient(90deg, #64b5a7, #0f766e);
}

.service-unit-bars i.average {
  background: linear-gradient(90deg, #f7c978, #d97706);
}

.service-unit-bars b {
  color: #334155;
  text-align: right;
}

.service-rectification-legend {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 16px;
  margin: -8px 0 16px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.service-rectification-legend span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.service-rectification-legend i {
  width: 11px;
  height: 11px;
  border-radius: 4px;
}

.service-rectification-legend .unreceived,
.service-stacked-track .unreceived {
  background: #94a3b8;
}

.service-rectification-legend .pending,
.service-stacked-track .pending {
  background: #e18c3b;
}

.service-rectification-legend .rectified,
.service-stacked-track .rectified {
  background: #2f9b6d;
}

.service-rectification-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.service-rectification-grid > article {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 17px;
  background: #fbfdff;
}

.service-rectification-grid > article > div:first-child {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.service-rectification-grid small {
  color: #0f766e;
  font-size: 10px;
  font-weight: 900;
}

.service-rectification-grid strong {
  color: #1e293b;
}

.service-rectification-grid > article > div:first-child span {
  margin-left: auto;
  color: #94a3b8;
  font-size: 11px;
}

.service-rectification-counts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 7px;
  margin: 13px 0 10px;
}

.service-rectification-counts span {
  padding: 8px 6px;
  border-radius: 10px;
  color: #64748b;
  background: #f1f5f9;
  font-size: 10px;
  text-align: center;
}

.service-rectification-counts b {
  display: block;
  margin-bottom: 2px;
  color: #334155;
  font-size: 16px;
}

.service-stacked-track {
  height: 8px;
  display: flex;
  overflow: hidden;
  border-radius: 999px;
  background: #edf2f4;
}

.service-stacked-track i {
  display: block;
  height: 100%;
}

.service-mode-section,
.service-category-section {
  overflow: hidden;
  padding: 19px;
  border: 1px solid #dfe9e6;
  border-radius: 20px;
  background: linear-gradient(145deg, #f9fcfb, #ffffff);
}

.service-mode-section + .service-mode-section,
.service-category-section + .service-category-section {
  margin-top: 20px;
}

.service-mode-section > p,
.service-category-section > p {
  margin: -4px 0 18px;
  color: #475569;
  line-height: 1.8;
}

.service-average-chart {
  display: grid;
  gap: 1px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 15px;
  background: #e2e8f0;
}

.service-average-chart > article {
  display: grid;
  grid-template-columns: minmax(120px, 0.7fr) minmax(220px, 2fr) 46px;
  align-items: center;
  gap: 12px;
  padding: 11px 13px;
  background: #ffffff;
}

.service-average-chart strong {
  color: #334155;
  font-size: 13px;
}

.service-average-chart > article > div {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: #edf3f1;
}

.service-average-chart span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #7dcabc, #0f766e);
}

.service-average-chart b {
  color: #0f766e;
  text-align: right;
}

.service-category-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 13px;
}

.service-category-grid > article {
  min-width: 0;
  padding: 15px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #ffffff;
}

.service-category-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.service-category-head strong {
  color: #1e293b;
}

.service-category-head span {
  flex: 0 0 auto;
  color: #0f766e;
  font-size: 11px;
  font-weight: 900;
}

.service-category-track {
  height: 9px;
  margin: 12px 0;
  overflow: hidden;
  border-radius: 999px;
  background: #edf3f1;
}

.service-category-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #8ed4c8, #16867c);
}

.service-category-children {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.service-category-children span {
  max-width: 100%;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 9px;
  color: #64748b;
  background: #f3f7f6;
  font-size: 11px;
}

.service-category-children b {
  overflow: hidden;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.service-category-children em {
  flex: 0 0 auto;
  color: #0f766e;
  font-style: normal;
  font-weight: 900;
}

.service-region-analysis-list {
  display: grid;
  gap: 20px;
}

.service-region-analysis {
  overflow: hidden;
  border: 1px solid #dce8e4;
  border-radius: 22px;
  background: #ffffff;
}

.service-region-analysis > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border-bottom: 1px solid #e2ebe8;
  background:
    radial-gradient(circle at 100% 0%, rgba(15, 118, 110, 0.1), transparent 36%),
    #f5faf8;
}

.service-region-analysis > header small,
.service-region-analysis > header h3,
.service-region-analysis > header p {
  margin: 0;
}

.service-region-analysis > header small {
  color: #0f766e;
  font-size: 10px;
  font-weight: 900;
}

.service-region-analysis > header h3 {
  margin-top: 3px;
  color: #0f172a;
  font-size: 21px;
}

.service-region-analysis > header p {
  margin-top: 5px;
  color: #64748b;
  font-size: 12px;
}

.service-region-analysis > header > span {
  padding: 8px 11px;
  border-radius: 12px;
  color: #0f766e;
  background: #dff3ed;
  font-size: 12px;
  font-weight: 900;
}

.service-area-analysis {
  padding: 18px 20px;
}

.service-area-analysis + .service-area-analysis {
  border-top: 1px dashed #dbe5e2;
}

.service-area-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.service-area-head > div {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.service-area-head > div > span {
  color: #0f766e;
  font-size: 17px;
  font-weight: 900;
}

.service-area-head > div > strong {
  color: #334155;
  font-size: 13px;
}

.service-area-analysis > p {
  margin: 10px 0 14px;
  color: #475569;
  line-height: 1.75;
}

.service-highlight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.service-highlight-grid > article {
  min-width: 0;
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fbfdff;
}

.service-highlight-title {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
}

.service-highlight-title > span {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  color: #ffffff;
  background: #0f766e;
  font-size: 12px;
  font-weight: 900;
}

.service-highlight-title h4,
.service-highlight-title p {
  margin: 0;
}

.service-highlight-title h4 {
  color: #1e293b;
}

.service-highlight-title p {
  margin-top: 5px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.service-highlight-issues {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.service-highlight-issues > div {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 74px;
  align-items: center;
  gap: 10px;
  padding: 9px;
  border-radius: 12px;
  background: #f3f7f6;
}

.service-highlight-issues strong,
.service-highlight-issues span {
  display: block;
}

.service-highlight-issues strong {
  margin-bottom: 4px;
  color: #1e293b;
  font-size: 12px;
}

.service-highlight-issues span {
  color: #475569;
  font-size: 12px;
  line-height: 1.55;
}

.service-highlight-issues button {
  width: 74px;
  height: 62px;
  overflow: hidden;
  padding: 0;
  border: 0;
  border-radius: 10px;
  background: #dce7e4;
  cursor: zoom-in;
}

.service-highlight-issues img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.service-summary-list {
  display: grid;
  gap: 12px;
}

.service-summary-list > article {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr);
  gap: 14px;
  padding: 17px;
  border: 1px solid #dfe9e6;
  border-radius: 17px;
  background: linear-gradient(145deg, #f8fcfb, #ffffff);
}

.service-summary-list > article > span {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  color: #ffffff;
  background: linear-gradient(145deg, #0f766e, #2aa393);
  font-size: 12px;
  font-weight: 900;
}

.service-ai-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.service-ai-title h4,
.service-summary-list p {
  margin: 0;
}

.service-ai-title h4 {
  color: #1e293b;
}

.service-summary-list p {
  margin-top: 7px;
  color: #475569;
  line-height: 1.8;
}

.service-work-list .work-plan-card > span {
  background: linear-gradient(145deg, #0f766e, #2aa393);
}

@keyframes pulseOrb {
  0%, 100% {
    transform: scale(0.94);
    opacity: 0.72;
  }
  50% {
    transform: scale(1.05);
    opacity: 1;
  }
}

@keyframes aiOrbitSpin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes aiCorePulse {
  0%, 100% {
    transform: scale(0.97);
    box-shadow: 0 0 0 10px rgba(34, 211, 238, 0.08), 0 0 38px rgba(56, 189, 248, 0.3);
  }
  50% {
    transform: scale(1.03);
    box-shadow: 0 0 0 14px rgba(34, 211, 238, 0.11), 0 0 58px rgba(56, 189, 248, 0.48);
  }
}

@keyframes aiSparkFloat {
  0%, 100% {
    transform: translateY(-5px);
    opacity: 0.45;
  }
  50% {
    transform: translateY(7px);
    opacity: 1;
  }
}

@keyframes liveDotPulse {
  0%, 100% {
    opacity: 0.45;
    transform: scale(0.82);
  }
  50% {
    opacity: 1;
    transform: scale(1.12);
  }
}

@media (max-width: 900px) {
  .report-hero,
  .report-document-head {
    flex-direction: column;
  }

  .report-document-head {
    grid-template-columns: 1fr;
    align-items: stretch;
    gap: 16px;
  }

  .report-context-grid {
    grid-template-columns: 1fr;
  }

  .report-month-control,
  .doc-meta,
  .report-data-scope-note {
    width: 100%;
    max-width: none;
    min-width: 0;
    box-sizing: border-box;
  }

  .report-type-grid {
    grid-template-columns: 1fr;
  }

  .report-source-panel {
    grid-template-columns: 1fr;
  }

  .report-source-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .source-configure-btn,
  .source-apply-generate-btn {
    width: 100%;
  }

  .source-station-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ai-generation-state {
    grid-template-columns: 150px minmax(0, 1fr);
    gap: 24px;
    padding: 30px;
  }

  .ai-generation-visual {
    width: 148px;
    height: 148px;
  }

  .ai-core {
    width: 72px;
    height: 72px;
    border-radius: 23px;
    font-size: 23px;
  }

  .summary-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .report-document,
  .report-hero {
    padding: 18px;
    border-radius: 20px;
  }

  .chapter-card {
    padding: 20px;
    margin-top: 26px;
    border-radius: 20px;
  }

  .strong-lead {
    font-size: 20px;
  }

  .finding-flow-row {
    grid-template-columns: minmax(130px, 0.9fr) minmax(180px, 2fr) 86px;
    gap: 12px;
  }

  .chapter-banner {
    min-height: 56px;
    margin: -20px -20px 22px;
    padding: 14px 18px;
    border-radius: 19px 19px 0 0;
    font-size: 19px;
  }

  .bar-chart {
    padding-left: 70px;
  }

  .chart-bars {
    gap: 22px;
  }

  .flow-highlight-head,
  .highlight-issue-card {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: flex-start;
  }

  .highlight-photo {
    width: 100%;
    height: 180px;
  }

  .trace-analysis-grid {
    grid-template-columns: 1fr;
  }

  .safety-typical-card,
  .safety-highlight-list {
    grid-template-columns: 1fr;
  }

  .safety-typical-photo {
    min-height: 240px;
  }

  .safety-category-row {
    grid-template-columns: minmax(130px, 0.8fr) minmax(180px, 2fr) 88px;
    gap: 12px;
  }

  .finance-summary-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .finance-distribution-grid,
  .finance-ai-grid {
    grid-template-columns: 1fr;
  }

  .finance-distribution-card > p {
    min-height: 0;
  }

  .equipment-region-row {
    grid-template-columns: minmax(140px, 0.8fr) minmax(220px, 1.6fr) 78px;
    gap: 12px;
  }

  .equipment-station-ranking > article {
    grid-template-columns: 38px minmax(130px, 0.8fr) minmax(170px, 1.3fr) 48px;
  }

  .equipment-distribution-grid,
  .equipment-typical-card {
    grid-template-columns: 1fr;
  }

  .equipment-typical-photo {
    min-height: 260px;
  }

  .service-unit-comparison > article {
    grid-template-columns: minmax(130px, 0.7fr) minmax(260px, 1.8fr);
  }

  .service-rectification-grid,
  .service-category-grid,
  .service-highlight-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .report-type-panel {
    padding: 16px;
    border-radius: 20px;
  }

  .report-source-panel {
    padding: 18px 16px;
    border-radius: 20px;
    gap: 16px;
  }

  .report-source-main {
    gap: 12px;
  }

  .report-source-icon {
    width: 46px;
    height: 46px;
    flex-basis: 46px;
    border-radius: 15px;
  }

  .source-panel-title-row h3 {
    font-size: 17px;
  }

  .report-source-actions {
    grid-template-columns: 1fr;
  }

  .source-summary-grid {
    grid-column: auto;
  }

  .report-source-dialog-layer {
    padding: 10px;
    align-items: center;
  }

  .report-source-dialog {
    width: calc(100vw - 20px);
    max-height: calc(100dvh - 20px);
    border-radius: 22px;
  }

  .source-dialog-close {
    top: 12px;
    right: 12px;
    width: 40px;
    height: 40px;
  }

  .source-dialog-head {
    align-items: flex-start;
    padding: 20px 60px 16px 18px;
  }

  .source-dialog-head h3 {
    font-size: 20px;
  }

  .source-dialog-head p {
    font-size: 12px;
  }

  .source-dialog-total {
    display: none;
  }

  .source-mode-switch {
    grid-template-columns: 1fr;
    gap: 8px;
    padding: 14px 14px 10px;
  }

  .source-mode-switch button {
    padding: 11px 13px;
  }

  .source-dialog-toolbar {
    grid-template-columns: 1fr 1fr;
    padding: 0 14px 10px;
  }

  .source-search-box {
    grid-column: 1 / -1;
  }

  .source-selected-toggle {
    justify-content: center;
  }

  .source-dialog-batch {
    align-items: flex-start;
    flex-direction: column;
    margin: 0 14px 10px;
  }

  .source-dialog-batch > div:last-child {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .source-dialog-batch button {
    min-height: 34px;
  }

  .source-station-list {
    padding: 0 14px 14px;
  }

  .source-station-grid {
    grid-template-columns: 1fr;
  }

  .source-dialog-footer {
    align-items: stretch;
    flex-direction: column;
    padding: 12px 14px;
  }

  .source-dialog-footer > div {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .source-cancel-btn,
  .source-confirm-btn {
    width: 100%;
  }

  .report-type-panel-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 5px;
  }

  .report-type-card {
    padding: 16px;
  }

  .report-type-card strong {
    padding-right: 0;
    margin-top: 32px;
    font-size: 17px;
  }

  .report-type-status {
    left: 15px;
    right: auto;
    top: 14px;
  }

  .template-placeholder {
    min-height: 250px;
    padding: 28px 20px;
    flex-direction: column;
    text-align: center;
  }

  .ai-generation-state {
    min-height: 0;
    padding: 26px 20px;
    grid-template-columns: 1fr;
    justify-items: center;
    gap: 14px;
    border-radius: 22px;
  }

  .ai-generation-visual {
    width: 126px;
    height: 126px;
  }

  .ai-generation-content {
    width: 100%;
    text-align: center;
  }

  .ai-generation-content h3 {
    font-size: 21px;
  }

  .ai-generation-content>p {
    margin-bottom: 18px;
    font-size: 13px;
  }

  .ai-stage-list {
    gap: 4px;
  }

  .ai-stage-list span {
    font-size: 11px;
  }

  .summary-cards {
    grid-template-columns: 1fr;
  }

  .report-document h1 {
    font-size: 24px;
    line-height: 1.35;
  }

  .chapter-card {
    margin-top: 24px;
  }

  .chapter-banner {
    font-size: 17px;
    letter-spacing: 0;
  }

  .finding-chart-head {
    align-items: flex-start;
    padding: 16px;
  }

  .finding-chart-total {
    flex-direction: column;
    align-items: flex-end;
    gap: 3px;
  }

  .finding-chart-total strong {
    font-size: 26px;
  }

  .finding-flow-list {
    gap: 17px;
    padding: 18px 16px 20px;
  }

  .finding-flow-row {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px 12px;
  }

  .finding-flow-track {
    grid-column: 1 / -1;
    grid-row: 2;
  }

  .finding-flow-value {
    grid-column: 2;
    grid-row: 1;
  }

  .finding-flow-label strong {
    white-space: normal;
  }

  .chart-title {
    margin-left: 0;
    font-size: 20px;
  }

  .bar-chart {
    margin-left: -8px;
    margin-right: -8px;
  }

  .safety-scope-section,
  .safety-category-section,
  .safety-highlight-group {
    padding: 16px;
    border-radius: 17px;
  }

  .safety-section-head,
  .safety-category-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .safety-section-metrics {
    width: 100%;
  }

  .safety-section-metrics span {
    flex: 1;
    text-align: center;
  }

  .safety-narrative {
    text-indent: 0;
    line-height: 1.8;
  }

  .safety-unit-chart-scroll {
    padding-left: 10px;
    padding-right: 10px;
  }

  .safety-chart-legend {
    justify-content: flex-start;
  }

  .safety-typical-card {
    padding: 15px;
  }

  .safety-typical-photo {
    min-height: 200px;
  }

  .safety-category-row {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px 12px;
  }

  .safety-category-track {
    grid-column: 1 / -1;
    grid-row: 2;
  }

  .safety-category-row > div:last-child {
    grid-column: 2;
    grid-row: 1;
  }

  .safety-highlight-issue {
    grid-template-columns: minmax(0, 1fr) 64px;
  }

  .safety-highlight-issue button {
    width: 64px;
  }

  .safety-analysis-list > article {
    grid-template-columns: 38px minmax(0, 1fr);
    gap: 11px;
    padding: 14px;
  }

  .safety-analysis-list > article > span {
    width: 36px;
    height: 36px;
  }

  .finance-summary-cards {
    grid-template-columns: 1fr;
  }

  .finance-scope-strip {
    grid-template-columns: 1fr;
  }

  .finance-subsection-head,
  .finance-station-report-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .finance-chart-section .safety-chart-legend {
    align-self: stretch;
    justify-content: flex-start;
  }

  .finance-station-report-head > strong {
    margin-left: 50px;
  }

  .finance-ai-item-title {
    align-items: flex-start;
    flex-direction: column;
  }

  .equipment-subsection-head,
  .equipment-analysis-title {
    align-items: flex-start;
    flex-direction: column;
  }

  .equipment-chart-legend {
    justify-content: flex-start;
  }

  .equipment-region-chart,
  .equipment-station-ranking {
    margin: 14px;
  }

  .equipment-region-row {
    grid-template-columns: minmax(0, 1fr) 72px;
    gap: 10px;
    padding: 13px;
  }

  .equipment-region-name {
    grid-column: 1;
    grid-row: 1;
  }

  .equipment-region-bars {
    grid-column: 1 / -1;
    grid-row: 2;
  }

  .equipment-average-value {
    grid-column: 2;
    grid-row: 1;
  }

  .equipment-station-ranking > article {
    grid-template-columns: 36px minmax(0, 1fr) auto;
    gap: 10px;
  }

  .equipment-station-track {
    grid-column: 2 / -1;
  }

  .equipment-typical-card {
    padding: 15px;
  }

  .equipment-typical-photo,
  .equipment-typical-photo img {
    min-height: 210px;
  }

  .service-mode-overview-grid {
    grid-template-columns: 1fr;
  }

  .service-mode-overview-grid > article {
    grid-template-columns: 68px minmax(0, 1fr);
    padding: 14px;
  }

  .service-mode-mark {
    height: 56px;
    border-radius: 15px;
  }

  .service-section-intro,
  .service-region-analysis > header,
  .service-area-head,
  .service-ai-title {
    align-items: flex-start;
    flex-direction: column;
  }

  .service-section-intro > strong,
  .service-region-analysis > header > span {
    align-self: flex-start;
  }

  .service-unit-comparison > article {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 14px;
  }

  .service-unit-name {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 2px 10px;
  }

  .service-unit-name small {
    grid-column: 1;
  }

  .service-unit-name strong {
    grid-column: 1;
  }

  .service-unit-name span {
    grid-column: 2;
    grid-row: 1 / 3;
  }

  .service-unit-bars > div {
    grid-template-columns: 64px minmax(0, 1fr) 34px;
    gap: 8px;
  }

  .service-rectification-legend {
    justify-content: flex-start;
  }

  .service-rectification-grid {
    grid-template-columns: 1fr;
  }

  .service-mode-section,
  .service-category-section {
    padding: 15px;
    border-radius: 17px;
  }

  .service-average-chart > article {
    grid-template-columns: minmax(96px, 0.75fr) minmax(100px, 1.5fr) 38px;
    gap: 8px;
    padding: 10px;
  }

  .service-category-grid,
  .service-highlight-grid {
    grid-template-columns: 1fr;
  }

  .service-region-analysis {
    border-radius: 18px;
  }

  .service-region-analysis > header,
  .service-area-analysis {
    padding: 15px;
  }

  .service-area-head > div {
    align-items: flex-start;
    flex-direction: column;
    gap: 3px;
  }

  .service-highlight-issues > div {
    grid-template-columns: minmax(0, 1fr) 64px;
  }

  .service-highlight-issues button {
    width: 64px;
    height: 58px;
  }

  .service-summary-list > article {
    grid-template-columns: 38px minmax(0, 1fr);
    gap: 11px;
    padding: 14px;
  }

  .service-summary-list > article > span {
    width: 36px;
    height: 36px;
  }

  .report-export-dialog-layer {
    align-items: end;
    padding: 10px;
  }

  .report-export-dialog {
    width: calc(100vw - 20px);
    max-height: calc(100dvh - 20px);
    border-radius: 24px;
  }

  .export-dialog-close {
    top: 12px;
    right: 12px;
    width: 40px;
    height: 40px;
  }

  .export-dialog-head {
    align-items: flex-start;
    gap: 12px;
    padding: 18px 56px 16px 16px;
  }

  .export-dialog-icon {
    width: 44px;
    height: 51px;
    flex-basis: 44px;
    border-radius: 12px;
  }

  .export-dialog-head h3 {
    font-size: 20px;
  }

  .export-dialog-head p {
    font-size: 12px;
  }

  .export-dialog-body {
    gap: 11px;
    padding: 15px;
  }

  .export-snapshot-card {
    align-items: flex-start;
    flex-direction: column;
    gap: 9px;
  }

  .export-snapshot-card strong {
    white-space: normal;
  }

  .export-feature-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 6px;
  }

  .export-feature-grid > div {
    padding: 10px 8px;
  }

  .export-task-head {
    align-items: flex-start;
  }

  .export-dialog-footer {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
    padding: 12px 15px 16px;
  }

  .export-secondary-btn,
  .export-primary-btn {
    width: 100%;
    min-width: 0;
  }
}
</style>
