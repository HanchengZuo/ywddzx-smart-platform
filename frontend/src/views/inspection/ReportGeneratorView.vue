<template>
  <div class="report-page">
    <section class="report-hero card-surface">
      <div>
        <div class="page-kicker">AI REPORT STUDIO</div>
        <h2>AI报告生成</h2>
        <p>选择报告类型和历史时间段查看报告；具备生成权限时可按新的日期范围覆盖生成。</p>
      </div>
      <div class="report-month-control">
        <button
          type="button"
          class="export-ppt-btn"
          :disabled="!hasReport || loading || templateUnavailable"
          :title="!hasReport ? '请先选择一份历史报告' : '导出当前查看的历史报告快照'"
          @click="openExportDialog"
        >
          <span class="ppt-file-mark">P</span>
          {{ exportBusy ? `PPT生成中 ${exportTask?.progress || 0}%` : '导出PPT' }}
        </button>
        <small v-if="!canGenerateReports" class="report-readonly-note">
          当前账号可查看、分类和选择问题；新建或覆盖时间段报告需由管理员分配生成权限。
        </small>
      </div>
    </section>

    <section class="report-period-workspace card-surface">
      <div class="report-period-editor">
        <div class="period-editor-title">
          <span>REPORT DATE RANGE</span>
          <h3>本次报告数据日期范围</h3>
          <p>相同日期范围再次生成会直接覆盖原历史报告；历史报告查看不会重新调用 AI。</p>
        </div>
        <div class="period-editor-fields">
          <label>
            <span>开始日期</span>
            <input v-model="reportDateFrom" type="date" :disabled="!canGenerateReports" @change="handleReportDateRangeChange" />
          </label>
          <i aria-hidden="true">至</i>
          <label>
            <span>结束日期</span>
            <input v-model="reportDateTo" type="date" :disabled="!canGenerateReports" @change="handleReportDateRangeChange" />
          </label>
          <button
            v-if="canGenerateReports"
            type="button"
            class="period-generate-btn"
            :disabled="loading || templateUnavailable || !validReportDateRange"
            @click="startGeneration({ force: true })"
          >
            {{ matchingHistory ? '覆盖此时间段报告' : '生成此时间段报告' }}
          </button>
        </div>
        <small v-if="!canGenerateReports" class="period-readonly-note">当前日期范围为只读，选择下方历史记录可切换查看。</small>
      </div>
      <div class="report-history-panel">
        <div class="report-history-title">
          <div>
            <span>REPORT HISTORY</span>
            <h3>已生成历史报告</h3>
          </div>
          <strong>{{ reportHistory.length }}</strong>
        </div>
        <div v-if="reportHistory.length" class="report-history-list">
          <button
            v-for="item in reportHistory"
            :key="item.id"
            type="button"
            :class="['report-history-item', { active: selectedSnapshotId === item.id }]"
            @click="selectHistorySnapshot(item)"
          >
            <span>{{ item.date_from }} 至 {{ item.date_to }}</span>
            <small>生成于 {{ item.generated_at }}<template v-if="item.generated_by_name"> · {{ item.generated_by_name }}</template></small>
          </button>
        </div>
        <div v-else class="report-history-empty">当前报告类型还没有历史报告。</div>
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

    <section v-if="isQualityMeasurementReport && !templateUnavailable" class="report-source-panel card-surface">
      <div class="report-source-main">
        <div class="report-source-icon" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="report-source-copy">
          <span class="source-panel-kicker">DATA SOURCE</span>
          <div class="source-panel-title-row">
            <h3>{{ selectedSnapshotId ? '后续生成数据来源' : '本次报告数据来源' }}</h3>
            <span :class="['source-mode-badge', sourceSelectionMode]">
              {{ sourceSelectionMode === 'custom' ? '自定义范围' : '全部可用站点' }}
            </span>
          </div>
          <p v-if="sourceLoading">正在核对当前日期范围可用于报告的站点数据...</p>
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
            最近保存的数据范围与当前历史报告不同；覆盖生成时会采用最近保存配置。
          </div>
          <small v-if="sourceSelectionMeta.updated_at" class="source-last-saved">
            最近保存配置：{{ sourceSelectionMeta.updated_by_name || '未知用户' }} · {{ sourceSelectionMeta.updated_at }}
          </small>
          <div v-if="selectedSnapshotId" class="historical-config-note">
            <div>
              <span>当前历史报告采用</span>
              <strong>{{ historicalSourceSelectionDescription }}</strong>
              <small>{{ historicalSourceSelection.updated_by_name || '生成报告时的用户' }}<template v-if="historicalSourceSelection.updated_at"> · {{ historicalSourceSelection.updated_at }}</template></small>
            </div>
            <button type="button" @click="openSourceDialog('historical')">查看当时配置</button>
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
          @click="openSourceDialog('saved')"
        >
          设置数据来源
        </button>
        <button
          type="button"
          class="selection-configure-btn"
          :disabled="selectionSettingsLoading"
          @click="openSelectionSettingsDialog('saved')"
        >
          设置选题规则
        </button>
        <small class="source-last-saved compact">
          最近保存规则：{{ selectionSettingsMeta.updated_by_name || '系统默认' }}<template v-if="selectionSettingsMeta.updated_at"> · {{ selectionSettingsMeta.updated_at }}</template>
        </small>
        <button v-if="selectedSnapshotId" type="button" class="historical-rule-btn" @click="openSelectionSettingsDialog('historical')">
          查看历史报告当时规则
        </button>
      </div>
    </section>

    <section v-if="isQualityMeasurementReport && !templateUnavailable" class="quality-classification-panel card-surface">
      <div class="classification-panel-intro">
        <div class="classification-ai-mark" aria-hidden="true">AI</div>
        <div>
          <span>FLOW CLASSIFICATION</span>
          <h3>AI环节分类</h3>
          <p>原业务流程为“其他”或未设置的问题，由 AI 结合两张计量检查表规范归入具体环节；结果按问题ID长期保留。</p>
        </div>
      </div>
      <div class="classification-panel-stats">
        <div><span>涉及问题</span><strong>{{ flowClassificationStats.total }}</strong></div>
        <div><span>AI已分类</span><strong>{{ flowClassificationStats.ai }}</strong></div>
        <div><span>人工调整</span><strong>{{ flowClassificationStats.manual }}</strong></div>
        <div :class="{ pending: flowClassificationStats.pending }"><span>待分类</span><strong>{{ flowClassificationStats.pending }}</strong></div>
      </div>
      <div class="classification-panel-preview">
        <span v-if="flowClassificationsLoading">正在读取当前日期范围分类结果...</span>
        <span v-else-if="flowClassificationsError" class="classification-panel-error">{{ flowClassificationsError }}</span>
        <template v-else-if="visibleFlowClassifications.length">
          <span v-for="item in visibleFlowClassifications.slice(0, 4)" :key="`classification-preview-${item.issue_id}`">
            ID {{ item.issue_id }} · {{ item.effective_category || '待分类' }}
          </span>
          <em v-if="visibleFlowClassifications.length > 4">另有 {{ visibleFlowClassifications.length - 4 }} 条</em>
        </template>
        <span v-else>当前日期范围没有需要AI重新分类的问题。</span>
      </div>
      <button type="button" class="classification-manage-btn" :disabled="flowClassificationsLoading" @click="openFlowClassificationDialog">
        查看与调整分类
      </button>
    </section>

    <section v-if="isNonOilReport && !templateUnavailable" class="quality-classification-panel non-oil-issue-library-panel card-surface">
      <div class="classification-panel-intro">
        <div class="classification-ai-mark library-mark" aria-hidden="true">库</div>
        <div>
          <span>REPORT ISSUE LIBRARY</span>
          <h3>报告问题库</h3>
          <p>按检查项目归类展示当前日期范围内的审核通过问题，可自由选择哪些问题参与报告。</p>
        </div>
      </div>
      <div class="classification-panel-stats">
        <div><span>可用问题</span><strong>{{ nonOilIssueLibraryStats.total }}</strong></div>
        <div><span>已选参与</span><strong>{{ nonOilIssueLibraryStats.included }}</strong></div>
        <div :class="{ pending: nonOilIssueLibraryStats.excluded }"><span>已排除</span><strong>{{ nonOilIssueLibraryStats.excluded }}</strong></div>
        <div><span>问题类别</span><strong>{{ nonOilIssueLibraryStats.categories }}</strong></div>
      </div>
      <div class="classification-panel-preview issue-library-preview">
        <span v-if="nonOilIssueLibraryLoading">正在读取当前日期范围的问题库...</span>
        <span v-else-if="nonOilIssueLibraryError" class="classification-panel-error">{{ nonOilIssueLibraryError }}</span>
        <template v-else-if="nonOilIssueCategories.length">
          <span v-for="category in nonOilIssueCategories.slice(0, 5)" :key="`issue-library-preview-${category.name}`">
            {{ category.display_name }} {{ category.included_count }}/{{ category.total_count }}
          </span>
          <em v-if="nonOilIssueCategories.length > 5">另有 {{ nonOilIssueCategories.length - 5 }} 类</em>
        </template>
        <span v-else>当前日期范围暂无可用的审核通过问题。</span>
      </div>
      <button type="button" class="classification-manage-btn issue-library-manage-btn" :disabled="nonOilIssueLibraryLoading" @click="openNonOilIssueLibraryDialog">
        查看与选择问题
      </button>
    </section>

    <section v-if="isNonOilReport && !templateUnavailable" class="quality-classification-panel card-surface">
      <div class="classification-panel-intro">
        <div class="classification-ai-mark" aria-hidden="true">AI</div>
        <div>
          <span>NON-OIL CLASSIFICATION</span>
          <h3>AI“其他”问题分类</h3>
          <p>现场检查项目为“其他”的问题会自动归入明确类别，结果按问题ID保留，并支持人工调整。</p>
        </div>
      </div>
      <div class="classification-panel-stats">
        <div><span>涉及问题</span><strong>{{ nonOilClassificationStats.total }}</strong></div>
        <div><span>AI已分类</span><strong>{{ nonOilClassificationStats.ai }}</strong></div>
        <div><span>人工调整</span><strong>{{ nonOilClassificationStats.manual }}</strong></div>
        <div><span>规则兜底</span><strong>{{ nonOilClassificationStats.fallback }}</strong></div>
      </div>
      <div class="classification-panel-preview">
        <span v-if="nonOilClassificationsLoading">正在读取当前报告分类结果...</span>
        <span v-else-if="nonOilClassificationsError" class="classification-panel-error">{{ nonOilClassificationsError }}</span>
        <template v-else-if="nonOilClassifications.length">
          <span v-for="item in nonOilClassifications.slice(0, 4)" :key="`non-oil-class-preview-${item.issue_id}`">
            ID {{ item.issue_id }} · {{ item.effective_category }}
          </span>
          <em v-if="nonOilClassifications.length > 4">另有 {{ nonOilClassifications.length - 4 }} 条</em>
        </template>
        <span v-else>当前报告没有需要重新分类的“其他”问题。</span>
      </div>
      <button type="button" class="classification-manage-btn" :disabled="nonOilClassificationsLoading" @click="openNonOilClassificationDialog">
        查看与调整分类
      </button>
    </section>

    <section v-if="isNonOilReport && !templateUnavailable" class="quality-classification-panel non-oil-key-panel card-surface">
      <div class="classification-panel-intro">
        <div class="classification-ai-mark key-mark" aria-hidden="true">重</div>
        <div>
          <span>KEY ISSUE REVIEW</span>
          <h3>AI重点问题分类</h3>
          <p>AI只挑选符合定义的重点商品、月度盘点、商品过期和团购问题，其他问题保持不纳入。</p>
        </div>
      </div>
      <div class="classification-panel-stats">
        <div><span>问题总数</span><strong>{{ nonOilKeyClassificationStats.total }}</strong></div>
        <div><span>已纳入重点</span><strong>{{ nonOilKeyClassificationStats.selected }}</strong></div>
        <div><span>AI判定</span><strong>{{ nonOilKeyClassificationStats.ai }}</strong></div>
        <div><span>人工调整</span><strong>{{ nonOilKeyClassificationStats.manual }}</strong></div>
      </div>
      <div class="classification-panel-preview">
        <span v-if="nonOilKeyClassificationsLoading">正在读取重点问题分类结果...</span>
        <span v-else-if="nonOilKeyClassificationsError" class="classification-panel-error">{{ nonOilKeyClassificationsError }}</span>
        <template v-else-if="selectedNonOilKeyClassifications.length">
          <span v-for="item in selectedNonOilKeyClassifications.slice(0, 4)" :key="`non-oil-key-preview-${item.issue_id}`">
            ID {{ item.issue_id }} · {{ item.effective_category }}
          </span>
          <em v-if="selectedNonOilKeyClassifications.length > 4">另有 {{ selectedNonOilKeyClassifications.length - 4 }} 条</em>
        </template>
        <span v-else>当前报告暂无纳入四类重点问题的数据。</span>
      </div>
      <button type="button" class="classification-manage-btn" :disabled="nonOilKeyClassificationsLoading" @click="openNonOilKeyClassificationDialog">
        查看与调整分类
      </button>
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
      <div v-if="!isQualityMeasurementReport && !isNonOilReport" class="report-document-head">
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
        <div class="quality-ppt-viewer">
          <header class="quality-ppt-toolbar">
            <div>
              <span>PRESENTATION PREVIEW</span>
              <strong>{{ report.title || reportTitleFallback }}</strong>
              <small>生成于 {{ reportGeneratedAt }} · 网页预览与导出PPT使用同一份内容 · 支持键盘 ← → 翻页</small>
            </div>
            <div class="quality-ppt-page-count">{{ activeQualitySlideIndex + 1 }} / {{ qualitySlides.length }}</div>
          </header>

          <div v-if="currentQualitySlide" class="quality-ppt-stage">
            <article class="quality-ppt-slide" :class="`slide-${currentQualitySlide.kind}`">
              <header v-if="!['cover', 'agenda', 'ending'].includes(currentQualitySlide.kind)" class="quality-slide-header">
                <h2><span>{{ currentQualitySlide.title_prefix || currentQualitySlide.title }}</span><em v-if="currentQualitySlide.title_accent">{{ currentQualitySlide.title_accent }}</em></h2>
                <div class="quality-slide-brand">
                  <AiContentBadge
                    v-if="currentQualitySlide.ai_generated"
                    :generated="true"
                    ai-label="AI生成"
                    compact
                  />
                  <img src="/report-assets/quality-report-logo.png" alt="品牌标识" />
                </div>
              </header>

              <template v-if="currentQualitySlide.kind === 'cover'">
                <img class="quality-cover-logo" src="/report-assets/quality-report-logo.png" alt="品牌标识" />
                <h2 class="quality-cover-title">{{ currentQualitySlide.title }}</h2>
                <p class="quality-cover-period">{{ currentQualitySlide.period_label }}</p>
              </template>

              <template v-else-if="currentQualitySlide.kind === 'agenda'">
                <div class="quality-agenda-rule"></div>
                <img class="quality-agenda-logo" src="/report-assets/quality-report-logo.png" alt="品牌标识" />
                <div class="quality-agenda-list">
                  <div v-for="(section, index) in currentQualitySlide.sections" :key="`agenda-${section.number}`" :class="{ active: Number(currentQualitySlide.active_section) === index + 1 }">
                    {{ section.number }}、{{ section.label }}
                  </div>
                </div>
                <div v-if="currentQualitySlide.details?.length" class="quality-agenda-details">
                  <i aria-hidden="true"></i>
                  <span v-for="item in currentQualitySlide.details" :key="item.label" :class="`tone-${item.tone || 'ink'}`">{{ item.label }}</span>
                </div>
              </template>

              <template v-else-if="currentQualitySlide.kind === 'overall'">
                <p class="quality-slide-narrative overall-copy"><template v-for="(run, index) in currentQualitySlide.narrative_runs || [{ text: currentQualitySlide.narrative, tone: 'ink' }]" :key="`overall-run-${index}`"><span :class="`tone-${run.tone || 'ink'}`">{{ run.text }}</span></template></p>
                <div class="quality-slide-table-wrap overall-table">
                  <table>
                    <colgroup><col style="width: 5%" /><col style="width: 17%" /><col style="width: 10%" /><col style="width: 10%" /><col style="width: 11%" /><col style="width: 9%" /><col style="width: 9%" /><col style="width: 10%" /><col style="width: 9%" /></colgroup>
                    <thead>
                      <tr><th rowspan="2">序号</th><th rowspan="2">二级单位</th><th rowspan="2">检查油库数量</th><th rowspan="2">检查加油站数量</th><th rowspan="2">检查运输车辆数量</th><th colspan="3">发现问题数量</th><th rowspan="2">单库、车、站问题数量</th></tr>
                      <tr><th>一般性问题</th><th>违规违纪问题</th><th>涉及禁止项问题</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in qualityOverallRows" :key="`overall-${row.sequence}-${row.unit_name}`" :class="{ total: row.sequence === '合计' }">
                        <td v-if="row.sequence === '合计'" colspan="2">合计</td><template v-else><td>{{ row.sequence }}</td><td>{{ row.unit_name }}</td></template><td>{{ row.oil_depot_count || 0 }}</td><td>{{ row.station_count || 0 }}</td><td>{{ row.transport_vehicle_count || 0 }}</td><td>{{ row.general_issue_count || 0 }}</td><td>{{ row.violation_issue_count || 0 }}</td><td>{{ row.prohibited_issue_count || 0 }}</td><td>{{ row.total_issue_count || 0 }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>

              <template v-else-if="currentQualitySlide.kind === 'finding_overview'">
                <div class="quality-finding-layout">
                  <div class="quality-finding-copy"><p v-for="(block, blockIndex) in currentQualitySlide.text_blocks || currentQualitySlide.text_lines.map((line) => ({ runs: [{ text: line, tone: 'ink' }] }))" :key="`finding-copy-${blockIndex}`"><span v-for="(run, runIndex) in block.runs" :key="`finding-run-${blockIndex}-${runIndex}`" :class="`tone-${run.tone || 'ink'}`">{{ run.text }}</span></p></div>
                  <div class="quality-slide-table-wrap finding-table"><table><thead><tr><th>序号</th><th>环节排前三</th><th>问题类型</th><th>问题数量</th><th>占比/%</th></tr></thead><tbody><tr v-for="(row, index) in currentQualitySlide.rows" :key="`finding-${index}-${row.problem_type}`" :class="{ total: row.sequence === '合计', 'oil-station-row': row.section === '油站环节' }"><td>{{ row.sequence }}</td><td>{{ row.section }}</td><td>{{ row.problem_type }}</td><td>{{ row.count }}</td><td>{{ row.percentage }}</td></tr></tbody></table></div>
                </div>
              </template>

              <template v-else-if="currentQualitySlide.kind === 'prohibited'">
                <div class="quality-prohibited-band">{{ currentQualitySlide.subtitle || '1.禁止项问题' }}</div>
                <p class="quality-slide-narrative prohibited-copy">{{ currentQualitySlide.narrative }}</p>
                <div class="quality-slide-table-wrap prohibited-table"><table><thead><tr><th>序号</th><th>环节</th><th>基层单位名称</th><th>禁止项管理规定</th><th>处罚情况</th></tr></thead><tbody><tr v-if="!currentQualitySlide.rows?.length"><td colspan="5">当前月份暂无禁止项问题</td></tr><tr v-for="row in currentQualitySlide.rows" :key="`prohibited-slide-${row.issue_id}`"><td>{{ row.sequence }}</td><td>加油站环节</td><td>{{ row.unit_name }}</td><td class="align-left">{{ row.description }}</td><td>{{ row.penalty || '' }}</td></tr></tbody></table></div>
              </template>

              <template v-else-if="currentQualitySlide.kind === 'flow_chart'">
                <div class="quality-slide-band quality-flow-band">{{ currentQualitySlide.subtitle || '3.加油站环节' }}</div>
                <p class="quality-slide-narrative flow-copy">{{ currentQualitySlide.narrative }}</p>
                <h3 class="quality-chart-heading">{{ currentQualitySlide.chart_title }}</h3>
                <div class="quality-ppt-chart">
                  <div v-for="item in currentQualitySlide.distribution" :key="`ppt-flow-${item.name}`" class="quality-ppt-bar-column">
                    <div class="quality-ppt-bar-area"><span class="quality-ppt-bar-value" :style="{ bottom: `calc(${getQualityBarHeight(item.count)}% + 8px)` }">{{ item.count }}</span><i :style="{ height: `${getQualityBarHeight(item.count)}%` }"></i></div>
                    <strong>{{ item.name }}</strong>
                  </div>
                  <div v-if="!currentQualitySlide.distribution?.length" class="quality-slide-empty">当前月份暂无业务流程分布数据</div>
                </div>
              </template>

              <template v-else-if="currentQualitySlide.kind === 'issue_pairs'">
                <div class="quality-slide-band quality-issue-band">{{ currentQualitySlide.subtitle }}</div>
                <p class="quality-issue-summary">{{ currentQualitySlide.summary_text }}</p>
                <div :class="['quality-issue-pair-grid', currentQualitySlide.layout_variant || 'paired']">
                  <article
                    v-for="issue in currentQualitySlide.issues"
                    :key="`slide-issue-${issue.issue_id}`"
                    :class="getQualityIssueLayoutClasses(issue)"
                  >
                    <h3>{{ issue.station_name || '未命名站点' }}：</h3><p>{{ issue.description || '暂无问题描述' }}</p>
                    <button v-if="issue.issue_photo" type="button" @click="openImagePreview(issue.issue_photo, `${issue.station_name || '问题'}照片`)"><img :src="resolveImage(issue.issue_photo)" alt="问题照片" @load="rememberQualityImageAspect($event, getQualityImageKey(issue))" /></button>
                    <div v-else class="quality-slide-photo-empty">暂无问题照片</div>
                  </article>
                </div>
              </template>

              <template v-else-if="currentQualitySlide.kind === 'management_trace'">
                <div :class="['quality-trace-layout', getQualityTraceLayoutClasses(currentQualitySlide)]">
                  <div><p class="quality-typical-issue"><b>典型问题：</b>{{ formatStationIssue(currentQualitySlide.typical_issue || {}) }}</p><section v-for="item in currentQualitySlide.analysis_items" :key="item.label"><strong>{{ item.label }}</strong><p>{{ item.content || '-' }}</p></section></div>
                  <button v-if="currentQualitySlide.typical_issue?.issue_photo" type="button" @click="openImagePreview(currentQualitySlide.typical_issue.issue_photo, '典型问题照片')"><img :src="resolveImage(currentQualitySlide.typical_issue.issue_photo)" alt="典型问题照片" @load="rememberQualityImageAspect($event, getQualityImageKey(currentQualitySlide.typical_issue, 'trace'))" /></button>
                  <div v-else class="quality-slide-photo-empty">暂无问题照片</div>
                </div>
              </template>

              <template v-else-if="currentQualitySlide.kind === 'trace_analysis'">
                <div class="quality-slide-band wide">{{ currentQualitySlide.subtitle }}</div>
                <div class="quality-trace-analysis"><h3>综上所述：</h3><p>{{ stripTracePrefix(currentQualitySlide.conclusion) }}</p><h3>改进措施：</h3><ol><li v-for="item in currentQualitySlide.improvement_measures" :key="`${item.level}-${item.content}`"><strong>{{ item.level }}：</strong>{{ item.content }}</li></ol></div>
              </template>

              <template v-else-if="currentQualitySlide.kind === 'work_plan'">
                <ol class="quality-work-plan"><li v-for="item in currentQualitySlide.items" :key="`${item.title}-${item.content}`"><h3>{{ item.title }}</h3><p>{{ item.content }}</p></li></ol>
              </template>

              <template v-else-if="currentQualitySlide.kind === 'ending'">
                <div class="quality-ending-rule"></div>
                <img class="quality-ending-corner-logo" src="/report-assets/quality-report-logo.png" alt="品牌标识" />
                <div class="quality-ending-content">
                  <img src="/report-assets/quality-report-logo.png" alt="品牌标识" />
                  <strong>{{ currentQualitySlide.title || '通报完毕' }}</strong>
                </div>
              </template>

            </article>
          </div>
          <div v-else class="quality-slide-empty">当前报告还没有可展示的幻灯片，请重新生成。</div>

          <nav v-if="qualitySlides.length" class="quality-ppt-pagination" aria-label="报告翻页">
            <button type="button" :disabled="activeQualitySlideIndex === 0" @click="goToQualitySlide(activeQualitySlideIndex - 1)">上一页</button>
            <div><button v-for="(slide, index) in qualitySlides" :key="`slide-page-${index}`" type="button" :class="{ active: index === activeQualitySlideIndex }" @click="goToQualitySlide(index)">{{ index + 1 }}</button></div>
            <button type="button" :disabled="activeQualitySlideIndex >= qualitySlides.length - 1" @click="goToQualitySlide(activeQualitySlideIndex + 1)">下一页</button>
          </nav>
        </div>
      </template>

      <template v-else-if="isNonOilReport">
        <div class="quality-ppt-viewer non-oil-ppt-viewer">
          <header class="quality-ppt-toolbar">
            <div>
              <span>PRESENTATION PREVIEW</span>
              <strong>{{ report.title || reportTitleFallback }}</strong>
              <small>生成于 {{ reportGeneratedAt }} · 网页与导出PPT共用同一批幻灯片 · 支持键盘 ← → 翻页</small>
            </div>
            <div class="quality-ppt-page-count">{{ activeQualitySlideIndex + 1 }} / {{ nonOilSlideUrls.length }}</div>
          </header>
          <div v-if="currentNonOilSlideUrl" class="quality-ppt-stage non-oil-ppt-stage">
            <img :src="currentNonOilSlideUrl" :alt="`非油检查报告第${activeQualitySlideIndex + 1}页`" />
          </div>
          <div v-else class="quality-slide-empty">当前报告还没有可展示的PPT预览，请重新生成。</div>
          <nav v-if="nonOilSlideUrls.length" class="quality-ppt-pagination" aria-label="报告翻页">
            <button type="button" :disabled="activeQualitySlideIndex === 0" @click="goToQualitySlide(activeQualitySlideIndex - 1)">上一页</button>
            <div><button v-for="(_slide, index) in nonOilSlideUrls" :key="`non-oil-slide-page-${index}`" type="button" :class="{ active: index === activeQualitySlideIndex }" @click="goToQualitySlide(index)">{{ index + 1 }}</button></div>
            <button type="button" :disabled="activeQualitySlideIndex >= nonOilSlideUrls.length - 1" @click="goToQualitySlide(activeQualitySlideIndex + 1)">下一页</button>
          </nav>
        </div>
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
      <p v-if="canGenerateReports">请在上方选择日期范围并生成报告。</p>
      <p v-else>当前报告类型暂无可查看的历史报告。</p>
    </section>

    <teleport to="body">
      <div v-if="sourceDialogVisible && isQualityMeasurementReport" class="report-source-dialog-layer">
        <section class="report-source-dialog" role="dialog" aria-modal="true" aria-label="设置报告数据来源">
          <button type="button" class="source-dialog-close" aria-label="关闭" @click="closeSourceDialog">×</button>
          <header class="source-dialog-head">
            <div>
              <span>REPORT DATA SCOPE</span>
              <h3>{{ sourceDialogMode === 'historical' ? '历史报告当时数据来源' : '设置报告数据来源' }}</h3>
              <p>候选站点已按报告模板、日期范围和当前账号权限自动筛选。</p>
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
              :disabled="!canManageQualityReportSource"
              @click="setSourceDraftMode('all')"
            >
              <strong>全部可用站点</strong>
              <span>自动包含当前日期范围全部可统计站点</span>
            </button>
            <button
              type="button"
              :class="{ active: sourceDraftMode === 'custom' }"
              :disabled="!canManageQualityReportSource"
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
            <div v-if="canManageQualityReportSource && sourceDraftMode === 'custom'">
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
                      readonly: !canManageQualityReportSource || sourceDraftMode === 'all'
                    }
                  ]"
                >
                  <input
                    type="checkbox"
                    :checked="isDraftSourceStationSelected(station.station_id)"
                    :disabled="!canManageQualityReportSource || sourceDraftMode === 'all'"
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
              {{ canManageQualityReportSource
                ? '当前选择不会修改原始巡检数据，只影响下一次报告生成。'
                : '当前账号可以查看数据范围，但不能修改。' }}
            </p>
            <div>
              <button type="button" class="source-cancel-btn" @click="closeSourceDialog">
                {{ canManageQualityReportSource ? '取消' : '关闭' }}
              </button>
              <button
                v-if="canManageQualityReportSource"
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
      <div v-if="flowClassificationDialogVisible && isQualityMeasurementReport" class="flow-classification-dialog-layer">
        <section class="flow-classification-dialog" role="dialog" aria-modal="true" aria-label="AI环节分类结果">
          <button type="button" class="classification-dialog-close" aria-label="关闭" @click="closeFlowClassificationDialog">×</button>
          <header class="classification-dialog-head">
            <div>
              <span>AI FLOW REVIEW</span>
              <h3>{{ canManageQualityReportSelectionRules ? '查看与调整AI环节分类' : '查看AI环节分类结果' }}</h3>
              <p>只展示当前日期范围内原业务流程为“其他”或未设置的问题。人工调整会优先于AI结果。</p>
            </div>
            <div><strong>{{ visibleFlowClassifications.length }}</strong><span>条问题</span></div>
          </header>
          <div class="classification-dialog-toolbar">
            <label><span>搜索</span><input v-model.trim="flowClassificationKeyword" type="search" placeholder="问题ID、站点、描述或外部规范ID" /></label>
            <label><span>当前分类</span><select v-model="flowClassificationCategoryFilter"><option value="">全部分类</option><option value="pending">待分类</option><option v-for="category in flowClassificationCategories" :key="`classification-filter-${category}`" :value="category">{{ category }}</option></select></label>
          </div>
          <div v-if="flowClassificationsError" class="classification-dialog-message error">{{ flowClassificationsError }}</div>
          <div v-else-if="flowClassificationMessage" class="classification-dialog-message success">{{ flowClassificationMessage }}</div>
          <div class="classification-dialog-list">
            <div v-if="!filteredFlowClassifications.length" class="classification-list-empty">当前筛选条件下没有分类记录。</div>
            <article v-for="item in filteredFlowClassifications" :key="`classification-row-${item.issue_id}`">
              <div class="classification-issue-main">
                <div class="classification-issue-meta"><b>ID {{ item.issue_id }}</b><span>{{ item.station_name }}</span><span>{{ item.table_name }}</span><span>外部规范ID {{ item.external_standard_id }}</span></div>
                <p>{{ item.description || '暂无问题描述' }}</p>
                <small v-if="item.reason">分类依据：{{ item.reason }}</small>
              </div>
              <div class="classification-result-compare">
                <div><span>AI分类</span><strong>{{ item.ai_category || (item.classification_source === 'fallback' ? item.effective_category : '待分类') }}</strong></div>
                <label><span>报告采用</span><select v-model="flowClassificationDrafts[item.issue_id]" :disabled="!canManageQualityReportSelectionRules"><option value="" disabled>请选择环节</option><option v-for="category in flowClassificationCategories" :key="`${item.issue_id}-${category}`" :value="category">{{ category }}</option></select></label>
                <em :class="item.classification_source">{{ formatFlowClassificationSource(item.classification_source) }}</em>
              </div>
            </article>
          </div>
          <footer class="classification-dialog-footer">
            <p>保存只更新后续报告采用的分类，不会改写当前历史报告。</p>
            <div><button type="button" class="classification-cancel-btn" @click="closeFlowClassificationDialog">关闭</button><button type="button" class="classification-save-btn" :disabled="flowClassificationsSaving || !hasFlowClassificationChanges" @click="saveFlowClassificationAdjustments">{{ flowClassificationsSaving ? '保存中...' : '保存分类' }}</button></div>
          </footer>
        </section>
      </div>
      <div v-if="nonOilIssueLibraryDialogVisible && isNonOilReport" class="flow-classification-dialog-layer non-oil-issue-library-layer">
        <section class="flow-classification-dialog non-oil-issue-library-dialog" role="dialog" aria-modal="true" aria-label="非油报告问题库">
          <button type="button" class="classification-dialog-close" aria-label="关闭" @click="closeNonOilIssueLibraryDialog">×</button>
          <header class="classification-dialog-head issue-library-dialog-head">
            <div>
              <span>REPORT ISSUE LIBRARY</span>
              <h3>选择参与非油报告的问题</h3>
              <p>数据只包含当前日期范围内、检查人已确认且审核通过的问题。选择不会改动原始问题数据。</p>
            </div>
            <div><strong>{{ nonOilIssueSelectionDraftIds.length }}/{{ nonOilIssueLibrary.length }}</strong><span>已选问题</span></div>
          </header>
          <div class="issue-library-toolbar">
            <label class="issue-library-search"><span>搜索问题</span><input v-model.trim="nonOilIssueLibraryKeyword" type="search" placeholder="问题ID、站点、描述或外部规范ID" /></label>
            <label><span>参与状态</span><select v-model="nonOilIssueLibrarySelectionFilter"><option value="">全部问题</option><option value="included">仅看已选</option><option value="excluded">仅看未选</option></select></label>
            <div class="issue-library-batch-actions">
              <button type="button" @click="selectVisibleNonOilIssues(true)">全选当前类别</button>
              <button type="button" @click="selectVisibleNonOilIssues(false)">清空当前类别</button>
              <button type="button" @click="selectAllNonOilIssues">恢复全部参与</button>
            </div>
          </div>
          <div v-if="nonOilIssueLibraryError" class="classification-dialog-message error">{{ nonOilIssueLibraryError }}</div>
          <div class="issue-library-workspace">
            <nav class="issue-library-categories" aria-label="问题类别">
              <button type="button" :class="{ active: !nonOilIssueLibraryCategory }" @click="nonOilIssueLibraryCategory = ''">
                <span>全部类别</span><strong>{{ selectedNonOilIssueCountForCategory('') }}/{{ nonOilIssueLibrary.length }}</strong>
              </button>
              <button
                v-for="category in nonOilIssueCategories"
                :key="`issue-library-category-${category.name}`"
                type="button"
                :class="{ active: nonOilIssueLibraryCategory === category.name }"
                @click="nonOilIssueLibraryCategory = category.name"
              >
                <span>{{ category.display_name }}</span><strong>{{ selectedNonOilIssueCountForCategory(category.name) }}/{{ category.total_count }}</strong>
              </button>
            </nav>
            <div class="issue-library-list">
              <div v-if="nonOilIssueLibraryLoading" class="classification-list-empty">正在整理问题数据库...</div>
              <div v-else-if="!filteredNonOilIssueLibrary.length" class="classification-list-empty">当前类别和筛选条件下没有问题。</div>
              <article
                v-for="item in filteredNonOilIssueLibrary"
                :key="`issue-library-row-${item.issue_id}`"
                :class="{ selected: isNonOilIssueSelected(item.issue_id), excluded: !isNonOilIssueSelected(item.issue_id) }"
              >
                <label class="issue-library-checkbox">
                  <input
                    type="checkbox"
                    :checked="isNonOilIssueSelected(item.issue_id)"
                    @change="toggleNonOilIssueSelection(item.issue_id, $event.target.checked)"
                  />
                  <span aria-hidden="true"></span>
                </label>
                <div class="classification-issue-main">
                  <div class="classification-issue-meta">
                    <b>ID {{ item.issue_id }}</b><span>{{ item.category_display_name }}</span><span>{{ item.station_name }}</span><span>{{ item.unit_name }}</span><span>{{ item.report_date }}</span><button type="button" class="standard-detail-link" :disabled="!item.standard_detail_text" @click="openStandardDetail(item)">外部规范ID {{ item.external_standard_id || '-' }}</button>
                  </div>
                  <p>{{ item.description || '暂无问题描述' }}</p>
                  <small>{{ item.table_name }}</small>
                </div>
                <button v-if="item.issue_photo" type="button" class="issue-library-photo" @click="openImagePreview(item.issue_photo, `${item.station_name || '问题'}照片`)">
                  <img :src="resolveImage(item.issue_photo)" alt="问题照片" loading="lazy" />
                  <span>查看照片</span>
                </button>
                <div v-else class="issue-library-photo empty">无照片</div>
              </article>
            </div>
          </div>
          <footer class="classification-dialog-footer issue-library-dialog-footer">
            <p>已选 {{ nonOilIssueSelectionDraftIds.length }} 条，未选 {{ nonOilIssueLibrary.length - nonOilIssueSelectionDraftIds.length }} 条；保存后供下一次生成使用。</p>
            <div><button type="button" class="classification-cancel-btn" @click="closeNonOilIssueLibraryDialog">关闭</button><button type="button" class="classification-save-btn" :disabled="nonOilIssueLibrarySaving || !hasNonOilIssueSelectionChanges" @click="saveNonOilIssueSelection">{{ nonOilIssueLibrarySaving ? '保存中...' : '保存问题选择' }}</button></div>
          </footer>
        </section>
      </div>
      <div v-if="nonOilClassificationDialogVisible && isNonOilReport" class="flow-classification-dialog-layer">
        <section class="flow-classification-dialog" role="dialog" aria-modal="true" aria-label="非油AI问题分类结果">
          <button type="button" class="classification-dialog-close" aria-label="关闭" @click="closeNonOilClassificationDialog">×</button>
          <header class="classification-dialog-head">
            <div>
              <span>NON-OIL CATEGORY REVIEW</span>
              <h3>查看与调整“其他”问题分类</h3>
              <p>每条问题必须归入明确类别；人工调整供后续生成使用，不改写历史快照。</p>
            </div>
            <div><strong>{{ nonOilClassifications.length }}</strong><span>条问题</span></div>
          </header>
          <div class="classification-dialog-toolbar">
            <label><span>搜索</span><input v-model.trim="nonOilClassificationKeyword" type="search" placeholder="问题ID、站点、描述或外部规范ID" /></label>
            <label><span>当前分类</span><select v-model="nonOilClassificationFilter"><option value="">全部分类</option><option v-for="category in nonOilClassificationCategories" :key="`non-oil-filter-${category}`" :value="category">{{ category }}</option></select></label>
          </div>
          <div v-if="nonOilClassificationsError" class="classification-dialog-message error">{{ nonOilClassificationsError }}</div>
          <div class="classification-dialog-list">
            <div v-if="!filteredNonOilClassifications.length" class="classification-list-empty">当前筛选条件下没有分类记录。</div>
            <article v-for="item in filteredNonOilClassifications" :key="`non-oil-class-row-${item.issue_id}`">
              <div class="classification-issue-main">
                <div class="classification-issue-meta"><b>ID {{ item.issue_id }}</b><span>{{ item.station_name }}</span><span>{{ item.unit_name }}</span><span>外部规范ID {{ item.external_standard_id || '-' }}</span></div>
                <p>{{ item.description || '暂无问题描述' }}</p>
                <small v-if="item.reason">分类依据：{{ item.reason }}</small>
              </div>
              <div class="classification-result-compare">
                <div><span>系统分类</span><strong>{{ item.effective_category }}</strong></div>
                <label><span>报告采用</span><select v-model="nonOilClassificationDrafts[item.issue_id]"><option v-for="category in nonOilClassificationCategories" :key="`${item.issue_id}-${category}`" :value="category">{{ category }}</option></select></label>
                <em :class="item.classification_source">{{ formatFlowClassificationSource(item.classification_source) }}</em>
              </div>
            </article>
          </div>
          <footer class="classification-dialog-footer">
            <p>保存只更新分类结果，不会重新调用 AI 或自动生成报告。</p>
            <div><button type="button" class="classification-cancel-btn" @click="closeNonOilClassificationDialog">关闭</button><button type="button" class="classification-save-btn" :disabled="nonOilClassificationsSaving || !hasNonOilClassificationChanges" @click="saveNonOilClassificationAdjustments">{{ nonOilClassificationsSaving ? '保存中...' : '保存分类' }}</button></div>
          </footer>
        </section>
      </div>
      <div v-if="nonOilKeyClassificationDialogVisible && isNonOilReport" class="flow-classification-dialog-layer">
        <section class="flow-classification-dialog non-oil-key-dialog" role="dialog" aria-modal="true" aria-label="非油AI重点问题分类结果">
          <button type="button" class="classification-dialog-close" aria-label="关闭" @click="closeNonOilKeyClassificationDialog">×</button>
          <header class="classification-dialog-head">
            <div>
              <span>KEY ISSUE REVIEW</span>
              <h3>查看与调整重点问题分类</h3>
              <p>不符合四类定义的问题会标记为“不纳入重点问题”；人工调整在后续重新生成时不会被 AI 覆盖。</p>
            </div>
            <div><strong>{{ nonOilKeyClassifications.length }}</strong><span>条问题</span></div>
          </header>
          <div class="classification-dialog-toolbar">
            <label><span>搜索</span><input v-model.trim="nonOilKeyClassificationKeyword" type="search" placeholder="问题ID、站点、描述或外部规范ID" /></label>
            <label><span>当前分类</span><select v-model="nonOilKeyClassificationFilter"><option value="">全部分类</option><option v-for="category in nonOilKeyClassificationCategories" :key="`non-oil-key-filter-${category}`" :value="category">{{ category }}</option></select></label>
          </div>
          <div v-if="nonOilKeyClassificationsError" class="classification-dialog-message error">{{ nonOilKeyClassificationsError }}</div>
          <div class="classification-dialog-list">
            <div v-if="!filteredNonOilKeyClassifications.length" class="classification-list-empty">当前筛选条件下没有重点问题分类记录。</div>
            <article v-for="item in filteredNonOilKeyClassifications" :key="`non-oil-key-row-${item.issue_id}`">
              <div class="classification-issue-main">
                <div class="classification-issue-meta"><b>ID {{ item.issue_id }}</b><span>{{ item.station_name }}</span><span>{{ item.unit_name }}</span><span>{{ item.business_category }}</span><span>外部规范ID {{ item.external_standard_id || '-' }}</span></div>
                <p>{{ item.description || '暂无问题描述' }}</p>
                <small v-if="item.reason">判定依据：{{ item.reason }}</small>
              </div>
              <div class="classification-result-compare">
                <div><span>当前判定</span><strong>{{ item.effective_category }}</strong></div>
                <label><span>报告采用</span><select v-model="nonOilKeyClassificationDrafts[item.issue_id]"><option v-for="category in nonOilKeyClassificationCategories" :key="`${item.issue_id}-key-${category}`" :value="category">{{ category }}</option></select></label>
                <em :class="item.classification_source">{{ formatFlowClassificationSource(item.classification_source) }}</em>
              </div>
            </article>
          </div>
          <footer class="classification-dialog-footer">
            <p>保存只更新重点问题判定，不会重新调用 AI 或自动生成报告。</p>
            <div><button type="button" class="classification-cancel-btn" @click="closeNonOilKeyClassificationDialog">关闭</button><button type="button" class="classification-save-btn" :disabled="nonOilKeyClassificationsSaving || !hasNonOilKeyClassificationChanges" @click="saveNonOilKeyClassificationAdjustments">{{ nonOilKeyClassificationsSaving ? '保存中...' : '保存分类' }}</button></div>
          </footer>
        </section>
      </div>
      <div v-if="selectionSettingsDialogVisible && isQualityMeasurementReport" class="report-selection-dialog-layer">
        <section class="report-selection-dialog" role="dialog" aria-modal="true" aria-label="质量计量报告选题规则">
          <button type="button" class="selection-dialog-close" aria-label="关闭" @click="closeSelectionSettingsDialog">×</button>
          <header class="selection-dialog-head">
            <div>
              <span>REPORT ISSUE RULES</span>
              <h3>{{ selectionSettingsDialogMode === 'historical' ? '历史报告当时选题规则' : '设置质量计量报告选题规则' }}</h3>
              <p>{{ selectionSettingsDialogMode === 'historical' ? '当前显示该历史报告生成时使用的规则；保存后会设为后续报告的默认规则。' : '规则全局共享并自动记忆，保存后在下一次生成报告时生效。' }}</p>
            </div>
            <div class="selection-updated-meta">
              <span>最后更新</span>
              <strong>{{ selectionDialogMeta.updated_at || '尚未保存' }}</strong>
              <small>{{ selectionDialogMeta.updated_by_name || '系统默认规则' }}</small>
            </div>
          </header>

          <div v-if="selectionSettingsError" class="selection-settings-message error">{{ selectionSettingsError }}</div>
          <div v-else-if="selectionSettingsMessage" class="selection-settings-message success">{{ selectionSettingsMessage }}</div>

          <div class="selection-rule-tabs">
            <button type="button" :class="{ active: selectionRuleTab === 'prohibited' }" @click="selectionRuleTab = 'prohibited'">
              <strong>禁止项选题</strong>
              <span>星标优先，其次按外部规范顺序</span>
            </button>
            <button type="button" :class="{ active: selectionRuleTab === 'flow' }" @click="selectionRuleTab = 'flow'">
              <strong>分环节突出问题</strong>
              <span>控制抽取数量和规范优先级</span>
            </button>
          </div>

          <div v-if="selectionSettingsLoading" class="selection-settings-loading">正在读取可配置的外部规范...</div>
          <template v-else>
            <section v-if="selectionRuleTab === 'flow'" class="selection-sampling-section">
              <div class="selection-section-title">
                <div><span>01</span><div><h4>各档突出问题数量</h4><p>实际问题不足时按真实数量展示，长描述会自动独占一页。</p></div></div>
              </div>
              <div class="selection-sampling-grid">
                <label v-for="item in selectionSampleRuleOptions" :key="item.key">
                  <span>{{ item.label }}</span>
                  <div><input v-model.number="selectionSettingsDraft.sample_counts[item.key]" type="number" min="1" max="12" :disabled="!canManageQualityReportSelectionRules" /><em>项</em></div>
                </label>
              </div>
            </section>

            <section class="selection-priority-section">
              <div class="selection-section-title">
                <div><span>{{ selectionRuleTab === 'flow' ? '02' : '01' }}</span><div><h4>{{ selectionPriorityTitle }}</h4><p>越靠上优先级越高；同级仍无法唯一确定时由AI结合问题内容裁决。</p></div></div>
              </div>

              <div v-if="selectionRuleTab === 'flow'" class="selection-flow-tabs">
                <button v-for="flow in selectionBusinessFlows" :key="flow" type="button" :class="{ active: selectionActiveFlow === flow }" @click="selectionActiveFlow = flow">{{ flow }}</button>
                <span v-if="!selectionBusinessFlows.length">暂无业务流程字段数据</span>
              </div>

              <div class="selection-standard-toolbar">
                <label><span>搜索规范</span><input v-model.trim="selectionStandardKeyword" type="search" placeholder="输入外部规范ID或规范内容" /></label>
                <label><span>检查表</span><select v-model="selectionTableFilter"><option value="">全部检查表</option><option v-for="tableName in selectionTableNames" :key="tableName" :value="tableName">{{ tableName }}</option></select></label>
              </div>

              <div class="selection-priority-workbench">
                <div class="selection-standard-pool">
                  <header><strong>可选外部规范</strong><span>{{ filteredSelectionStandards.length }} 条</span></header>
                  <div>
                    <button v-for="standard in filteredSelectionStandards.slice(0, 80)" :key="`candidate-${selectionRuleTab}-${standard.standard_id}`" type="button" :disabled="!canManageQualityReportSelectionRules || isSelectionStandardSelected(standard.standard_id)" @click="addSelectionPriority(standard.standard_id)">
                      <span class="selection-standard-id">{{ standard.standard_id }}</span>
                      <span><strong>{{ standard.table_name }}</strong><small>{{ standard.business_flow }} · {{ standard.detail_text || '-' }}</small></span>
                      <b>{{ isSelectionStandardSelected(standard.standard_id) ? '已添加' : '添加' }}</b>
                    </button>
                    <p v-if="!filteredSelectionStandards.length">当前条件下没有可选规范。</p>
                  </div>
                </div>

                <div class="selection-priority-list">
                  <header><strong>当前优先级</strong><span>{{ currentSelectionPriorityIds.length }} 条</span></header>
                  <div>
                    <article v-for="(standard, index) in currentSelectionPriorityStandards" :key="`priority-${selectionRuleTab}-${standard.standard_id}`">
                      <span class="selection-rank">{{ index + 1 }}</span>
                      <div><strong>外部规范ID {{ standard.standard_id }}</strong><small>{{ standard.table_name }} · {{ standard.business_flow }}</small></div>
                      <div class="selection-rank-actions">
                        <button type="button" :disabled="!canManageQualityReportSelectionRules || index === 0" title="上移" @click="moveSelectionPriority(index, -1)">↑</button>
                        <button type="button" :disabled="!canManageQualityReportSelectionRules || index === currentSelectionPriorityIds.length - 1" title="下移" @click="moveSelectionPriority(index, 1)">↓</button>
                        <button type="button" class="remove" :disabled="!canManageQualityReportSelectionRules" title="移除" @click="removeSelectionPriority(index)">×</button>
                      </div>
                    </article>
                    <p v-if="!currentSelectionPriorityStandards.length">暂未设置规范优先级，将由AI在并列候选中决策。</p>
                  </div>
                </div>
              </div>
            </section>
          </template>

          <footer class="selection-dialog-footer">
            <p>{{ canManageQualityReportSelectionRules
              ? '禁止项始终先选星标问题；规范优先级不会修改原始问题数据。'
              : '当前账号可以查看选题规则，但不能修改。' }}</p>
            <div>
              <button type="button" class="selection-cancel-btn" @click="closeSelectionSettingsDialog">{{ canManageQualityReportSelectionRules ? '取消' : '关闭' }}</button>
              <button v-if="canManageQualityReportSelectionRules" type="button" class="selection-save-btn" :disabled="selectionSettingsSaving || selectionSettingsLoading" @click="saveSelectionSettings">{{ selectionSettingsSaving ? '保存中...' : '保存选题规则' }}</button>
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
      <div v-if="standardDetailPreview.visible" class="standard-detail-preview" @click.self="closeStandardDetail">
        <section role="dialog" aria-modal="true" aria-label="外部规范详情">
          <button type="button" aria-label="关闭" @click="closeStandardDetail">×</button>
          <header>
            <span>EXTERNAL STANDARD</span>
            <h3>外部规范ID {{ standardDetailPreview.standardId || '-' }}</h3>
            <small>{{ standardDetailPreview.tableName || '未记录检查表' }}</small>
          </header>
          <div>
            <span>规范内容</span>
            <p>{{ standardDetailPreview.detail || '暂无可查看的规范详情。' }}</p>
          </div>
        </section>
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
    data_scope_note: '巡检周期按上月25日至本月24日统计；站点覆盖以已确认完成的非油团购与现场检查记录为准，问题分析仅使用审核通过的问题。',
    template_ready: true
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
  total_row: {},
  slides: [],
  presentation: {},
  category_classifications: []
})

const createDefaultSelectionSettings = () => ({
  sample_counts: {
    more_than_20: 8,
    more_than_10: 6,
    more_than_4: 4,
    at_most_4: 2
  },
  prohibited_standard_priorities: [],
  flow_standard_priorities: {}
})

const cloneSelectionSettings = (value = {}) => {
  const defaults = createDefaultSelectionSettings()
  return {
    sample_counts: {
      ...defaults.sample_counts,
      ...(value.sample_counts || {})
    },
    prohibited_standard_priorities: [...(value.prohibited_standard_priorities || [])].map(Number),
    flow_standard_priorities: Object.fromEntries(
      Object.entries(value.flow_standard_priorities || {}).map(([flowName, ids]) => [
        flowName,
        [...(ids || [])].map(Number)
      ])
    )
  }
}

const getDefaultReportMonth = () => {
  const now = new Date()
  const previousMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1)
  const year = previousMonth.getFullYear()
  const month = String(previousMonth.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

const getDefaultNonOilDateRange = (monthValue) => {
  const [year, month] = String(monthValue || '').split('-').map(Number)
  if (!year || !month) return { date_from: '', date_to: '' }
  const start = new Date(year, month - 1, 1)
  const end = new Date(year, month, 0)
  const format = (value) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  return { date_from: format(start), date_to: format(end) }
}

const selectedMonth = ref(getDefaultReportMonth())
const initialReportDateRange = getDefaultNonOilDateRange(selectedMonth.value)
const reportDateFrom = ref(initialReportDateRange.date_from)
const reportDateTo = ref(initialReportDateRange.date_to)
const reportHistory = ref([])
const selectedSnapshotId = ref(0)
const selectedReportType = ref('quality_measurement')
const reportTypes = ref(DEFAULT_REPORT_TYPES)
const loading = ref(false)
const error = ref('')
const activeJob = ref(null)
const canGenerateReports = ref(
  currentRole === 'root' || Boolean(storedPermissions.generate_inspection_reports)
)
const canManageQualityReportSource = ref(true)
const canManageQualityReportSelectionRules = ref(true)

const applyReportCapabilities = (payload = {}) => {
  if (Object.prototype.hasOwnProperty.call(payload, 'can_generate')) {
    canGenerateReports.value = Boolean(payload.can_generate)
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'can_manage_quality_report_source')) {
    canManageQualityReportSource.value = Boolean(payload.can_manage_quality_report_source)
  }
  if (Object.prototype.hasOwnProperty.call(payload, 'can_manage_quality_report_selection_rules')) {
    canManageQualityReportSelectionRules.value = Boolean(payload.can_manage_quality_report_selection_rules)
  }
}
const imagePreview = ref({
  visible: false,
  src: '',
  title: ''
})
const standardDetailPreview = ref({
  visible: false,
  standardId: '',
  tableName: '',
  detail: ''
})
const report = ref(createEmptyReport())
const sourceStations = ref([])
const sourceLoading = ref(false)
const sourceError = ref('')
const sourceSelectionMode = ref('all')
const selectedSourceStationIds = ref([])
const sourceSelectionMeta = ref({ updated_at: '', updated_by_name: '' })
const sourceDialogVisible = ref(false)
const sourceDraftMode = ref('all')
const sourceDraftIds = ref([])
const sourceKeyword = ref('')
const sourceRegionFilter = ref('')
const sourceOnlySelected = ref(false)
const sourceDialogMode = ref('saved')
const selectionSettingsDialogVisible = ref(false)
const selectionSettingsDialogMode = ref('saved')
const selectionSettingsLoading = ref(false)
const selectionSettingsSaving = ref(false)
const selectionSettingsError = ref('')
const selectionSettingsMessage = ref('')
const selectionSettings = ref(createDefaultSelectionSettings())
const selectionSettingsDraft = ref(createDefaultSelectionSettings())
const selectionSettingsMeta = ref({ updated_at: '', updated_by_name: '' })
const selectionStandardOptions = ref([])
const selectionBusinessFlows = ref([])
const selectionRuleTab = ref('prohibited')
const selectionActiveFlow = ref('')
const selectionStandardKeyword = ref('')
const selectionTableFilter = ref('')
const flowClassifications = ref([])
const flowClassificationCategories = ref([])
const flowClassificationsLoading = ref(false)
const flowClassificationsSaving = ref(false)
const flowClassificationsError = ref('')
const flowClassificationMessage = ref('')
const flowClassificationDialogVisible = ref(false)
const flowClassificationDrafts = ref({})
const flowClassificationKeyword = ref('')
const flowClassificationCategoryFilter = ref('')
const nonOilDateFrom = reportDateFrom
const nonOilDateTo = reportDateTo
const nonOilIssueLibrary = ref([])
const nonOilIssueCategories = ref([])
const nonOilIssueLibraryLoading = ref(false)
const nonOilIssueLibrarySaving = ref(false)
const nonOilIssueLibraryError = ref('')
const nonOilIssueLibraryDialogVisible = ref(false)
const nonOilIssueSelectionDraftIds = ref([])
const nonOilIssueLibraryCategory = ref('')
const nonOilIssueLibraryKeyword = ref('')
const nonOilIssueLibrarySelectionFilter = ref('')
const nonOilClassifications = ref([])
const nonOilClassificationCategories = ref([])
const nonOilClassificationsLoading = ref(false)
const nonOilClassificationsSaving = ref(false)
const nonOilClassificationsError = ref('')
const nonOilClassificationDialogVisible = ref(false)
const nonOilClassificationDrafts = ref({})
const nonOilClassificationKeyword = ref('')
const nonOilClassificationFilter = ref('')
const nonOilKeyClassifications = ref([])
const nonOilKeyClassificationCategories = ref([])
const nonOilKeyClassificationsLoading = ref(false)
const nonOilKeyClassificationsSaving = ref(false)
const nonOilKeyClassificationsError = ref('')
const nonOilKeyClassificationDialogVisible = ref(false)
const nonOilKeyClassificationDrafts = ref({})
const nonOilKeyClassificationKeyword = ref('')
const nonOilKeyClassificationFilter = ref('')
const activeQualitySlideIndex = ref(0)
const qualityImageAspects = ref({})
const exportDialogVisible = ref(false)
const exportTask = ref(null)
const exportError = ref('')
const exportSubmitting = ref(false)
const exportDownloading = ref(false)
let pollTimer = null
let exportPollTimer = null
let contextRequestId = 0
let nonOilIssueLibraryRequestId = 0

const currentReportType = computed(() => (
  reportTypes.value.find((item) => item.key === selectedReportType.value)
  || DEFAULT_REPORT_TYPES[0]
))
const templateUnavailable = computed(() => currentReportType.value.template_ready === false)
const validReportDateRange = computed(() => Boolean(
  reportDateFrom.value
  && reportDateTo.value
  && reportDateFrom.value <= reportDateTo.value
))
const matchingHistory = computed(() => reportHistory.value.find((item) => (
  item.date_from === reportDateFrom.value && item.date_to === reportDateTo.value
)) || null)
const isQualityMeasurementReport = computed(() => selectedReportType.value === 'quality_measurement')
const isSafetyQualityReport = computed(() => selectedReportType.value === 'safety_quality')
const isFinanceReport = computed(() => selectedReportType.value === 'finance')
const isOnSiteServiceReport = computed(() => selectedReportType.value === 'on_site_service')
const isEquipmentFacilitiesReport = computed(() => selectedReportType.value === 'equipment_facilities')
const isNonOilReport = computed(() => selectedReportType.value === 'non_oil')
const qualitySlides = computed(() => (
  Array.isArray(report.value?.slides) ? report.value.slides : []
))
const currentQualitySlide = computed(() => (
  qualitySlides.value[activeQualitySlideIndex.value] || null
))
const nonOilSlideUrls = computed(() => (
  Array.isArray(report.value?.presentation?.slide_urls)
    ? report.value.presentation.slide_urls
    : []
))
const currentNonOilSlideUrl = computed(() => (
  nonOilSlideUrls.value[activeQualitySlideIndex.value] || ''
))
const activePresentationSlideCount = computed(() => (
  isQualityMeasurementReport.value ? qualitySlides.value.length : nonOilSlideUrls.value.length
))
const qualityOverallRows = computed(() => {
  if (currentQualitySlide.value?.kind !== 'overall') return []
  const rows = [...(currentQualitySlide.value.rows || [])]
  if (currentQualitySlide.value.total_row) rows.push(currentQualitySlide.value.total_row)
  return rows
})
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
const historicalSourceSelection = computed(() => (
  report.value?.generation_context?.source_selection
  || reportSourceSelection.value
  || {}
))
const historicalSelectionSettingsRecord = computed(() => (
  report.value?.generation_context?.selection_settings || {}
))
const selectionDialogMeta = computed(() => (
  selectionSettingsDialogMode.value === 'historical'
    ? {
        updated_at: historicalSelectionSettingsRecord.value.updated_at || '',
        updated_by_name: historicalSelectionSettingsRecord.value.updated_by_name || ''
      }
    : selectionSettingsMeta.value
))
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
  if (!sourceStations.value.length) return '当前日期范围暂无符合报告口径的可用站点数据。'
  if (sourceSelectionMode.value === 'custom') {
    return `已选择 ${summary.station_count} 个站点，覆盖 ${summary.region_count} 个片区；下一次生成只统计这些站点。`
  }
  return `使用当前日期范围全部 ${summary.station_count} 个可用站点，覆盖 ${summary.region_count} 个片区。`
})
const historicalSourceSelectionDescription = computed(() => {
  const selection = historicalSourceSelection.value
  const stationCount = Number(selection.station_count ?? (selection.station_ids || []).length) || 0
  return selection.mode === 'custom'
    ? `自定义 ${stationCount} 个站点`
    : `当时全部 ${stationCount} 个可用站点`
})
const sourceSelectionDirty = computed(() => {
  if (!canManageQualityReportSource.value) return false
  if (!hasReport.value) return false
  const savedMode = reportSourceSelection.value.mode === 'custom' ? 'custom' : 'all'
  if (savedMode !== sourceSelectionMode.value) return true
  if (savedMode !== 'custom') return false
  const savedIds = [...(reportSourceSelection.value.station_ids || [])].map(Number).sort((a, b) => a - b)
  const currentIds = [...selectedSourceStationIds.value].map(Number).sort((a, b) => a - b)
  return JSON.stringify(savedIds) !== JSON.stringify(currentIds)
})
const nonOilIssueLibraryStats = computed(() => ({
  total: nonOilIssueLibrary.value.length,
  included: nonOilIssueLibrary.value.filter((item) => item.included).length,
  excluded: nonOilIssueLibrary.value.filter((item) => !item.included).length,
  categories: nonOilIssueCategories.value.length
}))
const nonOilIssueSelectionDraftSet = computed(() => new Set(
  nonOilIssueSelectionDraftIds.value.map(Number)
))
const filteredNonOilIssueLibrary = computed(() => {
  const keyword = nonOilIssueLibraryKeyword.value.toLowerCase()
  const selectedIds = nonOilIssueSelectionDraftSet.value
  return nonOilIssueLibrary.value.filter((item) => {
    if (nonOilIssueLibraryCategory.value && item.category_name !== nonOilIssueLibraryCategory.value) return false
    const selected = selectedIds.has(Number(item.issue_id))
    if (nonOilIssueLibrarySelectionFilter.value === 'included' && !selected) return false
    if (nonOilIssueLibrarySelectionFilter.value === 'excluded' && selected) return false
    if (!keyword) return true
    return [item.issue_id, item.station_name, item.unit_name, item.table_name, item.external_standard_id, item.description]
      .some((value) => String(value || '').toLowerCase().includes(keyword))
  })
})
const hasNonOilIssueSelectionChanges = computed(() => {
  const savedIds = nonOilIssueLibrary.value
    .filter((item) => item.included)
    .map((item) => Number(item.issue_id))
    .sort((a, b) => a - b)
  const draftIds = [...nonOilIssueSelectionDraftIds.value]
    .map(Number)
    .sort((a, b) => a - b)
  return JSON.stringify(savedIds) !== JSON.stringify(draftIds)
})
const visibleFlowClassifications = computed(() => {
  if (sourceSelectionMode.value !== 'custom') return flowClassifications.value
  const selectedIds = new Set(selectedSourceStationIds.value.map(Number))
  return flowClassifications.value.filter((item) => selectedIds.has(Number(item.station_id)))
})
const flowClassificationStats = computed(() => {
  const rows = visibleFlowClassifications.value
  return {
    total: rows.length,
    ai: rows.filter((item) => item.classification_source === 'ai').length,
    manual: rows.filter((item) => item.classification_source === 'manual').length,
    pending: rows.filter((item) => !item.effective_category).length
  }
})
const nonOilClassificationStats = computed(() => ({
  total: nonOilClassifications.value.length,
  ai: nonOilClassifications.value.filter((item) => item.classification_source === 'ai').length,
  manual: nonOilClassifications.value.filter((item) => item.classification_source === 'manual').length,
  fallback: nonOilClassifications.value.filter((item) => item.classification_source === 'fallback').length
}))
const filteredNonOilClassifications = computed(() => {
  const keyword = nonOilClassificationKeyword.value.toLowerCase()
  return nonOilClassifications.value.filter((item) => {
    if (nonOilClassificationFilter.value && item.effective_category !== nonOilClassificationFilter.value) return false
    if (!keyword) return true
    return [item.issue_id, item.station_name, item.unit_name, item.external_standard_id, item.description]
      .some((value) => String(value || '').toLowerCase().includes(keyword))
  })
})
const hasNonOilClassificationChanges = computed(() => (
  nonOilClassifications.value.some((item) => (
    String(nonOilClassificationDrafts.value[item.issue_id] || '') !== String(item.effective_category || '')
  ))
))
const selectedNonOilKeyClassifications = computed(() => (
  nonOilKeyClassifications.value.filter((item) => item.effective_category !== '不纳入重点问题')
))
const nonOilKeyClassificationStats = computed(() => ({
  total: nonOilKeyClassifications.value.length,
  selected: selectedNonOilKeyClassifications.value.length,
  ai: nonOilKeyClassifications.value.filter((item) => item.classification_source === 'ai').length,
  manual: nonOilKeyClassifications.value.filter((item) => item.classification_source === 'manual').length
}))
const filteredNonOilKeyClassifications = computed(() => {
  const keyword = nonOilKeyClassificationKeyword.value.toLowerCase()
  return nonOilKeyClassifications.value.filter((item) => {
    if (nonOilKeyClassificationFilter.value && item.effective_category !== nonOilKeyClassificationFilter.value) return false
    if (!keyword) return true
    return [item.issue_id, item.station_name, item.unit_name, item.business_category, item.external_standard_id, item.description]
      .some((value) => String(value || '').toLowerCase().includes(keyword))
  })
})
const hasNonOilKeyClassificationChanges = computed(() => (
  nonOilKeyClassifications.value.some((item) => (
    String(nonOilKeyClassificationDrafts.value[item.issue_id] || '') !== String(item.effective_category || '')
  ))
))
const filteredFlowClassifications = computed(() => {
  const keyword = flowClassificationKeyword.value.toLowerCase()
  const category = flowClassificationCategoryFilter.value
  return visibleFlowClassifications.value.filter((item) => {
    const effectiveCategory = item.effective_category || ''
    if (category === 'pending' && effectiveCategory) return false
    if (category && category !== 'pending' && effectiveCategory !== category) return false
    if (!keyword) return true
    return [item.issue_id, item.station_name, item.region, item.table_name, item.external_standard_id, item.description]
      .some((value) => String(value || '').toLowerCase().includes(keyword))
  })
})
const hasFlowClassificationChanges = computed(() => (
  visibleFlowClassifications.value.some((item) => (
    String(flowClassificationDrafts.value[item.issue_id] || '')
      !== String(item.effective_category || '')
  ))
))
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
const selectionSampleRuleOptions = [
  { key: 'more_than_20', label: '问题数超过20项' },
  { key: 'more_than_10', label: '问题数11至20项' },
  { key: 'more_than_4', label: '问题数5至10项' },
  { key: 'at_most_4', label: '问题数不超过4项' }
]
const selectionTableNames = computed(() => (
  [...new Set(selectionStandardOptions.value.map((item) => item.table_name).filter(Boolean))]
))
const selectionStandardMap = computed(() => new Map(
  selectionStandardOptions.value.map((item) => [Number(item.standard_id), item])
))
const currentSelectionPriorityIds = computed(() => {
  if (selectionRuleTab.value === 'prohibited') {
    return selectionSettingsDraft.value.prohibited_standard_priorities || []
  }
  return selectionSettingsDraft.value.flow_standard_priorities?.[selectionActiveFlow.value] || []
})
const currentSelectionPriorityStandards = computed(() => (
  currentSelectionPriorityIds.value
    .map((standardId) => selectionStandardMap.value.get(Number(standardId)))
    .filter(Boolean)
))
const selectionPriorityTitle = computed(() => (
  selectionRuleTab.value === 'prohibited'
    ? '禁止项外部规范优先级'
    : `${selectionActiveFlow.value || '当前环节'}规范优先级`
))
const filteredSelectionStandards = computed(() => {
  const keyword = selectionStandardKeyword.value.toLowerCase()
  return selectionStandardOptions.value.filter((item) => {
    if (selectionRuleTab.value === 'flow' && selectionActiveFlow.value && item.business_flow !== selectionActiveFlow.value) return false
    if (selectionTableFilter.value && item.table_name !== selectionTableFilter.value) return false
    if (!keyword) return true
    return [item.standard_id, item.table_name, item.business_flow, item.detail_text]
      .some((value) => String(value || '').toLowerCase().includes(keyword))
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
  if (isNonOilReport.value) {
    return [
      {
        label: '巡检周期',
        value: summary.date_from && summary.date_to ? `${summary.date_from.slice(5)}—${summary.date_to.slice(5)}` : '-',
        desc: '上月25日至本月24日'
      },
      {
        label: '覆盖站点',
        value: summary.station_count ?? 0,
        desc: `${summary.unit_count ?? 0}个管理单位`
      },
      {
        label: '发现问题',
        value: summary.total_issue_count ?? 0,
        desc: '仅统计审核通过问题'
      },
      {
        label: '站均问题',
        value: Number(summary.average_issue_count || 0).toFixed(1),
        desc: `覆盖${summary.category_count ?? 0}类非油业务`
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

const joinChineseList = (items) => {
  const values = items.map((item) => String(item || '').trim()).filter(Boolean)
  if (!values.length) return ''
  if (values.length === 1) return values[0]
  if (values.length === 2) return values.join('和')
  return `${values.slice(0, -1).join('、')}和${values[values.length - 1]}`
}

const formatPercent = (value) => `${Number(value || 0).toFixed(1)}%`

const findingFlowColors = ['#167fb3', '#20a0a0', '#e8993f', '#5479c9', '#7b61b3', '#d76565', '#4b9b68', '#8b6f47']

const getFindingFlowColor = (index) => findingFlowColors[index % findingFlowColors.length]

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

const getQualityImageKey = (issue = {}, prefix = 'issue') => (
  `${prefix}:${issue.issue_id || issue.id || issue.issue_photo || issue.station_name || 'unknown'}`
)

const rememberQualityImageAspect = (event, key) => {
  const image = event?.target
  if (!image?.naturalWidth || !image?.naturalHeight || !key) return
  const ratio = image.naturalWidth / image.naturalHeight
  if (Math.abs((qualityImageAspects.value[key] || 0) - ratio) < 0.01) return
  qualityImageAspects.value = {
    ...qualityImageAspects.value,
    [key]: ratio
  }
}

const getQualityCopyClass = (value) => {
  const length = String(value || '').trim().length
  if (length >= 150) return 'copy-long'
  if (length <= 70) return 'copy-short'
  return 'copy-medium'
}

const getQualityPhotoClass = (ratio) => {
  if (ratio >= 2.15) return 'photo-panorama'
  if (ratio >= 1.35) return 'photo-landscape'
  if (ratio <= 0.72) return 'photo-portrait'
  return 'photo-balanced'
}

const getQualityIssueLayoutClasses = (issue = {}) => {
  const ratio = qualityImageAspects.value[getQualityImageKey(issue)] || 1.35
  return [getQualityPhotoClass(ratio), getQualityCopyClass(issue.description)]
}

const getQualityTraceLayoutClasses = (slide = {}) => {
  const issue = slide.typical_issue || {}
  const ratio = qualityImageAspects.value[getQualityImageKey(issue, 'trace')] || 1.35
  const text = [issue.description, ...(slide.analysis_items || []).map((item) => item.content)].join('')
  return [getQualityPhotoClass(ratio), getQualityCopyClass(text)]
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

const openStandardDetail = (item = {}) => {
  if (!item.standard_detail_text) return
  standardDetailPreview.value = {
    visible: true,
    standardId: item.external_standard_id || '',
    tableName: item.table_name || '',
    detail: item.standard_detail_text || ''
  }
}

const closeStandardDetail = () => {
  standardDetailPreview.value = {
    visible: false,
    standardId: '',
    tableName: '',
    detail: ''
  }
}

const goToQualitySlide = (index) => {
  const lastIndex = Math.max(0, activePresentationSlideCount.value - 1)
  activeQualitySlideIndex.value = Math.max(0, Math.min(lastIndex, Number(index) || 0))
  window.requestAnimationFrame(() => {
    document.querySelector('.quality-ppt-stage')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

const isKeyboardEditingTarget = (target) => {
  if (!(target instanceof HTMLElement)) return false
  return Boolean(
    target.closest('input, textarea, select, [contenteditable="true"], [role="textbox"]')
  )
}

const handleQualitySlideKeydown = (event) => {
  if (
    (!isQualityMeasurementReport.value && !isNonOilReport.value)
    || activePresentationSlideCount.value < 2
    || event.defaultPrevented
    || event.ctrlKey
    || event.metaKey
    || event.altKey
    || isKeyboardEditingTarget(event.target)
    || sourceDialogVisible.value
    || selectionSettingsDialogVisible.value
    || flowClassificationDialogVisible.value
    || nonOilClassificationDialogVisible.value
    || nonOilKeyClassificationDialogVisible.value
    || exportDialogVisible.value
    || imagePreview.value.visible
    || standardDetailPreview.value.visible
  ) return

  const direction = event.key === 'ArrowLeft' ? -1 : event.key === 'ArrowRight' ? 1 : 0
  if (!direction) return
  const targetIndex = activeQualitySlideIndex.value + direction
  if (targetIndex < 0 || targetIndex >= activePresentationSlideCount.value) return
  event.preventDefault()
  goToQualitySlide(targetIndex)
}

const getQualityBarHeight = (value) => {
  const values = currentQualitySlide.value?.distribution || []
  const maximum = Math.max(1, ...values.map((item) => Number(item.count) || 0))
  return Math.max(4, Math.round(((Number(value) || 0) / maximum) * 82))
}

const stripTracePrefix = (value) => String(value || '暂无分析结论。').replace(/^综上所述[:：]?\s*/, '')

const setCurrentSelectionPriorityIds = (ids) => {
  const normalized = [...new Set((ids || []).map(Number).filter((value) => Number.isInteger(value) && value > 0))]
  if (selectionRuleTab.value === 'prohibited') {
    selectionSettingsDraft.value.prohibited_standard_priorities = normalized
    return
  }
  selectionSettingsDraft.value.flow_standard_priorities = {
    ...(selectionSettingsDraft.value.flow_standard_priorities || {}),
    [selectionActiveFlow.value]: normalized
  }
}

const isSelectionStandardSelected = (standardId) => (
  currentSelectionPriorityIds.value.map(Number).includes(Number(standardId))
)

const addSelectionPriority = (standardId) => {
  if (!canManageQualityReportSelectionRules.value || isSelectionStandardSelected(standardId)) return
  setCurrentSelectionPriorityIds([...currentSelectionPriorityIds.value, Number(standardId)])
}

const removeSelectionPriority = (index) => {
  if (!canManageQualityReportSelectionRules.value) return
  const ids = [...currentSelectionPriorityIds.value]
  ids.splice(index, 1)
  setCurrentSelectionPriorityIds(ids)
}

const moveSelectionPriority = (index, direction) => {
  if (!canManageQualityReportSelectionRules.value) return
  const ids = [...currentSelectionPriorityIds.value]
  const targetIndex = index + direction
  if (index < 0 || targetIndex < 0 || targetIndex >= ids.length) return
  const [item] = ids.splice(index, 1)
  ids.splice(targetIndex, 0, item)
  setCurrentSelectionPriorityIds(ids)
}

const loadSelectionSettings = async () => {
  selectionSettingsLoading.value = true
  selectionSettingsError.value = ''
  selectionSettingsMessage.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/quality-selection-settings')
    if (!response.data?.success) throw new Error(response.data?.error || '读取选题规则失败。')
    selectionSettings.value = cloneSelectionSettings(response.data.settings)
    selectionSettingsDraft.value = cloneSelectionSettings(response.data.settings)
    selectionSettingsMeta.value = {
      updated_at: response.data.updated_at || '',
      updated_by_name: response.data.updated_by_name || ''
    }
    selectionStandardOptions.value = Array.isArray(response.data.standards) ? response.data.standards : []
    selectionBusinessFlows.value = Array.isArray(response.data.business_flows) ? response.data.business_flows : []
    canManageQualityReportSelectionRules.value = Boolean(response.data?.can_edit)
    if (!selectionBusinessFlows.value.includes(selectionActiveFlow.value)) {
      selectionActiveFlow.value = selectionBusinessFlows.value[0] || ''
    }
  } catch (err) {
    selectionSettingsError.value = err?.response?.data?.error || err?.message || '读取选题规则失败。'
  } finally {
    selectionSettingsLoading.value = false
  }
}

const openSelectionSettingsDialog = async (mode = 'saved') => {
  if (!isQualityMeasurementReport.value) return
  selectionSettingsDialogMode.value = mode === 'historical' ? 'historical' : 'saved'
  selectionSettingsDialogVisible.value = true
  selectionRuleTab.value = 'prohibited'
  selectionStandardKeyword.value = ''
  selectionTableFilter.value = ''
  await loadSelectionSettings()
  if (selectionSettingsDialogMode.value === 'historical') {
    selectionSettingsDraft.value = cloneSelectionSettings(
      historicalSelectionSettingsRecord.value.settings || selectionSettings.value
    )
  }
}

const closeSelectionSettingsDialog = () => {
  selectionSettingsDialogVisible.value = false
  selectionSettingsError.value = ''
  selectionSettingsMessage.value = ''
}

const saveSelectionSettings = async () => {
  if (!canManageQualityReportSelectionRules.value || selectionSettingsSaving.value) return
  selectionSettingsSaving.value = true
  selectionSettingsError.value = ''
  selectionSettingsMessage.value = ''
  try {
    const normalizedCounts = {}
    for (const item of selectionSampleRuleOptions) {
      const value = Number(selectionSettingsDraft.value.sample_counts?.[item.key])
      if (!Number.isInteger(value) || value < 1 || value > 12) {
        throw new Error(`${item.label}的抽取数量必须是1至12之间的整数。`)
      }
      normalizedCounts[item.key] = value
    }
    const payload = cloneSelectionSettings({
      ...selectionSettingsDraft.value,
      sample_counts: normalizedCounts
    })
    const response = await axios.put('/api/inspection-reports/quality-selection-settings', {
      settings: payload
    })
    if (!response.data?.success) throw new Error(response.data?.error || '保存选题规则失败。')
    selectionSettings.value = cloneSelectionSettings(response.data.settings)
    selectionSettingsDraft.value = cloneSelectionSettings(response.data.settings)
    selectionSettingsMeta.value = {
      updated_at: response.data.updated_at || '',
      updated_by_name: response.data.updated_by_name || ''
    }
    selectionSettingsDialogMode.value = 'saved'
    selectionSettingsMessage.value = '选题规则已保存，重新生成报告后生效。'
  } catch (err) {
    selectionSettingsError.value = err?.response?.data?.error || err?.message || '保存选题规则失败。'
  } finally {
    selectionSettingsSaving.value = false
  }
}

const resetFlowClassificationState = () => {
  flowClassifications.value = []
  flowClassificationCategories.value = []
  flowClassificationsError.value = ''
  flowClassificationMessage.value = ''
  flowClassificationDialogVisible.value = false
  flowClassificationDrafts.value = {}
  flowClassificationKeyword.value = ''
  flowClassificationCategoryFilter.value = ''
}

const loadFlowClassifications = async (requestId = contextRequestId) => {
  if (!isQualityMeasurementReport.value) {
    resetFlowClassificationState()
    flowClassificationsLoading.value = false
    return
  }
  flowClassificationsLoading.value = true
  flowClassificationsError.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/quality-flow-classifications', {
      params: {
        month: selectedMonth.value,
        date_from: reportDateFrom.value,
        date_to: reportDateTo.value
      }
    })
    if (requestId !== contextRequestId) return
    if (!response.data?.success) throw new Error(response.data?.error || '读取AI环节分类失败。')
    flowClassifications.value = Array.isArray(response.data.classifications)
      ? response.data.classifications
      : []
    flowClassificationCategories.value = Array.isArray(response.data.business_flows)
      ? response.data.business_flows
      : []
    flowClassificationDrafts.value = Object.fromEntries(
      flowClassifications.value.map((item) => [item.issue_id, item.effective_category || ''])
    )
  } catch (err) {
    if (requestId !== contextRequestId) return
    flowClassifications.value = []
    flowClassificationCategories.value = []
    flowClassificationsError.value = err?.response?.data?.error || err?.message || '读取AI环节分类失败。'
  } finally {
    if (requestId === contextRequestId) flowClassificationsLoading.value = false
  }
}

const formatFlowClassificationSource = (source) => {
  const labels = {
    ai: 'AI分类',
    manual: '人工调整',
    fallback: '系统兜底',
    pending: '等待AI分类'
  }
  return labels[source] || '等待AI分类'
}

const openFlowClassificationDialog = () => {
  flowClassificationDrafts.value = Object.fromEntries(
    flowClassifications.value.map((item) => [item.issue_id, item.effective_category || ''])
  )
  flowClassificationKeyword.value = ''
  flowClassificationCategoryFilter.value = ''
  flowClassificationMessage.value = ''
  flowClassificationDialogVisible.value = true
}

const closeFlowClassificationDialog = () => {
  flowClassificationDialogVisible.value = false
}

const saveFlowClassificationAdjustments = async () => {
  if (!canManageQualityReportSelectionRules.value || flowClassificationsSaving.value) return
  const classifications = visibleFlowClassifications.value
    .filter((item) => (
      String(flowClassificationDrafts.value[item.issue_id] || '')
        !== String(item.effective_category || '')
    ))
    .map((item) => ({
      issue_id: item.issue_id,
      category: flowClassificationDrafts.value[item.issue_id]
    }))
    .filter((item) => item.category)
  if (!classifications.length) return
  flowClassificationsSaving.value = true
  flowClassificationsError.value = ''
  flowClassificationMessage.value = ''
  try {
    const response = await axios.put('/api/inspection-reports/quality-flow-classifications', {
      month: selectedMonth.value,
      date_from: reportDateFrom.value,
      date_to: reportDateTo.value,
      classifications
    })
    if (!response.data?.success) throw new Error(response.data?.error || '保存环节分类失败。')
    flowClassifications.value = Array.isArray(response.data.classifications)
      ? response.data.classifications
      : flowClassifications.value
    flowClassificationCategories.value = Array.isArray(response.data.business_flows)
      ? response.data.business_flows
      : flowClassificationCategories.value
    flowClassificationDrafts.value = Object.fromEntries(
      flowClassifications.value.map((item) => [item.issue_id, item.effective_category || ''])
    )
    closeFlowClassificationDialog()
    flowClassificationMessage.value = '分类已保存。历史报告保持原快照，新报告将使用本次调整。'
  } catch (err) {
    flowClassificationsError.value = err?.response?.data?.error || err?.message || '保存环节分类失败。'
  } finally {
    flowClassificationsSaving.value = false
  }
}

const resetNonOilIssueLibraryState = () => {
  nonOilIssueLibraryRequestId += 1
  nonOilIssueLibrary.value = []
  nonOilIssueCategories.value = []
  nonOilIssueLibraryError.value = ''
  nonOilIssueLibraryDialogVisible.value = false
  nonOilIssueSelectionDraftIds.value = []
  nonOilIssueLibraryCategory.value = ''
  nonOilIssueLibraryKeyword.value = ''
  nonOilIssueLibrarySelectionFilter.value = ''
}

const loadNonOilIssueLibrary = async (requestId = contextRequestId) => {
  if (!isNonOilReport.value || !nonOilDateFrom.value || !nonOilDateTo.value) {
    if (!isNonOilReport.value) resetNonOilIssueLibraryState()
    return
  }
  const libraryRequestId = ++nonOilIssueLibraryRequestId
  nonOilIssueLibraryLoading.value = true
  nonOilIssueLibraryError.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/non-oil-issue-selection', {
      params: {
        month: selectedMonth.value,
        date_from: nonOilDateFrom.value,
        date_to: nonOilDateTo.value,
        snapshot_id: selectedSnapshotId.value || undefined
      }
    })
    if (requestId !== contextRequestId || libraryRequestId !== nonOilIssueLibraryRequestId) return
    if (!response.data?.success) throw new Error(response.data?.error || '读取非油报告问题库失败。')
    nonOilIssueLibrary.value = Array.isArray(response.data.issues) ? response.data.issues : []
    nonOilIssueCategories.value = Array.isArray(response.data.categories) ? response.data.categories : []
    nonOilIssueSelectionDraftIds.value = nonOilIssueLibrary.value
      .filter((item) => item.included)
      .map((item) => Number(item.issue_id))
  } catch (err) {
    if (requestId !== contextRequestId || libraryRequestId !== nonOilIssueLibraryRequestId) return
    nonOilIssueLibrary.value = []
    nonOilIssueCategories.value = []
    nonOilIssueSelectionDraftIds.value = []
    nonOilIssueLibraryError.value = err?.response?.data?.error || err?.message || '读取非油报告问题库失败。'
  } finally {
    if (requestId === contextRequestId && libraryRequestId === nonOilIssueLibraryRequestId) {
      nonOilIssueLibraryLoading.value = false
    }
  }
}

const openNonOilIssueLibraryDialog = async () => {
  nonOilIssueLibraryCategory.value = ''
  nonOilIssueLibraryKeyword.value = ''
  nonOilIssueLibrarySelectionFilter.value = ''
  nonOilIssueLibraryDialogVisible.value = true
  if (!selectedSnapshotId.value) await loadNonOilIssueLibrary(contextRequestId)
}

const closeNonOilIssueLibraryDialog = () => {
  nonOilIssueLibraryDialogVisible.value = false
}

const isNonOilIssueSelected = (issueId) => (
  nonOilIssueSelectionDraftSet.value.has(Number(issueId))
)

const toggleNonOilIssueSelection = (issueId, selected) => {
  const next = new Set(nonOilIssueSelectionDraftIds.value.map(Number))
  if (selected) next.add(Number(issueId))
  else next.delete(Number(issueId))
  nonOilIssueSelectionDraftIds.value = [...next].sort((a, b) => a - b)
}

const selectedNonOilIssueCountForCategory = (categoryName) => (
  nonOilIssueLibrary.value.filter((item) => (
    (!categoryName || item.category_name === categoryName)
    && isNonOilIssueSelected(item.issue_id)
  )).length
)

const selectVisibleNonOilIssues = (selected) => {
  const targetIds = nonOilIssueLibrary.value
    .filter((item) => !nonOilIssueLibraryCategory.value || item.category_name === nonOilIssueLibraryCategory.value)
    .map((item) => Number(item.issue_id))
  const next = new Set(nonOilIssueSelectionDraftIds.value.map(Number))
  targetIds.forEach((issueId) => {
    if (selected) next.add(issueId)
    else next.delete(issueId)
  })
  nonOilIssueSelectionDraftIds.value = [...next].sort((a, b) => a - b)
}

const selectAllNonOilIssues = () => {
  nonOilIssueSelectionDraftIds.value = nonOilIssueLibrary.value
    .map((item) => Number(item.issue_id))
    .sort((a, b) => a - b)
}

const saveNonOilIssueSelection = async () => {
  if (nonOilIssueLibrarySaving.value) return
  nonOilIssueLibrarySaving.value = true
  nonOilIssueLibraryError.value = ''
  try {
    const selectedIds = new Set(nonOilIssueSelectionDraftIds.value.map(Number))
    const excludedIssueIds = nonOilIssueLibrary.value
      .map((item) => Number(item.issue_id))
      .filter((issueId) => !selectedIds.has(issueId))
    const response = await axios.put('/api/inspection-reports/non-oil-issue-selection', {
      month: selectedMonth.value,
      date_from: nonOilDateFrom.value,
      date_to: nonOilDateTo.value,
      excluded_issue_ids: excludedIssueIds
    })
    if (!response.data?.success) throw new Error(response.data?.error || '保存报告问题选择失败。')
    nonOilIssueLibrary.value = Array.isArray(response.data.issues) ? response.data.issues : []
    nonOilIssueCategories.value = Array.isArray(response.data.categories) ? response.data.categories : []
    nonOilIssueSelectionDraftIds.value = nonOilIssueLibrary.value
      .filter((item) => item.included)
      .map((item) => Number(item.issue_id))
    closeNonOilIssueLibraryDialog()
  } catch (err) {
    nonOilIssueLibraryError.value = err?.response?.data?.error || err?.message || '保存报告问题选择失败。'
  } finally {
    nonOilIssueLibrarySaving.value = false
  }
}

const resetNonOilClassificationState = () => {
  nonOilClassifications.value = []
  nonOilClassificationCategories.value = []
  nonOilClassificationsError.value = ''
  nonOilClassificationDialogVisible.value = false
  nonOilClassificationDrafts.value = {}
  nonOilClassificationKeyword.value = ''
  nonOilClassificationFilter.value = ''
}

const loadNonOilClassifications = async (requestId = contextRequestId) => {
  if (!isNonOilReport.value) {
    resetNonOilClassificationState()
    return
  }
  nonOilClassificationsLoading.value = true
  nonOilClassificationsError.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/non-oil-category-classifications', {
      params: {
        month: selectedMonth.value,
        date_from: reportDateFrom.value,
        date_to: reportDateTo.value,
        snapshot_id: selectedSnapshotId.value || undefined
      }
    })
    if (requestId !== contextRequestId) return
    if (!response.data?.success) throw new Error(response.data?.error || '读取非油问题分类失败。')
    nonOilClassifications.value = Array.isArray(response.data.classifications) ? response.data.classifications : []
    nonOilClassificationCategories.value = Array.isArray(response.data.categories) ? response.data.categories : []
    nonOilClassificationDrafts.value = Object.fromEntries(
      nonOilClassifications.value.map((item) => [item.issue_id, item.effective_category || ''])
    )
  } catch (err) {
    if (requestId !== contextRequestId) return
    nonOilClassifications.value = []
    nonOilClassificationCategories.value = []
    nonOilClassificationsError.value = err?.response?.data?.error || err?.message || '读取非油问题分类失败。'
  } finally {
    if (requestId === contextRequestId) nonOilClassificationsLoading.value = false
  }
}

const openNonOilClassificationDialog = () => {
  nonOilClassificationDrafts.value = Object.fromEntries(
    nonOilClassifications.value.map((item) => [item.issue_id, item.effective_category || ''])
  )
  nonOilClassificationKeyword.value = ''
  nonOilClassificationFilter.value = ''
  nonOilClassificationDialogVisible.value = true
}

const closeNonOilClassificationDialog = () => {
  nonOilClassificationDialogVisible.value = false
}

const saveNonOilClassificationAdjustments = async () => {
  if (nonOilClassificationsSaving.value) return
  const classifications = nonOilClassifications.value
    .filter((item) => String(nonOilClassificationDrafts.value[item.issue_id] || '') !== String(item.effective_category || ''))
    .map((item) => ({ issue_id: item.issue_id, category: nonOilClassificationDrafts.value[item.issue_id] }))
    .filter((item) => item.category)
  if (!classifications.length) return
  nonOilClassificationsSaving.value = true
  nonOilClassificationsError.value = ''
  try {
    const response = await axios.put('/api/inspection-reports/non-oil-category-classifications', {
      month: selectedMonth.value,
      snapshot_id: selectedSnapshotId.value || undefined,
      classifications
    })
    if (!response.data?.success) throw new Error(response.data?.error || '保存非油问题分类失败。')
    closeNonOilClassificationDialog()
    await loadNonOilClassifications(contextRequestId)
  } catch (err) {
    nonOilClassificationsError.value = err?.response?.data?.error || err?.message || '保存非油问题分类失败。'
  } finally {
    nonOilClassificationsSaving.value = false
  }
}

const resetNonOilKeyClassificationState = () => {
  nonOilKeyClassifications.value = []
  nonOilKeyClassificationCategories.value = []
  nonOilKeyClassificationsError.value = ''
  nonOilKeyClassificationDialogVisible.value = false
  nonOilKeyClassificationDrafts.value = {}
  nonOilKeyClassificationKeyword.value = ''
  nonOilKeyClassificationFilter.value = ''
}

const loadNonOilKeyClassifications = async (requestId = contextRequestId) => {
  if (!isNonOilReport.value) {
    resetNonOilKeyClassificationState()
    return
  }
  nonOilKeyClassificationsLoading.value = true
  nonOilKeyClassificationsError.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/non-oil-key-issue-classifications', {
      params: {
        month: selectedMonth.value,
        date_from: reportDateFrom.value,
        date_to: reportDateTo.value,
        snapshot_id: selectedSnapshotId.value || undefined
      }
    })
    if (requestId !== contextRequestId) return
    if (!response.data?.success) throw new Error(response.data?.error || '读取重点问题分类失败。')
    nonOilKeyClassifications.value = Array.isArray(response.data.classifications) ? response.data.classifications : []
    nonOilKeyClassificationCategories.value = Array.isArray(response.data.categories) ? response.data.categories : []
    nonOilKeyClassificationDrafts.value = Object.fromEntries(
      nonOilKeyClassifications.value.map((item) => [item.issue_id, item.effective_category || '不纳入重点问题'])
    )
  } catch (err) {
    if (requestId !== contextRequestId) return
    nonOilKeyClassifications.value = []
    nonOilKeyClassificationCategories.value = []
    nonOilKeyClassificationsError.value = err?.response?.data?.error || err?.message || '读取重点问题分类失败。'
  } finally {
    if (requestId === contextRequestId) nonOilKeyClassificationsLoading.value = false
  }
}

const openNonOilKeyClassificationDialog = () => {
  nonOilKeyClassificationDrafts.value = Object.fromEntries(
    nonOilKeyClassifications.value.map((item) => [item.issue_id, item.effective_category || '不纳入重点问题'])
  )
  nonOilKeyClassificationKeyword.value = ''
  nonOilKeyClassificationFilter.value = ''
  nonOilKeyClassificationDialogVisible.value = true
}

const closeNonOilKeyClassificationDialog = () => {
  nonOilKeyClassificationDialogVisible.value = false
}

const saveNonOilKeyClassificationAdjustments = async () => {
  if (nonOilKeyClassificationsSaving.value) return
  const classifications = nonOilKeyClassifications.value
    .filter((item) => String(nonOilKeyClassificationDrafts.value[item.issue_id] || '') !== String(item.effective_category || ''))
    .map((item) => ({ issue_id: item.issue_id, category: nonOilKeyClassificationDrafts.value[item.issue_id] }))
    .filter((item) => item.category)
  if (!classifications.length) return
  nonOilKeyClassificationsSaving.value = true
  nonOilKeyClassificationsError.value = ''
  try {
    const response = await axios.put('/api/inspection-reports/non-oil-key-issue-classifications', {
      month: selectedMonth.value,
      snapshot_id: selectedSnapshotId.value || undefined,
      classifications
    })
    if (!response.data?.success) throw new Error(response.data?.error || '保存重点问题分类失败。')
    closeNonOilKeyClassificationDialog()
    await loadNonOilKeyClassifications(contextRequestId)
  } catch (err) {
    nonOilKeyClassificationsError.value = err?.response?.data?.error || err?.message || '保存重点问题分类失败。'
  } finally {
    nonOilKeyClassificationsSaving.value = false
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
  if (!isQualityMeasurementReport.value) {
    sourceStations.value = []
    sourceSelectionMode.value = 'all'
    selectedSourceStationIds.value = []
    sourceLoading.value = false
    sourceError.value = ''
    return
  }
  sourceLoading.value = true
  sourceError.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/source-options', {
      params: {
        report_type: selectedReportType.value,
        month: selectedMonth.value,
        date_from: reportDateFrom.value,
        date_to: reportDateTo.value
      }
    })
    if (requestId !== contextRequestId) return
    if (!response.data?.success) {
      throw new Error(response.data?.error || '读取报告数据来源失败。')
    }
    sourceStations.value = Array.isArray(response.data?.stations) ? response.data.stations : []
    canManageQualityReportSource.value = Boolean(response.data?.can_edit)
    const persistedSelection = response.data?.saved_selection || {}
    sourceSelectionMeta.value = {
      updated_at: savedSelection?.updated_at || persistedSelection.updated_at || '',
      updated_by_name: savedSelection?.updated_by_name || persistedSelection.updated_by_name || ''
    }
    const effectiveSelection = Object.keys(savedSelection || {}).length
      ? savedSelection
      : persistedSelection
    syncSourceSelection(effectiveSelection, jobOptions)
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

const openSourceDialog = (mode = 'saved') => {
  if (!isQualityMeasurementReport.value) return
  sourceDialogMode.value = mode === 'historical' ? 'historical' : 'saved'
  const historicalMode = historicalSourceSelection.value.mode === 'custom' ? 'custom' : 'all'
  const initialMode = sourceDialogMode.value === 'historical'
    ? historicalMode
    : sourceSelectionMode.value
  const initialIds = sourceDialogMode.value === 'historical'
    ? historicalSourceSelection.value.station_ids
    : selectedSourceStationIds.value
  sourceDraftMode.value = initialMode
  sourceDraftIds.value = initialMode === 'custom'
    ? normalizeSourceIds(initialIds)
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
  if (!canManageQualityReportSource.value) return
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
  if (!canManageQualityReportSource.value || sourceDraftMode.value !== 'custom') return
  const targetId = Number(stationId)
  const selectedIds = new Set(sourceDraftIds.value.map(Number))
  if (selectedIds.has(targetId)) selectedIds.delete(targetId)
  else selectedIds.add(targetId)
  sourceDraftIds.value = [...selectedIds].sort((a, b) => a - b)
}

const selectVisibleSourceStations = () => {
  if (!canManageQualityReportSource.value) return
  const selectedIds = new Set(sourceDraftIds.value.map(Number))
  filteredSourceStations.value.forEach((item) => selectedIds.add(Number(item.station_id)))
  sourceDraftIds.value = [...selectedIds].sort((a, b) => a - b)
}

const invertVisibleSourceStations = () => {
  if (!canManageQualityReportSource.value) return
  const selectedIds = new Set(sourceDraftIds.value.map(Number))
  filteredSourceStations.value.forEach((item) => {
    const stationId = Number(item.station_id)
    if (selectedIds.has(stationId)) selectedIds.delete(stationId)
    else selectedIds.add(stationId)
  })
  sourceDraftIds.value = [...selectedIds].sort((a, b) => a - b)
}

const applySourceSelection = async () => {
  if (!canManageQualityReportSource.value) {
    closeSourceDialog()
    return
  }
  if (sourceDraftMode.value === 'custom' && !sourceDraftIds.value.length) return
  sourceSelectionMode.value = sourceDraftMode.value
  selectedSourceStationIds.value = sourceDraftMode.value === 'custom'
    ? normalizeSourceIds(sourceDraftIds.value)
    : []
  sourceError.value = ''
  try {
    const response = await axios.put('/api/inspection-reports/source-options', {
      report_type: selectedReportType.value,
      month: selectedMonth.value,
      date_from: reportDateFrom.value,
      date_to: reportDateTo.value,
      selection_mode: sourceSelectionMode.value,
      station_ids: selectedSourceStationIds.value
    })
    if (!response.data?.success) throw new Error(response.data?.error || '保存数据来源失败。')
    const savedSelection = response.data.saved_selection || {}
    sourceSelectionMeta.value = {
      updated_at: savedSelection.updated_at || '',
      updated_by_name: savedSelection.updated_by_name || ''
    }
    sourceDialogMode.value = 'saved'
    closeSourceDialog()
  } catch (err) {
    sourceError.value = err?.response?.data?.error || err?.message || '保存数据来源失败。'
  }
}

const clearExportPolling = () => {
  if (exportPollTimer) {
    window.clearTimeout(exportPollTimer)
    exportPollTimer = null
  }
}

const syncSelectedMonthFromDateRange = () => {
  const monthValue = String(reportDateTo.value || reportDateFrom.value || '').slice(0, 7)
  if (/^\d{4}-\d{2}$/.test(monthValue)) selectedMonth.value = monthValue
}

const buildIssueLibraryCategoryStats = (issues = []) => {
  const groups = new Map()
  issues.forEach((item) => {
    const name = item.category_name || '未分类'
    const current = groups.get(name) || {
      name,
      display_name: item.category_display_name || name,
      total_count: 0,
      included_count: 0
    }
    current.total_count += 1
    if (item.included) current.included_count += 1
    groups.set(name, current)
  })
  return [...groups.values()]
}

const applyHistoricalGenerationContext = (reportPayload = {}) => {
  const context = reportPayload.generation_context || {}
  if (isQualityMeasurementReport.value && Array.isArray(context.flow_classifications)) {
    flowClassifications.value = context.flow_classifications
    flowClassificationCategories.value = Array.isArray(context.flow_categories) && context.flow_categories.length
      ? context.flow_categories
      : [...new Set(context.flow_classifications.map((item) => item.effective_category).filter(Boolean))]
    flowClassificationDrafts.value = Object.fromEntries(
      flowClassifications.value.map((item) => [item.issue_id, item.effective_category || ''])
    )
  }
  if (!isNonOilReport.value) return
  if (Array.isArray(context.issue_library) && context.issue_library.length) {
    nonOilIssueLibrary.value = context.issue_library
    nonOilIssueCategories.value = buildIssueLibraryCategoryStats(context.issue_library)
    nonOilIssueSelectionDraftIds.value = context.issue_library
      .filter((item) => item.included)
      .map((item) => Number(item.issue_id))
  }
  nonOilClassifications.value = Array.isArray(context.category_classifications)
    ? context.category_classifications
    : []
  nonOilClassificationCategories.value = Array.isArray(context.non_oil_categories)
    ? context.non_oil_categories
    : [...new Set(nonOilClassifications.value.map((item) => item.effective_category).filter(Boolean))]
  nonOilClassificationDrafts.value = Object.fromEntries(
    nonOilClassifications.value.map((item) => [item.issue_id, item.effective_category || ''])
  )
  nonOilKeyClassifications.value = Array.isArray(context.key_issue_classifications)
    ? context.key_issue_classifications
    : []
  nonOilKeyClassificationCategories.value = Array.isArray(context.non_oil_key_issue_options)
    ? context.non_oil_key_issue_options
    : [...new Set(nonOilKeyClassifications.value.map((item) => item.effective_category).filter(Boolean))]
  nonOilKeyClassificationDrafts.value = Object.fromEntries(
    nonOilKeyClassifications.value.map((item) => [item.issue_id, item.effective_category || '不纳入重点问题'])
  )
}

const refreshReportHistory = async () => {
  const response = await axios.get('/api/inspection-reports/history', {
    params: { report_type: selectedReportType.value }
  })
  if (response.data?.success) {
    reportHistory.value = Array.isArray(response.data.history) ? response.data.history : []
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
        month: selectedMonth.value,
        snapshot_id: selectedSnapshotId.value
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
      month: selectedMonth.value,
      snapshot_id: selectedSnapshotId.value
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
      if (response.data?.report) {
        report.value = response.data.report
        selectedSnapshotId.value = Number(response.data.report?.snapshot?.id || 0)
        reportDateFrom.value = response.data.report?.snapshot?.date_from || reportDateFrom.value
        reportDateTo.value = response.data.report?.snapshot?.date_to || reportDateTo.value
        applyHistoricalGenerationContext(response.data.report)
        activeQualitySlideIndex.value = 0
      }
      await refreshReportHistory()
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
  if (!validReportDateRange.value || templateUnavailable.value || !canGenerateReports.value) return
  syncSelectedMonthFromDateRange()
  selectedSnapshotId.value = 0
  const requestId = ++contextRequestId
  clearPolling()
  loading.value = true
  error.value = ''
  activeJob.value = {
    progress: 3,
    stage_message: '正在向后台提交 AI 报告生成任务'
  }
  try {
    const payload = {
      report_type: selectedReportType.value,
      month: selectedMonth.value,
      force: options?.force === true,
      generation_options: {
        date_from: reportDateFrom.value,
        date_to: reportDateTo.value
      }
    }
    if (isQualityMeasurementReport.value) {
      payload.generation_options = {
        ...payload.generation_options,
        station_filter_enabled: sourceSelectionMode.value === 'custom',
        station_ids: sourceSelectionMode.value === 'custom'
          ? selectedSourceStationIds.value
          : []
      }
    }
    const response = await axios.post('/api/inspection-reports/generate', payload)
    if (requestId !== contextRequestId) return
    if (!response.data?.success) {
      throw new Error(response.data?.error || 'AI报告生成任务提交失败。')
    }
    if (response.data?.report && !response.data?.job) {
      report.value = response.data.report
      selectedSnapshotId.value = Number(response.data.report?.snapshot?.id || 0)
      applyHistoricalGenerationContext(response.data.report)
      activeQualitySlideIndex.value = 0
      activeJob.value = null
      loading.value = false
      await refreshReportHistory()
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

const loadReportState = async (snapshotId = selectedSnapshotId.value) => {
  const requestId = ++contextRequestId
  clearPolling()
  activeJob.value = null
  error.value = ''
  if (templateUnavailable.value) {
    report.value = createEmptyReport()
    sourceStations.value = []
    sourceSelectionMode.value = 'all'
    selectedSourceStationIds.value = []
    resetFlowClassificationState()
    resetNonOilIssueLibraryState()
    resetNonOilClassificationState()
    resetNonOilKeyClassificationState()
    loading.value = false
    return
  }
  loading.value = true
  try {
    const response = await axios.get('/api/inspection-reports/status', {
      params: {
        report_type: selectedReportType.value,
        month: selectedMonth.value,
        date_from: reportDateFrom.value,
        date_to: reportDateTo.value,
        snapshot_id: snapshotId || undefined
      }
    })
    if (requestId !== contextRequestId) return
    if (!response.data?.success) {
      throw new Error(response.data?.error || '读取报告状态失败。')
    }
    applyReportCapabilities(response.data)
    reportHistory.value = Array.isArray(response.data?.history) ? response.data.history : []
    if (!response.data?.report && !snapshotId && reportHistory.value.length) {
      loading.value = false
      await selectHistorySnapshot(reportHistory.value[0])
      return
    }
    report.value = response.data?.report || createEmptyReport()
    selectedSnapshotId.value = Number(report.value?.snapshot?.id || snapshotId || 0)
    if (report.value?.snapshot?.date_from) reportDateFrom.value = report.value.snapshot.date_from
    if (report.value?.snapshot?.date_to) reportDateTo.value = report.value.snapshot.date_to
    syncSelectedMonthFromDateRange()
    applyHistoricalGenerationContext(report.value)
    if (isQualityMeasurementReport.value) {
      await loadSourceOptions({}, {}, requestId)
      await loadSelectionSettings()
      if (!selectedSnapshotId.value) await loadFlowClassifications(requestId)
      resetNonOilIssueLibraryState()
      resetNonOilClassificationState()
      resetNonOilKeyClassificationState()
    } else if (isNonOilReport.value) {
      if (!selectedSnapshotId.value) {
        await loadNonOilIssueLibrary(requestId)
        await loadNonOilClassifications(requestId)
        await loadNonOilKeyClassifications(requestId)
      }
      sourceStations.value = []
      sourceSelectionMode.value = 'all'
      selectedSourceStationIds.value = []
      resetFlowClassificationState()
    } else {
      sourceStations.value = []
      sourceSelectionMode.value = 'all'
      selectedSourceStationIds.value = []
      resetFlowClassificationState()
      resetNonOilIssueLibraryState()
      resetNonOilClassificationState()
      resetNonOilKeyClassificationState()
    }
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

const selectHistorySnapshot = async (item) => {
  if (!item?.id || selectedSnapshotId.value === Number(item.id)) return
  closeExportDialog()
  exportTask.value = null
  exportError.value = ''
  selectedSnapshotId.value = Number(item.id)
  reportDateFrom.value = item.date_from
  reportDateTo.value = item.date_to
  syncSelectedMonthFromDateRange()
  activeQualitySlideIndex.value = 0
  await loadReportState(selectedSnapshotId.value)
}

const handleReportDateRangeChange = async () => {
  if (!canGenerateReports.value || !validReportDateRange.value) return
  syncSelectedMonthFromDateRange()
  closeExportDialog()
  selectedSnapshotId.value = 0
  report.value = createEmptyReport()
  exportTask.value = null
  exportError.value = ''
  activeQualitySlideIndex.value = 0
  if (isQualityMeasurementReport.value) {
    await loadSourceOptions({}, {}, contextRequestId)
    await loadFlowClassifications(contextRequestId)
  } else if (isNonOilReport.value) {
    await loadNonOilIssueLibrary(contextRequestId)
    await loadNonOilClassifications(contextRequestId)
    await loadNonOilKeyClassifications(contextRequestId)
  }
}

const selectReportType = async (reportType) => {
  if (selectedReportType.value === reportType) return
  closeExportDialog()
  exportTask.value = null
  exportError.value = ''
  selectedReportType.value = reportType
  selectedSnapshotId.value = 0
  reportHistory.value = []
  report.value = createEmptyReport()
  sourceStations.value = []
  sourceSelectionMode.value = 'all'
  selectedSourceStationIds.value = []
  resetFlowClassificationState()
  resetNonOilIssueLibraryState()
  resetNonOilClassificationState()
  resetNonOilKeyClassificationState()
  activeQualitySlideIndex.value = 0
  await loadReportState()
}

const loadReportTypes = async () => {
  try {
    const response = await axios.get('/api/inspection-reports/types')
    if (response.data?.success && Array.isArray(response.data.report_types) && response.data.report_types.length) {
      reportTypes.value = response.data.report_types
      applyReportCapabilities(response.data)
    }
  } catch {
    reportTypes.value = DEFAULT_REPORT_TYPES
  }
}

onMounted(async () => {
  window.addEventListener('keydown', handleQualitySlideKeydown)
  await loadReportTypes()
  await loadReportState()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleQualitySlideKeydown)
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

.report-month-control input:disabled {
  cursor: not-allowed;
  color: #64748b;
  background: #cbd5e1;
  opacity: 0.82;
}

.report-month-control .report-month-custom-note {
  color: #fde68a;
  font-size: 11px;
  line-height: 1.55;
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

.report-period-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: 18px;
  padding: 20px;
  border-radius: 24px;
  background:
    radial-gradient(circle at 8% 8%, rgba(14, 165, 233, 0.12), transparent 34%),
    linear-gradient(145deg, #f8fbfd, #ffffff 58%, #f3f8fb);
}

.report-period-editor,
.report-history-panel {
  min-width: 0;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 19px;
  background: rgba(255, 255, 255, 0.9);
}

.report-period-editor {
  padding: 18px;
}

.period-editor-title > span,
.report-history-title > div > span {
  color: #0284c7;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.15em;
}

.period-editor-title h3,
.report-history-title h3 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 17px;
}

.period-editor-title p {
  margin: 7px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.55;
}

.period-editor-fields {
  display: grid;
  grid-template-columns: minmax(145px, 1fr) auto minmax(145px, 1fr) auto;
  align-items: end;
  gap: 10px;
  margin-top: 16px;
}

.period-editor-fields label {
  display: grid;
  gap: 7px;
}

.period-editor-fields label > span {
  color: #475569;
  font-size: 11px;
  font-weight: 850;
}

.period-editor-fields input {
  width: 100%;
  min-width: 0;
  height: 42px;
  box-sizing: border-box;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 0 11px;
  color: #0f172a;
  background: #ffffff;
  font: inherit;
  font-weight: 750;
}

.period-editor-fields input:disabled {
  color: #475569;
  background: #f1f5f9;
  cursor: not-allowed;
}

.period-editor-fields > i {
  align-self: center;
  margin-top: 18px;
  color: #94a3b8;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.period-generate-btn {
  height: 42px;
  border: 0;
  border-radius: 12px;
  padding: 0 16px;
  color: #ffffff;
  background: linear-gradient(135deg, #0369a1, #0891b2);
  box-shadow: 0 10px 20px rgba(3, 105, 161, 0.18);
  font-weight: 900;
  white-space: nowrap;
  cursor: pointer;
}

.period-generate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.period-readonly-note {
  display: block;
  margin-top: 12px;
  color: #64748b;
  font-size: 11px;
}

.report-history-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.report-history-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 15px 16px 12px;
  border-bottom: 1px solid #e2e8f0;
}

.report-history-title > strong {
  min-width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  color: #0369a1;
  background: #e0f2fe;
  font-size: 14px;
}

.report-history-list {
  display: grid;
  gap: 7px;
  max-height: 156px;
  overflow-y: auto;
  padding: 10px;
}

.report-history-item {
  min-width: 0;
  display: grid;
  gap: 3px;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 12px;
  color: #334155;
  background: #f8fafc;
  text-align: left;
  cursor: pointer;
}

.report-history-item:hover,
.report-history-item.active {
  border-color: #7dd3fc;
  background: #f0f9ff;
}

.report-history-item.active {
  box-shadow: inset 3px 0 0 #0284c7;
}

.report-history-item > span {
  overflow: hidden;
  font-size: 13px;
  font-weight: 850;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.report-history-item > small {
  color: #64748b;
  font-size: 10px;
}

.report-history-empty {
  flex: 1;
  display: grid;
  place-items: center;
  min-height: 98px;
  padding: 18px;
  color: #94a3b8;
  font-size: 12px;
  text-align: center;
}

.source-last-saved {
  display: block;
  margin-top: 8px;
  color: #0f766e;
  font-size: 11px;
  line-height: 1.5;
}

.source-last-saved.compact {
  max-width: 260px;
  margin: 0;
  color: #64748b;
  text-align: right;
}

.historical-config-note {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: min(100%, 620px);
  margin-top: 10px;
  padding: 9px 11px;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.9);
}

.historical-config-note div,
.historical-config-note span,
.historical-config-note strong,
.historical-config-note small {
  display: block;
}

.historical-config-note span,
.historical-config-note small {
  color: #64748b;
  font-size: 10px;
}

.historical-config-note strong {
  margin: 2px 0;
  color: #334155;
  font-size: 12px;
}

.historical-config-note button,
.historical-rule-btn {
  flex: 0 0 auto;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid #cbd5e1;
  border-radius: 9px;
  color: #334155;
  background: #fff;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
}

.historical-config-note button:hover,
.historical-rule-btn:hover {
  border-color: #38bdf8;
  color: #0369a1;
  background: #f0f9ff;
}

.historical-rule-btn {
  grid-column: 1 / -1;
  justify-self: end;
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
.selection-configure-btn,
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

.selection-configure-btn {
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  background: #eff6ff;
}

.source-apply-generate-btn {
  border: 1px solid #0f766e;
  color: #ffffff;
  background: #0f766e;
}

.source-configure-btn:disabled,
.selection-configure-btn:disabled,
.source-apply-generate-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.non-oil-source-panel {
  display: grid;
  grid-template-columns: minmax(360px, 1.35fr) minmax(360px, 0.9fr) auto;
  align-items: center;
  gap: 20px;
  padding: 20px 24px;
  border: 1px solid rgba(13, 148, 136, 0.2);
  border-radius: 24px;
  background:
    radial-gradient(circle at 92% 0%, rgba(20, 184, 166, 0.13), transparent 34%),
    linear-gradient(135deg, #f5fffd, #ffffff 60%, #ecfdf5);
}

.classification-ai-mark.date-mark {
  background: linear-gradient(145deg, #0f766e, #14b8a6);
  box-shadow: 0 12px 24px rgba(13, 148, 136, 0.2);
}

.non-oil-key-panel {
  border-color: rgba(217, 119, 6, 0.22);
  background:
    radial-gradient(circle at 92% 0%, rgba(251, 191, 36, 0.16), transparent 34%),
    linear-gradient(135deg, #fffdf7, #ffffff 58%, #fff7ed);
}

.classification-ai-mark.key-mark {
  background: linear-gradient(145deg, #b45309, #f59e0b);
  box-shadow: 0 12px 24px rgba(217, 119, 6, 0.2);
}

.non-oil-issue-library-panel {
  border-color: rgba(8, 145, 178, 0.24);
  background:
    radial-gradient(circle at 92% 0%, rgba(34, 211, 238, 0.14), transparent 34%),
    linear-gradient(135deg, #f3fcff, #ffffff 58%, #ecfeff);
}

.classification-ai-mark.library-mark {
  background: linear-gradient(145deg, #0e7490, #06b6d4);
  box-shadow: 0 12px 24px rgba(8, 145, 178, 0.22);
}

.non-oil-issue-library-panel .classification-panel-intro > div:last-child > span {
  color: #0e7490;
}

.non-oil-issue-library-panel .classification-panel-stats > div {
  border-color: #bae6fd;
}

.issue-library-preview span,
.issue-library-preview em {
  color: #155e75;
  background: #cffafe;
}

.issue-library-manage-btn {
  border-color: #67e8f9;
  color: #0e7490;
  background: #ecfeff;
}

.non-oil-key-panel .classification-panel-intro > div:last-child > span {
  color: #b45309;
}

.non-oil-key-panel .classification-panel-stats > div {
  border-color: #fde68a;
}

.non-oil-key-panel .classification-panel-preview span,
.non-oil-key-panel .classification-panel-preview em {
  color: #92400e;
  background: #fef3c7;
}

.non-oil-date-fields {
  display: grid;
  grid-template-columns: minmax(145px, 1fr) auto minmax(145px, 1fr);
  align-items: end;
  gap: 10px;
}

.non-oil-date-fields label {
  display: grid;
  gap: 6px;
}

.non-oil-date-fields label span {
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
}

.non-oil-date-fields input {
  width: 100%;
  min-width: 0;
  height: 42px;
  box-sizing: border-box;
  padding: 0 12px;
  border: 1px solid #99f6e4;
  border-radius: 12px;
  color: #0f172a;
  background: rgba(255, 255, 255, 0.9);
  font: inherit;
}

.non-oil-date-fields > i {
  padding-bottom: 12px;
  color: #0f766e;
  font-size: 12px;
  font-style: normal;
  font-weight: 900;
}

.non-oil-custom-range-note {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid #fcd34d;
  border-radius: 11px;
  color: #92400e;
  background: #fffbeb;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.45;
}

.non-oil-custom-range-note button {
  flex: 0 0 auto;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid #f59e0b;
  border-radius: 9px;
  color: #92400e;
  background: #ffffff;
  font: inherit;
  font-weight: 900;
  cursor: pointer;
}

.quality-classification-panel {
  display: grid;
  grid-template-columns: minmax(360px, 1.2fr) minmax(320px, 0.9fr) auto;
  align-items: center;
  gap: 18px;
  padding: 20px 24px;
  border-radius: 24px;
  border-color: rgba(37, 99, 235, 0.2);
  background:
    radial-gradient(circle at 92% 0%, rgba(59, 130, 246, 0.13), transparent 34%),
    linear-gradient(135deg, #f8fbff, #ffffff 58%, #eff6ff);
}

.classification-panel-intro {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  min-width: 0;
}

.classification-ai-mark {
  display: grid;
  place-items: center;
  width: 50px;
  height: 50px;
  flex: 0 0 50px;
  border-radius: 17px;
  color: #ffffff;
  background: linear-gradient(145deg, #1d4ed8, #0ea5e9);
  box-shadow: 0 12px 24px rgba(37, 99, 235, 0.2);
  font-size: 16px;
  font-weight: 950;
  letter-spacing: 0.06em;
}

.classification-panel-intro > div:last-child > span {
  color: #2563eb;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.14em;
}

.classification-panel-intro h3 {
  margin: 3px 0 5px;
  color: #0f172a;
  font-size: 19px;
}

.classification-panel-intro p {
  margin: 0;
  color: #64748b;
  line-height: 1.55;
}

.classification-panel-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(68px, 1fr));
  gap: 7px;
}

.classification-panel-stats > div {
  padding: 9px 8px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  text-align: center;
  background: rgba(255, 255, 255, 0.78);
}

.classification-panel-stats > div.pending {
  border-color: #fed7aa;
  background: #fff7ed;
}

.classification-panel-stats span,
.classification-panel-stats strong {
  display: block;
}

.classification-panel-stats span {
  color: #64748b;
  font-size: 10px;
}

.classification-panel-stats strong {
  margin-top: 2px;
  color: #0f172a;
  font-size: 18px;
}

.classification-panel-preview {
  grid-column: 1 / 3;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-height: 28px;
}

.classification-panel-preview span,
.classification-panel-preview em {
  padding: 5px 8px;
  border-radius: 8px;
  color: #1e40af;
  background: #dbeafe;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
}

.classification-panel-preview > span:first-child:last-child,
.classification-panel-preview .classification-panel-error {
  color: #64748b;
  background: transparent;
  font-weight: 600;
}

.classification-panel-preview .classification-panel-error {
  color: #b91c1c;
}

.classification-manage-btn {
  grid-column: 3;
  grid-row: 1 / 3;
  min-height: 44px;
  padding: 0 16px;
  border: 1px solid #93c5fd;
  border-radius: 13px;
  color: #1d4ed8;
  background: #eff6ff;
  font-weight: 900;
  cursor: pointer;
}

.classification-manage-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.report-source-dialog-layer,
.report-selection-dialog-layer,
.flow-classification-dialog-layer {
  position: fixed;
  inset: 0;
  z-index: 15000;
  display: grid;
  place-items: center;
  padding: 34px;
  background: rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(8px);
}

.report-selection-dialog-layer {
  z-index: 15500;
}

.flow-classification-dialog-layer {
  z-index: 15600;
}

.flow-classification-dialog {
  position: relative;
  width: min(1180px, calc(100vw - 68px));
  max-height: min(900px, calc(100dvh - 56px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(147, 197, 253, 0.42);
  border-radius: 28px;
  background: #f8fafc;
  box-shadow: 0 38px 110px rgba(15, 23, 42, 0.34);
}

.non-oil-issue-library-layer {
  z-index: 15700;
}

.non-oil-issue-library-dialog {
  width: min(1320px, calc(100vw - 68px));
  height: calc(100dvh - 42px);
  max-height: min(930px, calc(100dvh - 42px));
  border-color: rgba(34, 211, 238, 0.42);
}

.issue-library-dialog-head {
  border-bottom-color: #bae6fd;
  background: radial-gradient(circle at 15% 0%, rgba(6, 182, 212, 0.16), transparent 42%), #ffffff;
}

.issue-library-dialog-head > div:first-child > span {
  color: #0e7490;
}

.issue-library-toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(160px, 0.34fr) auto;
  align-items: end;
  gap: 12px;
  padding: 14px 24px;
  border-bottom: 1px solid #dbeafe;
  background: #f8fafc;
}

.issue-library-toolbar label {
  min-width: 0;
  display: grid;
  gap: 5px;
}

.issue-library-toolbar label > span {
  color: #64748b;
  font-size: 10px;
  font-weight: 900;
}

.issue-library-toolbar input,
.issue-library-toolbar select {
  width: 100%;
  min-width: 0;
  height: 40px;
  box-sizing: border-box;
  padding: 0 11px;
  border: 1px solid #cbd5e1;
  border-radius: 11px;
  color: #0f172a;
  background: #ffffff;
  font: inherit;
}

.issue-library-batch-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 7px;
}

.issue-library-batch-actions button {
  min-height: 40px;
  padding: 0 11px;
  border: 1px solid #a5f3fc;
  border-radius: 10px;
  color: #0e7490;
  background: #ecfeff;
  font-size: 11px;
  font-weight: 900;
  cursor: pointer;
}

.issue-library-workspace {
  min-height: 260px;
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  overflow: hidden;
}

.issue-library-categories {
  overflow: auto;
  padding: 16px 12px;
  border-right: 1px solid #dbeafe;
  background: linear-gradient(180deg, #f0f9ff, #f8fafc);
}

.issue-library-categories button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 9px;
  padding: 10px 11px;
  border: 1px solid transparent;
  border-radius: 11px;
  color: #475569;
  background: transparent;
  text-align: left;
  font: inherit;
  cursor: pointer;
}

.issue-library-categories button + button {
  margin-top: 5px;
}

.issue-library-categories button.active {
  border-color: #67e8f9;
  color: #155e75;
  background: #ffffff;
  box-shadow: 0 8px 20px rgba(8, 145, 178, 0.1);
}

.issue-library-categories span {
  min-width: 0;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.35;
}

.issue-library-categories strong {
  flex: 0 0 auto;
  color: #0891b2;
  font-size: 11px;
}

.issue-library-list {
  overflow: auto;
  padding: 15px 18px 20px;
  background: #f8fafc;
}

.issue-library-list article {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 112px;
  align-items: center;
  gap: 13px;
  padding: 13px 14px;
  border: 1px solid #dbe3ec;
  border-radius: 15px;
  background: #ffffff;
  transition: border-color 0.16s ease, background 0.16s ease, opacity 0.16s ease;
}

.issue-library-list article + article {
  margin-top: 9px;
}

.issue-library-list article.selected {
  border-color: #a5f3fc;
  background: linear-gradient(100deg, #f0fdff, #ffffff 32%);
}

.issue-library-list article.excluded {
  opacity: 0.64;
  background: #f1f5f9;
}

.issue-library-checkbox {
  display: grid;
  place-items: center;
  cursor: pointer;
}

.issue-library-checkbox input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.issue-library-checkbox span {
  width: 23px;
  height: 23px;
  display: grid;
  place-items: center;
  border: 2px solid #94a3b8;
  border-radius: 8px;
  background: #ffffff;
}

.issue-library-checkbox input:checked + span {
  border-color: #0891b2;
  background: #0891b2;
}

.issue-library-checkbox input:checked + span::after {
  content: '';
  width: 8px;
  height: 4px;
  border-left: 2px solid #ffffff;
  border-bottom: 2px solid #ffffff;
  transform: translateY(-1px) rotate(-45deg);
}

.issue-library-checkbox input:disabled + span {
  cursor: not-allowed;
  opacity: 0.72;
}

.standard-detail-link {
  max-width: 210px;
  overflow: hidden;
  border: 0;
  border-bottom: 1px dashed #0284c7;
  padding: 0 0 1px;
  color: #0369a1;
  background: transparent;
  font: inherit;
  font-size: 11px;
  font-weight: 850;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.standard-detail-link:disabled {
  border-bottom-color: transparent;
  color: #94a3b8;
  cursor: default;
}

.issue-library-photo {
  width: 112px;
  height: 78px;
  position: relative;
  overflow: hidden;
  padding: 0;
  border: 1px solid #cbd5e1;
  border-radius: 11px;
  background: #e2e8f0;
  cursor: zoom-in;
}

.issue-library-photo img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.issue-library-photo span {
  position: absolute;
  right: 5px;
  bottom: 5px;
  padding: 3px 6px;
  border-radius: 7px;
  color: #ffffff;
  background: rgba(15, 23, 42, 0.76);
  font-size: 9px;
  font-weight: 800;
}

.issue-library-photo.empty {
  display: grid;
  place-items: center;
  color: #94a3b8;
  cursor: default;
  font-size: 11px;
  font-weight: 800;
}

.issue-library-dialog-footer {
  border-top-color: #bae6fd;
}

.classification-dialog-close {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 4;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 50%;
  color: #dc2626;
  background: rgba(254, 226, 226, 0.92);
  font-size: 29px;
  line-height: 1;
  cursor: pointer;
}

.classification-dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  padding: 24px 78px 20px 26px;
  border-bottom: 1px solid #dbeafe;
  background: radial-gradient(circle at 15% 0%, rgba(37, 99, 235, 0.15), transparent 40%), #ffffff;
}

.classification-dialog-head > div:first-child > span {
  color: #2563eb;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.15em;
}

.classification-dialog-head h3 {
  margin: 5px 0;
  color: #0f172a;
  font-size: 23px;
}

.classification-dialog-head p {
  margin: 0;
  color: #64748b;
}

.classification-dialog-head > div:last-child {
  min-width: 104px;
  padding: 10px 13px;
  border: 1px solid #bfdbfe;
  border-radius: 14px;
  text-align: center;
  background: #eff6ff;
}

.classification-dialog-head > div:last-child strong,
.classification-dialog-head > div:last-child span {
  display: block;
}

.classification-dialog-head > div:last-child strong {
  color: #1d4ed8;
  font-size: 23px;
}

.classification-dialog-head > div:last-child span {
  color: #64748b;
  font-size: 11px;
}

.classification-dialog-toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 220px;
  gap: 10px;
  padding: 14px 24px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}

.classification-dialog-toolbar label {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 9px;
  padding: 0 12px;
  border: 1px solid #dbe3ec;
  border-radius: 12px;
  background: #ffffff;
}

.classification-dialog-toolbar span {
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
}

.classification-dialog-toolbar input,
.classification-dialog-toolbar select {
  min-width: 0;
  height: 42px;
  border: 0;
  outline: 0;
  background: transparent;
}

.classification-dialog-message {
  margin: 12px 24px 0;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 800;
}

.classification-dialog-message.error { color: #b91c1c; background: #fee2e2; }
.classification-dialog-message.success { color: #166534; background: #dcfce7; }

.classification-dialog-list {
  min-height: 220px;
  flex: 1 1 auto;
  overflow: auto;
  padding: 16px 24px 22px;
}

.classification-dialog-list article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 330px;
  gap: 18px;
  padding: 15px 16px;
  border: 1px solid #dbe3ec;
  border-radius: 15px;
  background: #ffffff;
}

.classification-dialog-list article + article {
  margin-top: 10px;
}

.classification-issue-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.classification-issue-meta b,
.classification-issue-meta span {
  padding: 4px 7px;
  border-radius: 7px;
  color: #475569;
  background: #f1f5f9;
  font-size: 11px;
}

.classification-issue-meta b { color: #1d4ed8; background: #dbeafe; }

.classification-issue-main p {
  margin: 9px 0 5px;
  color: #0f172a;
  font-weight: 750;
  line-height: 1.55;
}

.classification-issue-main small {
  color: #64748b;
  line-height: 1.45;
}

.classification-result-compare {
  display: grid;
  grid-template-columns: 1fr 1.25fr auto;
  align-items: end;
  gap: 8px;
}

.classification-result-compare > div,
.classification-result-compare label {
  display: grid;
  gap: 5px;
}

.classification-result-compare span {
  color: #64748b;
  font-size: 10px;
  font-weight: 800;
}

.classification-result-compare strong,
.classification-result-compare select {
  min-height: 38px;
  padding: 8px 9px;
  box-sizing: border-box;
  border: 1px solid #dbe3ec;
  border-radius: 10px;
  color: #0f172a;
  background: #f8fafc;
  font-size: 12px;
}

.classification-result-compare em {
  align-self: center;
  padding: 5px 7px;
  border-radius: 999px;
  color: #1d4ed8;
  background: #dbeafe;
  font-size: 10px;
  font-style: normal;
  font-weight: 900;
  white-space: nowrap;
}

.classification-result-compare em.manual { color: #7c3aed; background: #ede9fe; }
.classification-result-compare em.fallback { color: #9a3412; background: #ffedd5; }
.classification-result-compare em.pending { color: #64748b; background: #e2e8f0; }

.classification-list-empty {
  display: grid;
  min-height: 180px;
  place-items: center;
  border: 1px dashed #bfdbfe;
  border-radius: 16px;
  color: #64748b;
  background: #ffffff;
}

.classification-dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 15px 24px 18px;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
}

.classification-dialog-footer p {
  margin: 0;
  color: #64748b;
  font-size: 12px;
}

.classification-dialog-footer > div {
  display: flex;
  gap: 8px;
}

.classification-cancel-btn,
.classification-save-btn {
  min-height: 42px;
  padding: 0 17px;
  border-radius: 12px;
  font-weight: 900;
  cursor: pointer;
}

.classification-cancel-btn { border: 1px solid #cbd5e1; color: #475569; background: #ffffff; }
.classification-save-btn { border: 1px solid #2563eb; color: #ffffff; background: #2563eb; }
.classification-save-btn:disabled { cursor: not-allowed; opacity: 0.48; }

.report-selection-dialog {
  position: relative;
  width: min(1180px, calc(100vw - 68px));
  max-height: min(900px, calc(100dvh - 56px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 28px;
  background: #f8fafc;
  box-shadow: 0 38px 110px rgba(15, 23, 42, 0.34);
}

.selection-dialog-close {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 4;
  width: 44px;
  height: 44px;
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #dc2626;
  background: rgba(254, 226, 226, 0.92);
  font-size: 29px;
  line-height: 1;
  cursor: pointer;
}

.selection-dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 24px 80px 20px 26px;
  border-bottom: 1px solid #e2e8f0;
  background:
    radial-gradient(circle at 14% 0%, rgba(37, 99, 235, 0.14), transparent 38%),
    #ffffff;
}

.selection-dialog-head > div:first-child > span {
  color: #2563eb;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.15em;
}

.selection-dialog-head h3 {
  margin: 5px 0;
  color: #0f172a;
  font-size: 23px;
}

.selection-dialog-head p {
  margin: 0;
  color: #64748b;
}

.selection-updated-meta {
  min-width: 150px;
  padding: 11px 14px;
  border: 1px solid #dbeafe;
  border-radius: 15px;
  text-align: right;
  background: #eff6ff;
}

.selection-updated-meta span,
.selection-updated-meta strong,
.selection-updated-meta small {
  display: block;
}

.selection-updated-meta span,
.selection-updated-meta small {
  color: #64748b;
  font-size: 11px;
}

.selection-updated-meta strong {
  margin: 3px 0;
  color: #1e3a8a;
  font-size: 14px;
}

.selection-settings-message {
  margin: 12px 24px 0;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 800;
}

.selection-settings-message.error {
  color: #b91c1c;
  background: #fee2e2;
}

.selection-settings-message.success {
  color: #047857;
  background: #d1fae5;
}

.selection-rule-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 16px 24px 12px;
}

.selection-rule-tabs button {
  min-width: 0;
  padding: 13px 15px;
  border: 1px solid #dbe4ee;
  border-radius: 15px;
  text-align: left;
  color: #475569;
  background: #ffffff;
  cursor: pointer;
}

.selection-rule-tabs button.active {
  border-color: #60a5fa;
  color: #1e3a8a;
  background: #eff6ff;
  box-shadow: inset 4px 0 #2563eb;
}

.selection-rule-tabs strong,
.selection-rule-tabs span {
  display: block;
}

.selection-rule-tabs strong {
  font-size: 14px;
}

.selection-rule-tabs span {
  margin-top: 4px;
  color: #64748b;
  font-size: 11px;
}

.selection-settings-loading {
  min-height: 320px;
  display: grid;
  place-items: center;
  color: #64748b;
}

.selection-sampling-section,
.selection-priority-section {
  padding: 6px 24px 14px;
}

.selection-priority-section {
  min-height: 0;
  overflow-y: auto;
}

.selection-section-title > div {
  display: flex;
  align-items: flex-start;
  gap: 11px;
}

.selection-section-title > div > span {
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: #ffffff;
  background: #2563eb;
  font-size: 11px;
  font-weight: 900;
}

.selection-section-title h4,
.selection-section-title p {
  margin: 0;
}

.selection-section-title h4 {
  color: #0f172a;
  font-size: 16px;
}

.selection-section-title p {
  margin-top: 3px;
  color: #64748b;
  font-size: 12px;
}

.selection-sampling-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.selection-sampling-grid label {
  padding: 11px 12px;
  border: 1px solid #dbe4ee;
  border-radius: 14px;
  background: #ffffff;
}

.selection-sampling-grid label > span {
  display: block;
  color: #475569;
  font-size: 11px;
  font-weight: 800;
}

.selection-sampling-grid label > div {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 7px;
}

.selection-sampling-grid input {
  width: 74px;
  height: 34px;
  box-sizing: border-box;
  border: 1px solid #bfdbfe;
  border-radius: 9px;
  text-align: center;
  color: #1e3a8a;
  font-weight: 900;
  background: #eff6ff;
}

.selection-sampling-grid em {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
}

.selection-flow-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  margin-top: 13px;
  padding-bottom: 3px;
}

.selection-flow-tabs button {
  flex: 0 0 auto;
  padding: 7px 11px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  color: #475569;
  background: #ffffff;
  font-weight: 800;
  cursor: pointer;
}

.selection-flow-tabs button.active {
  border-color: #2563eb;
  color: #ffffff;
  background: #2563eb;
}

.selection-standard-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(180px, 0.7fr);
  gap: 10px;
  margin-top: 12px;
}

.selection-standard-toolbar label {
  display: grid;
  gap: 5px;
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
}

.selection-standard-toolbar input,
.selection-standard-toolbar select {
  width: 100%;
  height: 40px;
  box-sizing: border-box;
  border: 1px solid #cbd5e1;
  border-radius: 11px;
  padding: 0 12px;
  color: #0f172a;
  background: #ffffff;
}

.selection-priority-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(0, 0.82fr);
  gap: 12px;
  margin-top: 12px;
}

.selection-standard-pool,
.selection-priority-list {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #dbe4ee;
  border-radius: 16px;
  background: #ffffff;
}

.selection-standard-pool > header,
.selection-priority-list > header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 13px;
  border-bottom: 1px solid #e2e8f0;
  color: #334155;
  background: #f8fafc;
}

.selection-standard-pool > header span,
.selection-priority-list > header span {
  color: #64748b;
  font-size: 11px;
}

.selection-standard-pool > div,
.selection-priority-list > div {
  max-height: 300px;
  overflow-y: auto;
  padding: 8px;
}

.selection-standard-pool > div > button,
.selection-priority-list article {
  width: 100%;
  min-width: 0;
  display: grid;
  align-items: center;
  gap: 9px;
  margin-bottom: 7px;
  padding: 9px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  text-align: left;
  background: #ffffff;
}

.selection-standard-pool > div > button {
  grid-template-columns: auto minmax(0, 1fr) auto;
  cursor: pointer;
}

.selection-standard-pool > div > button:disabled {
  cursor: default;
  opacity: 0.58;
}

.selection-standard-id,
.selection-rank {
  width: 38px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  color: #1d4ed8;
  background: #dbeafe;
  font-size: 11px;
  font-weight: 900;
}

.selection-standard-pool strong,
.selection-standard-pool small,
.selection-priority-list strong,
.selection-priority-list small {
  display: block;
  min-width: 0;
}

.selection-standard-pool small,
.selection-priority-list small {
  margin-top: 3px;
  overflow: hidden;
  color: #64748b;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.selection-standard-pool b {
  color: #2563eb;
  font-size: 11px;
}

.selection-priority-list article {
  grid-template-columns: auto minmax(0, 1fr) auto;
}

.selection-rank-actions {
  display: flex;
  gap: 4px;
}

.selection-rank-actions button {
  width: 29px;
  height: 29px;
  padding: 0;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  color: #334155;
  background: #ffffff;
  cursor: pointer;
}

.selection-rank-actions button.remove {
  color: #dc2626;
  border-color: #fecaca;
}

.selection-rank-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.35;
}

.selection-standard-pool p,
.selection-priority-list p {
  margin: 22px 10px;
  color: #94a3b8;
  text-align: center;
  font-size: 12px;
}

.selection-dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 24px 18px;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
}

.selection-dialog-footer p {
  margin: 0;
  color: #64748b;
  font-size: 11px;
}

.selection-dialog-footer > div {
  display: flex;
  gap: 9px;
}

.selection-cancel-btn,
.selection-save-btn {
  min-width: 112px;
  height: 40px;
  border-radius: 12px;
  font-weight: 900;
  cursor: pointer;
}

.selection-cancel-btn {
  border: 1px solid #cbd5e1;
  color: #475569;
  background: #ffffff;
}

.selection-save-btn {
  border: 1px solid #2563eb;
  color: #ffffff;
  background: #2563eb;
}

.selection-save-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
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

.quality-ppt-viewer {
  margin-top: 20px;
}

.quality-ppt-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
  padding: 15px 18px;
  border: 1px solid #dbe6ee;
  border-radius: 18px;
  background: #f6f9fb;
}

.quality-ppt-toolbar > div:first-child {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.quality-ppt-toolbar span {
  color: #1686bd;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.14em;
}

.quality-ppt-toolbar strong {
  color: #0f172a;
  font-size: 18px;
}

.quality-ppt-toolbar small {
  color: #64748b;
}

.quality-ppt-page-count {
  flex: 0 0 auto;
  padding: 9px 14px;
  border-radius: 12px;
  color: #ffffff;
  background: #125f8c;
  font-weight: 900;
}

.quality-ppt-stage {
  padding: 18px;
  border-radius: 22px;
  background: #dfe4e8;
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.08);
}

.non-oil-ppt-stage {
  display: grid;
  width: 100%;
  box-sizing: border-box;
  place-items: center;
  overflow: hidden;
}

.non-oil-ppt-stage > img {
  display: block;
  width: 100%;
  height: auto;
  aspect-ratio: 16 / 9;
  object-fit: contain;
  image-rendering: auto;
  background: #ffffff;
  box-shadow: 0 15px 38px rgba(15, 23, 42, 0.18);
}

.quality-ppt-slide {
  position: relative;
  overflow: hidden;
  width: 100%;
  aspect-ratio: 16 / 9;
  box-sizing: border-box;
  padding: 9.2% 4.5% 3.7%;
  color: #101820;
  background: #ffffff;
  box-shadow: 0 15px 38px rgba(15, 23, 42, 0.18);
}

.quality-slide-header {
  position: absolute;
  inset: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 12.5%;
  padding: 0 3.8% 0 4.6%;
  border-bottom: 5px solid #2a9bd3;
}

.quality-slide-header h2 {
  margin: 0;
  color: #05080b;
  font-size: clamp(20px, 2.25vw, 34px);
  font-weight: 950;
  letter-spacing: 0.02em;
}

.quality-slide-header h2 em {
  color: #3477c3;
  font-style: normal;
}

.quality-slide-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 60%;
}

.quality-slide-brand img {
  display: block;
  width: auto;
  height: 100%;
  object-fit: contain;
}

.quality-slide-page {
  position: absolute;
  right: 2.5%;
  bottom: 1.2%;
  color: #7b8790;
  font-size: clamp(7px, 0.7vw, 10px);
}

.tone-ink { color: #101820; }
.tone-blue { color: #3477c3; }
.tone-red { color: #ef1f24; }
.tone-muted { color: #64748b; }

.slide-cover,
.slide-agenda,
.slide-ending {
  padding: 0;
}

.quality-cover-logo {
  position: absolute;
  top: 3.2%;
  left: 2.5%;
  width: auto;
  height: 9.7%;
  object-fit: contain;
}

.quality-cover-title {
  position: absolute;
  top: 39%;
  right: 8%;
  left: 8%;
  margin: 0;
  color: #000000;
  font-size: clamp(23px, 3.5vw, 52px);
  font-weight: 950;
  line-height: 1.15;
  text-align: center;
}

.quality-cover-period {
  position: absolute;
  right: 36%;
  bottom: 14.5%;
  left: 36%;
  margin: 0;
  color: #000000;
  font-size: clamp(14px, 1.9vw, 28px);
  font-weight: 850;
  text-align: center;
}

.quality-agenda-rule {
  position: absolute;
  top: 11.7%;
  right: 0;
  left: 0;
  height: 0.7%;
  background: #2a9bd3;
}

.quality-agenda-logo {
  position: absolute;
  top: 3%;
  right: 3.1%;
  width: auto;
  height: 8.5%;
  object-fit: contain;
}

.quality-agenda-list {
  position: absolute;
  top: 27%;
  bottom: 20%;
  left: 35.2%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  color: #080808;
  font-size: clamp(18px, 2.25vw, 34px);
  font-weight: 950;
  line-height: 1;
}

.quality-agenda-list > div.active {
  color: #3477c3;
}

.quality-agenda-details {
  position: absolute;
  top: 33.7%;
  left: 56%;
  display: grid;
  grid-template-columns: 32px auto;
  grid-template-rows: repeat(2, auto);
  gap: 4.5vh 20px;
  font-size: clamp(12px, 1.42vw, 21px);
  font-weight: 850;
}

.quality-agenda-details i {
  grid-row: 1 / 3;
  width: 24px;
  border-top: 1px solid #111827;
  border-bottom: 1px solid #111827;
  border-left: 1px solid #111827;
}

.quality-ending-rule {
  position: absolute;
  top: 11.7%;
  right: 0;
  left: 0;
  height: 0.7%;
  background: #2a9bd3;
}

.quality-ending-corner-logo {
  position: absolute;
  top: 3%;
  right: 3.1%;
  width: auto;
  height: 8.5%;
  object-fit: contain;
}

.quality-ending-content {
  position: absolute;
  top: 41%;
  left: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8%;
  width: 20%;
  height: 28%;
  transform: translateX(-50%);
}

.quality-ending-content img {
  display: block;
  width: auto;
  height: 70%;
  object-fit: contain;
}

.quality-ending-content strong {
  color: #05080b;
  font-size: clamp(13px, 1.8vw, 26px);
  font-weight: 950;
  white-space: nowrap;
}

.quality-slide-narrative {
  margin: 0;
  color: #101820;
  font-size: clamp(10px, 1.38vw, 20px);
  font-weight: 700;
  line-height: 1.75;
  text-indent: 2em;
}

.overall-copy {
  position: absolute;
  top: 15.2%;
  right: 5.4%;
  left: 5.4%;
  min-height: 0;
  font-size: clamp(10px, 1.3vw, 19px);
  line-height: 1.62;
  text-indent: 2em;
}

.quality-slide-table-wrap {
  overflow: hidden;
  border: 1px solid #7490a5;
  background: #ffffff;
}

.quality-slide-table-wrap table {
  width: 100%;
  height: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.quality-slide-table-wrap th,
.quality-slide-table-wrap td {
  padding: 0.35em 0.42em;
  border: 1px solid #91a5b4;
  text-align: center;
  vertical-align: middle;
  font-size: clamp(7px, 0.88vw, 12px);
  line-height: 1.35;
}

.quality-slide-table-wrap th {
  color: #ffffff;
  background: #13528b;
  font-weight: 900;
}

.quality-slide-table-wrap tbody tr:nth-child(even) td {
  background: #f2f7fb;
}

.quality-slide-table-wrap tr.total td {
  color: #0f4e78;
  background: #e1f0f8;
  font-weight: 900;
}

.quality-slide-table-wrap td.align-left {
  text-align: left;
}

.overall-table {
  position: absolute;
  top: 39.8%;
  right: 8.4%;
  bottom: 8.7%;
  left: 8.4%;
  height: auto;
  margin: 0;
}

.overall-table th {
  color: #ffffff;
  background: #5b9bd5;
}

.overall-table tbody tr:nth-child(odd) td {
  background: #dce6f2;
}

.overall-table tbody tr:nth-child(even) td {
  background: #ebf1f8;
}

.overall-table th:nth-child(1) { width: 5%; }
.overall-table th:nth-child(2) { width: 15%; }

.quality-finding-layout {
  position: absolute;
  top: 16.2%;
  right: 5.6%;
  bottom: 9.5%;
  left: 5.8%;
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  gap: 4%;
  height: auto;
}

.quality-finding-copy {
  padding: 2.5% 0;
}

.quality-finding-copy p {
  margin: 0 0 1.2em;
  font-size: clamp(10px, 1.25vw, 18px);
  font-weight: 850;
  line-height: 1.7;
  white-space: pre-wrap;
}

.finding-table {
  height: 92%;
  align-self: start;
}

.finding-table th,
.prohibited-table th {
  color: #101820;
  background: #84d8e8;
}

.finding-table tbody tr td,
.prohibited-table tbody tr td,
.finding-table tbody tr:nth-child(even) td,
.prohibited-table tbody tr:nth-child(even) td {
  background: #ffffff;
}

.finding-table tr.oil-station-row td {
  color: #ef1f24;
}

.prohibited-copy {
  position: absolute;
  top: 24.8%;
  right: 5.2%;
  left: 5.2%;
  height: auto;
  text-indent: 0;
}

.quality-prohibited-band {
  position: absolute;
  top: 14.4%;
  right: 6.4%;
  left: 4.4%;
  display: flex;
  align-items: center;
  height: 7.5%;
  padding: 0 1.1%;
  color: #ffffff;
  background: #3477c3;
  box-shadow: 7px 7px 0 rgba(15, 23, 42, 0.2);
  font-size: clamp(12px, 1.85vw, 27px);
  font-weight: 950;
}

.prohibited-table {
  position: absolute;
  top: 33%;
  right: 6.3%;
  bottom: 9.2%;
  left: 4.4%;
  height: auto;
  margin: 0;
}

.prohibited-table th:nth-child(1) { width: 6%; }
.prohibited-table th:nth-child(2) { width: 13%; }
.prohibited-table th:nth-child(3) { width: 15%; }
.prohibited-table th:nth-child(4) { width: 54%; }

.quality-slide-band.quality-flow-band,
.quality-slide-band.quality-issue-band {
  position: absolute;
  top: 14.1%;
  right: 4.6%;
  left: 4.05%;
  display: flex;
  align-items: center;
  min-height: 0;
  height: 7.45%;
  box-sizing: border-box;
  margin: 0;
  padding: 0 1.2%;
  box-shadow: 7px 7px 0 rgba(15, 23, 42, 0.34);
  font-size: clamp(12px, 1.65vw, 24px);
}

.flow-copy {
  position: absolute;
  top: 25.1%;
  right: 6.4%;
  left: 6.4%;
  min-height: 0;
  font-size: clamp(9px, 1.17vw, 17px);
  line-height: 1.62;
  text-indent: 2em;
}

.quality-chart-heading {
  position: absolute;
  top: 40.3%;
  right: 30%;
  left: 30%;
  margin: 0;
  text-align: center;
  font-size: clamp(10px, 1.35vw, 20px);
}

.quality-ppt-chart {
  position: absolute;
  top: 46.4%;
  right: 18%;
  bottom: 8.8%;
  left: 18%;
  display: flex;
  align-items: stretch;
  justify-content: center;
  gap: 3%;
  height: auto;
  padding: 0 4%;
  border-bottom: 1px solid #94a3b8;
  background: repeating-linear-gradient(to top, transparent 0, transparent 24.5%, #d9e0e5 25%);
}

.quality-ppt-bar-column {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  width: min(14%, 118px);
  min-width: 42px;
  text-align: center;
}

.quality-ppt-bar-area {
  position: relative;
  height: 100%;
}

.quality-ppt-bar-area i {
  position: absolute;
  right: 14%;
  bottom: 0;
  left: 14%;
  display: block;
  background: #4c9dd5;
}

.quality-ppt-bar-value {
  position: absolute;
  right: 0;
  left: 0;
  z-index: 1;
  font-size: clamp(7px, 0.95vw, 14px);
  font-weight: 900;
}

.quality-ppt-bar-column strong {
  padding-top: 0.5em;
  font-size: clamp(7px, 0.9vw, 13px);
  white-space: nowrap;
}

.quality-ppt-bar-column small {
  color: #246f9b;
  font-size: clamp(6px, 0.75vw, 11px);
  font-weight: 800;
}

.quality-slide-band {
  margin: -1.6% -2.8% 2.5%;
  padding: 1.15% 1.2%;
  color: #ffffff;
  background: #2a89c1;
  box-shadow: 7px 7px 0 rgba(15, 23, 42, 0.2);
  font-size: clamp(9px, 1.4vw, 20px);
  font-weight: 900;
}

.quality-slide-band.wide {
  width: 62%;
}

.quality-issue-pair-grid {
  position: absolute;
  top: 33.9%;
  right: 4.7%;
  bottom: 8.5%;
  left: 4.7%;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  height: auto;
}

.quality-issue-pair-grid article {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 2.2%;
  min-width: 0;
  min-height: 0;
  padding: 0 2%;
  overflow: hidden;
}

.quality-issue-pair-grid article.copy-short {
  grid-template-rows: auto auto minmax(0, 1fr);
}

.quality-issue-pair-grid article.copy-long {
  grid-template-rows: auto auto minmax(0, 1fr);
}

.quality-issue-pair-grid article + article {
  border-left: 1px dashed #7bb6d6;
}

.quality-issue-pair-grid h3 {
  margin: 0 0 0.5em;
  color: #101820;
  font-size: clamp(10px, 1.3vw, 19px);
}

.quality-issue-pair-grid p {
  margin: 0;
  overflow-wrap: anywhere;
  font-size: clamp(9px, 1.18vw, 17px);
  font-weight: 700;
  line-height: 1.48;
}

.quality-issue-pair-grid article.copy-long p {
  font-size: clamp(8px, 1.02vw, 15px);
  line-height: 1.4;
}

.quality-issue-pair-grid button,
.quality-trace-layout > button {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  box-sizing: border-box;
  padding: 0;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  background: #f1f5f9;
  cursor: zoom-in;
}

.quality-issue-pair-grid img,
.quality-trace-layout img {
  display: block;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  object-fit: contain;
}

.quality-issue-summary {
  position: absolute;
  top: 25.3%;
  right: 5.6%;
  left: 5.6%;
  margin: 0;
  color: #101820;
  font-size: clamp(10px, 1.32vw, 19px);
  font-weight: 900;
}

.quality-issue-pair-grid.paired article.photo-portrait.copy-short {
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  grid-template-rows: auto minmax(0, 1fr);
  gap: 2.5%;
}

.quality-issue-pair-grid.paired article.photo-portrait.copy-short h3 {
  grid-column: 1 / -1;
}

.quality-issue-pair-grid.paired article.photo-portrait.copy-short p {
  grid-column: 1;
  grid-row: 2;
  align-self: center;
  font-size: clamp(10px, 1.24vw, 18px);
}

.quality-issue-pair-grid.paired article.photo-portrait.copy-short button,
.quality-issue-pair-grid.paired article.photo-portrait.copy-short .quality-slide-photo-empty {
  grid-column: 2;
  grid-row: 2;
}

.quality-issue-pair-grid.single article {
  grid-column: 1 / -1;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
  grid-template-rows: auto minmax(0, 1fr);
  gap: 2% 4%;
  padding: 0 2%;
}

.quality-issue-pair-grid.single article.photo-portrait {
  grid-template-columns: minmax(0, 1.68fr) minmax(0, 0.62fr);
}

.quality-issue-pair-grid.single article.photo-landscape.copy-short {
  grid-template-columns: minmax(0, 0.72fr) minmax(0, 1.28fr);
}

.quality-issue-pair-grid.single article.copy-long {
  grid-template-columns: minmax(0, 1.45fr) minmax(0, 0.8fr);
}

.quality-issue-pair-grid.single article h3 {
  grid-column: 1;
  grid-row: 1;
  font-size: clamp(13px, 1.7vw, 25px);
}

.quality-issue-pair-grid.single article p {
  grid-column: 1;
  grid-row: 2;
  font-size: clamp(10px, 1.3vw, 19px);
  line-height: 1.7;
}

.quality-issue-pair-grid.single article button,
.quality-issue-pair-grid.single article .quality-slide-photo-empty {
  grid-column: 2;
  grid-row: 1 / 3;
}

.quality-issue-pair-grid.single article.photo-panorama.copy-short {
  grid-template-columns: 1fr;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 1.5%;
}

.quality-issue-pair-grid.single article.photo-panorama.copy-short h3,
.quality-issue-pair-grid.single article.photo-panorama.copy-short p,
.quality-issue-pair-grid.single article.photo-panorama.copy-short button,
.quality-issue-pair-grid.single article.photo-panorama.copy-short .quality-slide-photo-empty {
  grid-column: 1;
}

.quality-issue-pair-grid.single article.photo-panorama.copy-short h3 { grid-row: 1; }
.quality-issue-pair-grid.single article.photo-panorama.copy-short p {
  grid-row: 2;
  font-size: clamp(10px, 1.18vw, 17px);
  line-height: 1.45;
}
.quality-issue-pair-grid.single article.photo-panorama.copy-short button,
.quality-issue-pair-grid.single article.photo-panorama.copy-short .quality-slide-photo-empty { grid-row: 3; }

.quality-slide-photo-empty,
.quality-slide-empty {
  display: grid;
  place-items: center;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  color: #64748b;
  border: 1px dashed #a9b8c4;
  background: #f5f8fa;
  font-size: clamp(7px, 0.9vw, 13px);
}

.quality-trace-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.85fr) minmax(220px, 0.75fr);
  gap: 3%;
  height: 100%;
}

.quality-trace-layout.photo-portrait {
  grid-template-columns: minmax(0, 2.05fr) minmax(170px, 0.55fr);
}

.quality-trace-layout.copy-long {
  grid-template-columns: minmax(0, 2.15fr) minmax(180px, 0.58fr);
}

.quality-trace-layout.photo-panorama.copy-short {
  grid-template-columns: 1fr;
  grid-template-rows: minmax(0, 1.08fr) minmax(0, 0.92fr);
  gap: 2%;
}

.quality-typical-issue {
  min-height: 17%;
  margin: 0 0 2%;
  color: #d60000;
  font-size: clamp(10px, 1.32vw, 19px);
  font-weight: 800;
  line-height: 1.55;
}

.quality-trace-layout section {
  display: grid;
  grid-template-columns: 18% minmax(0, 1fr);
  gap: 1%;
  margin-bottom: 2%;
}

.quality-trace-layout section strong {
  color: #3477c3;
  font-size: clamp(9px, 1.15vw, 16px);
}

.quality-trace-layout section p {
  margin: 0;
  font-size: clamp(9px, 1.08vw, 16px);
  font-weight: 700;
  line-height: 1.6;
}

.quality-trace-analysis {
  padding: 2% 4%;
}

.quality-trace-analysis h3 {
  margin: 0.8em 0 0.3em;
  color: #3477c3;
  font-size: clamp(9px, 1.25vw, 18px);
}

.quality-trace-analysis p,
.quality-trace-analysis li {
  font-size: clamp(10px, 1.25vw, 18px);
  font-weight: 700;
  line-height: 1.7;
}

.quality-work-plan {
  display: grid;
  gap: 1.5%;
  margin: 0;
  padding: 1% 4% 0 7%;
}

.quality-work-plan li {
  padding-left: 0.5em;
}

.quality-work-plan h3 {
  margin: 0;
  color: #3477c3;
  font-size: clamp(11px, 1.45vw, 21px);
}

.quality-work-plan p {
  margin: 0.25em 0 0;
  font-size: clamp(10px, 1.28vw, 18px);
  font-weight: 700;
  line-height: 1.55;
}

.quality-ppt-pagination {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  margin-top: 16px;
}

.quality-ppt-pagination > div {
  display: flex;
  gap: 7px;
  overflow-x: auto;
  padding: 3px;
  scrollbar-width: thin;
}

.quality-ppt-pagination button {
  flex: 0 0 auto;
  min-width: 38px;
  height: 38px;
  padding: 0 12px;
  border: 1px solid #cbd5e1;
  border-radius: 11px;
  color: #334155;
  background: #ffffff;
  font-weight: 850;
  cursor: pointer;
}

.quality-ppt-pagination button.active {
  color: #ffffff;
  border-color: #1479ae;
  background: #1479ae;
}

.quality-ppt-pagination button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
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

.standard-detail-preview {
  position: fixed;
  inset: 0;
  z-index: 90000;
  display: grid;
  place-items: center;
  padding: 22px;
  background: rgba(2, 6, 23, 0.68);
  backdrop-filter: blur(7px);
}

.standard-detail-preview > section {
  position: relative;
  width: min(620px, calc(100vw - 36px));
  overflow: hidden;
  border: 1px solid rgba(186, 230, 253, 0.72);
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 32px 90px rgba(2, 6, 23, 0.34);
}

.standard-detail-preview > section > button {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(248, 113, 113, 0.38);
  border-radius: 50%;
  color: #dc2626;
  background: rgba(254, 226, 226, 0.84);
  font-size: 27px;
  line-height: 1;
  cursor: pointer;
}

.standard-detail-preview header {
  padding: 22px 70px 18px 22px;
  color: #e0f2fe;
  background:
    radial-gradient(circle at 0% 0%, rgba(34, 211, 238, 0.3), transparent 40%),
    #0f3b5d;
}

.standard-detail-preview header > span {
  color: #67e8f9;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.16em;
}

.standard-detail-preview h3 {
  margin: 5px 0 4px;
  color: #ffffff;
  font-size: 20px;
}

.standard-detail-preview header small {
  color: #bae6fd;
}

.standard-detail-preview section > div {
  padding: 22px;
}

.standard-detail-preview section > div > span {
  color: #64748b;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.standard-detail-preview section > div > p {
  max-height: min(48vh, 360px);
  overflow-y: auto;
  margin: 10px 0 0;
  color: #1e293b;
  font-size: 15px;
  line-height: 1.85;
  white-space: pre-wrap;
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
  .report-period-workspace {
    grid-template-columns: 1fr;
  }

  .period-editor-fields {
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  }

  .period-generate-btn {
    grid-column: 1 / -1;
    width: 100%;
  }

  .report-history-list {
    max-height: 180px;
  }

  .non-oil-source-panel {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .non-oil-source-panel .source-apply-generate-btn {
    justify-self: stretch;
  }

  .quality-ppt-stage {
    padding: 10px;
    border-radius: 16px;
  }

  .quality-ppt-toolbar {
    align-items: flex-start;
  }

  .quality-trace-layout {
    grid-template-columns: minmax(0, 1.9fr) minmax(140px, 0.7fr);
  }

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

  .quality-classification-panel {
    grid-template-columns: minmax(0, 1fr);
    align-items: stretch;
  }

  .classification-panel-stats {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .classification-panel-preview,
  .classification-manage-btn {
    grid-column: 1;
    grid-row: auto;
  }

  .classification-manage-btn {
    width: 100%;
  }

  .flow-classification-dialog-layer {
    padding: 18px;
  }

  .flow-classification-dialog {
    width: calc(100vw - 36px);
    max-height: calc(100dvh - 36px);
    border-radius: 23px;
  }

  .classification-dialog-head {
    align-items: flex-start;
    padding: 20px 68px 17px 20px;
  }

  .classification-dialog-head > div:last-child {
    min-width: 82px;
  }

  .classification-dialog-toolbar {
    grid-template-columns: minmax(0, 1fr) minmax(180px, 0.55fr);
    padding: 12px 18px;
  }

  .classification-dialog-list {
    padding: 14px 18px 18px;
  }

  .classification-dialog-list article {
    grid-template-columns: minmax(0, 1fr);
  }

  .classification-dialog-footer {
    padding: 13px 18px 16px;
  }

  .report-source-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .source-configure-btn,
  .selection-configure-btn,
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
  .report-period-workspace {
    gap: 11px;
    padding: 12px;
    border-radius: 19px;
  }

  .report-period-editor,
  .report-history-panel {
    border-radius: 15px;
  }

  .report-period-editor {
    padding: 14px;
  }

  .period-editor-fields {
    grid-template-columns: 1fr;
    gap: 9px;
    margin-top: 13px;
  }

  .period-editor-fields > i {
    display: none;
  }

  .period-generate-btn {
    grid-column: auto;
  }

  .report-history-title {
    padding: 13px;
  }

  .report-history-list {
    max-height: 194px;
    padding: 8px;
  }

  .source-last-saved.compact {
    max-width: none;
    text-align: left;
  }

  .standard-detail-preview {
    align-items: end;
    padding: 8px;
  }

  .standard-detail-preview > section {
    width: calc(100vw - 16px);
    max-height: calc(100dvh - 16px);
    border-radius: 22px;
  }

  .standard-detail-preview header {
    padding: 19px 62px 16px 17px;
  }

  .standard-detail-preview section > div {
    padding: 17px;
  }

  .non-oil-source-panel {
    gap: 16px;
    padding: 16px;
    border-radius: 20px;
  }

  .non-oil-date-fields {
    grid-template-columns: 1fr;
    align-items: stretch;
    gap: 8px;
  }

  .non-oil-date-fields > i {
    display: none;
  }

  .non-oil-custom-range-note {
    align-items: stretch;
    flex-direction: column;
  }

  .non-oil-custom-range-note button {
    width: 100%;
  }

  .quality-classification-panel {
    gap: 14px;
    padding: 17px;
    border-radius: 19px;
  }

  .classification-panel-intro {
    gap: 11px;
  }

  .classification-ai-mark {
    width: 43px;
    height: 43px;
    flex-basis: 43px;
    border-radius: 14px;
  }

  .classification-panel-intro h3 {
    font-size: 17px;
  }

  .classification-panel-intro p {
    font-size: 12px;
  }

  .classification-panel-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .classification-panel-preview {
    max-height: 68px;
    overflow: auto;
  }

  .flow-classification-dialog-layer {
    align-items: end;
    padding: 8px;
  }

  .flow-classification-dialog {
    width: calc(100vw - 16px);
    max-height: calc(100dvh - 16px);
    border-radius: 23px;
  }

  .classification-dialog-close {
    top: 11px;
    right: 11px;
    width: 40px;
    height: 40px;
  }

  .classification-dialog-head {
    display: block;
    padding: 17px 58px 14px 16px;
  }

  .classification-dialog-head h3 {
    font-size: 19px;
  }

  .classification-dialog-head p {
    font-size: 12px;
  }

  .classification-dialog-head > div:last-child {
    display: none;
  }

  .classification-dialog-toolbar {
    grid-template-columns: 1fr;
    gap: 7px;
    padding: 10px 12px;
  }

  .classification-dialog-toolbar label {
    min-width: 0;
  }

  .classification-dialog-message {
    margin: 9px 12px 0;
  }

  .classification-dialog-list {
    padding: 10px 12px 14px;
  }

  .classification-dialog-list article {
    gap: 13px;
    padding: 13px;
  }

  .classification-result-compare {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
    align-items: end;
  }

  .classification-result-compare em {
    grid-column: 1 / -1;
    justify-self: start;
  }

  .classification-dialog-footer {
    align-items: stretch;
    flex-direction: column;
    gap: 9px;
    padding: 11px 12px 13px;
  }

  .classification-dialog-footer > div {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .classification-cancel-btn,
  .classification-save-btn {
    min-width: 0;
    padding: 0 10px;
  }

  .quality-ppt-viewer {
    margin-top: 8px;
  }

  .quality-ppt-toolbar {
    gap: 8px;
    margin-bottom: 10px;
    padding: 11px 12px;
    border-radius: 14px;
  }

  .quality-ppt-toolbar strong {
    font-size: 14px;
  }

  .quality-ppt-toolbar small {
    font-size: 10px;
  }

  .quality-ppt-page-count {
    padding: 7px 9px;
    font-size: 11px;
  }

  .quality-ppt-stage {
    padding: 5px;
    border-radius: 10px;
  }

  .quality-slide-header {
    border-bottom-width: 2px;
  }

  .quality-slide-header h2 {
    font-size: 10px;
  }

  .quality-slide-brand {
    gap: 3px;
  }

  .quality-slide-table-wrap th,
  .quality-slide-table-wrap td {
    padding: 0.16em;
    font-size: 5px;
    line-height: 1.2;
  }

  .quality-ppt-pagination {
    grid-template-columns: 64px minmax(0, 1fr) 64px;
    gap: 6px;
    margin-top: 10px;
  }

  .quality-ppt-pagination button {
    min-width: 32px;
    height: 34px;
    padding: 0 7px;
    border-radius: 9px;
    font-size: 11px;
  }

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

  .historical-config-note {
    align-items: flex-start;
    flex-direction: column;
  }

  .historical-config-note button,
  .historical-rule-btn {
    width: 100%;
  }

  .historical-rule-btn {
    justify-self: stretch;
  }

  .source-summary-grid {
    grid-column: auto;
  }

  .report-source-dialog-layer,
  .report-selection-dialog-layer {
    padding: 10px;
    align-items: center;
  }

  .report-source-dialog {
    width: calc(100vw - 20px);
    max-height: calc(100dvh - 20px);
    border-radius: 22px;
  }

  .report-selection-dialog {
    width: calc(100vw - 20px);
    max-height: calc(100dvh - 20px);
    border-radius: 22px;
  }

  .selection-dialog-close {
    top: 12px;
    right: 12px;
    width: 40px;
    height: 40px;
  }

  .selection-dialog-head {
    align-items: flex-start;
    padding: 20px 60px 16px 18px;
  }

  .selection-dialog-head h3 {
    font-size: 19px;
  }

  .selection-dialog-head p,
  .selection-updated-meta {
    display: none;
  }

  .selection-rule-tabs {
    grid-template-columns: 1fr;
    gap: 7px;
    padding: 12px 14px 8px;
  }

  .selection-rule-tabs button {
    padding: 10px 12px;
  }

  .selection-sampling-section,
  .selection-priority-section {
    padding-right: 14px;
    padding-left: 14px;
  }

  .selection-sampling-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .selection-standard-toolbar,
  .selection-priority-workbench {
    grid-template-columns: 1fr;
  }

  .selection-standard-pool > div,
  .selection-priority-list > div {
    max-height: 220px;
  }

  .selection-dialog-footer {
    align-items: stretch;
    flex-direction: column;
    padding: 11px 14px 14px;
  }

  .selection-dialog-footer > div,
  .selection-cancel-btn,
  .selection-save-btn {
    width: 100%;
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

@media (max-width: 900px) {
  .non-oil-issue-library-dialog {
    width: calc(100vw - 36px);
  }

  .issue-library-toolbar {
    grid-template-columns: minmax(0, 1fr) minmax(150px, 0.42fr);
    padding: 12px 18px;
  }

  .issue-library-batch-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }

  .issue-library-workspace {
    grid-template-columns: 190px minmax(0, 1fr);
  }

  .issue-library-list article {
    grid-template-columns: 32px minmax(0, 1fr) 96px;
  }

  .issue-library-photo {
    width: 96px;
    height: 70px;
  }
}

@media (max-width: 520px) {
  .non-oil-issue-library-dialog {
    width: calc(100vw - 16px);
    height: auto;
    min-height: calc(100dvh - 16px);
    max-height: calc(100dvh - 16px);
  }

  .issue-library-toolbar {
    grid-template-columns: 1fr;
    gap: 8px;
    padding: 10px 12px;
  }

  .issue-library-batch-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .issue-library-batch-actions button:last-child {
    grid-column: 1 / -1;
  }

  .issue-library-workspace {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .issue-library-categories {
    flex: 0 0 auto;
    display: flex;
    gap: 6px;
    overflow-x: auto;
    padding: 9px 10px;
    border-right: 0;
    border-bottom: 1px solid #dbeafe;
  }

  .issue-library-categories button {
    width: auto;
    min-width: max-content;
    padding: 8px 10px;
  }

  .issue-library-categories button + button {
    margin-top: 0;
  }

  .issue-library-list {
    padding: 10px 10px 14px;
  }

  .issue-library-list article {
    grid-template-columns: 28px minmax(0, 1fr);
    align-items: start;
    gap: 9px;
    padding: 11px;
  }

  .issue-library-photo {
    grid-column: 2;
    width: 100%;
    height: 132px;
  }

  .issue-library-checkbox span {
    width: 21px;
    height: 21px;
  }
}
</style>
