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
          :disabled="loading || templateUnavailable"
          @click="startGeneration({ force: true })"
        >
          {{ templateUnavailable ? '模板待配置' : '重新生成' }}
        </button>
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
    </section>

    <section v-else class="state-card card-surface">
      <div class="state-orb"></div>
      <h3>暂未生成报告</h3>
      <p>点击重新生成，后台会开始整理当前月份的巡检数据。</p>
    </section>

    <teleport to="body">
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
    template_ready: false
  },
  {
    key: 'on_site_service',
    name: '现场服务检查报告',
    description: '汇总现场服务视频与现场检查数据。',
    target_tables: ['现场检查明细表（视频）', '现场检查明细表（现场）'],
    template_ready: false
  },
  {
    key: 'equipment_facilities',
    name: '设备设施检查报告',
    description: '汇总设备设施现场检查数据。',
    target_tables: ['设备设施检查表（现场）'],
    template_ready: false
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
  summary: {},
  overview_text: '',
  finding_summary: {},
  prohibited_examples: [],
  deep_analysis: {},
  sections: [],
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
const imagePreview = ref({
  visible: false,
  src: '',
  title: ''
})
const report = ref(createEmptyReport())
let pollTimer = null
let contextRequestId = 0

const currentReportType = computed(() => (
  reportTypes.value.find((item) => item.key === selectedReportType.value)
  || DEFAULT_REPORT_TYPES[0]
))
const templateUnavailable = computed(() => currentReportType.value.template_ready === false)
const isQualityMeasurementReport = computed(() => selectedReportType.value === 'quality_measurement')
const isSafetyQualityReport = computed(() => selectedReportType.value === 'safety_quality')
const hasReport = computed(() => Boolean(report.value?.month))
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
  if (!selectedMonth.value || templateUnavailable.value) return
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
      force: options?.force === true
    })
    if (requestId !== contextRequestId) return
    if (!response.data?.success) {
      throw new Error(response.data?.error || 'AI报告生成任务提交失败。')
    }
    if (response.data?.report && !response.data?.job) {
      report.value = response.data.report
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

const loadReportState = async ({ autoStart = true } = {}) => {
  const requestId = ++contextRequestId
  clearPolling()
  activeJob.value = null
  error.value = ''
  if (templateUnavailable.value) {
    report.value = createEmptyReport()
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
    report.value = response.data?.report || createEmptyReport()
    if (response.data?.job?.task_id) {
      activeJob.value = response.data.job
      scheduleJobPoll()
      return
    }
    loading.value = false
    if (!response.data?.report && autoStart) {
      await startGeneration()
    }
  } catch (err) {
    if (requestId !== contextRequestId) return
    loading.value = false
    error.value = err?.response?.data?.error || err?.message || '读取报告状态失败，请稍后重试。'
  }
}

const selectReportType = async (reportType) => {
  if (selectedReportType.value === reportType) return
  selectedReportType.value = reportType
  report.value = createEmptyReport()
  await loadReportState()
}

const handleReportContextChange = async () => {
  report.value = createEmptyReport()
  await loadReportState()
}

const loadReportTypes = async () => {
  try {
    const response = await axios.get('/api/inspection-reports/types')
    if (response.data?.success && Array.isArray(response.data.report_types) && response.data.report_types.length) {
      reportTypes.value = response.data.report_types
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
}

@media (max-width: 520px) {
  .report-type-panel {
    padding: 16px;
    border-radius: 20px;
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
}
</style>
