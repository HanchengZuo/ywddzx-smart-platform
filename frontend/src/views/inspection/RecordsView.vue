<template>
  <div class="page-shell records-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>巡检记录</h2>
      </div>
    </div>

    <transition name="record-action-toast">
      <div v-if="actionMessage.text" class="record-action-toast card-surface" :class="actionMessage.type">
        {{ actionMessage.text }}
      </div>
    </transition>

    <div class="filter-card card-surface" :class="{ 'mobile-expanded': showMobileFilters }">
      <div class="filter-head">
        <div>
          <div class="filter-kicker">筛选面板</div>
          <h3>快速定位巡检记录</h3>
        </div>
        <div class="filter-head-actions">
          <span v-if="activeFilterCount" class="active-filter-pill">已选 {{ activeFilterCount }} 项</span>
          <button v-if="isMobileView" class="btn btn-secondary mobile-filter-toggle" type="button"
            @click="showMobileFilters = !showMobileFilters">
            {{ showMobileFilters ? '收起筛选' : '展开筛选' }}
          </button>
        </div>
      </div>

      <div class="filter-grid">
        <div class="filter-item filter-item-month">
          <label>巡检月度</label>
          <input v-model="filters.month" type="month" @change="handleRecordMonthChange" />
        </div>
        <div class="filter-item filter-item-date">
          <label>巡检日期</label>
          <DateRangePicker
            v-model:date-from="filters.dateFrom"
            v-model:date-to="filters.dateTo"
            placeholder="选择巡检日期范围"
            aria-label="选择巡检日期范围"
            @change="handleRecordDateRangeChange"
          />
        </div>
        <div class="filter-item filter-item-station">
          <label>站点</label>
          <div class="search-select multi-search-select" ref="stationSelectRef">
            <div class="multi-select-control" @click="focusMultiFilterInput('station')">
              <div class="multi-selected-values">
                <span v-for="value in filters.station" :key="`station-${value}`" class="multi-selected-chip">
                  {{ value }}
                  <button type="button" @click.stop="removeMultiFilterValue('station', value)">×</button>
                </span>
                <input ref="stationFilterInputRef" v-model="filterSearch.station" type="text"
                  :placeholder="filters.station.length ? '继续搜索站点' : '搜索并多选站点'"
                  @focus="openFilterDropdown('station')" @input="openFilterDropdown('station')" />
              </div>
              <span v-if="filters.station.length" class="multi-selected-count">已选 {{ filters.station.length }}</span>
            </div>
            <div v-if="dropdownVisible.station" class="search-select-dropdown">
              <button v-for="option in filteredStationOptions" :key="option" type="button"
                class="search-select-option multi-select-option"
                :class="{ selected: isMultiFilterSelected('station', option) }"
                @mousedown.prevent @click="toggleMultiFilter('station', option)">
                <span class="multi-option-check">{{ isMultiFilterSelected('station', option) ? '✓' : '' }}</span>
                <div class="option-main">{{ option }}</div>
              </button>
              <div v-if="filteredStationOptions.length === 0" class="search-select-empty">无匹配站点</div>
            </div>
          </div>
        </div>
        <div class="filter-item filter-item-table">
          <label>检查表</label>
          <div class="search-select multi-search-select" ref="inspectionTableSelectRef">
            <div class="multi-select-control" @click="focusMultiFilterInput('inspectionTableName')">
              <div class="multi-selected-values">
                <span v-for="value in filters.inspectionTableName" :key="`table-${value}`" class="multi-selected-chip">
                  {{ value }}
                  <button type="button" @click.stop="removeMultiFilterValue('inspectionTableName', value)">×</button>
                </span>
                <input ref="inspectionTableFilterInputRef" v-model="filterSearch.inspectionTableName" type="text"
                  :placeholder="filters.inspectionTableName.length ? '继续搜索检查表' : '搜索并多选检查表'"
                  @focus="openFilterDropdown('inspectionTableName')" @input="openFilterDropdown('inspectionTableName')" />
              </div>
              <span v-if="filters.inspectionTableName.length" class="multi-selected-count">已选 {{ filters.inspectionTableName.length }}</span>
            </div>
            <div v-if="dropdownVisible.inspectionTableName" class="search-select-dropdown">
              <button v-for="option in filteredInspectionTableOptions" :key="option" type="button"
                class="search-select-option multi-select-option"
                :class="{ selected: isMultiFilterSelected('inspectionTableName', option) }"
                @mousedown.prevent @click="toggleMultiFilter('inspectionTableName', option)">
                <span class="multi-option-check">{{ isMultiFilterSelected('inspectionTableName', option) ? '✓' : '' }}</span>
                <div class="option-main">{{ option }}</div>
              </button>
              <div v-if="filteredInspectionTableOptions.length === 0" class="search-select-empty">无匹配检查表</div>
            </div>
          </div>
        </div>
        <div v-if="!hideInspectorContactInfo" class="filter-item filter-item-inspector">
          <label>检查人</label>
          <div class="search-select multi-search-select" ref="inspectorSelectRef">
            <div class="multi-select-control" @click="focusMultiFilterInput('inspector')">
              <div class="multi-selected-values">
                <span v-for="value in filters.inspector" :key="`inspector-${value}`" class="multi-selected-chip">
                  {{ value }}
                  <button type="button" @click.stop="removeMultiFilterValue('inspector', value)">×</button>
                </span>
                <input ref="inspectorFilterInputRef" v-model="filterSearch.inspector" type="text"
                  :placeholder="filters.inspector.length ? '继续搜索检查人' : '搜索并多选检查人'"
                  @focus="openFilterDropdown('inspector')" @input="openFilterDropdown('inspector')" />
              </div>
              <span v-if="filters.inspector.length" class="multi-selected-count">已选 {{ filters.inspector.length }}</span>
            </div>
            <div v-if="dropdownVisible.inspector" class="search-select-dropdown">
              <button v-for="option in filteredInspectorOptions" :key="option" type="button"
                class="search-select-option multi-select-option"
                :class="{ selected: isMultiFilterSelected('inspector', option) }"
                @mousedown.prevent @click="toggleMultiFilter('inspector', option)">
                <span class="multi-option-check">{{ isMultiFilterSelected('inspector', option) ? '✓' : '' }}</span>
                <div class="option-main">{{ option }}</div>
              </button>
              <div v-if="filteredInspectorOptions.length === 0" class="search-select-empty">无匹配检查人</div>
            </div>
          </div>
        </div>
        <div class="filter-item filter-item-result">
          <label>检查结果</label>
          <select v-model="filters.result">
            <option value="">全部</option>
            <option value="正常">正常</option>
            <option value="异常">异常</option>
          </select>
        </div>
        <div class="filter-item filter-item-completion">
          <label>检查人确认状态</label>
          <select v-model="filters.completionStatus">
            <option value="">全部</option>
            <option value="completed">已确认完成</option>
            <option value="pending">待检查人确认</option>
          </select>
        </div>
        <div class="filter-item filter-item-signature">
          <label>站经理签名状态</label>
          <select v-model="filters.signStatus">
            <option value="">全部</option>
            <option value="signed">已签名</option>
            <option value="pending">待签名</option>
          </select>
        </div>
      </div>

      <div class="filter-actions">
        <div class="filter-quick-actions">
          <button class="btn btn-primary today-filter-btn" type="button" @click="filterMyTodayRecords">
            只看我今天的巡检记录
          </button>
        </div>
        <div class="filter-main-actions">
          <button class="btn btn-secondary" type="button" @click="resetFilters">重置筛选</button>
          <button class="btn btn-secondary" type="button" @click="fetchInspections({ forceOptions: true })" :disabled="loading">
            {{ loading ? '刷新中...' : '刷新数据' }}
          </button>
        </div>
      </div>
    </div>

    <div class="mobile-record-list">
      <div v-if="loading" class="mobile-empty empty-state-card card-surface">
        <div class="empty-state-orb loading"></div>
        <div class="empty-state-kicker">同步中</div>
        <h3>正在加载巡检记录</h3>
        <p>系统正在同步最新巡检记录，请稍候。</p>
      </div>

      <div v-else-if="paginatedInspectionGroups.length === 0" class="mobile-empty empty-state-card card-surface">
        <div class="empty-state-orb"></div>
        <div class="empty-state-kicker">暂无记录</div>
        <h3>当前没有符合条件的巡检记录</h3>
        <p>可以调整筛选条件，或刷新后查看最新巡检情况。</p>
        <button class="btn btn-secondary empty-state-action" type="button" @click="resetFilters">重置筛选</button>
      </div>

      <div v-else class="mobile-record-cards">
        <div v-for="batch in paginatedInspectionGroups" :key="batch.batchKey" class="mobile-record-card card-surface">
          <div class="mobile-card-head">
            <div class="mobile-card-title-row">
              <div class="mobile-card-station">{{ batch.station }}</div>
              <span :class="statusClass(batch.batchResult)">{{ batch.batchResult }}</span>
            </div>
            <div class="mobile-card-date">巡检日期：{{ batch.date }}</div>
          </div>

          <div class="mobile-card-body">
            <div class="mobile-card-row">
              <span>当日检查表数</span>
              <strong>{{ batch.rowspan }}</strong>
            </div>
            <div class="mobile-card-row">
              <span>当日问题总数</span>
              <strong>{{ batch.batchIssueCount }}</strong>
            </div>
            <div class="mobile-card-row">
              <span>检查表签名进度</span>
              <strong>{{ batch.signedCount }}/{{ batch.rowspan }}</strong>
            </div>
          </div>

          <div class="mobile-batch-list">
            <div v-for="record in batch.records" :key="record.id" class="mobile-batch-item">
              <div class="mobile-batch-item-head">
                <div class="mobile-batch-table-name">{{ record.inspection_table_name || '暂无' }}</div>
                <span :class="statusClass(record.result)">{{ record.result }}</span>
              </div>
              <div class="mobile-batch-item-meta-row">
                <span class="mobile-meta-pill">问题 {{ record.issue_count }}</span>
                <span class="mobile-meta-pill"
                  :class="{ signed: record.sign_status === '已签名确认' }">
                  {{ record.sign_status === '已签名确认' ? '已签名' : '待签名' }}
                </span>
                <span class="mobile-meta-pill"
                  :class="{ signed: isInspectionCompleted(record) }">
                  {{ isInspectionCompleted(record) ? '已完成' : '待完成确认' }}
                </span>
              </div>

              <div class="mobile-batch-item-actions">
                <button class="btn btn-secondary batch-action-btn mobile-action-btn mobile-action-view" type="button"
                  aria-label="查看本表录入问题" @click="openInspectionDetail(record)">
                  查看问题
                </button>

                <button v-if="canCompleteInspectionRecord(record)"
                  class="btn btn-primary batch-action-btn mobile-action-btn mobile-action-complete" type="button"
                  :disabled="completingInspectionId === record.id" aria-label="确认检查表完成"
                  @click="completeInspectionRecord(record)">
                  {{ completingInspectionId === record.id ? '确认中...' : '确认完成' }}
                </button>

                <button v-if="canSignInspectionRecord(record)"
                  class="btn btn-primary signature-action-btn mobile-action-btn mobile-action-sign" type="button"
                  aria-label="本表站经理签字确认" @click="openSignatureDialog(record)">
                  站经理签名
                </button>

                <div v-else-if="shouldShowSignatureProgress(record)" class="mobile-sign-progress-card">
                  <strong>{{ getSignatureProgressTitle(record) }}</strong>
                  <span v-for="line in getSignatureProgressLines(record)" :key="line">{{ line }}</span>
                </div>

                <button v-if="canDeleteInspectionRecord(record)"
                  class="btn btn-danger batch-action-btn mobile-action-btn mobile-action-delete" type="button"
                  :disabled="deletingInspectionId === record.id" aria-label="删除巡检记录"
                  @click="deleteInspectionRecord(record)">
                  {{ deletingInspectionId === record.id ? '删除中...' : '删除记录' }}
                </button>
              </div>

              <div v-if="record.sign_status === '已签名确认' && record.station_manager_signature_path"
                class="mobile-signature-box">
                <div class="mobile-signature-label">站经理已签名</div>
                <img v-if="recordImagesReady" :src="resolveImage(record.station_manager_signature_path)"
                  class="signature-preview-image" alt="站经理签名" loading="lazy" decoding="async" fetchpriority="low" />
                <div v-else class="signature-preview-placeholder">签名</div>
                <div class="mobile-signature-time">{{ record.station_manager_signed_at || '已完成签名确认' }}</div>
                <button v-if="canResetInspectionSignature(record)" class="btn btn-secondary btn-sm signature-reset-btn"
                  type="button" :disabled="resettingSignatureId === record.id" @click="resetInspectionSignature(record)">
                  {{ resettingSignatureId === record.id ? '重置中' : '重置' }}
                </button>
                <span v-else-if="record.reset_signature_lock_reason" class="signature-reset-locked">
                  {{ record.reset_signature_lock_reason }}
                </span>
              </div>
            </div>
          </div>

        </div>
      </div>

      <div v-if="!loading && totalRecords" class="pagination-bar mobile-pagination-bar card-surface">
        <div class="pagination-summary">共 {{ totalRecords }} 条巡检记录</div>
        <div class="pagination-controls">
          <div class="pagination-size-control">
            <label>每页显示</label>
            <select v-model.number="pageSize">
              <option :value="5">5</option>
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
            </select>
          </div>
          <div class="pagination-nav-row">
            <button class="btn btn-secondary pagination-btn" :disabled="page <= 1" @click="goToPage(1)">首页</button>
            <button class="btn btn-secondary pagination-btn" :disabled="page <= 1" @click="prevPage">上一页</button>
          </div>
          <div class="pagination-page-list" aria-label="巡检记录页码">
            <template v-for="item in visiblePageItems" :key="item.key">
              <span v-if="item.type === 'ellipsis'" class="pagination-ellipsis">...</span>
              <button v-else class="pagination-page-btn" :class="{ active: item.value === page }" type="button"
                @click="goToPage(item.value)">
                {{ item.value }}
              </button>
            </template>
          </div>
          <div class="pagination-nav-row">
            <button class="btn btn-secondary pagination-btn" :disabled="page >= totalPage" @click="nextPage">下一页</button>
            <button class="btn btn-secondary pagination-btn" :disabled="page >= totalPage" @click="goToPage(totalPage)">末页</button>
          </div>
          <div class="pagination-jump">
            <span>跳至</span>
            <input v-model="pageJumpInput" type="number" min="1" :max="totalPage" :placeholder="`1-${totalPage}`"
              @keyup.enter="jumpToInputPage" />
            <button class="btn btn-primary pagination-jump-btn" type="button" @click="jumpToInputPage">跳转</button>
          </div>
        </div>
      </div>
    </div>

    <div class="table-card card-surface">
      <div class="table-scroll-wrap">
        <div class="table-scroll">
          <table class="records-table">
            <thead>
              <tr>
                <th>巡检日期</th>
                <th>站点</th>
                <th>检查表</th>
                <th>检查结果</th>
                <th>发现问题数</th>
                <th>本表问题</th>
                <th>本表检查人完成确认</th>
                <th>本表站经理签字确认</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(batch, batchIndex) in paginatedInspectionGroups" :key="batch.batchKey">
                <tr v-if="shouldShowStationDivider(batch, batchIndex)" :key="`${batch.batchKey}-station-divider`"
                  class="station-divider-row">
                  <td colspan="8">
                    <div class="station-divider-content">
                      <div class="station-divider-main">
                        <span class="station-divider-dot"></span>
                        <strong>{{ batch.station || '未命名站点' }}</strong>
                      </div>
                      <div class="station-divider-meta">
                        <span>{{ batch.date }}</span>
                        <span>{{ batch.rowspan }} 张检查表</span>
                        <span>问题 {{ batch.batchIssueCount }}</span>
                      </div>
                    </div>
                  </td>
                </tr>
                <tr v-for="(record, index) in batch.records" :key="record.id"
                  :class="getRecordTableRowClasses(index)">
                  <td v-if="index === 0" :rowspan="batch.rowspan"
                    class="batch-merged-cell batch-main-cell batch-date-cell">
                    <div class="batch-date-content">
                      <span class="batch-date-text">{{ batch.date }}</span>
                    </div>
                  </td>
                  <td v-if="index === 0" :rowspan="batch.rowspan"
                    class="batch-merged-cell batch-main-cell batch-station-cell">
                    <div class="batch-station-content">
                      <strong class="batch-station-name">{{ batch.station }}</strong>
                    </div>
                  </td>
                  <td class="long-text">{{ record.inspection_table_name || '暂无' }}</td>
                  <td>
                    <span :class="statusClass(record.result)">{{ record.result }}</span>
                  </td>
                  <td>{{ record.issue_count }}</td>

                  <td class="batch-action-cell">
                    <div class="record-action-stack">
                      <button class="btn btn-secondary batch-action-btn" type="button"
                        @click="openInspectionDetail(record)">
                        查看本表录入问题
                      </button>
                      <button v-if="canDeleteInspectionRecord(record)" class="btn btn-danger batch-action-btn"
                        type="button" :disabled="deletingInspectionId === record.id"
                        @click="deleteInspectionRecord(record)">
                        {{ deletingInspectionId === record.id ? '删除中...' : '删除记录' }}
                      </button>
                    </div>
                  </td>

                  <td class="batch-completion-cell">
                    <div v-if="isInspectionCompleted(record)" class="completion-preview-box">
                      <div class="signature-status-badge success">已确认完成</div>
                      <div class="signature-preview-time">{{ getCompletionMeta(record) }}</div>
                    </div>
                    <button v-else-if="canCompleteInspectionRecord(record)" class="btn btn-primary batch-action-btn"
                      type="button" :disabled="completingInspectionId === record.id"
                      @click="completeInspectionRecord(record)">
                      {{ completingInspectionId === record.id ? '确认中...' : '确认完成' }}
                    </button>
                    <span v-else class="signature-status-badge pending">待检查人确认</span>
                  </td>

                  <td class="batch-signature-cell">
                    <div v-if="record.sign_status === '已签名确认' && record.station_manager_signature_path"
                      class="signature-signed-wrap">
                      <div class="signature-preview-box">
                        <div class="signature-status-badge success">已签名确认</div>
                        <img v-if="recordImagesReady" :src="resolveImage(record.station_manager_signature_path)"
                          class="signature-preview-image" alt="站经理签名" loading="lazy" decoding="async"
                          fetchpriority="low" />
                        <div v-else class="signature-preview-placeholder">签名</div>
                        <div class="signature-preview-time">{{ record.station_manager_signed_at || '已完成签名确认' }}</div>
                      </div>
                      <button v-if="canResetInspectionSignature(record)" class="btn btn-secondary btn-sm signature-reset-btn"
                        type="button" :disabled="resettingSignatureId === record.id" @click="resetInspectionSignature(record)">
                        {{ resettingSignatureId === record.id ? '重置中' : '重置' }}
                      </button>
                      <span v-else-if="record.reset_signature_lock_reason" class="signature-reset-locked">
                        {{ record.reset_signature_lock_reason }}
                      </span>
                    </div>

                    <button v-else-if="canSignInspectionRecord(record)" class="btn btn-primary signature-action-btn"
                      type="button" @click="openSignatureDialog(record)">
                      站经理签字
                    </button>

                    <div v-else-if="shouldShowSignatureProgress(record)" class="signature-progress-box">
                      <div class="signature-status-badge pending">{{ getSignatureProgressTitle(record) }}</div>
                      <p class="signature-progress-copy">
                        <span v-for="line in getSignatureProgressLines(record)" :key="line">{{ line }}</span>
                      </p>
                      <div v-if="getTotalIssueCount(record) > 0" class="signature-progress-track">
                        <span :style="{ width: getSignatureProgressWidth(record) }"></span>
                      </div>
                    </div>

                    <span v-else class="signature-status-badge pending">待签名确认</span>
                  </td>

                </tr>
              </template>
              <tr v-if="!loading && paginatedInspectionGroups.length === 0">
                <td colspan="8" class="empty-row">
                  <div class="empty-state-inline">
                    <div class="empty-state-orb"></div>
                    <div class="empty-state-kicker">暂无记录</div>
                    <h3>当前没有符合条件的巡检记录</h3>
                    <p>可以调整筛选条件，或刷新后查看最新巡检情况。</p>
                    <button class="btn btn-secondary btn-sm empty-state-action" type="button" @click="resetFilters">重置筛选</button>
                  </div>
                </td>
              </tr>
              <tr v-if="loading">
                <td colspan="8" class="empty-row">
                  <div class="empty-state-inline">
                    <div class="empty-state-orb loading"></div>
                    <div class="empty-state-kicker">同步中</div>
                    <h3>正在加载巡检记录</h3>
                    <p>系统正在同步最新巡检记录，请稍候。</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="pagination-bar">
        <div class="pagination-summary">共 {{ totalRecords }} 条巡检记录</div>
        <div class="pagination-controls">
          <div class="pagination-size-control">
            <label>每页显示</label>
            <select v-model.number="pageSize">
              <option :value="5">5</option>
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
            </select>
          </div>
          <div class="pagination-nav-row">
            <button class="btn btn-secondary pagination-btn" :disabled="page <= 1" @click="goToPage(1)">首页</button>
            <button class="btn btn-secondary pagination-btn" :disabled="page <= 1" @click="prevPage">上一页</button>
          </div>
          <div class="pagination-page-list" aria-label="巡检记录页码">
            <template v-for="item in visiblePageItems" :key="item.key">
              <span v-if="item.type === 'ellipsis'" class="pagination-ellipsis">...</span>
              <button v-else class="pagination-page-btn" :class="{ active: item.value === page }" type="button"
                @click="goToPage(item.value)">
                {{ item.value }}
              </button>
            </template>
          </div>
          <div class="pagination-nav-row">
            <button class="btn btn-secondary pagination-btn" :disabled="page >= totalPage" @click="nextPage">下一页</button>
            <button class="btn btn-secondary pagination-btn" :disabled="page >= totalPage" @click="goToPage(totalPage)">末页</button>
          </div>
          <div class="pagination-jump">
            <span>跳至</span>
            <input v-model="pageJumpInput" type="number" min="1" :max="totalPage" :placeholder="`1-${totalPage}`"
              @keyup.enter="jumpToInputPage" />
            <button class="btn btn-primary pagination-jump-btn" type="button" @click="jumpToInputPage">跳转</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="signatureDialog.visible" class="batch-detail-overlay">
      <div v-if="isMobileView" class="mobile-signature-board card-surface">
        <div v-if="!isLandscapeMobile" class="mobile-signature-orientation-overlay">
          <div class="mobile-signature-orientation-overlay-inner">
            <div class="mobile-signature-orientation-icon">↻</div>
            <div class="mobile-signature-orientation-title">请横屏后签字</div>
            <div class="mobile-signature-orientation-text">为了便于站经理手写签名，请将手机旋转为横屏后继续操作。</div>
            <button class="btn btn-secondary mobile-signature-close" type="button"
              @click="closeSignatureDialog">关闭</button>
          </div>
        </div>

        <template v-else>
          <div class="mobile-signature-layout">
            <div class="mobile-signature-canvas-wrap">
              <canvas ref="signatureCanvasRef" class="signature-canvas mobile-signature-canvas"></canvas>
            </div>

            <div class="mobile-signature-rail">
              <button class="mobile-signature-icon-btn mobile-signature-confirm" type="button"
                :disabled="signatureDialog.submitting" @click="submitInspectionSignature" aria-label="确认签名"
                title="确认签名">
                ✓
              </button>
              <button class="mobile-signature-icon-btn mobile-signature-reset" type="button" @click="clearSignature"
                aria-label="重置签名" title="重置签名">
                ↻
              </button>
              <button class="mobile-signature-icon-btn mobile-signature-close-btn" type="button"
                @click="closeSignatureDialog" aria-label="退出签名" title="退出签名">
                ✕
              </button>
            </div>
          </div>

          <div v-if="signatureDialog.error" class="signature-error mobile-signature-error">{{ signatureDialog.error }}
          </div>
        </template>
      </div>

      <div v-else class="signature-dialog card-surface">
        <div class="signature-dialog-header">
          <div>
            <div class="batch-detail-kicker">本表站经理签字确认</div>
            <h3>{{ signatureDialog.record?.inspection_table_name || '本表站经理签字确认' }}</h3>
            <div class="batch-detail-meta">
              <span>巡检日期：{{ signatureDialog.record?.date || '-' }}</span>
              <span>站点：{{ signatureDialog.record?.station || '-' }}</span>
              <span>检查表：{{ signatureDialog.record?.inspection_table_name || '-' }}</span>
            </div>
          </div>
          <button class="btn btn-secondary" type="button" @click="closeSignatureDialog">关闭</button>
        </div>

        <div class="signature-layout">
          <div class="signature-side-card">
            <div class="signature-side-title">确认提示</div>
            <div class="signature-side-desc">请将手机交由站经理签字。该环节仅保留站经理签字确认，检查表是否封存以“本表检查人完成确认”为准。</div>
            <div class="signature-side-meta">
              <span>站点：{{ signatureDialog.record?.station || '-' }}</span>
              <span>日期：{{ signatureDialog.record?.date || '-' }}</span>
              <span>检查表：{{ signatureDialog.record?.inspection_table_name || '-' }}</span>
            </div>
          </div>

          <div class="signature-pad-card signature-pad-card-landscape">
            <div class="signature-pad-head signature-pad-head-minimal"></div>
            <div class="signature-pad-wrap signature-pad-wrap-landscape">
              <canvas ref="signatureCanvasRef" class="signature-canvas signature-canvas-landscape"></canvas>
            </div>
            <div class="signature-pad-actions">
              <button class="btn btn-secondary" type="button" @click="clearSignature">清空签名</button>
              <button class="btn btn-primary" type="button" :disabled="signatureDialog.submitting"
                @click="submitInspectionSignature">
                {{ signatureDialog.submitting ? '提交中...' : '提交签名确认' }}
              </button>
            </div>
            <div v-if="signatureDialog.error" class="signature-error">{{ signatureDialog.error }}</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="batchDetail.visible" class="batch-detail-overlay" @click.self="closeBatchDetail">
      <div class="batch-detail-dialog card-surface">
        <div class="batch-detail-header">
          <div class="batch-detail-header-main">
            <div class="batch-detail-kicker">检查表录入问题</div>
            <h3>{{ batchDetail.inspection?.inspection_table_name || '检查表详情' }}</h3>
            <div class="batch-detail-meta">
              <span>巡检日期：{{ getInspectionDate(batchDetail.inspection) }}</span>
              <span>站点：{{ getInspectionStation(batchDetail.inspection) }}</span>
              <span v-if="!hideInspectorContactInfo">检查人：{{ batchDetailInspectorLabel }}</span>
              <span>问题数：{{ batchDetail.issues.length || 0 }}</span>
            </div>
          </div>
          <div class="batch-detail-actions">
            <button class="btn btn-secondary" type="button" :disabled="!canExportBatchDetail || exportingBatchDetail"
              @click="exportBatchDetail">
              {{ exportingBatchDetail ? '生成中...' : '导出 PDF' }}
            </button>
            <button class="btn btn-secondary" type="button" @click="closeBatchDetail">关闭</button>
          </div>
        </div>

        <div v-if="batchDetail.loading" class="batch-detail-empty">正在加载本表问题...</div>
        <div v-else-if="batchDetail.error" class="batch-detail-empty">{{ batchDetail.error }}</div>
        <template v-else>
          <div class="batch-detail-summary-grid">
            <div>
              <span>检查表</span>
              <strong>{{ batchDetail.inspection?.inspection_table_name || '-' }}</strong>
            </div>
            <div>
              <span>所属片区</span>
              <strong>{{ batchDetail.inspection?.station_region || '-' }}</strong>
            </div>
            <div>
              <span>站点负责人</span>
              <strong>{{ batchDetail.inspection?.station_manager_name || '-' }}</strong>
            </div>
            <div>
              <span>签名状态</span>
              <strong>{{ batchDetail.inspection?.sign_status || '待签名确认' }}</strong>
            </div>
            <div>
              <span>完成确认</span>
              <strong>{{ batchDetail.inspection?.inspector_completion_status || '待检查人确认' }}</strong>
            </div>
          </div>

          <div v-if="batchDetail.issues.length === 0" class="batch-detail-empty">本检查表暂无登记问题。</div>

          <div v-else class="batch-issue-list">
            <div v-for="issue in batchDetail.issues" :key="issue.id" class="batch-issue-card">
              <div class="batch-issue-card-head">
                <div>
                  <div class="batch-issue-title">{{ issue.inspection_table_name || '未命名检查表' }}</div>
                  <div class="batch-issue-subtitle">{{ issue.created_at || '暂无登记时间' }}</div>
                </div>
                <div class="batch-issue-id">问题 #{{ issue.id }}</div>
              </div>

              <div class="batch-issue-meta-grid">
                <div v-if="!hideInspectorContactInfo">
                  <span>检查人</span>
                  <strong>{{ getInspectorLabel(issue) }}</strong>
                </div>
                <div>
                  <span>当前状态</span>
                  <strong>{{ issue.status || '-' }}</strong>
                </div>
                <div>
                  <span>规范ID</span>
                  <strong>{{ issue.standard_id || '-' }}</strong>
                </div>
              </div>

              <div class="batch-issue-section">
                <span>引用规范</span>
                <p>{{ issue.standard_detail_text || '暂无规范详情' }}</p>
              </div>
              <div class="batch-issue-section issue-section-warning">
                <span>问题描述</span>
                <p>{{ issue.description || '暂无问题描述' }}</p>
              </div>

              <div class="batch-issue-section">
                <span>整改情况</span>
                <p>{{ issue.rectification_result || '暂无整改结果' }}</p>
                <p>整改时间：{{ issue.rectification_at || '暂无' }}</p>
                <p v-if="issue.rectification_note">{{ issue.rectification_note }}</p>
              </div>
              <div class="batch-issue-section">
                <span>督导复核</span>
                <p>{{ issue.review_result || '暂无复核结果' }}</p>
                <p>复核时间：{{ issue.review_at || '暂无' }}</p>
                <p v-if="issue.review_note">{{ issue.review_note }}</p>
              </div>

              <div class="batch-issue-image-grid">
                <div class="batch-issue-image-card">
                  <span>问题照片</span>
                  <img v-if="issue.issue_photo" :src="resolveImage(issue.issue_photo)" class="batch-issue-image"
                    alt="问题照片" loading="lazy" decoding="async" />
                  <div v-else class="batch-issue-image-empty">暂无问题照片</div>
                </div>
                <div class="batch-issue-image-card">
                  <span>整改照片</span>
                  <img v-if="issue.rectification_photo" :src="resolveImage(issue.rectification_photo)"
                    class="batch-issue-image" alt="整改照片" loading="lazy" decoding="async" />
                  <div v-else class="batch-issue-image-empty">暂无整改照片</div>
                </div>
                <div class="batch-issue-image-card">
                  <span>复核照片</span>
                  <img v-if="issue.review_photo" :src="resolveImage(issue.review_photo)" class="batch-issue-image"
                    alt="复核照片" loading="lazy" decoding="async" />
                  <div v-else class="batch-issue-image-empty">暂无复核照片</div>
                </div>
              </div>
            </div>
          </div>
        </template>

      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, shallowRef, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import axios from 'axios'
import SignaturePad from 'signature_pad'
import { pinyin } from 'pinyin-pro'
import DateRangePicker from '@/components/DateRangePicker.vue'

const formatLocalDate = (value = new Date()) => {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const getDefaultDateRange = () => {
  const now = new Date()
  return {
    dateFrom: formatLocalDate(new Date(now.getFullYear(), now.getMonth(), 1)),
    dateTo: formatLocalDate(new Date(now.getFullYear(), now.getMonth() + 1, 0))
  }
}

const defaultDateRange = getDefaultDateRange()
const filters = ref({
  month: '',
  dateFrom: defaultDateRange.dateFrom,
  dateTo: defaultDateRange.dateTo,
  station: [],
  inspectionTableName: [],
  inspector: [],
  result: '',
  signStatus: '',
  completionStatus: ''
})

const stationSelectRef = ref(null)
const inspectionTableSelectRef = ref(null)
const inspectorSelectRef = ref(null)
const stationFilterInputRef = ref(null)
const inspectionTableFilterInputRef = ref(null)
const inspectorFilterInputRef = ref(null)

const filterSearch = ref({
  station: '',
  inspectionTableName: '',
  inspector: ''
})

const dropdownVisible = ref({
  station: false,
  inspectionTableName: false,
  inspector: false
})

const list = shallowRef([])
const totalRecords = ref(0)
const filterOptions = ref({
  stations: [],
  inspectionTables: [],
  inspectors: []
})
const filterOptionsLoaded = ref(false)
const currentRole = ref(localStorage.getItem('role') || localStorage.getItem('user_role') || '')
const currentRealName = localStorage.getItem('real_name') || ''
const currentUsername = localStorage.getItem('username') || ''
let parsedPermissions = {}
try {
  parsedPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch (error) {
  parsedPermissions = {}
}
const localPermissions = ref(parsedPermissions)
const isSupervisorLike = computed(() => currentRole.value === 'root' || currentRole.value === 'supervisor')
const hideInspectorContactInfo = computed(() => currentRole.value !== 'root' && Boolean(localPermissions.value.hide_inspector_contact_info))
const deletingInspectionId = ref(null)
const completingInspectionId = ref(null)
const resettingSignatureId = ref(null)
const actionMessage = ref({
  text: '',
  type: 'info'
})
let actionMessageTimer = null

const detectMobileViewport = () => {
  const ua = navigator.userAgent || ''
  const mobileUa = /Android|iPhone|iPad|iPod|Mobile/i.test(ua)
  const coarsePointer = window.matchMedia('(pointer: coarse)').matches
  const narrowScreen = window.innerWidth <= 1024
  return mobileUa || (coarsePointer && narrowScreen)
}

const isMobileView = ref(detectMobileViewport())
const showMobileFilters = ref(false)
const isLandscapeMobile = ref(window.innerWidth > window.innerHeight)
const signatureCanvasRef = ref(null)
const signaturePadInstance = ref(null)
const visualViewportRef = ref(window.visualViewport || null)

const batchDetail = ref({
  visible: false,
  loading: false,
  error: '',
  inspection: null,
  issues: []
})

const exportState = ref({
  type: ''
})

const signatureDialog = ref({
  visible: false,
  submitting: false,
  error: '',
  record: null
})

const loading = ref(false)
const page = ref(1)
const pageSize = ref(5)
const pageJumpInput = ref('')
const recordImagesReady = ref(false)
let recordImagesReadyTimer = null
let inspectionFetchTimer = null
let inspectionFetchSequence = 0
let suppressNextPageFetch = false

const normalizedKeyword = (value) => String(value || '').trim().toLowerCase()

const normalizeSearchToken = (value) => {
  return String(value || '')
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]+/gu, '')
}

const toPinyinText = (value, options = {}) => {
  const text = String(value || '').trim()
  if (!text) return ''
  try {
    return pinyin(text, {
      toneType: 'none',
      nonZh: 'consecutive',
      ...options
    })
  } catch {
    return ''
  }
}

const buildSearchVariants = (value) => {
  const source = String(value || '').trim()
  if (!source) return []

  return [
    source,
    toPinyinText(source),
    toPinyinText(source, { pattern: 'first' })
  ].map(normalizeSearchToken).filter(Boolean)
}

const matchesSmartSearch = (values, keyword) => {
  const needle = normalizeSearchToken(keyword)
  if (!needle) return true

  return values.some((value) => {
    const variants = buildSearchVariants(value)
    return variants.some((variant) => variant.includes(needle))
  })
}

const uniqueSortedOptions = (values) => {
  return [...new Set(values.map((item) => String(item || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
}

const filterOptionByKeyword = (options, keyword) => {
  const normalized = normalizedKeyword(keyword)
  return options.filter((item) => !normalized || normalizedKeyword(item).includes(normalized))
}

const filterStationOptionByKeyword = (options, keyword) => {
  return options.filter((item) => matchesSmartSearch([item], keyword))
}

const getMultiFilterValues = (key) => Array.isArray(filters.value[key]) ? filters.value[key] : []

const matchesAnySelectedText = (value, selectedValues) => {
  const selected = Array.isArray(selectedValues) ? selectedValues : []
  if (!selected.length) return true
  const normalizedValue = normalizedKeyword(value)
  return selected.some((item) => normalizedValue === normalizedKeyword(item))
}

const matchesSelectedInspector = (record, selectedValues) => {
  if (hideInspectorContactInfo.value) return true
  const selected = Array.isArray(selectedValues) ? selectedValues : []
  if (!selected.length) return true
  const searchValues = getInspectionInspectorSearchValues(record)
  return selected.some((item) => matchesSmartSearch(searchValues, item))
}

const getDatePart = (value) => String(value || '').slice(0, 10)

const isDateInRange = (value, dateFrom, dateTo) => {
  const current = getDatePart(value)
  if (!current) return !dateFrom && !dateTo
  if (dateFrom && current < dateFrom) return false
  if (dateTo && current > dateTo) return false
  return true
}

const getInspectionInspectorSearchValues = (record) => {
  if (hideInspectorContactInfo.value) return []
  const inspectors = Array.isArray(record?.inspectors) ? record.inspectors : []
  const inspectorValues = inspectors.flatMap((item) => [
    item.real_name,
    item.username,
    item.phone
  ])
  return [
    record?.inspector_names,
    record?.inspector_search_text,
    record?.inspector_name,
    record?.inspector_username,
    record?.inspector_phone,
    ...inspectorValues
  ].filter(Boolean)
}

const getInspectionInspectorOptionValues = (record) => {
  if (hideInspectorContactInfo.value) return []
  const inspectors = Array.isArray(record?.inspectors) ? record.inspectors : []
  if (inspectors.length) {
    return inspectors
      .map((item) => item.real_name || item.username || item.phone || '')
      .filter(Boolean)
  }
  return String(record?.inspector_names || record?.inspector_name || record?.inspector_username || '')
    .split(/[、,，/]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

const filteredData = computed(() => list.value)

const stationOptions = computed(() => uniqueSortedOptions(
  filterOptions.value.stations.length
    ? filterOptions.value.stations
    : list.value.map((item) => item.station)
))
const inspectionTableOptions = computed(() => uniqueSortedOptions(
  filterOptions.value.inspectionTables.length
    ? filterOptions.value.inspectionTables
    : list.value.map((item) => item.inspection_table_name)
))
const inspectorOptions = computed(() => uniqueSortedOptions(
  filterOptions.value.inspectors.length
    ? filterOptions.value.inspectors
    : list.value.flatMap(getInspectionInspectorOptionValues)
))

const filteredStationOptions = computed(() => filterStationOptionByKeyword(stationOptions.value, filterSearch.value.station))
const filteredInspectionTableOptions = computed(() => filterOptionByKeyword(inspectionTableOptions.value, filterSearch.value.inspectionTableName))
const filteredInspectorOptions = computed(() => filterStationOptionByKeyword(inspectorOptions.value, filterSearch.value.inspector))

const activeFilterCount = computed(() => {
  return [
    filters.value.month,
    filters.value.dateFrom,
    filters.value.dateTo,
    filters.value.result,
    filters.value.signStatus,
    filters.value.completionStatus,
    ...filters.value.station,
    ...filters.value.inspectionTableName,
    ...(hideInspectorContactInfo.value ? [] : filters.value.inspector)
  ].filter((value) => String(value || '').trim()).length
})

const currentInspectorFilterValue = computed(() => {
  const candidates = [currentRealName, currentUsername]
    .map((value) => String(value || '').trim())
    .filter(Boolean)
  const options = inspectorOptions.value
  return candidates.find((candidate) => options.includes(candidate)) || candidates[0] || ''
})

const getRecordSignFilterStatus = (record) => {
  return record?.sign_status === '已签名确认' ? 'signed' : 'pending'
}

const isInspectionCompleted = (record) => record?.inspector_completion_status === '已确认完成'

const getRecordCompletionFilterStatus = (record) => {
  return isInspectionCompleted(record) ? 'completed' : 'pending'
}

const getCompletionMeta = (record) => {
  if (!isInspectionCompleted(record)) return '待检查人确认'
  const name = record.inspector_completed_by_name || record.inspector_completed_by_username || ''
  const time = record.inspector_completed_at || ''
  const source = record.inspector_completion_source_label || ''
  return [source, name, time].filter(Boolean).join('｜') || '已确认完成'
}

const groupedInspectionGroups = computed(() => {
  const batchMap = new Map()

  filteredData.value.forEach((item) => {
    const batchKey = String(item.batch_id || `${item.date || ''}__${item.station || ''}`)
    if (!batchMap.has(batchKey)) {
      batchMap.set(batchKey, {
        batchKey,
        batchId: item.batch_id,
        date: item.date,
        station: item.station,
        records: [],
        batchIssueCount: 0,
        batchResult: '正常',
        signedCount: 0,
        rowspan: 0
      })
    }

    const batch = batchMap.get(batchKey)
    batch.records.push(item)
    if (item.sign_status === '已签名确认') {
      batch.signedCount += 1
    }
    batch.batchIssueCount += Number(item.issue_count || 0)
    if (item.result === '异常') {
      batch.batchResult = '异常'
    }
  })

  return Array.from(batchMap.values()).map((batch) => {
    batch.rowspan = batch.records.length
    return batch
  })
})

const resolveImage = (path) => {
  const value = String(path || '').trim()
  if (!value) return ''
  if (value.startsWith('http://') || value.startsWith('https://') || value.startsWith('blob:') || value.startsWith('data:')) {
    return value
  }
  if (value.startsWith('/storage/')) {
    return value
  }
  if (value.startsWith('/')) {
    return `/storage${value}`
  }
  return `/storage/${value}`
}

const getInspectionDate = (inspection) => inspection?.inspection_date || inspection?.date || '-'

const getInspectionStation = (inspection) => inspection?.station_name || inspection?.station || '-'

const getInspectorLabel = (inspection) => {
  if (hideInspectorContactInfo.value) return '-'
  if (!inspection) return '-'
  if (Array.isArray(inspection.inspectors) && inspection.inspectors.length) {
    return inspection.inspectors
      .map((item) => {
        const name = item.real_name || item.username || ''
        const phone = item.phone || ''
        if (name && phone) return `${name}（${phone}）`
        return name || phone
      })
      .filter(Boolean)
      .join('、') || '-'
  }
  const name = inspection.inspector_name || inspection.inspector_username || ''
  const phone = inspection.inspector_phone || ''
  if (name && phone) return `${name}（${phone}）`
  return name || phone || '-'
}

const batchDetailInspectorLabel = computed(() => getInspectorLabel(batchDetail.value.inspection))

const canExportBatchDetail = computed(() => {
  return Boolean(batchDetail.value.inspection && !batchDetail.value.loading && !batchDetail.value.error)
})

const exportingBatchDetail = computed(() => Boolean(exportState.value.type))

const showActionMessage = (text, type = 'info') => {
  if (actionMessageTimer) {
    clearTimeout(actionMessageTimer)
    actionMessageTimer = null
  }
  actionMessage.value = { text, type }
  if (!text) return
  actionMessageTimer = setTimeout(() => {
    actionMessage.value = { text: '', type: 'info' }
    actionMessageTimer = null
  }, 2600)
}

const normalizeExportText = (value, fallback = '暂无') => {
  const text = String(value ?? '').trim()
  return text || fallback
}

const escapeHtml = (value) => {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const htmlWithLineBreaks = (value, fallback = '暂无') => {
  return escapeHtml(normalizeExportText(value, fallback)).replace(/\n/g, '<br>')
}

const absoluteFileUrl = (path) => {
  const resolved = resolveImage(path)
  if (!resolved) return ''
  if (resolved.startsWith('data:') || resolved.startsWith('blob:')) return resolved
  try {
    return new URL(resolved, window.location.origin).href
  } catch {
    return resolved
  }
}

const formatLocalDateTime = (date = new Date()) => {
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const exportInfoItem = (label, value) => {
  return `<div class="info-item"><span>${escapeHtml(label)}</span><strong>${htmlWithLineBreaks(value, '-')}</strong></div>`
}

const readBlobAsDataUrl = (blob) => {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onloadend = () => resolve(String(reader.result || ''))
    reader.onerror = () => resolve('')
    reader.readAsDataURL(blob)
  })
}

const buildExportImageUrl = async (path) => {
  const url = absoluteFileUrl(path)
  if (!url || url.startsWith('data:')) return url

  try {
    const response = await fetch(url, { credentials: 'include' })
    if (!response.ok) return url
    const blob = await response.blob()
    return await readBlobAsDataUrl(blob) || url
  } catch {
    return url
  }
}

const exportImageBlock = (label, url) => {
  if (!url) {
    return `<div class="photo-card"><span>${escapeHtml(label)}</span><div class="photo-empty">暂无图片</div></div>`
  }
  return `
    <div class="photo-card">
      <span>${escapeHtml(label)}</span>
      <img src="${escapeHtml(url)}" alt="${escapeHtml(label)}" />
    </div>
  `
}

const buildBatchDetailExportHtml = async () => {
  const inspection = batchDetail.value.inspection || {}
  const issues = batchDetail.value.issues || []
  const title = `${getInspectionStation(inspection)} - ${inspection.inspection_table_name || '检查表'}`
  const exportIssues = await Promise.all(issues.map(async (issue) => ({
    issue,
    issuePhotoUrl: await buildExportImageUrl(issue.issue_photo),
    rectificationPhotoUrl: await buildExportImageUrl(issue.rectification_photo),
    reviewPhotoUrl: await buildExportImageUrl(issue.review_photo)
  })))

  const issueSections = exportIssues.length
    ? exportIssues.map(({ issue, issuePhotoUrl, rectificationPhotoUrl, reviewPhotoUrl }, index) => `
      <section class="issue-card">
        <div class="issue-head">
          <h2>问题 ${index + 1} / #${escapeHtml(issue.id || '-')}</h2>
          <span>${escapeHtml(issue.status || '-')}</span>
        </div>
        <div class="info-grid compact">
          ${exportInfoItem('登记时间', issue.created_at)}
          ${hideInspectorContactInfo.value ? '' : exportInfoItem('检查人', getInspectorLabel(issue))}
          ${exportInfoItem('规范ID', issue.standard_id)}
          ${exportInfoItem('整改结果', issue.rectification_result)}
          ${exportInfoItem('整改时间', issue.rectification_at)}
          ${exportInfoItem('复核结果', issue.review_result)}
          ${exportInfoItem('复核时间', issue.review_at)}
        </div>
        <div class="text-block">
          <h3>引用规范</h3>
          <p>${htmlWithLineBreaks(issue.standard_detail_text)}</p>
        </div>
        <div class="text-block warning">
          <h3>问题描述</h3>
          <p>${htmlWithLineBreaks(issue.description)}</p>
        </div>
        <div class="text-block">
          <h3>整改说明</h3>
          <p>${htmlWithLineBreaks(issue.rectification_note)}</p>
        </div>
        <div class="text-block">
          <h3>督导复核说明</h3>
          <p>${htmlWithLineBreaks(issue.review_note)}</p>
        </div>
        <div class="photo-grid">
          ${exportImageBlock('问题照片', issuePhotoUrl)}
          ${exportImageBlock('整改照片', rectificationPhotoUrl)}
          ${exportImageBlock('复核照片', reviewPhotoUrl)}
        </div>
      </section>
    `).join('')
    : '<section class="issue-card empty">本检查表暂无登记问题。</section>'

  return `
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8">
        <title>${escapeHtml(title)} 巡检问题备份</title>
        <style>
          * { box-sizing: border-box; }
          body {
            margin: 0;
            padding: 32px;
            color: #0f172a;
            font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
            background: #f8fafc;
            line-height: 1.75;
          }
          .document {
            max-width: 960px;
            margin: 0 auto;
            padding: 34px;
            background: #ffffff;
            border: 1px solid #dbe4ee;
            border-radius: 22px;
          }
          .eyebrow {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background: #eff6ff;
            color: #1d4ed8;
            font-size: 12px;
            font-weight: 700;
          }
          h1 {
            margin: 12px 0 8px;
            font-size: 28px;
            line-height: 1.35;
          }
          .subline {
            color: #64748b;
            font-size: 13px;
            margin-bottom: 20px;
          }
          .info-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin: 18px 0;
          }
          .info-grid.compact {
            grid-template-columns: repeat(4, minmax(0, 1fr));
          }
          .info-item {
            padding: 12px 14px;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            background: #f8fafc;
          }
          .info-item span,
          .photo-card span {
            display: block;
            color: #64748b;
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 5px;
          }
          .info-item strong {
            display: block;
            color: #0f172a;
            font-size: 14px;
            word-break: break-word;
          }
          .issue-card {
            break-inside: avoid;
            margin-top: 22px;
            padding: 20px;
            border: 1px solid #dbe4ee;
            border-radius: 18px;
            background: #ffffff;
          }
          .issue-card.empty {
            color: #64748b;
            text-align: center;
          }
          .issue-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            border-bottom: 1px solid #e5edf5;
            padding-bottom: 10px;
            margin-bottom: 12px;
          }
          .issue-head h2 {
            margin: 0;
            font-size: 20px;
          }
          .issue-head span {
            padding: 4px 10px;
            border-radius: 999px;
            background: #eef4ff;
            color: #1d4ed8;
            font-size: 12px;
            font-weight: 700;
          }
          .text-block {
            margin-top: 14px;
            padding: 14px;
            border-radius: 14px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
          }
          .text-block.warning {
            background: #fff7ed;
            border-color: #fed7aa;
          }
          .text-block h3 {
            margin: 0 0 6px;
            font-size: 14px;
            color: #334155;
          }
          .text-block p {
            margin: 0;
            white-space: normal;
            word-break: break-word;
          }
          .photo-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin-top: 14px;
          }
          .photo-card {
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            background: #f8fafc;
            padding: 12px;
          }
          .photo-card img {
            display: block;
            max-width: 100%;
            max-height: 280px;
            margin: 0 auto 8px;
            object-fit: contain;
            background: #ffffff;
          }
          .photo-empty {
            min-height: 90px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #94a3b8;
            background: #ffffff;
            border-radius: 10px;
          }
          @media print {
            body { background: #ffffff; padding: 0; }
            .document { border: none; border-radius: 0; max-width: none; }
          }
        </style>
      </head>
      <body>
        <main class="document">
          <div class="eyebrow">巡检问题备份</div>
          <h1>${escapeHtml(title)}</h1>
          <div class="subline">导出时间：${escapeHtml(formatLocalDateTime())}</div>
          <div class="info-grid">
            ${exportInfoItem('巡检日期', getInspectionDate(inspection))}
            ${hideInspectorContactInfo.value ? '' : exportInfoItem('检查人', getInspectorLabel(inspection))}
            ${exportInfoItem('站点', getInspectionStation(inspection))}
            ${exportInfoItem('所属片区', inspection.station_region)}
            ${exportInfoItem('站点地址', inspection.station_address)}
            ${exportInfoItem('站点负责人', inspection.station_manager_name)}
            ${exportInfoItem('负责人手机号', inspection.station_manager_phone)}
            ${exportInfoItem('检查表', inspection.inspection_table_name)}
            ${exportInfoItem('问题数量', issues.length)}
            ${exportInfoItem('签名状态', inspection.sign_status || '待签名确认')}
            ${exportInfoItem('站经理签名人', inspection.station_manager_signed_name)}
            ${exportInfoItem('签名时间', inspection.station_manager_signed_at)}
          </div>
          ${issueSections}
        </main>
      </body>
    </html>
  `
}

const exportBatchDetail = async () => {
  if (!canExportBatchDetail.value || exportingBatchDetail.value) return
  const printWindow = window.open('', '_blank')

  if (!printWindow) {
    window.alert('浏览器阻止了导出窗口，请允许弹窗后再导出 PDF。')
    return
  }

  try {
    exportState.value.type = 'pdf'
    printWindow.document.open()
    printWindow.document.write('<!doctype html><meta charset="utf-8"><title>正在生成PDF</title><body style="font-family: sans-serif; padding: 32px;">正在生成巡检问题备份，请稍候...</body>')
    printWindow.document.close()

    const html = await buildBatchDetailExportHtml()

    printWindow.document.open()
    printWindow.document.write(html)
    printWindow.document.close()
    printWindow.focus()
    printWindow.setTimeout(() => {
      printWindow.print()
    }, 500)
  } catch {
    if (printWindow && !printWindow.closed) {
      printWindow.document.open()
      printWindow.document.write('<!doctype html><meta charset="utf-8"><title>导出失败</title><body style="font-family: sans-serif; padding: 32px;">导出失败，请稍后重试。</body>')
      printWindow.document.close()
    }
    window.alert('导出失败，请稍后重试。')
  } finally {
    exportState.value.type = ''
  }
}

const openInspectionDetail = async (record) => {
  if (!record?.id) {
    batchDetail.value = {
      visible: true,
      loading: false,
      error: '当前检查表缺少巡检记录编号，无法查看详情。',
      inspection: record || null,
      issues: []
    }
    return
  }

  batchDetail.value = {
    visible: true,
    loading: true,
    error: '',
    inspection: record,
    issues: []
  }

  try {
    const userId = localStorage.getItem('user_id') || ''
    const response = await axios.get(`/api/inspections/${record.id}/issues`, {
      params: { user_id: userId }
    })
    batchDetail.value.loading = false
    batchDetail.value.inspection = response.data?.inspection || record
    batchDetail.value.issues = response.data?.issues || []
  } catch (error) {
    batchDetail.value.loading = false
    batchDetail.value.error = error?.response?.data?.error || '加载本表问题失败。'
    batchDetail.value.issues = []
  }
}

const closeBatchDetail = () => {
  batchDetail.value = {
    visible: false,
    loading: false,
    error: '',
    inspection: null,
    issues: []
  }
}

const canSignInspectionRecord = (record) => Boolean(record?.can_sign_record)

const canCompleteInspectionRecord = (record) => Boolean(record?.can_complete_record)

const canDeleteInspectionRecord = (record) => Boolean(record?.can_delete_record)

const canResetInspectionSignature = (record) => Boolean(record?.can_reset_signature)

const getTotalIssueCount = (record) => Number(record?.total_issue_count ?? record?.issue_count ?? 0) || 0

const getPendingAuditCount = (record) => Number(record?.pending_audit_count || 0) || 0

const getAuditedIssueCount = (record) => Number(record?.audited_issue_count || 0) || 0

const shouldShowSignatureProgress = (record) => (
  record?.sign_status !== '已签名确认' &&
  getPendingAuditCount(record) > 0
)

const getSignatureProgressTitle = (record) => {
  return getPendingAuditCount(record) > 0 ? '等待问题审核' : '待站经理签名'
}

const getSignatureProgressText = (record) => {
  return getSignatureProgressLines(record).join('')
}

const getSignatureProgressLines = (record) => {
  const total = getTotalIssueCount(record)
  const pending = getPendingAuditCount(record)
  if (pending > 0) {
    return [
      '本表问题审核完成后进入签字环节：',
      `已审核 ${getAuditedIssueCount(record)}/${total}，剩余 ${pending} 条。`
    ]
  }
  return ['审核已完成，请等待站经理账号进行本表签字确认。']
}

const getSignatureProgressWidth = (record) => {
  const total = getTotalIssueCount(record)
  if (total <= 0) return '100%'
  const done = Math.min(getAuditedIssueCount(record), total)
  return `${Math.round((done / total) * 100)}%`
}

const completeInspectionRecord = async (record) => {
  if (!record?.id || completingInspectionId.value) return
  const confirmed = window.confirm(
    `确认【${record.station || '当前站点'}｜${record.inspection_table_name || '当前检查表'}】已经检查完成吗？\n\n确认后，本周期该站点这张检查表将封存，不能继续新增问题；已记录问题仍按权限维护。`
  )
  if (!confirmed) return

  try {
    completingInspectionId.value = record.id
    showActionMessage('')
    const userId = localStorage.getItem('user_id') || ''
    const response = await axios.post(`/api/inspections/${record.id}/complete`, {
      user_id: userId
    })
    if (String(batchDetail.value.inspection?.id || '') === String(record.id)) {
      batchDetail.value.inspection = {
        ...(batchDetail.value.inspection || {}),
        inspector_completion_status: '已确认完成',
        inspector_completion_source_label: '检查人手动确认'
      }
    }
    await fetchInspections()
    showActionMessage(response.data?.message || '检查表已确认完成。', 'success')
  } catch (error) {
    showActionMessage(error?.response?.data?.error || '确认完成失败。', 'error')
  } finally {
    completingInspectionId.value = null
  }
}

const deleteInspectionRecord = async (record) => {
  if (!record?.id || deletingInspectionId.value) return

  const confirmed = window.confirm(
    `确定删除【${record.station || '当前站点'}｜${record.inspection_table_name || '当前检查表'}】这条巡检记录吗？\n\n删除后会同步删除本记录下的所有巡检问题，并重新计算关联巡检计划完成状态。此操作不可恢复。`
  )
  if (!confirmed) return

  try {
    deletingInspectionId.value = record.id
    showActionMessage('')
    const userId = localStorage.getItem('user_id') || ''
    const response = await axios.delete(`/api/inspections/${record.id}`, {
      data: { user_id: userId }
    })
    if (String(batchDetail.value.inspection?.id || '') === String(record.id)) {
      closeBatchDetail()
    }
    await fetchInspections()
    showActionMessage(response.data?.message || '巡检记录已删除。', 'success')
  } catch (error) {
    showActionMessage(error?.response?.data?.error || '巡检记录删除失败。', 'error')
  } finally {
    deletingInspectionId.value = null
  }
}

const resetInspectionSignature = async (record) => {
  if (!record?.id || resettingSignatureId.value) return

  const confirmed = window.confirm(
    `确定重置【${record.station || '当前站点'}｜${record.inspection_table_name || '当前检查表'}】的站经理签名吗？\n\n重置后只撤销站经理签名，并将本记录下的问题退回待审核；检查人完成确认状态保持不变，重新审核完成后可再次签字。`
  )
  if (!confirmed) return

  try {
    resettingSignatureId.value = record.id
    showActionMessage('')
    const userId = localStorage.getItem('user_id') || ''
    const response = await axios.post(`/api/inspections/${record.id}/signature/reset`, {
      user_id: userId
    })
    if (String(batchDetail.value.inspection?.id || '') === String(record.id)) {
      batchDetail.value.inspection = {
        ...(batchDetail.value.inspection || {}),
        sign_status: '待签名确认',
        station_manager_signed_name: '',
        station_manager_signature_path: '',
        station_manager_signed_at: ''
      }
    }
    await fetchInspections()
    window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
    window.dispatchEvent(new Event('my-pending-rectification-refresh'))
    showActionMessage(response.data?.message || '站经理签名已重置。', 'success')
  } catch (error) {
    showActionMessage(error?.response?.data?.error || '重置站经理签名失败。', 'error')
  } finally {
    resettingSignatureId.value = null
  }
}

const getSignatureCanvas = () => signatureCanvasRef.value

const initSignaturePad = () => {
  const canvas = getSignatureCanvas()
  if (!canvas) return

  const existingInstance = signaturePadInstance.value
  const existingData = existingInstance && !existingInstance.isEmpty()
    ? existingInstance.toData()
    : null

  if (existingInstance) {
    existingInstance.off()
  }

  const ratio = Math.max(window.devicePixelRatio || 1, 1)
  const rect = canvas.getBoundingClientRect()
  const width = Math.max(Math.round(rect.width || 0), 1)
  const height = Math.max(Math.round(rect.height || 0), 1)

  canvas.width = width * ratio
  canvas.height = height * ratio

  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.scale(ratio, ratio)

  signaturePadInstance.value = new SignaturePad(canvas, {
    minWidth: 1.2,
    maxWidth: 2.8,
    penColor: '#0f172a',
    backgroundColor: 'rgba(255,255,255,0)'
  })

  signaturePadInstance.value.onBegin = () => {
    if (signatureDialog.value) {
      signatureDialog.value.error = ''
    }
  }

  if (existingData && existingData.length) {
    signaturePadInstance.value.fromData(existingData)
  }
}


const handleViewportResize = () => {
  isMobileView.value = detectMobileViewport()
  isLandscapeMobile.value = window.innerWidth > window.innerHeight
}

const openSignatureDialog = async (record) => {
  signatureDialog.value = {
    visible: true,
    submitting: false,
    error: '',
    record
  }

  await nextTick()
}

const closeSignatureDialog = () => {
  if (signaturePadInstance.value) {
    signaturePadInstance.value.off()
  }
  signaturePadInstance.value = null
  signatureDialog.value = {
    visible: false,
    submitting: false,
    error: '',
    record: null
  }
}

const clearSignature = () => {
  if (signaturePadInstance.value) {
    signaturePadInstance.value.clear()
  }
  if (signatureDialog.value) {
    signatureDialog.value.error = ''
  }
}

const submitInspectionSignature = async () => {
  const record = signatureDialog.value.record
  if (!record?.id) {
    signatureDialog.value.error = '当前检查表缺少巡检记录编号，无法提交签名。'
    return
  }

  if (!signaturePadInstance.value || signaturePadInstance.value.isEmpty()) {
    signatureDialog.value.error = '请先完成站经理签名。'
    return
  }

  if (isMobileView.value && !isLandscapeMobile.value) {
    signatureDialog.value.error = '请先将手机横屏后再完成签名。'
    return
  }

  try {
    signatureDialog.value.submitting = true
    signatureDialog.value.error = ''

    const userId = localStorage.getItem('user_id') || ''
    const dataUrl = signaturePadInstance.value.toDataURL('image/png')
    const blob = await fetch(dataUrl).then((res) => res.blob())
    const formData = new FormData()
    formData.append('user_id', userId)
    formData.append('signed_name', `${record.station || '站点'}站经理`)
    formData.append('signature', new File([blob], 'signature.png', { type: 'image/png' }))

    await axios.post(`/api/inspections/${record.id}/sign`, formData)
    closeSignatureDialog()
    await fetchInspections()
    window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
    window.dispatchEvent(new Event('my-pending-rectification-refresh'))
  } catch (error) {
    signatureDialog.value.error = error?.response?.data?.error || '提交签名失败。'
  } finally {
    signatureDialog.value.submitting = false
  }
}

const totalPage = computed(() => Math.max(1, Math.ceil(totalRecords.value / pageSize.value)))

const visiblePageItems = computed(() => {
  const total = totalPage.value
  const current = page.value

  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => {
      const value = index + 1
      return { type: 'page', value, key: `page-${value}` }
    })
  }

  const pages = new Set([1, total, current, current - 1, current + 1])
  if (current <= 3) {
    pages.add(2)
    pages.add(3)
    pages.add(4)
  }
  if (current >= total - 2) {
    pages.add(total - 1)
    pages.add(total - 2)
    pages.add(total - 3)
  }

  const sortedPages = [...pages]
    .filter((value) => value >= 1 && value <= total)
    .sort((a, b) => a - b)

  const result = []
  sortedPages.forEach((value, index) => {
    const previous = sortedPages[index - 1]
    if (index > 0 && value - previous > 1) {
      result.push({ type: 'ellipsis', key: `ellipsis-${previous}-${value}` })
    }
    result.push({ type: 'page', value, key: `page-${value}` })
  })

  return result
})

const paginatedInspectionGroups = computed(() => groupedInspectionGroups.value)

const shouldShowStationDivider = (batch, batchIndex) => {
  if (batchIndex === 0) return true
  const previousBatch = paginatedInspectionGroups.value[batchIndex - 1]
  return previousBatch?.station !== batch?.station
}

const getRecordTableRowClasses = (rowIndex) => ({
  'batch-group-start-row': rowIndex === 0
})

const scheduleFetchInspections = () => {
  if (inspectionFetchTimer) {
    clearTimeout(inspectionFetchTimer)
  }
  inspectionFetchTimer = window.setTimeout(() => {
    inspectionFetchTimer = null
    fetchInspections()
  }, 120)
}

watch([filters, pageSize], () => {
  page.value = 1
  scheduleFetchInspections()
}, { deep: true })

watch(page, () => {
  if (suppressNextPageFetch) {
    suppressNextPageFetch = false
    return
  }
  scheduleFetchInspections()
})

watch(totalPage, (value) => {
  if (page.value > value) {
    page.value = value
  }
})

const scheduleRecordImageLoading = () => {
  recordImagesReady.value = false
  if (recordImagesReadyTimer) {
    clearTimeout(recordImagesReadyTimer)
  }
  recordImagesReadyTimer = window.setTimeout(() => {
    recordImagesReady.value = true
    recordImagesReadyTimer = null
  }, 160)
}

watch(
  () => paginatedInspectionGroups.value.flatMap((group) => group.records.map((record) => record.id)).join(','),
  scheduleRecordImageLoading,
  { immediate: true }
)

watch(
  () => [signatureDialog.value.visible, isLandscapeMobile.value, isMobileView.value],
  async ([visible, landscape, mobile]) => {
    if (!visible) return
    await nextTick()
    if (!mobile || landscape) {
      initSignaturePad()
    }
  }
)

watch(
  () => signatureDialog.value.visible,
  (visible) => {
    document.body.style.overflow = visible ? 'hidden' : ''
    document.documentElement.style.overflow = visible ? 'hidden' : ''
  }
)

const serializeMultiFilter = (value) => JSON.stringify(Array.isArray(value) ? value : [])

const fetchInspections = async (options = {}) => {
  const sequence = ++inspectionFetchSequence
  try {
    loading.value = true
    const userId = localStorage.getItem('user_id') || ''
    const response = await axios.get('/api/inspections', {
      params: {
        user_id: userId,
        page: page.value,
        page_size: pageSize.value,
        include_options: options?.forceOptions || !filterOptionsLoaded.value ? 1 : 0,
        month: filters.value.month,
        date_from: filters.value.dateFrom,
        date_to: filters.value.dateTo,
        stations: serializeMultiFilter(filters.value.station),
        inspection_tables: serializeMultiFilter(filters.value.inspectionTableName),
        inspectors: serializeMultiFilter(filters.value.inspector),
        result: filters.value.result,
        sign_status: filters.value.signStatus,
        completion_status: filters.value.completionStatus
      }
    })
    if (sequence !== inspectionFetchSequence) return

    const payload = response.data || {}
    if (Array.isArray(payload)) {
      list.value = payload
      totalRecords.value = payload.length
      return
    }

    list.value = Array.isArray(payload.items) ? payload.items : []
    totalRecords.value = Number(payload.total || 0)

    if (payload.filter_options) {
      filterOptions.value = {
        stations: Array.isArray(payload.filter_options.stations) ? payload.filter_options.stations : [],
        inspectionTables: Array.isArray(payload.filter_options.inspection_tables) ? payload.filter_options.inspection_tables : [],
        inspectors: Array.isArray(payload.filter_options.inspectors) ? payload.filter_options.inspectors : []
      }
      filterOptionsLoaded.value = true
    }

    const serverPage = Number(payload.page || page.value)
    if (Number.isFinite(serverPage) && serverPage >= 1 && serverPage !== page.value) {
      suppressNextPageFetch = true
      page.value = serverPage
    }
  } catch (error) {
    if (sequence !== inspectionFetchSequence) return
    list.value = []
    totalRecords.value = 0
  } finally {
    if (sequence === inspectionFetchSequence) {
      loading.value = false
    }
  }
}

const resetFilters = () => {
  const nextDefaultRange = getDefaultDateRange()
  filters.value = {
    month: '',
    dateFrom: nextDefaultRange.dateFrom,
    dateTo: nextDefaultRange.dateTo,
    station: [],
    inspectionTableName: [],
    inspector: [],
    result: '',
    signStatus: '',
    completionStatus: ''
  }
  filterSearch.value = {
    station: '',
    inspectionTableName: '',
    inspector: ''
  }
  closeAllDropdowns()
}

const filterMyTodayRecords = () => {
  const inspector = currentInspectorFilterValue.value
  if (!inspector) {
    showActionMessage('当前账号缺少姓名，暂时不能自动筛选。', 'error')
    return
  }
  filters.value = {
    month: '',
    dateFrom: formatLocalDate(),
    dateTo: formatLocalDate(),
    station: [],
    inspectionTableName: [],
    inspector: [inspector],
    result: '',
    signStatus: '',
    completionStatus: ''
  }
  filterSearch.value = {
    station: '',
    inspectionTableName: '',
    inspector: ''
  }
  closeAllDropdowns()
  showMobileFilters.value = false
  showActionMessage('已筛选我今天的巡检记录。', 'success')
}

const handleRecordMonthChange = () => {
  if (!filters.value.month) return
  filters.value.dateFrom = ''
  filters.value.dateTo = ''
}

const handleRecordDateRangeChange = () => {
  if (!filters.value.dateFrom && !filters.value.dateTo) return
  filters.value.month = ''
}

const goToPage = (targetPage) => {
  const normalizedPage = Number.parseInt(targetPage, 10)
  if (!Number.isFinite(normalizedPage)) return
  page.value = Math.min(Math.max(normalizedPage, 1), totalPage.value)
}

const prevPage = () => {
  goToPage(page.value - 1)
}

const nextPage = () => {
  goToPage(page.value + 1)
}

const jumpToInputPage = () => {
  goToPage(pageJumpInput.value)
  pageJumpInput.value = ''
}

const openFilterDropdown = (key) => {
  dropdownVisible.value[key] = true
}

const isMultiFilterSelected = (key, value) => {
  return getMultiFilterValues(key).includes(value)
}

const toggleMultiFilter = (key, value) => {
  const selected = getMultiFilterValues(key)
  filters.value[key] = selected.includes(value)
    ? selected.filter((item) => item !== value)
    : [...selected, value]
  filterSearch.value[key] = ''
  dropdownVisible.value[key] = true
}

const removeMultiFilterValue = (key, value) => {
  filters.value[key] = getMultiFilterValues(key).filter((item) => item !== value)
}

const focusMultiFilterInput = async (key) => {
  openFilterDropdown(key)
  await nextTick()
  const refMap = {
    station: stationFilterInputRef,
    inspectionTableName: inspectionTableFilterInputRef,
    inspector: inspectorFilterInputRef
  }
  refMap[key]?.value?.focus()
}

const closeAllDropdowns = () => {
  dropdownVisible.value = {
    station: false,
    inspectionTableName: false,
    inspector: false
  }
}

const handleClickOutside = (event) => {
  if (stationSelectRef.value && !stationSelectRef.value.contains(event.target)) {
    dropdownVisible.value.station = false
  }
  if (inspectionTableSelectRef.value && !inspectionTableSelectRef.value.contains(event.target)) {
    dropdownVisible.value.inspectionTableName = false
  }
  if (inspectorSelectRef.value && !inspectorSelectRef.value.contains(event.target)) {
    dropdownVisible.value.inspector = false
  }
}

const statusClass = (value) => {
  if (value === '正常') return 'status-tag success'
  if (value === '异常') return 'status-tag danger'
  return 'status-tag'
}

const handleVisualViewportChange = () => {
  handleViewportResize()
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('resize', handleViewportResize)
  visualViewportRef.value?.addEventListener('resize', handleVisualViewportChange)
  fetchInspections()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('resize', handleViewportResize)
  visualViewportRef.value?.removeEventListener('resize', handleVisualViewportChange)
  if (actionMessageTimer) {
    clearTimeout(actionMessageTimer)
    actionMessageTimer = null
  }
  if (recordImagesReadyTimer) {
    clearTimeout(recordImagesReadyTimer)
  }
  if (inspectionFetchTimer) {
    clearTimeout(inspectionFetchTimer)
    inspectionFetchTimer = null
  }
  if (signaturePadInstance.value) {
    signaturePadInstance.value.off()
  }
  signaturePadInstance.value = null
  document.body.style.overflow = ''
  document.documentElement.style.overflow = ''
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
}

.page-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 14px;
}

.page-header h2 {
  margin: 0;
  font-size: 34px;
  color: #0f172a;
}

.record-action-toast {
  position: fixed;
  left: 50%;
  top: 84px;
  z-index: 3000;
  transform: translateX(-50%);
  min-width: min(420px, calc(100vw - 32px));
  padding: 14px 18px;
  text-align: center;
  font-size: 14px;
  font-weight: 800;
  color: #0f172a;
  border-color: rgba(37, 99, 235, 0.22);
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.16);
}

.record-action-toast.success {
  color: #166534;
  border-color: rgba(22, 163, 74, 0.28);
  background: rgba(240, 253, 244, 0.98);
}

.record-action-toast.error {
  color: #991b1b;
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(254, 242, 242, 0.98);
}

.record-action-toast-enter-active,
.record-action-toast-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.record-action-toast-enter-from,
.record-action-toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px) scale(0.98);
}

.filter-card,
.table-card {
  padding: 20px;
}

.filter-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.filter-kicker {
  display: inline-flex;
  margin-bottom: 8px;
  padding: 5px 10px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 900;
}

.filter-head h3 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
}

.filter-head-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.active-filter-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 0 11px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.mobile-filter-toggle {
  display: none;
}

.today-filter-btn {
  display: inline-flex;
  border-color: rgba(37, 99, 235, 0.28);
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.14);
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(220px, 1fr));
  gap: 16px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-item label {
  font-size: 14px;
  font-weight: 700;
  color: #374151;
}

.search-select {
  position: relative;
}

.multi-search-select {
  min-width: 0;
}

.search-select input {
  width: 100%;
  box-sizing: border-box;
}

.multi-select-control {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  padding: 5px 8px;
  background: #fff;
  box-sizing: border-box;
  cursor: text;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.multi-select-control:focus-within {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.multi-selected-values {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}

.multi-selected-values input {
  flex: 1 1 110px;
  min-width: 88px;
  height: 30px;
  border: none;
  outline: none;
  padding: 0 4px;
  background: transparent;
  font-size: 14px;
  color: #0f172a;
}

.multi-selected-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 100%;
  padding: 4px 7px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.2;
}

.multi-selected-chip button {
  width: 16px;
  height: 16px;
  border: none;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.12);
  color: #1d4ed8;
  font-weight: 900;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.multi-selected-count {
  flex: 0 0 auto;
  padding: 3px 7px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.search-select-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  max-height: 240px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #dbe4ee;
  border-radius: 14px;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.12);
  z-index: 200;
}

.search-select-option {
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid #eef2f7;
}

.multi-select-option {
  width: 100%;
  border-top: none;
  border-left: none;
  border-right: none;
  background: #fff;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 9px;
}

.multi-select-option.selected {
  background: #eff6ff;
}

.multi-option-check {
  width: 18px;
  height: 18px;
  border-radius: 6px;
  border: 1px solid #bfdbfe;
  background: #fff;
  color: #1d4ed8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 900;
  flex: 0 0 auto;
}

.search-select-option:last-child {
  border-bottom: none;
}

.search-select-option:hover {
  background: #f8fafc;
}

.search-select-empty {
  padding: 12px;
  color: #64748b;
  font-size: 13px;
}

.option-main {
  font-size: 14px;
  color: #0f172a;
}

.filter-item input,
.filter-item select {
  width: 100%;
  height: 42px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0 12px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
  box-sizing: border-box;
  color-scheme: light;
}

.filter-item .multi-selected-values input {
  height: 30px;
  border: none;
  border-radius: 0;
  padding: 0 4px;
  background: transparent;
  box-shadow: none;
}

.filter-item select {
  appearance: none;
  background-image:
    linear-gradient(45deg, transparent 50%, #64748b 50%),
    linear-gradient(135deg, #64748b 50%, transparent 50%);
  background-position:
    calc(100% - 18px) 50%,
    calc(100% - 13px) 50%;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
  padding-right: 34px;
}

.filter-actions {
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 14px;
  border-top: 1px solid #eef2f7;
}

.filter-quick-actions,
.filter-main-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-main-actions {
  justify-content: flex-end;
}

.btn {
  height: 40px;
  padding: 0 16px;
  border-radius: 10px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-sm {
  height: 34px;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 700;
}

.btn-primary {
  border-color: #1d4ed8;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #fff;
  font-weight: 700;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.2);
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
}

.btn-danger {
  border-color: #fecaca;
  background: #fff1f2;
  color: #b91c1c;
  font-weight: 800;
}

.btn-danger:hover:not(:disabled) {
  border-color: #fca5a5;
  background: #ffe4e6;
}

.signature-action-btn {
  width: auto;
  min-width: 118px;
  min-height: 38px;
  white-space: nowrap;
  line-height: 1.3;
  padding: 8px 13px;
}

.batch-action-btn {
  width: auto;
  min-width: 96px;
  white-space: nowrap;
  line-height: 1.3;
  padding: 8px 12px;
}

.record-action-stack {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.mobile-record-list {
  display: none;
}

.mobile-pagination-bar {
  display: none;
}

.mobile-record-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-record-card {
  padding: 15px;
  border-radius: 22px;
  background:
    radial-gradient(circle at 95% 0%, rgba(37, 99, 235, 0.1), transparent 30%),
    rgba(255, 255, 255, 0.98);
}

.mobile-card-head {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}

.mobile-card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mobile-card-station {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}

.mobile-card-date {
  font-size: 13px;
  color: #64748b;
}

.mobile-card-body {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.mobile-card-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 5px;
  min-width: 0;
  padding: 10px;
  border: 1px solid #e7edf4;
  border-radius: 14px;
  background: #f8fafc;
}

.mobile-card-row span {
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
  line-height: 1.3;
}

.mobile-card-row strong {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  text-align: left;
}


.mobile-batch-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px dashed #dbe4ee;
}

.mobile-batch-item {
  padding: 12px;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #e7edf4;
}

.mobile-batch-item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.mobile-batch-table-name {
  min-width: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.6;
}

.mobile-batch-item-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 8px;
}

.mobile-meta-pill {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 9px;
  border-radius: 999px;
  background: #eef2f7;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.mobile-meta-pill.signed {
  background: #ecfdf5;
  color: #047857;
}

.mobile-batch-item-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.mobile-action-btn {
  min-width: 0;
  width: 100%;
  min-height: 40px;
  height: 40px;
  padding: 0 8px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 900;
  line-height: 1;
  white-space: nowrap;
}

.mobile-action-btn:only-child {
  grid-column: 1 / -1;
}

.mobile-action-delete:nth-child(3) {
  grid-column: 1 / -1;
}

.mobile-signature-box {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid #dbe4ee;
  border-radius: 14px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.mobile-sign-progress-card {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid #bfdbfe;
  background: linear-gradient(135deg, #eff6ff 0%, #f8fbff 100%);
}

.mobile-sign-progress-card strong {
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 950;
}

.mobile-sign-progress-card span {
  color: #475569;
  font-size: 12px;
  line-height: 1.7;
}

.mobile-signature-label {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  margin-bottom: 10px;
}

.mobile-signature-time {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
}

.mobile-empty {
  margin-top: 2px;
}

.empty-state-card,
.empty-state-inline {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 8px;
  padding: 34px 22px;
  color: #475569;
}

.empty-state-card {
  min-height: 260px;
  background:
    radial-gradient(circle at 50% 0%, rgba(37, 99, 235, 0.12), transparent 36%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.94));
}

.empty-state-inline {
  min-height: 220px;
  padding: 32px 20px;
}

.empty-state-orb {
  width: 54px;
  height: 54px;
  border-radius: 20px;
  background:
    radial-gradient(circle at 30% 25%, rgba(255, 255, 255, 0.9), transparent 28%),
    linear-gradient(135deg, #dbeafe 0%, #93c5fd 100%);
  box-shadow:
    0 16px 34px rgba(37, 99, 235, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.86);
}

.empty-state-orb.loading {
  animation: emptyPulse 1.45s ease-in-out infinite;
}

.empty-state-kicker {
  margin-top: 4px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.empty-state-card h3,
.empty-state-inline h3 {
  margin: 0;
  color: #0f172a;
  font-size: 20px;
  line-height: 1.35;
}

.empty-state-card p,
.empty-state-inline p {
  max-width: 420px;
  margin: 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
}

.empty-state-action {
  margin-top: 8px;
}

@keyframes emptyPulse {
  0%,
  100% {
    transform: translateY(0) scale(1);
    opacity: 0.82;
  }

  50% {
    transform: translateY(-4px) scale(1.03);
    opacity: 1;
  }
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.btn-secondary:hover:not(:disabled) {
  background: #f9fafb;
}

.table-scroll-wrap {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  overflow: hidden;
}

.table-scroll {
  max-height: 60vh;
  overflow: auto;
}

.records-table {
  width: 100%;
  min-width: 1120px;
  border-collapse: collapse;
}

.records-table th,
.records-table td {
  border: 1px solid #e5e7eb;
  padding: 12px 14px;
  text-align: left;
  vertical-align: middle;
  font-size: 14px;
  color: #111827;
  word-break: break-word;
}

.records-table th {
  background: #f8fafc;
  font-weight: 700;
  white-space: nowrap;
}

.records-table tbody tr {
  transition: background 0.18s ease;
}

.records-table tbody tr:not(.station-divider-row):hover td {
  background: #f8fbff;
}

.station-divider-row td {
  padding: 10px 0 0;
  border: 0;
  background: #fff;
}

.station-divider-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 10px 14px 10px 12px;
  border-top: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
  border-left: 4px solid #93c5fd;
  background: linear-gradient(90deg, #f8fbff 0%, #f8fafc 100%);
}

.station-divider-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.station-divider-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
  flex-shrink: 0;
}

.station-divider-main strong {
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.station-divider-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.station-divider-meta span {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding-left: 9px;
  border-left: 1px solid #dbe4ee;
}

.station-divider-meta span:first-child {
  padding-left: 0;
  border-left: 0;
}

.batch-group-start-row > td {
  border-top-color: #dbe4ee;
}

.long-text {
  min-width: 220px;
  white-space: normal;
  line-height: 1.7;
}

.batch-merged-cell {
  background: #fcfdff;
}

.batch-main-cell {
  font-weight: 700;
  color: #0f172a;
  vertical-align: middle;
  text-align: center;
}

.batch-date-cell {
  min-width: 122px;
}

.batch-station-cell {
  min-width: 168px;
}

.batch-date-content,
.batch-station-content {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 58px;
  text-align: center;
}

.batch-date-text,
.batch-station-name {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  max-width: 100%;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.55;
}

.batch-date-text {
  color: #475569;
  font-weight: 800;
}

.batch-station-name {
  padding: 6px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
  font-size: 15px;
  font-weight: 900;
}

.batch-action-cell,
.batch-completion-cell,
.batch-signature-cell {
  vertical-align: middle;
  text-align: center !important;
}

.batch-action-cell {
  min-width: 132px;
}

.batch-completion-cell {
  min-width: 168px;
  padding: 10px 12px;
}

.batch-signature-cell {
  min-width: 218px;
  padding: 10px 12px;
}

.batch-completion-cell > *,
.batch-signature-cell > * {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: auto;
  margin-right: auto;
}

.batch-completion-cell .btn,
.batch-signature-cell .btn {
  justify-content: center;
  margin-left: auto;
  margin-right: auto;
}

.batch-completion-cell > .signature-status-badge,
.batch-signature-cell > .signature-status-badge {
  width: fit-content;
}

.completion-preview-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  max-width: 220px;
  text-align: center;
}

.signature-preview-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-align: center;
}

.signature-signed-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  text-align: center;
}

.signature-reset-btn {
  min-width: 58px;
  border-color: #fecaca;
  color: #b91c1c;
  background: #fff7f7;
}

.signature-reset-btn:hover:not(:disabled) {
  border-color: #fca5a5;
  background: #fee2e2;
}

.signature-reset-locked {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  max-width: 180px;
  padding: 7px 10px;
  border-radius: 999px;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.4;
  text-align: center;
  white-space: normal;
}

.signature-preview-image {
  width: 220px;
  max-width: 100%;
  height: 88px;
  object-fit: contain;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  padding: 8px;
  box-sizing: border-box;
}

.signature-preview-placeholder {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 220px;
  max-width: 100%;
  height: 88px;
  border: 1px dashed #bfdbfe;
  border-radius: 12px;
  background: linear-gradient(135deg, #f8fbff 0%, #eef6ff 100%);
  color: #2563eb;
  font-size: 13px;
  font-weight: 900;
  box-sizing: border-box;
}

.signature-preview-time {
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
  text-align: center;
}

.signature-status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.4;
  text-align: center;
}

.signature-status-badge.success {
  background: #ecfdf5;
  color: #15803d;
}

.signature-status-badge.pending {
  background: #eff6ff;
  color: #1d4ed8;
}

.signature-progress-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  max-width: 220px;
  margin: 0 auto;
}

.signature-progress-box p {
  margin: 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.7;
  text-align: center;
}

.signature-progress-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  white-space: normal;
}

.signature-progress-track {
  width: 100%;
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #dbeafe;
}

.signature-progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb 0%, #14b8a6 100%);
  transition: width 0.25s ease;
}

.signature-dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.signature-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 20px;
  align-items: stretch;
}

.signature-side-card {
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.signature-side-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
}

.signature-side-desc {
  font-size: 13px;
  color: #475569;
  line-height: 1.8;
}

.signature-side-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.7;
}

.signature-pad-card-landscape {
  min-width: 0;
}

.signature-pad-wrap-landscape {
  min-height: 0;
}

.signature-canvas-landscape {
  height: 420px;
}

.signature-dialog {
  width: min(1120px, 100%);
  max-height: min(92vh, 980px);
  padding: 24px;
  overflow: auto;
}


.signature-pad-card {
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #fff;
  padding: 18px;
}

.signature-pad-head {
  margin-bottom: 14px;
}


.signature-pad-wrap {
  border: 1px dashed #cbd5e1;
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  overflow: hidden;
}

.signature-canvas {
  display: block;
  width: 100%;
  height: 320px;
  touch-action: none;
  cursor: crosshair;
}

.signature-pad-actions {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.signature-error {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
  line-height: 1.7;
}

.empty-row {
  text-align: center;
  color: #6b7280;
  padding: 0 !important;
  background:
    radial-gradient(circle at 50% 0%, rgba(37, 99, 235, 0.08), transparent 32%),
    #fff;
}

.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.pagination-summary {
  color: #475569;
  font-size: 14px;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.pagination-size-control,
.pagination-nav-row,
.pagination-page-list,
.pagination-jump {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.pagination-size-control label,
.pagination-jump span {
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
  white-space: nowrap;
}

.pagination-controls select,
.pagination-jump input {
  height: 40px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0 10px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
}

.pagination-jump input {
  width: 78px;
  text-align: center;
}

.pagination-btn {
  min-width: 72px;
}

.pagination-page-list {
  padding: 4px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
}

.pagination-page-btn {
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #475569;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
  transition: all 0.18s ease;
}

.pagination-page-btn:hover {
  background: #e0edff;
  color: #1d4ed8;
}

.pagination-page-btn.active {
  background: #2563eb;
  color: #fff;
  box-shadow: 0 8px 16px rgba(37, 99, 235, 0.22);
}

.pagination-ellipsis {
  min-width: 28px;
  text-align: center;
  color: #94a3b8;
  font-weight: 900;
  line-height: 34px;
}

.pagination-jump-btn {
  min-width: 72px;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}

.status-tag.success {
  background: #f0fdf4;
  color: #16a34a;
}

.status-tag.danger {
  background: #fef2f2;
  color: #dc2626;
}

.batch-detail-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.46);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 1200;
}

.batch-detail-dialog {
  width: min(1040px, 100%);
  max-height: min(88vh, 920px);
  padding: 28px;
  overflow: auto;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.batch-detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;
  padding-bottom: 18px;
  border-bottom: 1px solid #e5edf5;
}

.batch-detail-header-main {
  min-width: 0;
}

.batch-detail-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.batch-detail-kicker {
  display: inline-flex;
  padding: 5px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 10px;
}

.batch-detail-header h3 {
  margin: 0;
  font-size: 30px;
  line-height: 1.25;
  color: #0f172a;
}

.batch-detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  margin-top: 12px;
  color: #475569;
  font-size: 13px;
}

.batch-detail-meta span {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eef4ff;
  border: 1px solid #dbe7ff;
}

.batch-detail-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.batch-detail-summary-grid div,
.batch-issue-meta-grid div {
  min-width: 0;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid #dbe4ee;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}

.batch-detail-summary-grid span,
.batch-issue-meta-grid span,
.batch-issue-section span,
.batch-issue-image-card span {
  display: block;
  margin-bottom: 5px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.batch-detail-summary-grid strong,
.batch-issue-meta-grid strong {
  display: block;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.batch-detail-empty {
  padding: 28px 12px;
  text-align: center;
  color: #64748b;
  font-size: 14px;
}

.batch-issue-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
}

.batch-issue-card {
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #ffffff;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.batch-issue-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.batch-issue-id {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.batch-issue-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.6;
}

.batch-issue-subtitle {
  margin-top: 2px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.batch-issue-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.batch-issue-section {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.batch-issue-section p {
  margin: 0;
  font-size: 14px;
  color: #334155;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.issue-section-warning {
  background: #fff7ed;
  border-color: #fed7aa;
}

.batch-issue-image-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.batch-issue-image-card {
  border-radius: 14px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  padding: 12px;
  min-width: 0;
}

.batch-issue-image-wrap {
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
}

.batch-issue-image {
  display: block;
  width: auto;
  max-width: 100%;
  height: auto;
  max-height: 280px;
  object-fit: contain;
  background: #fff;
  margin: 0 auto;
}

.batch-issue-image-empty {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 13px;
}

/* Mobile signature board normalized styles */
.mobile-signature-board {
  width: 100vw;
  height: 100dvh;
  height: 100svh;
  max-height: 100dvh;
  max-height: 100svh;
  border-radius: 0;
  padding-top: max(10px, env(safe-area-inset-top));
  padding-right: max(10px, env(safe-area-inset-right));
  padding-bottom: max(10px, env(safe-area-inset-bottom));
  padding-left: max(10px, env(safe-area-inset-left));
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
  position: fixed;
  inset: 0;
  z-index: 1300;
  overscroll-behavior: contain;
  box-sizing: border-box;
}

.mobile-signature-board-top {
  display: none;
}

.mobile-signature-board-title {
  display: none;
}

.mobile-signature-close {
  display: none;
}

.mobile-signature-orientation-overlay .mobile-signature-close {
  display: inline-flex;
  width: auto;
  min-width: 88px;
}


.mobile-signature-canvas-wrap {
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  overflow: hidden;
  min-height: 0;
  height: 100%;
  touch-action: none;
}

.mobile-signature-canvas {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 0;
  max-height: none;
  touch-action: none;
}

.mobile-signature-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 76px;
  gap: 10px;
  align-items: stretch;
  overflow: hidden;
}

.mobile-signature-rail {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
}

.mobile-signature-icon-btn {
  width: 100%;
  flex: 1;
  min-height: 0;
  border: none;
  border-radius: 18px;
  font-size: 28px;
  font-weight: 800;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.14);
}

.mobile-signature-icon-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.mobile-signature-confirm {
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
}

.mobile-signature-reset {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
}

.mobile-signature-close-btn {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.mobile-signature-error {
  margin-top: 0;
}

.mobile-signature-actions {
  display: none;
}

.signature-pad-head-minimal {
  display: none;
  margin: 0;
  padding: 0;
}

.mobile-signature-orientation-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 280px;
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 20px;
  box-sizing: border-box;
}

.mobile-signature-orientation-overlay .btn {
  width: auto;
  min-width: 96px;
}

.mobile-signature-orientation-overlay-inner {
  width: 100%;
  max-width: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
}

.mobile-signature-orientation-overlay-inner .mobile-signature-close {
  margin-top: 6px;
}

.mobile-signature-orientation-icon {
  width: 56px;
  height: 56px;
  border-radius: 999px;
  background: #eff6ff;
  border: 1px solid #dbe7ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #1d4ed8;
  font-weight: 700;
}

.mobile-signature-orientation-title {
  font-size: 20px;
  font-weight: 800;
  color: #0f172a;
}

.mobile-signature-orientation-text {
  font-size: 14px;
  line-height: 1.8;
  color: #475569;
}

@media (max-width: 900px) {
  .page-shell {
    gap: 14px;
  }

  .page-header {
    padding: 18px 16px;
  }

  .page-header h2 {
    font-size: 28px;
  }

  .page-kicker {
    margin-bottom: 10px;
  }

  .filter-card,
  .table-card {
    padding: 16px;
  }

  .filter-card {
    overflow: hidden;
    border-radius: 20px;
    background:
      radial-gradient(circle at 92% 8%, rgba(37, 99, 235, 0.12), transparent 28%),
      linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.96));
  }

  .filter-head {
    align-items: center;
    margin-bottom: 0;
  }

  .filter-card.mobile-expanded .filter-head {
    margin-bottom: 14px;
  }

  .filter-head h3 {
    font-size: 17px;
  }

  .filter-head-actions {
    align-items: flex-end;
    flex-direction: column;
    gap: 8px;
  }

  .mobile-filter-toggle {
    display: inline-flex;
    min-height: 38px;
    width: auto;
  }

  .today-filter-btn {
    display: inline-flex;
  }

  .filter-card:not(.mobile-expanded) .filter-grid,
  .filter-card:not(.mobile-expanded) .filter-actions {
    display: none;
  }

  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    width: 100%;
    min-width: 0;
  }

  .filter-item {
    min-width: 0;
    gap: 7px;
  }

  .filter-item-station,
  .filter-item-table {
    grid-column: 1 / -1;
  }

  .filter-item label {
    display: inline-flex;
    width: fit-content;
    padding: 4px 9px;
    border-radius: 999px;
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 12px;
    font-weight: 800;
  }

  .filter-item input,
  .filter-item select,
  .pagination-controls select,
  .pagination-jump input {
    height: 46px;
    font-size: 15px;
    padding: 0 12px;
  }

  .filter-item .multi-selected-values input {
    height: 32px;
    padding: 0 4px;
  }

  .filter-item-date input,
  .filter-item-result select,
  .filter-item-signature select {
    height: 48px;
    max-width: 100%;
    min-width: 0;
    border-color: #bfdbfe;
    border-radius: 16px;
    background-color: #fff;
    box-shadow:
      0 8px 18px rgba(15, 23, 42, 0.06),
      inset 0 0 0 1px rgba(255, 255, 255, 0.7);
    color: #0f172a;
    font-weight: 800;
  }

  .filter-item-date input {
    padding: 0 9px;
    -webkit-appearance: none;
    appearance: none;
  }

  .filter-item-date input::-webkit-date-and-time-value {
    text-align: left;
  }

  .filter-item-date input::-webkit-calendar-picker-indicator {
    opacity: 0.72;
  }

  .filter-item-result select {
    padding-right: 30px;
    background-position:
      calc(100% - 16px) 50%,
      calc(100% - 11px) 50%;
  }

  .filter-item-station input,
  .filter-item-table input {
    border-radius: 15px;
    border-color: #dbe4ee;
    background: #fff;
  }

  .filter-item-station .multi-selected-values input,
  .filter-item-table .multi-selected-values input,
  .filter-item-inspector .multi-selected-values input {
    border: none;
    border-radius: 0;
    background: transparent;
  }

  .search-select-dropdown {
    max-height: 210px;
    border-radius: 16px;
  }

  .filter-actions,
  .pagination-controls {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-actions {
    gap: 10px;
    padding-top: 0;
    border-top: none;
  }

  .filter-quick-actions,
  .filter-main-actions {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
  }

  .filter-quick-actions .btn,
  .filter-main-actions .btn {
    width: 100%;
  }

  .pagination-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .pagination-size-control,
  .pagination-nav-row,
  .pagination-jump {
    width: 100%;
  }

  .pagination-size-control {
    justify-content: space-between;
  }

  .pagination-size-control select {
    width: 128px;
  }

  .pagination-nav-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .pagination-page-list {
    width: 100%;
    justify-content: center;
    overflow-x: auto;
    padding: 5px;
  }

  .pagination-page-btn {
    flex: 0 0 auto;
    width: 36px;
    height: 36px;
  }

  .pagination-jump {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) 82px;
  }

  .pagination-jump input {
    width: 100%;
  }

  .table-card {
    display: none;
  }

  .mobile-record-list {
    display: block;
  }

  .mobile-pagination-bar {
    display: flex;
    padding: 14px;
  }

  .btn {
    width: 100%;
    min-height: 46px;
  }

  .pagination-btn,
  .pagination-jump-btn {
    width: 100%;
    min-width: 0;
  }

  .mobile-action-btn {
    min-height: 40px;
    height: 40px;
    padding: 0 8px;
    font-size: 13px;
    line-height: 1;
    white-space: nowrap;
  }

  .signature-preview-image,
  .signature-preview-placeholder {
    width: 100%;
    height: 82px;
  }

  .batch-detail-overlay {
    padding: 0;
  }

  .batch-detail-dialog {
    width: min(96vw, 960px);
    padding: 16px;
    max-height: 92vh;
  }

  .batch-detail-header {
    flex-direction: column;
    align-items: stretch;
  }

  .batch-detail-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }

  .batch-detail-summary-grid,
  .batch-issue-meta-grid,
  .batch-issue-image-grid {
    grid-template-columns: 1fr;
  }

  .batch-issue-list {
    grid-template-columns: 1fr;
  }

  .batch-detail-meta span {
    width: 100%;
    justify-content: flex-start;
  }

  .signature-dialog {
    width: min(96vw, 960px);
    padding: 14px;
    max-height: 92vh;
  }

  .mobile-signature-board {
    width: 100vw;
    height: 100dvh;
    height: 100svh;
    max-height: 100dvh;
    max-height: 100svh;
    border-radius: 0;
    padding-top: max(8px, env(safe-area-inset-top));
    padding-right: max(8px, env(safe-area-inset-right));
    padding-bottom: max(8px, env(safe-area-inset-bottom));
    padding-left: max(8px, env(safe-area-inset-left));
    gap: 8px;
  }

  .mobile-signature-canvas {
    height: 100%;
    min-height: 0;
    max-height: none;
  }

  .mobile-signature-canvas-wrap {
    height: 100%;
    min-height: 0;
  }

  .mobile-signature-layout {
    grid-template-columns: minmax(0, 1fr) 68px;
    gap: 8px;
  }

  .mobile-signature-icon-btn {
    border-radius: 16px;
    font-size: 24px;
  }
}

@media (max-width: 430px) {
  .records-page {
    padding-inline: 0;
  }

  .page-shell {
    gap: 12px;
  }

  .page-header,
  .filter-card,
  .mobile-record-card {
    border-radius: 18px;
  }

  .page-header {
    padding: 16px 14px;
  }

  .filter-card {
    padding: 14px;
  }

  .mobile-record-card {
    padding: 13px;
  }

  .mobile-card-body {
    gap: 7px;
  }

  .mobile-card-row {
    padding: 9px 8px;
    border-radius: 13px;
  }

  .mobile-card-row span {
    font-size: 11px;
  }

  .mobile-card-row strong {
    font-size: 15px;
  }

  .mobile-batch-list {
    margin-top: 12px;
    padding-top: 12px;
    gap: 9px;
  }

  .mobile-batch-item {
    padding: 11px;
  }

  .mobile-batch-table-name {
    font-size: 13px;
    line-height: 1.55;
  }

  .mobile-batch-item-actions {
    gap: 7px;
  }

  .mobile-action-btn {
    min-height: 38px;
    height: 38px;
    border-radius: 11px;
    font-size: 13px;
    letter-spacing: 0;
  }

  .status-tag {
    padding: 4px 8px;
    font-size: 12px;
    white-space: nowrap;
  }
}
</style>
