<template>
  <div class="page-shell issues-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>巡检问题列表</h2>
      </div>
    </div>

    <div class="mobile-issue-list">
      <div v-if="loading" class="mobile-empty empty-state-card card-surface">
        <div class="empty-state-orb loading"></div>
        <div class="empty-state-kicker">同步中</div>
        <h3>正在加载问题列表</h3>
        <p>系统正在同步最新的问题记录，请稍候。</p>
      </div>

      <div v-else-if="paginatedData.length === 0" class="mobile-empty empty-state-card card-surface">
        <div class="empty-state-orb"></div>
        <div class="empty-state-kicker">暂无记录</div>
        <h3>当前没有符合条件的问题记录</h3>
        <p>可以调整筛选条件，或刷新后查看最新巡检问题。</p>
        <button class="btn btn-secondary empty-state-action" type="button" @click="resetFilters">重置筛选</button>
      </div>

      <div v-else class="mobile-issue-cards">
        <div v-for="item in paginatedData" :key="item.id" class="mobile-issue-card card-surface"
          :class="issueAuditRowClass(item)">
          <div class="mobile-card-head">
            <div class="mobile-card-title-row">
              <span class="mobile-card-category">{{ item.inspection_table_name || '暂无' }}</span>
              <div class="mobile-card-title-actions">
                <button class="excellent-star mobile" type="button"
                  :class="{ active: item.is_excellent, locked: !canToggleExcellentIssue(item) }"
                  :disabled="!canToggleExcellentIssue(item) || markingExcellentIssueId === item.id"
                  :title="excellentStarTitle(item)" @click="toggleIssueExcellent(item)">
                  ★
                </button>
                <span :class="statusClass(item.status)">{{ item.status }}</span>
              </div>
            </div>
            <div class="mobile-card-code">
              <span>规范ID</span>
              <div class="standard-id-stack compact">
                <span v-for="part in getStandardIdParts(item)" :key="`${item.id}-${part.type}`" :class="part.type">
                  <em>{{ part.label }}</em><strong>{{ part.value }}</strong>
                </span>
              </div>
            </div>
            <div class="mobile-card-meta">{{ item.month }}｜{{ item.time }}</div>
          </div>

          <div class="mobile-card-body">
            <div class="mobile-card-row"><span>站点</span><strong>{{ item.station }}</strong></div>
            <div class="mobile-card-row"><span>所属地</span><strong>{{ item.region }}</strong></div>
            <div class="mobile-card-row"><span>站点负责人</span><strong>{{ item.station_manager }}</strong></div>
            <div class="mobile-card-row"><span>检查人员</span><strong>{{ item.inspector }}</strong></div>
            <div v-if="!isIssueAuditPending(item)" class="mobile-card-row"><span>审核结论</span><strong
                :class="auditStatusClass(item)">{{
              auditStatusLabel(item) }}</strong></div>

            <div class="mobile-card-row mobile-card-row-top">
              <span>规范详情</span>
              <div class="mobile-card-standard-box">
                <div class="mobile-card-standard-preview multiline-clamp">{{
                  getStandardDetailPreview(getCombinedStandardDetailText(item))
                  }}</div>
                <button class="text-link-btn" type="button" @click="openStandardDetail(item)">查看详情</button>
              </div>
            </div>
            <div class="mobile-card-row mobile-card-row-top">
              <span>问题描述</span>
              <div class="mobile-card-text">{{ item.description }}</div>
            </div>
            <div class="mobile-card-row mobile-card-row-top">
              <span>整改说明</span>
              <div class="mobile-card-text">{{ item.rectification_note || '暂无' }}</div>
            </div>
            <div class="mobile-card-row mobile-card-row-top">
              <span>复核说明</span>
              <div class="mobile-card-text">{{ item.review_note || '暂无' }}</div>
            </div>
          </div>

          <div class="mobile-card-images">
            <button v-if="item.issue_photo" class="mobile-image-btn" type="button"
              @click="preview(resolveImage(item.issue_photo), '问题照片')">
              <img v-if="listImagesReady" :src="resolveImage(item.issue_photo)" class="mobile-thumb" alt="问题照片"
                loading="lazy" decoding="async" fetchpriority="low" />
              <span v-else class="mobile-thumb-placeholder">问题照片</span>
              <span>问题照片</span>
            </button>

            <button v-if="item.rectification_photo" class="mobile-image-btn" type="button"
              @click="preview(resolveImage(item.rectification_photo), '站点反馈整改照片')">
              <img v-if="listImagesReady" :src="resolveImage(item.rectification_photo)" class="mobile-thumb"
                alt="站点反馈整改照片" loading="lazy" decoding="async" fetchpriority="low" />
              <span v-else class="mobile-thumb-placeholder">整改照片</span>
              <span>整改照片</span>
            </button>
            <button v-if="item.review_photo" class="mobile-image-btn" type="button"
              @click="preview(resolveImage(item.review_photo), '督导组复核照片')">
              <img v-if="listImagesReady" :src="resolveImage(item.review_photo)" class="mobile-thumb" alt="督导组复核照片"
                loading="lazy" decoding="async" fetchpriority="low" />
              <span v-else class="mobile-thumb-placeholder">复核照片</span>
              <span>复核照片</span>
            </button>
          </div>

          <div v-if="canManageIssues || canAuditIssues" class="mobile-card-actions">
            <template v-if="canAuditIssueRow(item)">
              <template v-if="isIssueAuditPending(item)">
                <button class="btn btn-success" type="button" :disabled="auditingIssueId === item.id"
                  @click="auditIssue(item, 'approved')">
                  通过
                </button>
                <button class="btn btn-danger" type="button" :disabled="auditingIssueId === item.id"
                  @click="auditIssue(item, 'rejected')">
                  否决
                </button>
              </template>
              <template v-else>
                <span :class="auditStatusClass(item)">{{ auditStatusLabel(item) }}</span>
                <button class="btn btn-secondary" type="button" :disabled="auditingIssueId === item.id"
                  @click="auditIssue(item, 'pending')">
                  重新判定
                </button>
              </template>
            </template>
            <button v-if="canOpenIssueEditDialog(item)" class="btn btn-secondary" type="button" @click="openEditDialog(item)">
              {{ canEditIssueRow(item) ? '编辑问题' : '调整检查人' }}
            </button>
            <button v-if="canUpdateRectificationPhotoRow(item)" class="btn btn-secondary" type="button"
              @click="openRectificationPhotoDialog(item)">
              更新整改照片
            </button>
            <button v-if="canDeleteIssueRow(item)" class="btn btn-danger" type="button"
              :disabled="deletingIssueId === item.id" @click="deleteIssue(item)">
              {{ deletingIssueId === item.id ? '删除中...' : '删除问题' }}
            </button>
            <span v-if="issueOperationLockReason(item)" class="locked-action">{{ issueOperationLockReason(item)
              }}</span>
            <span v-else-if="isClosedIssue(item) && currentRole !== 'root'" class="locked-action">已闭环锁定</span>
            <span v-else-if="!canAuditIssueRow(item) && !hasIssueOperation(item)" class="locked-action">暂无可操作</span>
          </div>
        </div>
      </div>

      <div v-if="!loading && filteredData.length" class="pagination-bar mobile-pagination-bar card-surface">
        <div class="pagination-summary">共 {{ filteredData.length }} 条</div>
        <div class="pagination-controls">
          <div class="pagination-size-control">
            <label>每页显示</label>
            <select v-model.number="pageSize">
              <option v-for="size in pageSizeOptions" :key="`mobile-${size}`" :value="size">{{ size }}</option>
            </select>
          </div>
          <div class="pagination-nav-row">
            <button class="btn btn-secondary pagination-btn" :disabled="page <= 1" @click="goToPage(1)">首页</button>
            <button class="btn btn-secondary pagination-btn" :disabled="page <= 1" @click="prevPage">上一页</button>
          </div>
          <div class="pagination-page-list" aria-label="巡检问题页码">
            <template v-for="item in visiblePageItems" :key="`mobile-${item.key}`">
              <span v-if="item.type === 'ellipsis'" class="pagination-ellipsis">...</span>
              <button v-else class="pagination-page-btn" :class="{ active: item.value === page }" type="button"
                @click="goToPage(item.value)">
                {{ item.value }}
              </button>
            </template>
          </div>
          <div class="pagination-nav-row">
            <button class="btn btn-secondary pagination-btn" :disabled="page >= totalPage" @click="nextPage">下一页</button>
            <button class="btn btn-secondary pagination-btn" :disabled="page >= totalPage"
              @click="goToPage(totalPage)">末页</button>
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

    <div class="filter-card card-surface" :class="{ 'mobile-expanded': showMobileFilters }">
      <div class="filter-head">
        <div>
          <div class="filter-kicker">筛选面板</div>
          <h3>快速定位巡检问题</h3>
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
        <div class="filter-item">
          <label>问题ID</label>
          <input v-model.trim="filters.issueId" placeholder="输入问题ID" />
        </div>
        <div class="filter-item">
          <label>检查月度</label>
          <input v-model="filters.month" type="month" />
        </div>
        <div class="filter-item">
          <label>检查时间（按天）</label>
          <input v-model="filters.date" type="date" />
        </div>

        <div class="filter-item">
          <label>站点所属地</label>
          <div class="search-select multi-search-select" ref="regionSelectRef">
            <div class="multi-select-control" @click="focusMultiFilterInput('region')">
              <div class="multi-selected-values">
                <span v-for="value in filters.region" :key="`region-${value}`" class="multi-selected-chip">
                  {{ value }}
                  <button type="button" @click.stop="removeMultiFilterValue('region', value)">×</button>
                </span>
                <input ref="regionFilterInputRef" v-model="filterSearch.region" type="text"
                  :placeholder="filters.region.length ? '继续搜索所属地' : '搜索并多选所属地'"
                  @focus="openFilterDropdown('region')" @input="openFilterDropdown('region')" />
              </div>
              <span v-if="filters.region.length" class="multi-selected-count">已选 {{ filters.region.length }}</span>
            </div>
            <div v-if="dropdownVisible.region" class="search-select-dropdown">
              <button v-for="option in filteredRegionOptions" :key="option" type="button"
                class="search-select-option multi-select-option"
                :class="{ selected: isMultiFilterSelected('region', option) }"
                @mousedown.prevent @click="toggleMultiFilter('region', option)">
                <span class="multi-option-check">{{ isMultiFilterSelected('region', option) ? '✓' : '' }}</span>
                <div class="option-main">{{ option }}</div>
              </button>
              <div v-if="filteredRegionOptions.length === 0" class="search-select-empty">无匹配站点所属地</div>
            </div>
          </div>
        </div>

        <div class="filter-item">
          <label>站点名称</label>
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
              <div v-if="filteredStationOptions.length === 0" class="search-select-empty">无匹配站点名称</div>
            </div>
          </div>
        </div>

        <div class="filter-item">
          <label>站点负责人</label>
          <div class="search-select" ref="stationManagerSelectRef">
            <input v-model="filters.stationManager" placeholder="搜索或选择站点负责人"
              @focus="openFilterDropdown('stationManager')" @input="openFilterDropdown('stationManager')" />
            <div v-if="dropdownVisible.stationManager" class="search-select-dropdown">
              <div v-for="option in filteredStationManagerOptions" :key="option" class="search-select-option"
                @click="selectFilterOption('stationManager', option)">
                <div class="option-main">{{ option }}</div>
              </div>
              <div v-if="filteredStationManagerOptions.length === 0" class="search-select-empty">无匹配站点负责人</div>
            </div>
          </div>
        </div>

        <div class="filter-item">
          <label>检查人员</label>
          <div class="search-select multi-search-select" ref="inspectorSelectRef">
            <div class="multi-select-control" @click="focusMultiFilterInput('inspector')">
              <div class="multi-selected-values">
                <span v-for="value in filters.inspector" :key="`inspector-${value}`" class="multi-selected-chip">
                  {{ value }}
                  <button type="button" @click.stop="removeMultiFilterValue('inspector', value)">×</button>
                </span>
                <input ref="inspectorFilterInputRef" v-model="filterSearch.inspector" type="text"
                  :placeholder="filters.inspector.length ? '继续搜索检查人员' : '搜索并多选检查人员'"
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
              <div v-if="filteredInspectorOptions.length === 0" class="search-select-empty">无匹配检查人员</div>
            </div>
          </div>
        </div>

        <div class="filter-item">
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

        <div class="filter-item">
          <label>规范ID</label>
          <input v-model="filters.standardId" placeholder="搜索规范ID" />
        </div>
        <div class="filter-item">
          <label>规范详情</label>
          <input v-model="filters.standardDetail" placeholder="搜索规范详情关键词" />
        </div>
        <div class="filter-item">
          <label>站经理整改结果</label>
          <select v-model="filters.rectificationResult">
            <option value="">全部</option>
            <option value="已整改">已整改</option>
            <option value="站经无法整改">站经无法整改</option>
          </select>
        </div>
        <div class="filter-item">
          <label>督导组复核结果</label>
          <select v-model="filters.reviewResult">
            <option value="">全部</option>
            <option value="已整改">已整改</option>
            <option value="站经无法整改">站经无法整改</option>
          </select>
        </div>
        <div class="filter-item">
          <label>问题状态</label>
          <select v-model="filters.status">
            <option value="">全部</option>
            <option value="待审核">待审核</option>
            <option value="待签名">待签名</option>
            <option value="待整改">待整改</option>
            <option value="待复核">待复核</option>
            <option value="已闭环">已闭环</option>
            <option value="站经无法整改">站经无法整改</option>
          </select>
        </div>
        <div class="filter-item">
          <label>优秀问题</label>
          <div class="excellent-filter-toggle" role="group" aria-label="优秀问题筛选">
            <button type="button" :class="{ active: filters.excellent === '' }" title="全部问题"
              @click="filters.excellent = ''">
              全部
            </button>
            <button type="button" class="star-filter-btn" :class="{ active: filters.excellent === 'starred' }"
              title="只看已点亮优秀问题" @click="filters.excellent = 'starred'">
              ★
            </button>
            <button type="button" class="star-filter-btn muted" :class="{ active: filters.excellent === 'unstarred' }"
              title="只看未点亮优秀问题" @click="filters.excellent = 'unstarred'">
              ☆
            </button>
          </div>
        </div>
        <div class="filter-item">
          <label>审核结论</label>
          <select v-model="filters.auditStatus">
            <option value="">全部</option>
            <option value="approved">审核通过</option>
            <option value="rejected">审核否决</option>
          </select>
        </div>
        <div class="filter-item">
          <label>审核状态</label>
          <select v-model="filters.auditState">
            <option value="">全部</option>
            <option value="pending">待审核</option>
            <option value="done">已审核</option>
          </select>
        </div>
      </div>

      <div class="filter-actions">
        <div class="filter-quick-actions">
          <button class="btn btn-primary today-filter-btn" type="button" @click="filterMyTodayIssues">
            只看我今天检查的问题
          </button>
        </div>
        <div class="filter-main-actions">
          <button class="btn btn-export" type="button" :disabled="loading || filteredData.length === 0"
            @click="openExportDialog">
            导出数据
          </button>
          <button class="btn btn-secondary" @click="resetFilters">重置筛选</button>
          <button class="btn btn-secondary" @click="fetchIssues" :disabled="loading">
            {{ loading ? '刷新中...' : '刷新数据' }}
          </button>
        </div>
      </div>
    </div>

    <div ref="tableCardRef" class="table-card card-surface" :class="{ 'fullscreen-table-card': tableFullscreen }"
      :style="{ '--issue-table-zoom': tableZoom, '--issue-table-min-width': `${issueTableMinWidth}px` }">
      <div class="table-card-head">
        <div>
          <div class="filter-kicker">问题清单</div>
          <h3>{{ tableFullscreen ? '全屏查看巡检问题' : '巡检问题明细' }}</h3>
        </div>
        <div class="table-view-actions">
          <label v-if="tableFullscreen" class="table-zoom-control">
            <span>缩放 {{ Math.round(tableZoom * 100) }}%</span>
            <input v-model.number="tableZoom" type="range" min="0.2" max="1" step="0.02"
              @input="rememberTableZoom" />
          </label>
          <div ref="columnSettingsRef" class="column-settings-wrap">
            <button class="btn btn-secondary column-settings-btn" type="button" @click.stop="toggleColumnSettings">
              字段显示 {{ visibleIssueColumns.length }}/{{ issueColumnDefinitions.length }}
            </button>
            <div v-if="columnSettingsOpen" class="column-settings-panel card-surface" @click.stop>
              <div class="column-settings-header">
                <div>
                  <strong>字段显示设置</strong>
                  <p>隐藏暂时不看的字段，问题数据不会受影响。</p>
                </div>
                <button class="close-btn" type="button" @click="columnSettingsOpen = false">×</button>
              </div>
              <div class="column-settings-actions">
                <button class="btn btn-primary btn-sm" type="button" @click="showAllIssueColumns">全部显示</button>
                <button class="btn btn-secondary btn-sm" type="button" @click="applyCompactIssueColumns">常用精简</button>
                <button class="btn btn-secondary btn-sm" type="button" @click="resetIssueColumns">恢复默认</button>
              </div>
              <div class="column-settings-groups">
                <section v-for="group in groupedIssueColumns" :key="group.name" class="column-settings-group">
                  <div class="column-settings-group-title">{{ group.name }}</div>
                  <label v-for="column in group.columns" :key="column.key" class="column-toggle-item"
                    :class="{ active: isIssueColumnVisible(column.key) }">
                    <input type="checkbox" :checked="isIssueColumnVisible(column.key)"
                      @change="toggleIssueColumn(column.key)" />
                    <span>{{ column.label }}</span>
                  </label>
                </section>
              </div>
            </div>
          </div>
          <button class="btn btn-secondary" type="button" @click="toggleTableFullscreen">
            {{ tableFullscreen ? '退出全屏' : '全屏显示' }}
          </button>
        </div>
      </div>
      <div class="table-scroll-wrap">
        <div ref="tableScrollRef" class="table-scroll">
          <table class="issues-table">
            <thead>
              <tr>
                <th v-if="isIssueColumnVisible('id')" class="nowrap">ID</th>
                <th v-if="isIssueColumnVisible('month')" class="nowrap">检查月度</th>
                <th v-if="isIssueColumnVisible('time')" class="nowrap">检查时间</th>
                <th v-if="isIssueColumnVisible('region')" class="nowrap">站点所属地</th>
                <th v-if="isIssueColumnVisible('station')" class="nowrap">站点名称</th>
                <th v-if="isIssueColumnVisible('station_manager')" class="nowrap">站点负责人</th>
                <th v-if="isIssueColumnVisible('station_manager_phone')" class="nowrap">站点负责人手机号</th>
                <th v-if="isIssueColumnVisible('inspector')" class="nowrap">检查人员</th>
                <th v-if="isIssueColumnVisible('inspector_phone')" class="nowrap">检查人员手机号</th>
                <th v-if="isIssueColumnVisible('inspection_table_name')" class="nowrap">检查表</th>
                <th v-if="isIssueColumnVisible('standard_id')" class="nowrap">规范ID（内/外）</th>
                <th v-if="isIssueColumnVisible('standard_detail')">规范详情</th>
                <th v-if="isIssueColumnVisible('description')">问题描述</th>
                <th v-if="isIssueColumnVisible('issue_photo')" class="nowrap">问题照片</th>
                <th v-if="isIssueColumnVisible('rectification_result')" class="nowrap">站经理整改结果</th>
                <th v-if="isIssueColumnVisible('rectification_note')" class="nowrap">站点反馈整改说明</th>
                <th v-if="isIssueColumnVisible('rectification_photo')" class="nowrap">站点反馈整改照片</th>
                <th v-if="isIssueColumnVisible('review_result')" class="nowrap">督导组复核结果</th>
                <th v-if="isIssueColumnVisible('review_note')" class="nowrap">督导组复核说明</th>
                <th v-if="isIssueColumnVisible('review_photo')" class="nowrap">督导组复核照片</th>
                <th v-if="isIssueColumnVisible('status')" class="nowrap-col status-col">问题状态</th>
                <th v-if="isIssueColumnVisible('audit')" class="nowrap audit-col">审核</th>
                <th v-if="canManageIssues" class="nowrap operation-col">操作</th>
                <th v-if="isIssueColumnVisible('excellent')" class="nowrap excellent-col">优秀</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in paginatedData" :key="item.id" :class="issueAuditRowClass(item)">
                <td v-if="isIssueColumnVisible('id')" class="nowrap issue-id-cell">{{ item.id }}</td>
                <td v-if="isIssueColumnVisible('month')" class="nowrap">{{ item.month }}</td>
                <td v-if="isIssueColumnVisible('time')" class="nowrap">{{ item.time }}</td>
                <td v-if="isIssueColumnVisible('region')" class="nowrap">{{ item.region }}</td>
                <td v-if="isIssueColumnVisible('station')" class="nowrap">{{ item.station }}</td>
                <td v-if="isIssueColumnVisible('station_manager')" class="nowrap">{{ item.station_manager }}</td>
                <td v-if="isIssueColumnVisible('station_manager_phone')" class="nowrap">{{ item.station_manager_phone }}</td>
                <td v-if="isIssueColumnVisible('inspector')" class="nowrap">{{ item.inspector }}</td>
                <td v-if="isIssueColumnVisible('inspector_phone')" class="nowrap">{{ item.inspector_phone }}</td>
                <td v-if="isIssueColumnVisible('inspection_table_name')" class="nowrap">{{ item.inspection_table_name || '暂无' }}</td>
                <td v-if="isIssueColumnVisible('standard_id')" class="nowrap standard-id-cell">
                  <div class="standard-id-stack">
                    <span v-for="part in getStandardIdParts(item)" :key="`${item.id}-table-${part.type}`"
                      :class="part.type">
                      <em>{{ part.label }}</em><strong>{{ part.value }}</strong>
                    </span>
                  </div>
                </td>
                <td v-if="isIssueColumnVisible('standard_detail')" class="standard-detail-cell">
                  <div class="standard-detail-box">
                    <div class="standard-detail-preview multiline-clamp">{{
                      getStandardDetailPreview(getCombinedStandardDetailText(item))
                      }}</div>
                    <button class="text-link-btn" type="button" @click="openStandardDetail(item)">查看详情</button>
                  </div>
                </td>
                <td v-if="isIssueColumnVisible('description')" class="long-text">{{ item.description }}</td>
                <td v-if="isIssueColumnVisible('issue_photo')" class="nowrap">
                  <button v-if="item.issue_photo" class="image-btn" type="button"
                    @click="preview(resolveImage(item.issue_photo), '问题照片')">
                    <img v-if="listImagesReady" :src="resolveImage(item.issue_photo)" class="thumb" alt="问题照片"
                      loading="lazy" decoding="async" fetchpriority="low" />
                    <span v-else class="thumb-placeholder">问题照片</span>
                  </button>
                  <span v-else>暂无</span>
                </td>
                <td v-if="isIssueColumnVisible('rectification_result')" class="nowrap">{{ item.rectification_result || '暂无' }}</td>
                <td v-if="isIssueColumnVisible('rectification_note')" class="nowrap">{{ item.rectification_note || '暂无' }}</td>
                <td v-if="isIssueColumnVisible('rectification_photo')" class="nowrap">
                  <button v-if="item.rectification_photo" class="image-btn" type="button"
                    @click="preview(resolveImage(item.rectification_photo), '站点反馈整改照片')">
                    <img v-if="listImagesReady" :src="resolveImage(item.rectification_photo)" class="thumb"
                      alt="站点反馈整改照片" loading="lazy" decoding="async" fetchpriority="low" />
                    <span v-else class="thumb-placeholder">整改照片</span>
                  </button>
                  <span v-else>暂无</span>
                </td>
                <td v-if="isIssueColumnVisible('review_result')" class="nowrap">{{ item.review_result || '暂无' }}</td>
                <td v-if="isIssueColumnVisible('review_note')" class="nowrap">{{ item.review_note || '暂无' }}</td>
                <td v-if="isIssueColumnVisible('review_photo')" class="nowrap">
                  <button v-if="item.review_photo" class="image-btn" type="button"
                    @click="preview(resolveImage(item.review_photo), '督导组复核照片')">
                    <img v-if="listImagesReady" :src="resolveImage(item.review_photo)" class="thumb" alt="督导组复核照片"
                      loading="lazy" decoding="async" fetchpriority="low" />
                    <span v-else class="thumb-placeholder">复核照片</span>
                  </button>
                  <span v-else>暂无</span>
                </td>
                <td v-if="isIssueColumnVisible('status')" class="nowrap-col status-col">
                  <span :class="statusClass(item.status)">{{ item.status }}</span>
                </td>
                <td v-if="isIssueColumnVisible('audit')" class="nowrap audit-col">
                  <div class="audit-actions">
                    <template v-if="canAuditIssueRow(item)">
                      <template v-if="isIssueAuditPending(item)">
                        <button class="btn btn-success btn-sm" type="button" :disabled="auditingIssueId === item.id"
                          @click="auditIssue(item, 'approved')">通过</button>
                        <button class="btn btn-danger btn-sm" type="button" :disabled="auditingIssueId === item.id"
                          @click="auditIssue(item, 'rejected')">否决</button>
                      </template>
                      <template v-else>
                        <span :class="auditStatusClass(item)">{{ auditStatusLabel(item) }}</span>
                        <button class="btn btn-secondary btn-sm" type="button" :disabled="auditingIssueId === item.id"
                          @click="auditIssue(item, 'pending')">重新判定</button>
                      </template>
                    </template>
                    <template v-else>
                      <span v-if="!isIssueAuditPending(item)" :class="auditStatusClass(item)">{{
                        auditStatusLabel(item) }}</span>
                      <span v-else class="audit-empty">-</span>
                    </template>
                  </div>
                </td>
                <td v-if="canManageIssues" class="nowrap operation-col">
                  <div class="table-actions">
                    <button v-if="canOpenIssueEditDialog(item)" class="btn btn-secondary btn-sm" type="button"
                      @click="openEditDialog(item)">
                      {{ canEditIssueRow(item) ? '编辑' : '调检查人' }}
                    </button>
                    <button v-if="canUpdateRectificationPhotoRow(item)" class="btn btn-secondary btn-sm" type="button"
                      @click="openRectificationPhotoDialog(item)">
                      更新整改照片
                    </button>
                    <button v-if="canDeleteIssueRow(item)" class="btn btn-danger btn-sm" type="button"
                      :disabled="deletingIssueId === item.id" @click="deleteIssue(item)">
                      {{ deletingIssueId === item.id ? '删除中' : '删除' }}
                    </button>
                    <span v-if="issueOperationLockReason(item)" class="locked-action">{{ issueOperationLockReason(item)
                      }}</span>
                    <span v-else-if="isClosedIssue(item) && currentRole !== 'root'" class="locked-action">已闭环锁定</span>
                    <span v-else-if="!hasIssueOperation(item)" class="locked-action">暂无可操作</span>
                  </div>
                </td>
                <td v-if="isIssueColumnVisible('excellent')" class="nowrap excellent-col">
                  <button class="excellent-star" type="button" :class="{ active: item.is_excellent, locked: !canToggleExcellentIssue(item) }"
                    :disabled="!canToggleExcellentIssue(item) || markingExcellentIssueId === item.id"
                    :title="excellentStarTitle(item)" @click="toggleIssueExcellent(item)">
                    ★
                  </button>
                </td>
              </tr>
              <tr v-if="!loading && paginatedData.length === 0">
                <td :colspan="issueTableColspan" class="empty-row">
                  <div class="empty-state-inline">
                    <div class="empty-state-orb"></div>
                    <div class="empty-state-kicker">暂无记录</div>
                    <h3>当前没有符合条件的问题记录</h3>
                    <p>可以调整筛选条件，或刷新后查看最新巡检问题。</p>
                    <button class="btn btn-secondary btn-sm empty-state-action" type="button"
                      @click="resetFilters">重置筛选</button>
                  </div>
                </td>
              </tr>
              <tr v-if="loading">
                <td :colspan="issueTableColspan" class="empty-row">
                  <div class="empty-state-inline">
                    <div class="empty-state-orb loading"></div>
                    <div class="empty-state-kicker">同步中</div>
                    <h3>正在加载问题列表</h3>
                    <p>系统正在同步最新的问题记录，请稍候。</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="pagination-bar">
        <div class="pagination-summary">共 {{ filteredData.length }} 条</div>
        <div class="pagination-controls">
          <div class="pagination-size-control">
            <label>每页显示</label>
            <select v-model.number="pageSize">
              <option v-for="size in pageSizeOptions" :key="`desktop-${size}`" :value="size">{{ size }}</option>
            </select>
          </div>
          <div class="pagination-nav-row">
            <button class="btn btn-secondary pagination-btn" :disabled="page <= 1" @click="goToPage(1)">首页</button>
            <button class="btn btn-secondary pagination-btn" :disabled="page <= 1" @click="prevPage">上一页</button>
          </div>
          <div class="pagination-page-list" aria-label="巡检问题页码">
            <template v-for="item in visiblePageItems" :key="`desktop-${item.key}`">
              <span v-if="item.type === 'ellipsis'" class="pagination-ellipsis">...</span>
              <button v-else class="pagination-page-btn" :class="{ active: item.value === page }" type="button"
                @click="goToPage(item.value)">
                {{ item.value }}
              </button>
            </template>
          </div>
          <div class="pagination-nav-row">
            <button class="btn btn-secondary pagination-btn" :disabled="page >= totalPage" @click="nextPage">下一页</button>
            <button class="btn btn-secondary pagination-btn" :disabled="page >= totalPage"
              @click="goToPage(totalPage)">末页</button>
          </div>
          <div class="pagination-jump">
            <span>跳至</span>
            <input v-model="pageJumpInput" type="number" min="1" :max="totalPage" :placeholder="`1-${totalPage}`"
              @keyup.enter="jumpToInputPage" />
            <button class="btn btn-primary pagination-jump-btn" type="button" @click="jumpToInputPage">跳转</button>
          </div>
        </div>
      </div>

      <div ref="fullscreenOverlayHostRef" class="fullscreen-overlay-host"></div>
    </div>

    <Teleport :to="overlayTeleportTarget" :disabled="!tableFullscreen">
      <transition name="toast-fade">
        <div v-if="actionMessage" class="message-toast" :class="actionMessageType">{{ actionMessage }}</div>
      </transition>
      <transition name="audit-notice-fade">
        <div v-if="auditNotice.visible" class="audit-center-notice" :class="auditNotice.type">
          <div class="audit-center-card card-surface">
            <div class="audit-center-icon">{{ auditNotice.type === 'success' ? '✓' : '!' }}</div>
            <strong>{{ auditNotice.title }}</strong>
            <p>{{ auditNotice.message }}</p>
          </div>
        </div>
      </transition>

      <div v-if="exportDialog.visible" class="image-modal">
        <div class="image-modal-content issue-export-modal">
          <div class="image-modal-header">
            <span>导出巡检问题数据</span>
            <button class="close-btn" type="button" :disabled="exportDialog.submitting"
              @click="closeExportDialog">×</button>
          </div>

          <div class="issue-export-body">
            <div class="export-notice">
              <div>
                <strong>导出说明</strong>
                <p>默认导出当前筛选后的文字数据，并按不同检查表拆分为多个 Sheet；外部规范详情会按检查表原字段展开为独立列。照片导出会明显增加生成时间和文件体积，仅授权用户可勾选，并会把对应照片嵌入 Excel 单元格。</p>
              </div>
              <span>Excel</span>
            </div>

            <div class="export-summary-grid">
              <div class="export-summary-card primary">
                <span>准备导出</span>
                <strong>{{ exportDialog.selectedCount }}</strong>
                <em>条巡检问题</em>
              </div>
              <div class="export-summary-card">
                <span>筛选条件</span>
                <strong>{{ exportFilterChips.length }}</strong>
                <em>{{ exportFilterChips.length ? '项已应用' : '当前为全部数据' }}</em>
              </div>
              <div class="export-summary-card">
                <span>保存期限</span>
                <strong>7天</strong>
                <em>到期自动清理</em>
              </div>
            </div>

            <div class="export-filter-panel">
              <div class="export-section-title">当前筛选结果</div>
              <div v-if="exportFilterChips.length" class="export-filter-chips">
                <span v-for="chip in exportFilterChips" :key="chip.key">{{ chip.label }}：{{ chip.value }}</span>
              </div>
              <div v-else class="export-empty-filter">未设置筛选条件，将按当前权限范围导出全部问题数据。</div>
            </div>

            <div class="export-field-panel">
              <div class="export-field-panel-head">
                <div>
                  <div class="export-section-title">导出字段选择</div>
                  <p>
                    默认勾选当前账号可导出的全部字段。内部规范和外部规范作为两个整体导出选项；外部规范会在 Excel 中按检查表原字段展开。
                    <span v-if="!canExportIssuePhotos">当前账号未获得“导出巡检照片”权限，照片字段暂不可勾选。</span>
                  </p>
                </div>
                <div class="export-field-actions">
                  <span>已选 {{ selectedExportFieldCount }} 项</span>
                  <button class="btn btn-secondary btn-sm" type="button" :disabled="Boolean(exportDialog.taskId)"
                    @click="setAllExportFields(true)">一键全选</button>
                  <button class="btn btn-secondary btn-sm" type="button" :disabled="Boolean(exportDialog.taskId)"
                    @click="invertExportFields">一键反选</button>
                </div>
              </div>

              <div class="export-field-groups">
                <section v-for="group in exportFieldGroups" :key="group.title" class="export-field-group">
                  <h4>{{ group.title }}</h4>
                  <div class="export-field-options">
                    <label v-for="option in group.options" :key="option.key" class="export-field-option"
                      :class="{ disabled: !canSelectExportField(option), photo: option.photo }">
                      <input v-model="exportDialog.includeFields[option.key]" type="checkbox"
                        :disabled="!canSelectExportField(option)" />
                      <span>{{ option.label }}</span>
                      <em>{{ option.help }}</em>
                    </label>
                  </div>
                </section>
              </div>
            </div>

            <div v-if="exportDialog.taskId" class="export-task-panel" :class="exportDialog.status">
              <div class="export-task-head">
                <div>
                  <span>任务状态</span>
                  <strong>{{ exportStatusLabel }}</strong>
                </div>
                <em v-if="exportDialog.fileSizeLabel">文件大小 {{ exportDialog.fileSizeLabel }}</em>
                <em v-if="exportDialog.expiresAt">文件保留至 {{ exportDialog.expiresAt }}</em>
              </div>
              <div class="export-progress">
                <div class="export-progress-bar" :style="{ width: exportProgressWidth }"></div>
              </div>
              <p v-if="exportDialog.status === 'completed'">
                Excel 文件已生成，共导出 {{ exportDialog.exportedCount }} 条数据，可以直接下载。
                <template v-if="exportDialog.fileSizeLabel"> 文件大小：{{ exportDialog.fileSizeLabel }}。</template>
              </p>
              <p v-else-if="exportDialog.status === 'failed'" class="export-error-text">
                {{ exportDialog.error || '导出失败，请稍后重试。' }}
              </p>
              <p v-else>系统正在后台整理数据并生成 Excel，数据量较大时请稍候。</p>
            </div>

            <div v-if="exportDialog.error && !exportDialog.taskId" class="form-error">{{ exportDialog.error }}</div>
          </div>

          <div class="issue-edit-actions export-actions">
            <button class="btn btn-secondary" type="button" :disabled="exportDialog.submitting"
              @click="closeExportDialog">
              关闭
            </button>
            <button v-if="exportDialog.taskId && ['completed', 'failed'].includes(exportDialog.status)"
              class="btn btn-secondary" type="button" :disabled="exportDialog.downloading"
              @click="resetExportDialogForCurrentFilters">
              重新按当前筛选导出
            </button>
            <button v-if="exportDialog.status !== 'completed'" class="btn btn-primary" type="button"
              :disabled="exportDialog.submitting || exportDialog.status === 'pending' || exportDialog.status === 'running'"
              @click="submitIssueExportTask">
              {{ exportDialog.submitting || exportDialog.status === 'pending' || exportDialog.status === 'running' ?
                '生成中...'
                : '提交导出任务' }}
            </button>
            <button v-else class="btn btn-primary" type="button" :disabled="exportDialog.downloading"
              @click="downloadIssueExport">
              {{ exportDialog.downloading ? '下载中...' : '下载Excel文件' }}
            </button>
          </div>
        </div>
      </div>

    <div v-if="editDialog.visible" class="image-modal">
      <div class="image-modal-content issue-edit-modal">
        <div class="image-modal-header">
          <span>编辑巡检问题</span>
          <button class="close-btn" type="button" :disabled="editDialog.saving" @click="closeEditDialog">×</button>
        </div>
        <form class="issue-edit-form" @submit.prevent="saveIssueEdit">
          <div class="issue-edit-summary">
            <div>
              <span>站点</span>
              <strong>{{ editDialog.issue?.station || '-' }}</strong>
            </div>
            <div>
              <span>检查表</span>
              <strong>{{ editDialog.issue?.inspection_table_name || '-' }}</strong>
            </div>
            <div>
              <span>规范ID</span>
              <div class="standard-id-stack compact">
                <span v-for="part in getStandardIdParts(editDialog.issue)" :key="`edit-${part.type}`"
                  :class="part.type">
                  <em>{{ part.label }}</em><strong>{{ part.value }}</strong>
                </span>
              </div>
            </div>
          </div>

          <div class="issue-edit-grid">
            <label v-if="editDialog.issue?.can_change_issue_inspector" class="issue-edit-field issue-edit-field-wide">
              <span>检查人归属</span>
              <select v-model="editDialog.form.target_inspector_id" :disabled="inspectorUserLoading">
                <option value="">{{ inspectorUserLoading ? '正在加载检查人...' : '请选择检查人' }}</option>
                <option v-for="inspector in inspectorUserOptions" :key="inspector.id" :value="inspector.id">
                  {{ inspectorUserLabel(inspector) }}
                </option>
              </select>
              <small class="field-help">保存后该问题会挂到新的检查人名下，巡检记录参与人同步更新。</small>
            </label>
            <div v-if="canEditDialogIssueContent" class="issue-edit-field issue-edit-field-wide">
              <span>编辑{{ editStandardInputLabel }}</span>
              <div class="edit-standard-panel">
                <div class="edit-standard-mode">
                  当前巡检登记使用：<strong>{{ standardSourceModeLabel }}</strong>
                  <span v-if="standardSourceMode === 'internal'">只能调整内部规范ID，外部规范会按挂载关系自动变化。</span>
                  <span v-else>只能调整外部规范ID，内部规范会随外部规范关联自动变化。</span>
                </div>
                <div class="search-select" ref="editStandardSelectRef">
                  <input v-model="editDialog.standardSearch" type="text" :placeholder="`搜索并选择${editStandardInputLabel}`"
                    :disabled="editStandardLoading" @focus="openEditStandardDropdown"
                    @input="handleEditStandardInput" />
                  <div v-if="editStandardDropdownVisible" class="search-select-dropdown search-select-dropdown-wide">
                    <div v-if="editStandardLoading" class="search-select-empty">正在加载规范数据...</div>
                    <template v-else>
                      <div v-for="standard in filteredEditStandards" :key="getEditStandardIdentity(standard)"
                        class="search-select-option" @click="selectEditStandard(standard)">
                        <div class="option-main">
                          {{ standard.standard_id }}｜{{ getEditStandardTitle(standard) }}
                        </div>
                        <div class="option-sub option-table-name">{{ standard.inspection_table_name || '未关联外部检查表' }}
                        </div>
                        <div class="option-sub standard-detail-preview">{{ getEditStandardPreview(standard) }}</div>
                      </div>
                      <div v-if="filteredEditStandards.length === 0" class="search-select-empty">无匹配规范</div>
                    </template>
                  </div>
                </div>
                <div class="edit-standard-result">
                  <div>
                    <span>{{ standardSourceMode === 'internal' ? '将保存的内部规范ID' : '将保存的外部规范ID' }}</span>
                    <strong>{{ editStandardReferenceValue || '-' }}</strong>
                  </div>
                  <div>
                    <span>{{ standardSourceMode === 'internal' ? '关联外部规范' : '关联内部规范' }}</span>
                    <strong v-if="standardSourceMode === 'internal'">
                      {{selectedEditStandard?.linked_externals?.length
                        ? selectedEditStandard.linked_externals.map((link) => link.external_standard_id).join('、')
                        : '-'}}
                    </strong>
                    <strong v-else>{{ selectedEditStandard?.internal_standard_id || '未关联内部规范' }}</strong>
                  </div>
                  <div>
                    <span>检查表</span>
                    <strong>{{ selectedEditStandard?.inspection_table_name || editDialog.issue?.inspection_table_name ||
                      '-'
                      }}</strong>
                  </div>
                </div>
              </div>
            </div>
            <label v-if="canEditDialogIssueContent" class="issue-edit-field issue-edit-field-wide">
              <span>问题描述</span>
              <textarea v-model="editDialog.form.description" rows="4" placeholder="请填写实际问题描述"></textarea>
            </label>
            <div v-if="canEditDialogIssueContent" ref="editIssuePhotoUploadSectionRef"
              class="issue-edit-field issue-edit-field-wide upload-follow-anchor">
              <span>问题照片</span>
              <div class="upload-card issue-edit-upload-card">
                <input id="edit-issue-photo-upload" class="upload-input" type="file" accept="image/*"
                  @change="handleIssuePhotoChange" />
                <input id="edit-issue-photo-camera" class="upload-input" type="file" accept="image/*"
                  capture="environment" @change="handleIssuePhotoChange" />

                <div class="upload-dropzone" :class="{ 'drag-active': editIssuePhotoDragActive }" role="button"
                  tabindex="0" @click="openEditIssuePhotoPicker" @keydown.enter.prevent="openEditIssuePhotoPicker"
                  @keydown.space.prevent="openEditIssuePhotoPicker" @dragenter.prevent="handleEditIssuePhotoDragEnter"
                  @dragover.prevent="handleEditIssuePhotoDragOver" @dragleave.prevent="handleEditIssuePhotoDragLeave"
                  @drop.prevent="handleEditIssuePhotoDrop" @paste="handleEditIssuePhotoPaste">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">
                    <span class="desktop-upload-title">选择或拖拽新的问题照片</span>
                    <span class="mobile-upload-title">选择或更换问题照片</span>
                  </div>
                  <div class="upload-desc">
                    不选择新照片则保留原照片；桌面端可拖拽图片，也可复制图片后在此处粘贴上传。
                  </div>
                  <div class="upload-trigger-group">
                    <label for="edit-issue-photo-camera" class="upload-trigger upload-trigger-secondary"
                      @click.stop>拍照上传</label>
                    <label for="edit-issue-photo-upload" class="upload-trigger" @click.stop>相册选择</label>
                  </div>
                </div>

                <div class="issue-edit-photo-grid">
                  <div v-if="editDialog.issue?.issue_photo" class="image-preview-panel issue-current-photo-panel">
                    <img :src="resolveImage(editDialog.issue.issue_photo)" alt="当前问题照片" class="image-preview-thumb" />
                    <div class="image-preview-meta">
                      <div class="image-preview-title">当前问题照片</div>
                      <div class="image-preview-name">未选择新照片时将继续保留</div>
                      <div class="image-preview-actions">
                        <button class="btn btn-light image-action-btn" type="button"
                          @click="preview(resolveImage(editDialog.issue.issue_photo), '当前问题照片')">
                          查看原图
                        </button>
                      </div>
                    </div>
                  </div>
                  <div v-if="editDialog.issuePhotoPreview" class="image-preview-panel">
                    <img :src="editDialog.issuePhotoPreview" alt="新的问题照片预览" class="image-preview-thumb" />
                    <div class="image-preview-meta">
                      <div class="image-preview-title">已选择新问题照片</div>
                      <div class="image-preview-name">{{ editDialog.issuePhotoFile?.name || '已上传图片' }}</div>
                      <div class="image-preview-actions">
                        <label for="edit-issue-photo-camera" class="btn btn-light image-action-btn">重新拍照</label>
                        <label for="edit-issue-photo-upload" class="btn btn-light image-action-btn">相册重选</label>
                        <button class="btn btn-secondary image-action-btn" type="button"
                          @click="clearIssuePhoto">移除图片</button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <label v-if="editDialog.issue?.can_edit_issue_workflow" class="issue-edit-field">
              <span>问题状态</span>
              <select v-model="editDialog.form.status">
                <option value="待整改">待整改</option>
                <option value="待复核">待复核</option>
                <option value="已闭环">已闭环</option>
                <option value="站经无法整改">站经无法整改</option>
              </select>
            </label>
            <label v-if="editDialog.issue?.can_edit_issue_workflow" class="issue-edit-field">
              <span>站经理整改结果</span>
              <select v-model="editDialog.form.rectification_result">
                <option value="">暂无/清空</option>
                <option value="已整改">已整改</option>
                <option value="站经无法整改">站经无法整改</option>
              </select>
            </label>
            <label v-if="editDialog.issue?.can_edit_issue_workflow" class="issue-edit-field issue-edit-field-wide">
              <span>站点反馈整改说明</span>
              <textarea v-model="editDialog.form.rectification_note" rows="3" placeholder="可补充或修正站点整改说明"></textarea>
            </label>
            <label v-if="editDialog.issue?.can_edit_issue_workflow" class="issue-edit-field">
              <span>督导组复核结果</span>
              <select v-model="editDialog.form.review_result">
                <option value="">暂无/清空</option>
                <option value="已整改">已整改</option>
                <option value="站经无法整改">站经无法整改</option>
              </select>
            </label>
            <label v-if="editDialog.issue?.can_edit_issue_workflow" class="issue-edit-field issue-edit-field-wide">
              <span>督导组复核说明</span>
              <textarea v-model="editDialog.form.review_note" rows="3" placeholder="可补充或修正督导组复核说明"></textarea>
            </label>
          </div>
          <div v-if="!canEditDialogIssueContent && canChangeDialogIssueInspector" class="issue-edit-hint">
            当前账号仅可调整该问题的检查人归属，不会修改问题描述、照片、规范或流转状态。
          </div>
          <div v-else-if="!editDialog.issue?.can_edit_issue_workflow" class="issue-edit-hint">
            你是该问题的上传人，可在站点提交整改前修改问题描述和问题照片；流转状态、整改和复核信息仍由业务流程控制。
          </div>

          <div v-if="editDialog.error" class="form-error">{{ editDialog.error }}</div>

          <div class="issue-edit-actions">
            <button class="btn btn-secondary" type="button" :disabled="editDialog.saving" @click="closeEditDialog">
              放弃修改
            </button>
            <button class="btn btn-primary" type="submit" :disabled="editDialog.saving">
              {{ editDialog.saving ? '保存中...' : '保存修改' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="rectificationPhotoDialog.visible" class="image-modal">
      <div class="image-modal-content issue-edit-modal">
        <div class="image-modal-header">
          <span>更新整改照片</span>
          <button class="close-btn" type="button" :disabled="rectificationPhotoDialog.saving"
            @click="closeRectificationPhotoDialog">×</button>
        </div>

        <form class="issue-edit-form" @submit.prevent="saveRectificationPhoto">
          <div class="issue-edit-summary">
            <div>
              <span>站点</span>
              <strong>{{ rectificationPhotoDialog.issue?.station || '-' }}</strong>
            </div>
            <div>
              <span>当前整改结果</span>
              <strong>{{ rectificationPhotoDialog.issue?.rectification_result || '-' }}</strong>
            </div>
            <div>
              <span>问题状态</span>
              <strong>{{ rectificationPhotoDialog.issue?.status || '-' }}</strong>
            </div>
          </div>

          <div class="rectification-photo-panel">
            <div v-if="rectificationPhotoDialog.issue?.rectification_photo" class="rectification-photo-current">
              <span>当前整改照片</span>
              <button class="image-btn" type="button"
                @click="preview(resolveImage(rectificationPhotoDialog.issue.rectification_photo), '当前整改照片')">
                <img :src="resolveImage(rectificationPhotoDialog.issue.rectification_photo)" class="thumb"
                  alt="当前整改照片" />
              </button>
            </div>

            <label class="issue-edit-field issue-edit-field-wide">
              <span>上传新的整改照片</span>
              <input type="file" accept="image/*" @change="handleRectificationPhotoChange" />
            </label>

            <div v-if="rectificationPhotoDialog.preview" class="rectification-photo-preview">
              <img :src="rectificationPhotoDialog.preview" alt="新的整改照片预览" />
              <div>
                <strong>已选择新照片</strong>
                <span>{{ rectificationPhotoDialog.file?.name || '待上传图片' }}</span>
              </div>
            </div>
          </div>

          <div v-if="rectificationPhotoDialog.error" class="form-error">{{ rectificationPhotoDialog.error }}</div>

          <div class="issue-edit-actions">
            <button class="btn btn-secondary" type="button" :disabled="rectificationPhotoDialog.saving"
              @click="closeRectificationPhotoDialog">
              放弃修改
            </button>
            <button class="btn btn-primary" type="submit" :disabled="rectificationPhotoDialog.saving">
              {{ rectificationPhotoDialog.saving ? '上传中...' : '保存新照片' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="previewState.visible" class="issue-photo-preview-overlay" @click.self="closePreview">
      <div class="issue-photo-preview-dialog" @wheel.prevent="handlePreviewWheel" @dblclick="resetPreviewScale">
        <img :src="previewState.url" :style="previewImageStyle" :alt="previewState.title || '图片预览'" />
      </div>
    </div>
    <div v-if="standardDetailState.visible" class="image-modal" @click.self="closeStandardDetail">
      <div class="image-modal-content standard-detail-modal">
        <div class="image-modal-header">
          <span>{{ standardDetailState.title }}</span>
          <button class="close-btn" type="button" @click="closeStandardDetail">×</button>
        </div>
        <div class="standard-detail-modal-body">
          <div class="standard-detail-section" :class="{ muted: !standardDetailState.item?.internal_standard_id }">
            <div class="standard-detail-section-head">
              <span>内部规范</span>
              <strong>{{ standardDetailState.item?.internal_standard_id || '未关联内部规范' }}</strong>
            </div>
            <div v-if="standardInternalEntries.length" class="standard-detail-grid">
              <div v-for="entry in standardInternalEntries" :key="`internal-${entry.key}`"
                class="standard-detail-card internal">
                <div class="standard-detail-card-label">{{ entry.label }}</div>
                <div class="standard-detail-card-value multiline-cell">{{ entry.value }}</div>
              </div>
            </div>
            <p v-else>这条外部规范尚未关联内部规范。</p>
          </div>

          <div class="standard-detail-section external">
            <div class="standard-detail-section-head">
              <span>外部规范</span>
              <strong>{{ standardDetailState.item?.standard_id || '暂无外部规范ID' }}</strong>
            </div>
            <div class="standard-detail-grid">
              <div v-for="entry in standardExternalEntries" :key="`external-${entry.key}`"
                class="standard-detail-card external">
                <div class="standard-detail-card-label">{{ entry.label }}</div>
                <div class="standard-detail-card-value multiline-cell">{{ entry.value }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, shallowRef, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import {
  clearFileInput,
  clearFileInputsById,
  getImageFileFromClipboardEvent,
  getImageFileFromDataTransfer,
  hasImageInDataTransfer,
  isDesktopImageDropEnabled,
  prepareImagePreview,
  revokeObjectUrl,
  scrollImageUploadIntoView
} from '@/utils/imageUpload'
import {
  getStandardDetailPreview,
  parseStandardDetailText
} from '@/utils/standardDetail'

const filters = ref({
  issueId: '',
  month: '',
  date: '',
  region: [],
  station: [],
  stationManager: '',
  inspector: [],
  inspectionTableName: [],
  standardId: '',
  standardDetail: '',
  rectificationResult: '',
  reviewResult: '',
  status: '',
  excellent: '',
  auditStatus: '',
  auditState: ''
})

const list = shallowRef([])
const loading = ref(false)
const regionSelectRef = ref(null)
const stationSelectRef = ref(null)
const stationManagerSelectRef = ref(null)
const inspectorSelectRef = ref(null)
const inspectionTableSelectRef = ref(null)
const regionFilterInputRef = ref(null)
const stationFilterInputRef = ref(null)
const inspectorFilterInputRef = ref(null)
const inspectionTableFilterInputRef = ref(null)
const editStandardSelectRef = ref(null)
const tableCardRef = ref(null)
const tableScrollRef = ref(null)
const fullscreenOverlayHostRef = ref(null)
const columnSettingsRef = ref(null)

const dropdownVisible = ref({
  region: false,
  station: false,
  stationManager: false,
  inspector: false,
  inspectionTableName: false
})
const filterSearch = ref({
  region: '',
  station: '',
  inspector: '',
  inspectionTableName: ''
})

const isMobileView = ref(false)
const showMobileFilters = ref(false)
const page = ref(1)
const pageSize = ref(20)
const pageJumpInput = ref('')
const listImagesReady = ref(false)
let listImagesReadyTimer = null
const deletingIssueId = ref(null)
const auditingIssueId = ref(null)
const markingExcellentIssueId = ref(null)
const auditNotice = ref({
  visible: false,
  type: 'success',
  title: '',
  message: ''
})
let auditNoticeTimer = null
const tableFullscreen = ref(false)
const tableZoom = ref(1)
const overlayTeleportTarget = computed(() => (
  tableFullscreen.value && fullscreenOverlayHostRef.value ? fullscreenOverlayHostRef.value : 'body'
))
let fullscreenDomMutationGuard = false
let fullscreenDomMutationTimer = null
let rememberedFullscreenZoom = null
const columnSettingsOpen = ref(false)
const currentRole = localStorage.getItem('user_role') || localStorage.getItem('role') || ''
const currentRealName = localStorage.getItem('real_name') || ''
const currentUsername = localStorage.getItem('username') || ''
let parsedPermissions = {}
try {
  parsedPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch (error) {
  parsedPermissions = {}
}

const localPermissions = ref(parsedPermissions)
const actionMessage = ref('')
const actionMessageType = ref('info')
let actionMessageTimer = null
const ISSUE_COLUMNS_STORAGE_KEY = 'inspection_issue_table_visible_columns_v2'
const issueColumnDefinitions = [
  { key: 'id', label: 'ID', group: '基础信息', width: 72 },
  { key: 'month', label: '检查月度', group: '基础信息', width: 104 },
  { key: 'time', label: '检查时间', group: '基础信息', width: 148 },
  { key: 'region', label: '站点所属地', group: '基础信息', width: 126 },
  { key: 'station', label: '站点名称', group: '基础信息', width: 150 },
  { key: 'station_manager', label: '站点负责人', group: '基础信息', width: 128 },
  { key: 'station_manager_phone', label: '站点负责人手机号', group: '基础信息', width: 148 },
  { key: 'inspector', label: '检查人员', group: '基础信息', width: 116 },
  { key: 'inspector_phone', label: '检查人员手机号', group: '基础信息', width: 148 },
  { key: 'inspection_table_name', label: '检查表', group: '规范问题', width: 146 },
  { key: 'standard_id', label: '规范ID（内/外）', group: '规范问题', width: 150 },
  { key: 'standard_detail', label: '规范详情', group: '规范问题', width: 250 },
  { key: 'description', label: '问题描述', group: '规范问题', width: 250 },
  { key: 'issue_photo', label: '问题照片', group: '规范问题', width: 104 },
  { key: 'rectification_result', label: '站经理整改结果', group: '整改复核', width: 136 },
  { key: 'rectification_note', label: '站点反馈整改说明', group: '整改复核', width: 210 },
  { key: 'rectification_photo', label: '站点反馈整改照片', group: '整改复核', width: 120 },
  { key: 'review_result', label: '督导组复核结果', group: '整改复核', width: 136 },
  { key: 'review_note', label: '督导组复核说明', group: '整改复核', width: 210 },
  { key: 'review_photo', label: '督导组复核照片', group: '整改复核', width: 120 },
  { key: 'status', label: '问题状态', group: '状态操作', width: 104 },
  { key: 'audit', label: '审核', group: '状态操作', width: 116 },
  { key: 'excellent', label: '优秀', group: '状态操作', width: 78 }
]
const defaultIssueColumnVisibility = issueColumnDefinitions.reduce((result, column) => {
  result[column.key] = true
  return result
}, {})
const compactIssueColumnKeys = new Set([
  'id',
  'excellent',
  'time',
  'station',
  'inspector',
  'inspection_table_name',
  'standard_id',
  'description',
  'issue_photo',
  'status',
  'audit'
])
const loadIssueColumnVisibility = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(ISSUE_COLUMNS_STORAGE_KEY) || '{}')
    const visibility = {
      ...defaultIssueColumnVisibility,
      ...Object.fromEntries(issueColumnDefinitions.map((column) => [column.key, parsed[column.key] !== false]))
    }
    return Object.values(visibility).some(Boolean) ? visibility : { ...defaultIssueColumnVisibility }
  } catch (error) {
    return { ...defaultIssueColumnVisibility }
  }
}
const issueColumnVisibility = ref(loadIssueColumnVisibility())
const standardSourceMode = ref('external')
const editStandards = ref([])
const editStandardFields = ref([])
const editStandardDropdownVisible = ref(false)
const editStandardLoading = ref(false)
const inspectorUserOptions = ref([])
const inspectorUserLoading = ref(false)
const editIssuePhotoDragActive = ref(false)
const editIssuePhotoUploadSectionRef = ref(null)
let editIssuePhotoDragDepth = 0

const editDialog = ref({
  visible: false,
  saving: false,
  error: '',
  issue: null,
  issuePhotoFile: null,
  issuePhotoPreview: '',
  standardSearch: '',
  standardDirty: false,
  form: {
    standard_id: '',
    internal_standard_id: '',
    target_inspector_id: '',
    description: '',
    status: '待整改',
    rectification_result: '',
    rectification_note: '',
    review_result: '',
    review_note: ''
  }
})

const rectificationPhotoDialog = ref({
  visible: false,
  saving: false,
  error: '',
  issue: null,
  file: null,
  preview: ''
})

const exportDialog = ref({
  visible: false,
  submitting: false,
  downloading: false,
  taskId: '',
  status: 'idle',
  error: '',
  selectedCount: 0,
  exportedCount: 0,
  fileName: '',
  fileSizeLabel: '',
  expiresAt: '',
  filterSummary: {},
  includeFields: {}
})
let exportPollTimer = null

const exportFieldGroups = [
  {
    title: '基础信息',
    options: [
      { key: 'id', label: 'ID', help: '问题唯一编号' },
      { key: 'month', label: '检查月度', help: '问题所属月份' },
      { key: 'time', label: '检查时间', help: '问题登记时间' },
      { key: 'region', label: '站点所属地', help: '站点片区/归属地' },
      { key: 'station', label: '站点名称', help: '问题所属站点' },
      { key: 'station_manager', label: '站点负责人', help: '站点负责人姓名' },
      { key: 'station_manager_phone', label: '负责人手机号', help: '站点负责人手机号' },
      { key: 'inspector', label: '检查人员', help: '问题登记人' },
      { key: 'inspector_phone', label: '检查人手机号', help: '检查人员手机号' },
      { key: 'inspection_table_name', label: '检查表', help: '问题所属检查表' }
    ]
  },
  {
    title: '规范与问题',
    options: [
      { key: 'internal_standard', label: '内部规范', help: '内部规范ID和内部规范详情' },
      { key: 'external_standard', label: '外部规范', help: '外部规范ID和检查表原字段' },
      { key: 'description', label: '问题描述', help: '现场登记的问题说明' },
      { key: 'issue_photo', label: '问题照片', help: '嵌入现场问题照片', photo: true }
    ]
  },
  {
    title: '状态与审核',
    options: [
      { key: 'status', label: '问题状态', help: '待审核、待签名、待整改等流转状态' },
      { key: 'audit_result', label: '审核结果', help: '通过或否决，未审核则留空' },
      { key: 'is_excellent', label: '是否优秀', help: '是否点亮优秀问题标记' }
    ]
  },
  {
    title: '整改复核',
    options: [
      { key: 'rectification_result', label: '整改结果', help: '站经理整改判定' },
      { key: 'rectification_note', label: '整改说明', help: '站点反馈整改说明' },
      { key: 'rectification_photo', label: '整改照片', help: '嵌入站点整改照片', photo: true },
      { key: 'review_result', label: '复核结果', help: '督导组复核判定' },
      { key: 'review_note', label: '复核说明', help: '督导组复核说明' },
      { key: 'review_photo', label: '复核照片', help: '嵌入督导复核照片', photo: true }
    ]
  }
]
const exportFieldOptions = exportFieldGroups.flatMap((group) => group.options)
const exportPhotoFieldKeys = ['issue_photo', 'rectification_photo', 'review_photo']

const exportFilterLabels = {
  issueId: '问题ID',
  month: '检查月度',
  date: '检查时间',
  region: '站点所属地',
  station: '站点名称',
  stationManager: '站点负责人',
  inspector: '检查人员',
  inspectionTableName: '检查表',
  standardId: '规范ID',
  standardDetail: '规范详情',
  rectificationResult: '站经理整改结果',
  reviewResult: '督导组复核结果',
  status: '问题状态',
  excellent: '优秀问题',
  auditStatus: '审核结论',
  auditState: '审核状态'
}

const normalizedKeyword = (value) => String(value || '').toLowerCase()
const uniqueSortedOptions = (values) => {
  return [...new Set(values.map((item) => String(item || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
}

const filterOptionByKeyword = (options, keyword) => {
  const normalized = normalizedKeyword(keyword)
  return options.filter((item) => !normalized || normalizedKeyword(item).includes(normalized))
}

const getMultiFilterValues = (key) => {
  const value = filters.value[key]
  return Array.isArray(value) ? value : []
}

const matchesAnySelectedText = (value, selectedValues) => {
  const selected = Array.isArray(selectedValues) ? selectedValues : []
  if (!selected.length) return true
  const normalizedValue = normalizedKeyword(value).trim()
  return selected.some((item) => normalizedValue === normalizedKeyword(item).trim())
}

const filteredData = computed(() => {
  return list.value.filter((item) => {
    const matchedIssueId = !filters.value.issueId || String(item.id || '').includes(String(filters.value.issueId || '').trim())
    const matchedMonth = !filters.value.month || item.month === filters.value.month
    const matchedDate = !filters.value.date || String(item.time || '').startsWith(filters.value.date)
    const matchedRegion = matchesAnySelectedText(item.region, filters.value.region)
    const matchedStation = matchesAnySelectedText(item.station, filters.value.station)
    const matchedStationManager = !filters.value.stationManager || normalizedKeyword(item.station_manager).includes(normalizedKeyword(filters.value.stationManager))
    const matchedInspector = matchesAnySelectedText(item.inspector, filters.value.inspector)
    const matchedInspectionTableName = matchesAnySelectedText(item.inspection_table_name, filters.value.inspectionTableName)
    const matchedStandardId = !filters.value.standardId || normalizedKeyword(getStandardIdSearchText(item)).includes(normalizedKeyword(filters.value.standardId))
    const matchedStandardDetail = !filters.value.standardDetail || normalizedKeyword(getCombinedStandardDetailText(item)).includes(normalizedKeyword(filters.value.standardDetail))
    const matchedRectificationResult = !filters.value.rectificationResult || item.rectification_result === filters.value.rectificationResult
    const matchedReviewResult = !filters.value.reviewResult || item.review_result === filters.value.reviewResult
    const matchedStatus = !filters.value.status || item.status === filters.value.status
    const matchedExcellent = !filters.value.excellent ||
      (filters.value.excellent === 'starred' ? Boolean(item.is_excellent) : !item.is_excellent)
    const matchedAuditStatus = !filters.value.auditStatus || normalizeAuditStatus(item) === filters.value.auditStatus
    const matchedAuditState = !filters.value.auditState ||
      (filters.value.auditState === 'pending'
        ? normalizeAuditStatus(item) === 'pending'
        : normalizeAuditStatus(item) !== 'pending')

    return (
      matchedIssueId &&
      matchedMonth &&
      matchedDate &&
      matchedRegion &&
      matchedStation &&
      matchedStationManager &&
      matchedInspector &&
      matchedInspectionTableName &&
      matchedStandardId &&
      matchedStandardDetail &&
      matchedRectificationResult &&
      matchedReviewResult &&
      matchedStatus &&
      matchedExcellent &&
      matchedAuditStatus &&
      matchedAuditState
    )
  })
})

const regionOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.region)))
const stationOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.station)))
const stationManagerOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.station_manager)))
const inspectorOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.inspector)))
const inspectionTableOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.inspection_table_name)))

const filteredRegionOptions = computed(() => filterOptionByKeyword(regionOptions.value, filterSearch.value.region))
const filteredStationOptions = computed(() => filterOptionByKeyword(stationOptions.value, filterSearch.value.station))
const filteredStationManagerOptions = computed(() => filterOptionByKeyword(stationManagerOptions.value, filters.value.stationManager))
const filteredInspectorOptions = computed(() => filterOptionByKeyword(inspectorOptions.value, filterSearch.value.inspector))
const filteredInspectionTableOptions = computed(() => filterOptionByKeyword(inspectionTableOptions.value, filterSearch.value.inspectionTableName))

const activeFilterCount = computed(() => {
  return Object.values(filters.value).reduce((count, value) => {
    if (Array.isArray(value)) {
      return count + value.filter((item) => String(item || '').trim()).length
    }
    return count + (String(value || '').trim() ? 1 : 0)
  }, 0)
})

const formatExportFilterValue = (key, value) => {
  if (key === 'excellent') {
    if (value === 'starred') return '★'
    if (value === 'unstarred') return '☆'
  }
  return value
}

const exportFilterChips = computed(() => {
  return Object.entries(exportDialog.value.filterSummary || {})
    .filter(([_key, value]) => String(value || '').trim())
    .map(([key, value]) => ({
      key,
      label: exportFilterLabels[key] || key,
      value: formatExportFilterValue(key, value)
    }))
})

const exportStatusLabel = computed(() => {
  const labels = {
    idle: '待提交',
    pending: '排队中',
    running: '生成中',
    completed: '已完成',
    failed: '生成失败'
  }
  return labels[exportDialog.value.status] || '准备中'
})

const exportProgressWidth = computed(() => {
  const status = exportDialog.value.status
  if (status === 'completed') return '100%'
  if (status === 'running') return '72%'
  if (status === 'pending') return '32%'
  if (status === 'failed') return '100%'
  return '0%'
})

const pageSizeOptions = computed(() => isMobileView.value ? [5, 10, 20] : [20, 50, 100])

const totalPage = computed(() => Math.max(1, Math.ceil(filteredData.value.length / pageSize.value)))

const paginatedData = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredData.value.slice(start, start + pageSize.value)
})

const currentInspectorFilterValue = computed(() => {
  const candidates = [currentRealName, currentUsername]
    .map((value) => String(value || '').trim())
    .filter(Boolean)
  const options = inspectorOptions.value
  return candidates.find((candidate) => options.includes(candidate)) || candidates[0] || ''
})

const visiblePageItems = computed(() => {
  const total = totalPage.value
  const current = page.value

  if (total <= 7) {
    return Array.from({ length: total }, (_item, index) => {
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

const canEditIssues = computed(() => currentRole === 'root' || Boolean(localPermissions.value.edit_inspection_issues))
const canDeleteIssues = computed(() => currentRole === 'root' || Boolean(localPermissions.value.delete_inspection_issues))
const canAuditIssues = computed(() => currentRole === 'root' || Boolean(localPermissions.value.audit_inspection_issues) || list.value.some((item) => item?.can_audit_issue))
const canChangeIssueInspectors = computed(() => currentRole === 'root' || Boolean(localPermissions.value.change_issue_inspector) || list.value.some((item) => item?.can_change_issue_inspector))
const canExportIssuePhotos = computed(() => currentRole === 'root' || Boolean(localPermissions.value.export_issue_photos))
const canManageIssues = computed(() => (
  canEditIssues.value ||
  canDeleteIssues.value ||
  canChangeIssueInspectors.value ||
  list.value.some((item) => (
    item?.can_edit_issue ||
    item?.can_delete_issue ||
    item?.can_update_rectification_photo ||
    item?.can_change_issue_inspector
  ))
))
const visibleIssueColumns = computed(() => issueColumnDefinitions.filter((column) => issueColumnVisibility.value[column.key] !== false))
const canEditDialogIssueContent = computed(() => Boolean(editDialog.value.issue?.can_edit_issue))
const canChangeDialogIssueInspector = computed(() => Boolean(editDialog.value.issue?.can_change_issue_inspector))
const groupedIssueColumns = computed(() => {
  const groupMap = new Map()
  issueColumnDefinitions.forEach((column) => {
    if (!groupMap.has(column.group)) {
      groupMap.set(column.group, [])
    }
    groupMap.get(column.group).push(column)
  })
  return Array.from(groupMap.entries()).map(([name, columns]) => ({ name, columns }))
})
const issueTableMinWidth = computed(() => {
  const operationWidth = canManageIssues.value ? 128 : 0
  const baseWidth = visibleIssueColumns.value.reduce((total, column) => total + column.width, operationWidth)
  return Math.max(980, baseWidth + 96)
})
const issueTableColspan = computed(() => visibleIssueColumns.value.length + (canManageIssues.value ? 1 : 0))

const isIssueColumnVisible = (key) => issueColumnVisibility.value[key] !== false

const saveIssueColumnVisibility = () => {
  localStorage.setItem(ISSUE_COLUMNS_STORAGE_KEY, JSON.stringify(issueColumnVisibility.value))
}

const setIssueColumnVisibility = (nextVisibility, message = '') => {
  issueColumnVisibility.value = { ...defaultIssueColumnVisibility, ...nextVisibility }
  saveIssueColumnVisibility()
  if (tableFullscreen.value) {
    setAutoTableZoom()
  }
  if (message) {
    showActionMessage(message, 'success')
  }
}

const toggleIssueColumn = (key) => {
  const nextVisible = !isIssueColumnVisible(key)
  if (!nextVisible && visibleIssueColumns.value.length <= 1) {
    showActionMessage('至少保留一个字段显示。', 'error')
    return
  }
  setIssueColumnVisibility({
    ...issueColumnVisibility.value,
    [key]: nextVisible
  })
}

const showAllIssueColumns = () => {
  setIssueColumnVisibility({ ...defaultIssueColumnVisibility }, '已显示全部字段。')
}

const resetIssueColumns = () => {
  setIssueColumnVisibility({ ...defaultIssueColumnVisibility }, '已恢复默认字段显示。')
}

const applyCompactIssueColumns = () => {
  const nextVisibility = issueColumnDefinitions.reduce((result, column) => {
    result[column.key] = compactIssueColumnKeys.has(column.key)
    return result
  }, {})
  setIssueColumnVisibility(nextVisibility, '已切换为常用精简字段。')
}

const toggleColumnSettings = () => {
  columnSettingsOpen.value = !columnSettingsOpen.value
}

const isClosedIssue = (item) => item?.status === '已闭环'
const issueOperationLockReason = (item = {}) => {
  const reason = String(item?.operation_lock_reason || '').trim()
  if (reason) return reason
  if (item?.inspection_signed) return '已签字不可操作'
  return ''
}
const canEditIssueRow = (item) => Boolean(item?.can_edit_issue)
const canChangeIssueInspectorRow = (item) => Boolean(item?.can_change_issue_inspector)
const canOpenIssueEditDialog = (item) => canEditIssueRow(item) || canChangeIssueInspectorRow(item)
const canDeleteIssueRow = (item) => Boolean(item?.can_delete_issue)
const canUpdateRectificationPhotoRow = (item) => Boolean(item?.can_update_rectification_photo)
const canAuditIssueRow = (item) => Boolean(item?.can_audit_issue)
const normalizeAuditStatus = (item = {}) => String(item?.audit_status || 'pending').trim() || 'pending'
const canToggleExcellentIssue = (item) => Boolean(item?.can_mark_excellent_issue) && normalizeAuditStatus(item) !== 'rejected'
const excellentStarTitle = (item) => {
  if (normalizeAuditStatus(item) === 'rejected') return '审核否决的问题不能标记为优秀'
  if (!item?.can_mark_excellent_issue) return item?.is_excellent ? '优秀问题' : '暂无标记权限'
  return item?.is_excellent ? '取消优秀问题标记' : '标记为优秀问题'
}
const hasIssueOperation = (item) => (
  canEditIssueRow(item) ||
  canUpdateRectificationPhotoRow(item) ||
  canDeleteIssueRow(item) ||
  Boolean(issueOperationLockReason(item)) ||
  (isClosedIssue(item) && currentRole !== 'root')
)
const isIssueAuditPending = (item) => normalizeAuditStatus(item) === 'pending'
const auditStatusLabel = (item) => {
  const status = normalizeAuditStatus(item)
  if (status === 'approved') return '通过'
  if (status === 'rejected') return '否决'
  return ''
}
const auditStatusClass = (item) => {
  const status = normalizeAuditStatus(item)
  if (status === 'approved') return 'audit-status-chip approved'
  if (status === 'rejected') return 'audit-status-chip rejected'
  return 'audit-status-chip pending'
}
const issueAuditRowClass = (item) => {
  const status = normalizeAuditStatus(item)
  if (status === 'approved') return 'issue-audit-approved'
  if (status === 'rejected') return 'issue-audit-rejected'
  return ''
}

const getStandardIdDisplay = (item = {}) => {
  const externalId = item?.standard_id ? `外部 ${item.standard_id}` : '外部 暂无'
  const internalId = item?.internal_standard_id ? `内部 ${item.internal_standard_id}` : ''
  return internalId ? `${internalId}｜${externalId}` : externalId
}

const getStandardIdParts = (item = {}) => {
  const parts = []
  if (item?.internal_standard_id) {
    parts.push({
      type: 'internal',
      label: '内部',
      value: item.internal_standard_id
    })
  }
  parts.push({
    type: 'external',
    label: '外部',
    value: item?.standard_id || '暂无'
  })
  return parts
}

const getStandardIdSearchText = (item = {}) => {
  return [
    item?.standard_id,
    item?.internal_standard_id,
    item?.code
  ].filter(Boolean).join(' ')
}

const getCombinedStandardDetailText = (item = {}) => {
  const sections = []
  if (item?.internal_standard_id || item?.internal_standard_detail_text) {
    sections.push([
      `内部规范ID：${item.internal_standard_id || '-'}`,
      item.internal_standard_detail_text || '暂无内部规范详情'
    ].join('\n'))
  }
  sections.push([
    `外部规范ID：${item.standard_id || '-'}`,
    item.standard_detail_text || '暂无外部规范详情'
  ].join('\n'))
  return sections.join('\n\n')
}

const standardSourceModeLabel = computed(() => (
  standardSourceMode.value === 'internal' ? '内部规范库' : '外部规范库'
))

const editStandardInputLabel = computed(() => (
  standardSourceMode.value === 'internal' ? '内部规范ID' : '外部规范ID'
))

const editStandardReferenceValue = computed(() => (
  standardSourceMode.value === 'internal'
    ? editDialog.value.form.internal_standard_id
    : editDialog.value.form.standard_id
))

const getStandardFallbackTitle = (item = {}) => {
  const firstLine = String(item.standard_detail_text || item.content || '')
    .replace(/\\n/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .find(Boolean)
  if (!firstLine) return ''
  const separatorIndex = firstLine.indexOf('：')
  return separatorIndex > -1 ? firstLine.slice(separatorIndex + 1).trim() : firstLine
}

const getEditStandardTitle = (item = {}) => {
  if (item.internal_standard_id) {
    const firstValue = editStandardFields.value
      .map((field) => String(item?.field_values?.[field.field_key] || '').trim())
      .find(Boolean)
    return firstValue || getStandardFallbackTitle(item) || '未命名内部规范'
  }
  return item.check_content || item.check_item || item.project_name || getStandardFallbackTitle(item) || '未命名外部规范'
}

const getEditStandardPreview = (item = {}) => {
  if (item.internal_standard_id) {
    return item.register_display_text || item.standard_detail_text || item.content || '暂无内部规范详情'
  }
  return item.register_display_text || item.standard_detail_text || '暂无外部规范详情'
}

const getEditStandardIdentity = (item = {}) => {
  if (item.internal_standard_id) return `internal:${item.internal_standard_id}`
  return `external:${item.inspection_table_id || 'unknown'}:${item.standard_id || ''}`
}

const selectedEditStandard = computed(() => {
  const currentValue = String(editStandardReferenceValue.value || '')
  if (!currentValue) return null
  if (standardSourceMode.value === 'internal') {
    return editStandards.value.find((item) => String(item.internal_standard_id || item.standard_id) === currentValue) || null
  }
  return editStandards.value.find((item) => String(item.standard_id) === currentValue) || null
})

const canKeepExternalOnlyIssueStandard = computed(() => (
  standardSourceMode.value === 'internal' &&
  !editDialog.value.standardDirty &&
  !editDialog.value.form.internal_standard_id &&
  Boolean(editDialog.value.form.standard_id)
))

const filteredEditStandards = computed(() => {
  const keyword = normalizedKeyword(editDialog.value.standardSearch).trim()
  return editStandards.value.filter((item) => {
    if (!keyword) return true
    const values = [
      item.standard_id,
      item.external_standard_id,
      item.internal_standard_id,
      item.inspection_table_name,
      item.standard_detail_text,
      item.register_display_text,
      item.content,
      ...Object.values(item.field_values || {}),
      ...(item.linked_externals || []).flatMap((link) => [
        link.external_standard_id,
        link.inspection_table_name,
        link.standard_detail_text
      ])
    ]
    return values.some((value) => normalizedKeyword(value).includes(keyword))
  }).slice(0, 40)
})

watch([filters, pageSize], () => {
  page.value = 1
}, { deep: true })

watch(totalPage, (value) => {
  if (page.value > value) {
    page.value = value
  }
})

watch(issueTableMinWidth, () => {
  if (tableFullscreen.value) {
    setAutoTableZoom()
  }
})

const scheduleListImageLoading = () => {
  listImagesReady.value = false
  if (listImagesReadyTimer) {
    clearTimeout(listImagesReadyTimer)
  }
  listImagesReadyTimer = window.setTimeout(() => {
    listImagesReady.value = true
    listImagesReadyTimer = null
  }, 160)
}

watch(
  () => paginatedData.value.map((item) => item.id).join(','),
  scheduleListImageLoading,
  { immediate: true }
)

const fetchIssues = async () => {
  try {
    loading.value = true
    const userId = localStorage.getItem('user_id') || ''
    const response = await axios.get('/api/issues', {
      params: {
        user_id: userId
      }
    })
    list.value = response.data || []
  } catch (error) {
    list.value = []
  } finally {
    loading.value = false
  }
}

const buildEditInternalStandardDetailText = (item, fields = editStandardFields.value) => {
  const lines = fields.map((field) => {
    const value = String(item?.field_values?.[field.field_key] || '').trim() || '-'
    return `${field.field_label}：${value}`
  })
  return lines.join('\n')
}

const fetchEditStandardReferenceData = async () => {
  try {
    editStandardLoading.value = true
    const modeResponse = await axios.get('/api/inspection-standard-usage-mode', {
      params: { _ts: Date.now() }
    })
    const nextMode = modeResponse.data?.usage_mode?.mode === 'internal' ? 'internal' : 'external'
    standardSourceMode.value = nextMode

    if (nextMode === 'internal') {
      const response = await axios.get('/api/inspection-internal-standards', {
        params: { _ts: Date.now() }
      })
      const fields = response.data?.fields || []
      editStandardFields.value = fields
      editStandards.value = (response.data?.items || []).map((item) => {
        const linkedExternals = item.linked_externals || []
        const linkedTableNames = [...new Set(
          linkedExternals
            .map((link) => String(link.inspection_table_name || '').trim())
            .filter(Boolean)
        )]
        return {
          ...item,
          standard_id: item.internal_standard_id,
          internal_standard_id: item.internal_standard_id,
          standard_detail_text: buildEditInternalStandardDetailText(item, fields),
          inspection_table_name: linkedTableNames.length
            ? `${linkedTableNames.join('、')}（共挂载${linkedExternals.length}条外部规范）`
            : '未挂载外部检查表',
          linked_externals: linkedExternals
        }
      })
      return
    }

    const response = await axios.get('/api/external-standards', {
      params: { _ts: Date.now() }
    })
    editStandardFields.value = []
    editStandards.value = (response.data?.items || []).map((item) => ({
      ...item,
      standard_id: String(item.standard_id || item.external_standard_id || ''),
      external_standard_id: item.external_standard_id || item.standard_id,
      internal_standard_id: item.linked_internal_standard_id || item.linked_internal?.internal_standard_id || '',
      inspection_table_id: String(item.inspection_table_id || ''),
      inspection_table_name: item.inspection_table_name || '未命名检查表',
      standard_detail_text: item.standard_detail_text || '',
      register_display_text: item.register_display_text || ''
    }))
  } catch (error) {
    editStandards.value = []
    editStandardFields.value = []
    showActionMessage(error?.response?.data?.error || '规范数据加载失败，请稍后重试。', 'error')
  } finally {
    editStandardLoading.value = false
  }
}

const fetchInspectorUserOptions = async () => {
  if (!editDialog.value.issue?.can_change_issue_inspector) {
    inspectorUserOptions.value = []
    return
  }
  try {
    inspectorUserLoading.value = true
    const response = await axios.get('/api/users', {
      params: { _ts: Date.now() }
    })
    inspectorUserOptions.value = (response.data || [])
      .filter((item) => ['root', 'supervisor'].includes(item.role))
      .map((item) => ({
        id: String(item.id),
        username: item.username || '',
        real_name: item.real_name || '',
        phone: item.phone || '',
        role: item.role || ''
      }))
  } catch (error) {
    inspectorUserOptions.value = []
    showActionMessage(error?.response?.data?.error || '检查人列表加载失败。', 'error')
  } finally {
    inspectorUserLoading.value = false
  }
}

const inspectorUserLabel = (item = {}) => {
  const name = item.real_name || item.username || `用户${item.id}`
  const extras = [item.username && item.username !== name ? item.username : '', item.phone]
    .filter(Boolean)
    .join('｜')
  return extras ? `${name}（${extras}）` : name
}

const resetFilters = () => {
  filters.value = {
    issueId: '',
    month: '',
    date: '',
    region: [],
    station: [],
    stationManager: '',
    inspector: [],
    inspectionTableName: [],
    standardId: '',
    standardDetail: '',
    rectificationResult: '',
    reviewResult: '',
    status: '',
    excellent: '',
    auditStatus: '',
    auditState: ''
  }
  filterSearch.value = {
    region: '',
    station: '',
    inspector: '',
    inspectionTableName: ''
  }
  closeAllDropdowns()
}

const formatLocalDate = (value = new Date()) => {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const filterMyTodayIssues = () => {
  const inspector = currentInspectorFilterValue.value
  if (!inspector) {
    showActionMessage('当前账号缺少姓名，暂时不能自动筛选。', 'error')
    return
  }
  filters.value = {
    issueId: '',
    month: '',
    date: formatLocalDate(),
    region: [],
    station: [],
    stationManager: '',
    inspector: [inspector],
    inspectionTableName: [],
    standardId: '',
    standardDetail: '',
    rectificationResult: '',
    reviewResult: '',
    status: '',
    excellent: '',
    auditStatus: '',
    auditState: ''
  }
  filterSearch.value = {
    region: '',
    station: '',
    inspector: '',
    inspectionTableName: ''
  }
  closeAllDropdowns()
  showMobileFilters.value = false
  showActionMessage('已筛选我今天检查的问题。', 'success')
}

const buildCurrentExportFilterSummary = () => {
  return Object.fromEntries(
    Object.entries(filters.value)
      .map(([key, value]) => {
        const normalized = Array.isArray(value)
          ? value.map((item) => String(item || '').trim()).filter(Boolean).join('、')
          : String(value || '').trim()
        return [key, normalized]
      })
      .filter(([_key, value]) => value)
  )
}

const createDefaultExportFieldOptions = () => {
  return Object.fromEntries(
    exportFieldOptions.map((option) => [
      option.key,
      option.photo ? canExportIssuePhotos.value : true
    ])
  )
}

const normalizeExportFieldOptions = (rawOptions = {}) => {
  const includeFields = rawOptions?.include_fields
  const defaults = createDefaultExportFieldOptions()
  if (!includeFields || typeof includeFields !== 'object') {
    return defaults
  }
  return Object.fromEntries(
    exportFieldOptions.map((option) => [
      option.key,
      option.photo
        ? Boolean(includeFields[option.key]) && canExportIssuePhotos.value
        : Boolean(includeFields[option.key])
    ])
  )
}

const buildExportPhotoOptionsFromFields = () => {
  return Object.fromEntries(
    exportPhotoFieldKeys.map((key) => [
      key,
      canExportIssuePhotos.value && Boolean(exportDialog.value.includeFields[key])
    ])
  )
}

const canSelectExportField = (option) => {
  if (exportDialog.value.taskId) return false
  return !option.photo || canExportIssuePhotos.value
}

const selectedExportFieldCount = computed(() => (
  exportFieldOptions.filter((option) => Boolean(exportDialog.value.includeFields[option.key])).length
))

const setAllExportFields = (checked) => {
  exportDialog.value.includeFields = Object.fromEntries(
    exportFieldOptions.map((option) => [
      option.key,
      canSelectExportField(option) ? checked : Boolean(exportDialog.value.includeFields[option.key])
    ])
  )
}

const invertExportFields = () => {
  exportDialog.value.includeFields = Object.fromEntries(
    exportFieldOptions.map((option) => [
      option.key,
      canSelectExportField(option)
        ? !Boolean(exportDialog.value.includeFields[option.key])
        : Boolean(exportDialog.value.includeFields[option.key])
    ])
  )
}

const resetExportDialogForCurrentFilters = () => {
  stopExportPolling()
  exportDialog.value = {
    visible: true,
    submitting: false,
    downloading: false,
    taskId: '',
    status: 'idle',
    error: '',
    selectedCount: filteredData.value.length,
    exportedCount: 0,
    fileName: '',
    fileSizeLabel: '',
    expiresAt: '',
    filterSummary: buildCurrentExportFilterSummary(),
    includeFields: createDefaultExportFieldOptions()
  }
}

const openExportDialog = () => {
  if (!filteredData.value.length) {
    showActionMessage('当前筛选结果为空，不能导出。', 'error')
    return
  }
  if (exportDialog.value.taskId && ['pending', 'running', 'completed', 'failed'].includes(exportDialog.value.status)) {
    exportDialog.value.visible = true
    if (['pending', 'running'].includes(exportDialog.value.status)) {
      startExportPolling()
    }
    return
  }
  resetExportDialogForCurrentFilters()
}

const closeExportDialog = () => {
  if (exportDialog.value.submitting) return
  exportDialog.value.visible = false
  if (!['pending', 'running'].includes(exportDialog.value.status)) {
    stopExportPolling()
  }
}

const stopExportPolling = () => {
  if (exportPollTimer) {
    window.clearInterval(exportPollTimer)
    exportPollTimer = null
  }
}

const applyExportTask = (task = {}) => {
  exportDialog.value.taskId = task.task_id || exportDialog.value.taskId
  exportDialog.value.status = task.status || exportDialog.value.status
  exportDialog.value.selectedCount = Number(task.selected_count ?? exportDialog.value.selectedCount) || 0
  exportDialog.value.exportedCount = Number(task.exported_count || 0)
  exportDialog.value.fileName = task.download_filename || exportDialog.value.fileName
  exportDialog.value.fileSizeLabel = task.file_size_label || ''
  exportDialog.value.expiresAt = task.expires_at || exportDialog.value.expiresAt
  exportDialog.value.filterSummary = task.filter_summary || exportDialog.value.filterSummary || {}
  exportDialog.value.includeFields = normalizeExportFieldOptions(task.export_options)
  exportDialog.value.error = task.error_message || ''
}

const pollIssueExportTask = async () => {
  if (!exportDialog.value.taskId) return
  try {
    const response = await axios.get(`/api/issues/export-tasks/${exportDialog.value.taskId}`, {
      params: {
        user_id: localStorage.getItem('user_id') || '',
        _ts: Date.now()
      }
    })
    applyExportTask(response.data?.task || {})
    if (['completed', 'failed'].includes(exportDialog.value.status)) {
      stopExportPolling()
      if (exportDialog.value.status === 'completed') {
        showActionMessage('巡检问题导出文件已生成。', 'success')
      }
    }
  } catch (error) {
    stopExportPolling()
    exportDialog.value.status = 'failed'
    exportDialog.value.error = error?.response?.data?.error || '导出任务状态查询失败。'
  }
}

const startExportPolling = () => {
  stopExportPolling()
  pollIssueExportTask()
  exportPollTimer = window.setInterval(pollIssueExportTask, 1600)
}

const submitIssueExportTask = async () => {
  if (!filteredData.value.length) {
    exportDialog.value.error = '当前筛选结果为空，不能导出。'
    return
  }
  if (!selectedExportFieldCount.value) {
    exportDialog.value.error = '请至少选择一个导出字段。'
    return
  }
  try {
    exportDialog.value.submitting = true
    exportDialog.value.error = ''
    const response = await axios.post('/api/issues/export-tasks', {
      user_id: localStorage.getItem('user_id') || '',
      issue_ids: filteredData.value.map((item) => item.id),
      filter_summary: buildCurrentExportFilterSummary(),
      export_options: {
        include_fields: { ...exportDialog.value.includeFields },
        include_photos: buildExportPhotoOptionsFromFields()
      }
    })
    applyExportTask(response.data?.task || {})
    startExportPolling()
  } catch (error) {
    exportDialog.value.error = error?.response?.data?.error || '导出任务提交失败。'
    exportDialog.value.status = 'failed'
  } finally {
    exportDialog.value.submitting = false
  }
}

const downloadIssueExport = async () => {
  if (!exportDialog.value.taskId) return
  try {
    exportDialog.value.downloading = true
    const response = await axios.get(`/api/issues/export-tasks/${exportDialog.value.taskId}/download`, {
      params: { user_id: localStorage.getItem('user_id') || '' },
      responseType: 'blob'
    })
    const blobUrl = window.URL.createObjectURL(new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }))
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = exportDialog.value.fileName || `巡检问题列表_${exportDialog.value.taskId.slice(0, 8)}.xlsx`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(blobUrl)
  } catch (error) {
    exportDialog.value.error = error?.response?.data?.error || '导出文件下载失败。'
  } finally {
    exportDialog.value.downloading = false
  }
}

const showActionMessage = (text, type = 'info') => {
  actionMessage.value = text
  actionMessageType.value = type
  if (actionMessageTimer) {
    clearTimeout(actionMessageTimer)
  }
  actionMessageTimer = window.setTimeout(() => {
    actionMessage.value = ''
  }, 2200)
}

const showAuditNotice = (title, message, type = 'success') => {
  auditNotice.value = {
    visible: true,
    type,
    title,
    message
  }
  if (auditNoticeTimer) {
    clearTimeout(auditNoticeTimer)
  }
  auditNoticeTimer = window.setTimeout(() => {
    auditNotice.value.visible = false
  }, 1900)
}

const createIssueEditForm = (item = {}) => ({
  standard_id: item.standard_id ? String(item.standard_id) : '',
  internal_standard_id: item.internal_standard_id ? String(item.internal_standard_id).toUpperCase() : '',
  target_inspector_id: item.inspector_user_id || item.inspector_id ? String(item.inspector_user_id || item.inspector_id) : '',
  description: item.description || '',
  status: item.raw_status || item.workflow_status || (item.status === '待签名' ? '待整改' : item.status) || '待整改',
  rectification_result: item.rectification_result || '',
  rectification_note: item.rectification_note || '',
  review_result: item.review_result || '',
  review_note: item.review_note || ''
})

const revokeIssuePhotoPreview = () => {
  revokeObjectUrl(editDialog.value.issuePhotoPreview)
}

const syncEditStandardSearch = () => {
  const selected = selectedEditStandard.value
  if (selected) {
    editDialog.value.standardSearch = `${editStandardReferenceValue.value}｜${getEditStandardTitle(selected)}`
    editDialog.value.standardDirty = false
    return
  }
  editDialog.value.standardSearch = editStandardReferenceValue.value || ''
  editDialog.value.standardDirty = false
}

const openEditDialog = async (item) => {
  revokeIssuePhotoPreview()
  editDialog.value = {
    visible: true,
    saving: false,
    error: '',
    issue: item,
    issuePhotoFile: null,
    issuePhotoPreview: '',
    standardSearch: '',
    standardDirty: false,
    form: createIssueEditForm(item)
  }
  editStandardDropdownVisible.value = false
  editIssuePhotoDragActive.value = false
  editIssuePhotoDragDepth = 0
  const preloadTasks = []
  if (item?.can_edit_issue) preloadTasks.push(fetchEditStandardReferenceData())
  if (item?.can_change_issue_inspector) preloadTasks.push(fetchInspectorUserOptions())
  await Promise.all(preloadTasks)
  if (item?.can_edit_issue) syncEditStandardSearch()
}

const closeEditDialog = () => {
  if (editDialog.value.saving) return
  revokeIssuePhotoPreview()
  clearFileInputsById(['edit-issue-photo-upload', 'edit-issue-photo-camera'])
  editStandardDropdownVisible.value = false
  editIssuePhotoDragActive.value = false
  editIssuePhotoDragDepth = 0
  editDialog.value = {
    visible: false,
    saving: false,
    error: '',
    issue: null,
    issuePhotoFile: null,
    issuePhotoPreview: '',
    standardSearch: '',
    standardDirty: false,
    form: createIssueEditForm()
  }
}

const processIssuePhotoFile = async (file) => {
  revokeIssuePhotoPreview()
  if (!file) {
    editDialog.value.issuePhotoFile = null
    editDialog.value.issuePhotoPreview = ''
    return false
  }

  try {
    const prepared = await prepareImagePreview(file)
    editDialog.value.issuePhotoFile = prepared.file
    editDialog.value.issuePhotoPreview = prepared.previewUrl
    editDialog.value.error = ''
    return true
  } catch (error) {
    editDialog.value.issuePhotoFile = null
    editDialog.value.issuePhotoPreview = ''
    editDialog.value.error = error?.message || '图片处理失败，请更换图片后重试。'
    return false
  }
}

const scrollToEditIssuePhotoUpload = async () => {
  await nextTick()
  scrollImageUploadIntoView(editIssuePhotoUploadSectionRef.value, {
    topOffset: 40,
    bottomOffset: 24
  })
}

const handleIssuePhotoChange = async (event) => {
  await processIssuePhotoFile(event.target.files?.[0])
  if (!editDialog.value.issuePhotoFile) {
    clearFileInput(event)
  }
}

const openEditIssuePhotoPicker = () => {
  document.getElementById('edit-issue-photo-upload')?.click()
}

const handleEditIssuePhotoDragEnter = (event) => {
  if (!isDesktopImageDropEnabled() || !hasImageInDataTransfer(event.dataTransfer)) return
  editIssuePhotoDragDepth += 1
  editIssuePhotoDragActive.value = true
}

const handleEditIssuePhotoDragOver = (event) => {
  if (!isDesktopImageDropEnabled() || !hasImageInDataTransfer(event.dataTransfer)) return
  event.dataTransfer.dropEffect = 'copy'
  editIssuePhotoDragActive.value = true
}

const handleEditIssuePhotoDragLeave = () => {
  if (!isDesktopImageDropEnabled()) return
  editIssuePhotoDragDepth = Math.max(editIssuePhotoDragDepth - 1, 0)
  if (editIssuePhotoDragDepth === 0) {
    editIssuePhotoDragActive.value = false
  }
}

const handleEditIssuePhotoDrop = async (event) => {
  if (!isDesktopImageDropEnabled()) return
  editIssuePhotoDragDepth = 0
  editIssuePhotoDragActive.value = false
  const file = getImageFileFromDataTransfer(event.dataTransfer)
  if (!file) {
    editDialog.value.error = '请拖入图片文件。'
    return
  }
  await processIssuePhotoFile(file)
}

const handleEditIssuePhotoPaste = async (event) => {
  const file = getImageFileFromClipboardEvent(event)
  if (!file) {
    editDialog.value.error = '剪贴板里没有可上传的图片。'
    return
  }
  event.preventDefault()
  editIssuePhotoDragDepth = 0
  editIssuePhotoDragActive.value = false
  const uploaded = await processIssuePhotoFile(file)
  if (uploaded) {
    await scrollToEditIssuePhotoUpload()
  }
}

const handleWindowEditIssuePhotoPaste = async (event) => {
  if (event.defaultPrevented || !editDialog.value.visible) return
  if (!canEditDialogIssueContent.value) return
  const file = getImageFileFromClipboardEvent(event)
  if (!file) return
  event.preventDefault()
  editIssuePhotoDragDepth = 0
  editIssuePhotoDragActive.value = false
  const uploaded = await processIssuePhotoFile(file)
  if (uploaded) {
    await scrollToEditIssuePhotoUpload()
  }
}

const clearIssuePhoto = () => {
  editDialog.value.issuePhotoFile = null
  revokeIssuePhotoPreview()
  editDialog.value.issuePhotoPreview = ''
  editIssuePhotoDragActive.value = false
  editIssuePhotoDragDepth = 0
  clearFileInputsById(['edit-issue-photo-upload', 'edit-issue-photo-camera'])
}

const openEditStandardDropdown = () => {
  editStandardDropdownVisible.value = true
}

const handleEditStandardInput = () => {
  editDialog.value.standardDirty = true
  if (standardSourceMode.value === 'internal') {
    editDialog.value.form.internal_standard_id = ''
  } else {
    editDialog.value.form.standard_id = ''
  }
  editStandardDropdownVisible.value = true
}

const selectEditStandard = (standard) => {
  if (standardSourceMode.value === 'internal') {
    editDialog.value.form.internal_standard_id = String(standard.internal_standard_id || standard.standard_id || '').toUpperCase()
    const firstExternal = (standard.linked_externals || [])[0]
    editDialog.value.form.standard_id = firstExternal?.external_standard_id ? String(firstExternal.external_standard_id) : ''
  } else {
    editDialog.value.form.standard_id = String(standard.standard_id || standard.external_standard_id || '')
    editDialog.value.form.internal_standard_id = standard.internal_standard_id ? String(standard.internal_standard_id).toUpperCase() : ''
  }
  editDialog.value.standardSearch = `${editStandardReferenceValue.value}｜${getEditStandardTitle(standard)}`
  editDialog.value.standardDirty = false
  editStandardDropdownVisible.value = false
  editDialog.value.error = ''
}

const revokeRectificationPhotoPreview = () => {
  revokeObjectUrl(rectificationPhotoDialog.value.preview)
}

const openRectificationPhotoDialog = (item) => {
  revokeRectificationPhotoPreview()
  rectificationPhotoDialog.value = {
    visible: true,
    saving: false,
    error: '',
    issue: item,
    file: null,
    preview: ''
  }
}

const closeRectificationPhotoDialog = () => {
  if (rectificationPhotoDialog.value.saving) return
  revokeRectificationPhotoPreview()
  rectificationPhotoDialog.value = {
    visible: false,
    saving: false,
    error: '',
    issue: null,
    file: null,
    preview: ''
  }
}

const handleRectificationPhotoChange = async (event) => {
  const file = event.target.files?.[0]
  revokeRectificationPhotoPreview()
  if (!file) {
    rectificationPhotoDialog.value.file = null
    rectificationPhotoDialog.value.preview = ''
    return
  }

  try {
    const prepared = await prepareImagePreview(file)
    rectificationPhotoDialog.value.file = prepared.file
    rectificationPhotoDialog.value.preview = prepared.previewUrl
    rectificationPhotoDialog.value.error = ''
  } catch (error) {
    clearFileInput(event)
    rectificationPhotoDialog.value.file = null
    rectificationPhotoDialog.value.preview = ''
    rectificationPhotoDialog.value.error = error?.message || '图片处理失败，请更换图片后重试。'
  }
}

const saveRectificationPhoto = async () => {
  const issueId = rectificationPhotoDialog.value.issue?.id
  if (!issueId) {
    rectificationPhotoDialog.value.error = '当前问题缺少编号，无法保存整改照片。'
    return
  }
  if (!rectificationPhotoDialog.value.file) {
    rectificationPhotoDialog.value.error = '请先选择新的整改照片。'
    return
  }

  let preserveFullscreen = false
  try {
    rectificationPhotoDialog.value.saving = true
    rectificationPhotoDialog.value.error = ''
    const formData = new FormData()
    formData.append('user_id', localStorage.getItem('user_id') || '')
    formData.append('rectification_photo', rectificationPhotoDialog.value.file)
    await axios.post(`/api/issues/${issueId}/rectification-photo`, formData)
    preserveFullscreen = beginFullscreenDomPreservation()
    closeRectificationPhotoDialog()
    showActionMessage('整改照片已更新。', 'success')
    await fetchIssues()
  } catch (error) {
    rectificationPhotoDialog.value.error = error?.response?.data?.error || '整改照片更新失败。'
  } finally {
    await finishFullscreenDomPreservation(preserveFullscreen)
    if (rectificationPhotoDialog.value.visible) {
      rectificationPhotoDialog.value.saving = false
    }
  }
}

const saveIssueEdit = async () => {
  const issueId = editDialog.value.issue?.id
  if (!issueId) {
    editDialog.value.error = '当前问题缺少编号，无法保存。'
    return
  }

  if (canEditDialogIssueContent.value) {
    if (!editDialog.value.form.description.trim()) {
      editDialog.value.error = '请填写问题描述。'
      return
    }

    if (!editStandardReferenceValue.value && !canKeepExternalOnlyIssueStandard.value) {
      editDialog.value.error = `请选择${editStandardInputLabel.value}。`
      return
    }

    if (!selectedEditStandard.value && !canKeepExternalOnlyIssueStandard.value) {
      editDialog.value.error = `请选择有效的${editStandardInputLabel.value}，不要只输入未匹配的文本。`
      return
    }
  } else if (!canChangeDialogIssueInspector.value) {
    editDialog.value.error = '当前账号无权保存该问题。'
    return
  }

  let preserveFullscreen = false
  try {
    editDialog.value.saving = true
    editDialog.value.error = ''
    const userId = localStorage.getItem('user_id') || ''
    const formData = new FormData()
    formData.append('user_id', userId)
    formData.append('standard_source_mode', standardSourceMode.value)
    Object.entries(editDialog.value.form).forEach(([key, value]) => {
      formData.append(key, value ?? '')
    })
    if (editDialog.value.issuePhotoFile) {
      formData.append('issue_photo', editDialog.value.issuePhotoFile)
    }
    await axios.put(`/api/issues/${issueId}`, formData)
    preserveFullscreen = beginFullscreenDomPreservation()
    editDialog.value.saving = false
    closeEditDialog()
    showActionMessage('巡检问题已保存。', 'success')
    await fetchIssues()
    window.dispatchEvent(new Event('my-pending-rectification-refresh'))
  } catch (error) {
    editDialog.value.error = error?.response?.data?.error || '保存巡检问题失败。'
  } finally {
    await finishFullscreenDomPreservation(preserveFullscreen)
    if (editDialog.value.visible) {
      editDialog.value.saving = false
    }
  }
}

const deleteIssue = async (item) => {
  if (!item?.id) return

  const confirmed = window.confirm(`确认删除问题 #${item.id} 吗？删除后巡检记录的问题数量会自动重新计算。`)
  if (!confirmed) return

  let preserveFullscreen = false
  try {
    deletingIssueId.value = item.id
    const userId = localStorage.getItem('user_id') || ''
    await axios.delete(`/api/issues/${item.id}`, {
      data: { user_id: userId }
    })
    preserveFullscreen = beginFullscreenDomPreservation()
    showActionMessage('巡检问题已删除。', 'success')
    await fetchIssues()
    window.dispatchEvent(new Event('my-pending-rectification-refresh'))
  } catch (error) {
    showActionMessage(error?.response?.data?.error || '删除巡检问题失败。', 'error')
  } finally {
    await finishFullscreenDomPreservation(preserveFullscreen)
    deletingIssueId.value = null
  }
}

const auditIssue = async (item, status) => {
  if (!item?.id || auditingIssueId.value === item.id) return
  const actionLabels = {
    approved: '审核通过',
    rejected: '审核否决',
    pending: '重新判定'
  }
  const actionLabel = actionLabels[status] || '审核'

  let preserveFullscreen = false
  try {
    auditingIssueId.value = item.id
    const response = await axios.post(`/api/issues/${item.id}/audit`, {
      user_id: localStorage.getItem('user_id') || '',
      action: status
    })
    preserveFullscreen = beginFullscreenDomPreservation()
    const message = response.data?.message || `问题 #${item.id} 已${actionLabel}。`
    showAuditNotice(actionLabel, message, status === 'rejected' ? 'danger' : 'success')
    await fetchIssues()
    window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
    window.dispatchEvent(new Event('my-pending-rectification-refresh'))
  } catch (error) {
    showAuditNotice('审核失败', error?.response?.data?.error || '问题审核操作失败。', 'danger')
  } finally {
    await finishFullscreenDomPreservation(preserveFullscreen)
    auditingIssueId.value = null
  }
}

const toggleIssueExcellent = async (item) => {
  if (!item?.id || markingExcellentIssueId.value === item.id) return
  if (!canToggleExcellentIssue(item)) {
    showActionMessage(excellentStarTitle(item), 'error')
    return
  }

  const nextExcellent = !item.is_excellent
  try {
    markingExcellentIssueId.value = item.id
    const response = await axios.post(`/api/issues/${item.id}/excellent`, {
      user_id: localStorage.getItem('user_id') || '',
      is_excellent: nextExcellent
    })
    const updatedExcellent = Boolean(response.data?.is_excellent)
    list.value = list.value.map((row) => (
      row.id === item.id ? { ...row, is_excellent: updatedExcellent } : row
    ))
    showActionMessage(response.data?.message || (updatedExcellent ? '已点亮优秀问题。' : '已取消优秀问题标记。'), 'success')
  } catch (error) {
    showActionMessage(error?.response?.data?.error || '优秀问题标记失败。', 'error')
  } finally {
    markingExcellentIssueId.value = null
  }
}

const calculateAutoTableZoom = () => {
  const tableWidth = issueTableMinWidth.value
  const viewportWidth = Math.max(window.innerWidth || tableWidth, 320)
  const horizontalPadding = tableFullscreen.value ? 64 : 40
  const nextZoom = (viewportWidth - horizontalPadding) / tableWidth
  return Number(Math.min(1, Math.max(0.2, nextZoom)).toFixed(2))
}

const setAutoTableZoom = () => {
  tableZoom.value = calculateAutoTableZoom()
}

const applyRememberedOrAutoTableZoom = () => {
  tableZoom.value = rememberedFullscreenZoom ?? calculateAutoTableZoom()
}

const rememberTableZoom = () => {
  rememberedFullscreenZoom = tableZoom.value
}

const enterTableFullscreen = async () => {
  const fullscreenTarget = tableCardRef.value
  try {
    if (fullscreenTarget?.requestFullscreen && !document.fullscreenElement) {
      await fullscreenTarget.requestFullscreen()
    }
  } catch (error) {
    // 浏览器拒绝原生全屏时，仍保留页面内全屏兜底。
  }
  tableFullscreen.value = true
  await nextTick()
  applyRememberedOrAutoTableZoom()
}

const beginFullscreenDomPreservation = () => {
  const shouldPreserve = tableFullscreen.value || document.fullscreenElement === tableCardRef.value
  if (!shouldPreserve) return false
  fullscreenDomMutationGuard = true
  if (fullscreenDomMutationTimer) {
    clearTimeout(fullscreenDomMutationTimer)
    fullscreenDomMutationTimer = null
  }
  return true
}

const finishFullscreenDomPreservation = async (shouldPreserve) => {
  if (!shouldPreserve) return
  await nextTick()
  tableFullscreen.value = true
  applyRememberedOrAutoTableZoom()
  if (!document.fullscreenElement && tableCardRef.value?.requestFullscreen) {
    try {
      await tableCardRef.value.requestFullscreen()
    } catch (error) {
      // 异步保存后浏览器可能拒绝重新进入原生全屏，保留页面内全屏兜底。
    }
  }
  await nextTick()
  tableFullscreen.value = true
  applyRememberedOrAutoTableZoom()
  fullscreenDomMutationTimer = window.setTimeout(() => {
    fullscreenDomMutationGuard = false
    fullscreenDomMutationTimer = null
  }, 450)
}

const exitTableFullscreen = async () => {
  rememberedFullscreenZoom = tableZoom.value
  fullscreenDomMutationGuard = false
  if (fullscreenDomMutationTimer) {
    clearTimeout(fullscreenDomMutationTimer)
    fullscreenDomMutationTimer = null
  }
  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    }
  } catch (error) {
    // 退出原生全屏失败不影响页面状态恢复。
  }
  tableFullscreen.value = false
  tableZoom.value = 1
}

const toggleTableFullscreen = () => {
  if (tableFullscreen.value || document.fullscreenElement === tableCardRef.value) {
    exitTableFullscreen()
    return
  }
  enterTableFullscreen()
}

const handleTableFullscreenChange = () => {
  if (document.fullscreenElement === tableCardRef.value) {
    tableFullscreen.value = true
    applyRememberedOrAutoTableZoom()
    return
  }
  if (!document.fullscreenElement && tableFullscreen.value) {
    if (fullscreenDomMutationGuard) {
      tableFullscreen.value = true
      nextTick(() => {
        if (tableFullscreen.value) {
          applyRememberedOrAutoTableZoom()
        }
      })
      return
    }
    tableFullscreen.value = false
    tableZoom.value = 1
  }
}


const nextPage = () => {
  goToPage(page.value + 1)
}

const scrollIssueTableToTop = async () => {
  await nextTick()
  const tableScroll = tableScrollRef.value
  if (tableScroll) {
    tableScroll.scrollTo({
      top: 0,
      left: tableScroll.scrollLeft,
      behavior: 'smooth'
    })
  }
  if (!isMobileView.value && !tableFullscreen.value && tableCardRef.value) {
    tableCardRef.value.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
      inline: 'nearest'
    })
  }
}

const goToPage = (targetPage) => {
  const normalizedPage = Number.parseInt(targetPage, 10)
  if (!Number.isFinite(normalizedPage)) return
  const safePage = Math.min(Math.max(normalizedPage, 1), totalPage.value)
  const pageChanged = safePage !== page.value
  page.value = safePage
  if (pageChanged) {
    scrollIssueTableToTop()
  }
}

const prevPage = () => {
  goToPage(page.value - 1)
}

const jumpToInputPage = () => {
  goToPage(pageJumpInput.value)
  pageJumpInput.value = ''
}

const previewState = ref({
  visible: false,
  url: '',
  title: '',
  scale: 1
})

const standardDetailState = ref({
  visible: false,
  title: '',
  content: '',
  item: null
})

const resolveImage = (path) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  const normalizedPath = String(path).startsWith('/') ? path.slice(1) : path
  return `/storage/${normalizedPath}`
}

const preview = (url, title) => {
  previewState.value = {
    visible: true,
    url,
    title,
    scale: 1
  }
}

const closePreview = () => {
  previewState.value = {
    visible: false,
    url: '',
    title: '',
    scale: 1
  }
}

const previewImageStyle = computed(() => ({
  transform: `scale(${previewState.value.scale})`
}))

const resetPreviewScale = () => {
  previewState.value.scale = 1
}

const handlePreviewWheel = (event) => {
  const delta = event.deltaY > 0 ? -0.12 : 0.12
  const nextScale = previewState.value.scale + delta
  previewState.value.scale = Math.min(4, Math.max(0.5, Number(nextScale.toFixed(2))))
}

const openStandardDetail = (item) => {
  standardDetailState.value = {
    visible: true,
    title: `规范详情｜${item.inspection_table_name || '未命名检查表'}｜${getStandardIdDisplay(item)}`,
    content: getCombinedStandardDetailText(item),
    item: { ...item }
  }
}

const closeStandardDetail = () => {
  standardDetailState.value = {
    visible: false,
    title: '',
    content: '',
    item: null
  }
}

const standardInternalEntries = computed(() => {
  const item = standardDetailState.value.item || {}
  if (!item.internal_standard_id && !item.internal_standard_detail_text) return []
  return parseStandardDetailText(item.internal_standard_detail_text || '暂无内部规范详情')
})

const standardExternalEntries = computed(() => {
  const item = standardDetailState.value.item || {}
  return parseStandardDetailText(item.standard_detail_text || '暂无外部规范详情')
})

const openFilterDropdown = (key) => {
  dropdownVisible.value[key] = true
}

const selectFilterOption = (key, value) => {
  filters.value[key] = value
  dropdownVisible.value[key] = false
}

const isMultiFilterSelected = (key, value) => {
  return getMultiFilterValues(key).includes(value)
}

const toggleMultiFilter = (key, value) => {
  const current = getMultiFilterValues(key)
  filters.value[key] = current.includes(value)
    ? current.filter((item) => item !== value)
    : [...current, value]
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
    region: regionFilterInputRef,
    station: stationFilterInputRef,
    inspector: inspectorFilterInputRef,
    inspectionTableName: inspectionTableFilterInputRef
  }
  refMap[key]?.value?.focus()
}

const closeAllDropdowns = () => {
  dropdownVisible.value = {
    region: false,
    station: false,
    stationManager: false,
    inspector: false,
    inspectionTableName: false
  }
}

const handleClickOutside = (event) => {
  if (regionSelectRef.value && !regionSelectRef.value.contains(event.target)) {
    dropdownVisible.value.region = false
  }
  if (stationSelectRef.value && !stationSelectRef.value.contains(event.target)) {
    dropdownVisible.value.station = false
  }
  if (stationManagerSelectRef.value && !stationManagerSelectRef.value.contains(event.target)) {
    dropdownVisible.value.stationManager = false
  }
  if (inspectorSelectRef.value && !inspectorSelectRef.value.contains(event.target)) {
    dropdownVisible.value.inspector = false
  }
  if (inspectionTableSelectRef.value && !inspectionTableSelectRef.value.contains(event.target)) {
    dropdownVisible.value.inspectionTableName = false
  }
  if (editStandardSelectRef.value && !editStandardSelectRef.value.contains(event.target)) {
    editStandardDropdownVisible.value = false
  }
  if (columnSettingsRef.value && !columnSettingsRef.value.contains(event.target)) {
    columnSettingsOpen.value = false
  }
}

const statusClass = (status) => {
  if (status === '待审核') return 'status-tag audit'
  if (status === '待签名') return 'status-tag pending'
  if (status === '待整改') return 'status-tag danger'
  if (status === '待复核') return 'status-tag warning'
  if (status === '已闭环') return 'status-tag success'
  if (status === '站经无法整改') return 'status-tag neutral'
  return 'status-tag'
}

const updateResponsiveState = () => {
  const nextIsMobile = window.matchMedia?.('(max-width: 768px)').matches ?? false
  if (tableFullscreen.value) {
    applyRememberedOrAutoTableZoom()
  }
  if (nextIsMobile === isMobileView.value) return
  isMobileView.value = nextIsMobile
  pageSize.value = nextIsMobile ? 5 : 20
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('paste', handleWindowEditIssuePhotoPaste)
  updateResponsiveState()
  window.addEventListener('resize', updateResponsiveState)
  document.addEventListener('fullscreenchange', handleTableFullscreenChange)
  fetchIssues()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('paste', handleWindowEditIssuePhotoPaste)
  window.removeEventListener('resize', updateResponsiveState)
  document.removeEventListener('fullscreenchange', handleTableFullscreenChange)
  stopExportPolling()
  revokeIssuePhotoPreview()
  revokeRectificationPhotoPreview()
  if (actionMessageTimer) {
    clearTimeout(actionMessageTimer)
  }
  if (auditNoticeTimer) {
    clearTimeout(auditNoticeTimer)
  }
  if (fullscreenDomMutationTimer) {
    clearTimeout(fullscreenDomMutationTimer)
  }
  if (listImagesReadyTimer) {
    clearTimeout(listImagesReadyTimer)
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

.filter-item-wide {
  grid-column: span 2;
}

.search-select {
  position: relative;
}

.search-select input {
  width: 100%;
}

.multi-search-select .multi-select-control {
  min-height: 42px;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 5px 8px;
  background: #fff;
  cursor: text;
  box-sizing: border-box;
}

.multi-search-select .multi-select-control:focus-within {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.multi-selected-values {
  flex: 1;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.multi-selected-values input {
  flex: 1;
  min-width: 96px;
  height: 28px;
  border: 0;
  border-radius: 0;
  padding: 0 4px;
  box-shadow: none;
  background: transparent;
}

.multi-selected-values input:focus {
  outline: none;
  box-shadow: none;
}

.multi-selected-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  padding: 4px 7px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #075985;
  font-size: 12px;
  font-weight: 800;
}

.multi-selected-chip button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border: 0;
  border-radius: 50%;
  background: rgba(7, 89, 133, 0.12);
  color: #075985;
  cursor: pointer;
}

.multi-selected-count {
  flex: 0 0 auto;
  padding: 3px 7px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
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
  width: 100%;
  display: block;
  padding: 10px 12px;
  border: 0;
  cursor: pointer;
  border-bottom: 1px solid #eef2f7;
  background: #fff;
  text-align: left;
}

.search-select-option:last-child {
  border-bottom: none;
}

.search-select-option:hover {
  background: #f8fafc;
}

.multi-select-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.multi-select-option.selected {
  background: #eff6ff;
}

.multi-option-check {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  color: #2563eb;
  font-size: 12px;
  font-weight: 900;
  background: #fff;
}

.multi-select-option.selected .multi-option-check {
  border-color: #2563eb;
  background: #dbeafe;
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

.filter-item label {
  font-size: 14px;
  font-weight: 700;
  color: #374151;
}

.filter-item input,
.filter-item select {
  width: 100%;
  height: 42px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 14px;
  box-sizing: border-box;
}

.filter-item .multi-selected-values input {
  width: auto;
  flex: 1;
  min-width: 96px;
  height: 28px;
  border: 0;
  border-radius: 0;
  padding: 0 4px;
  background: transparent;
  box-shadow: none;
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

.excellent-filter-toggle {
  display: grid;
  grid-template-columns: 1.2fr 0.9fr 0.9fr;
  gap: 8px;
}

.excellent-filter-toggle button {
  height: 40px;
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  background: #fff;
  color: #64748b;
  font-size: 15px;
  font-weight: 900;
  cursor: pointer;
  transition: all 0.18s ease;
}

.excellent-filter-toggle button:hover,
.excellent-filter-toggle button.active {
  border-color: #fbbf24;
  background: linear-gradient(135deg, #fffbeb 0%, #fff7ed 100%);
  color: #b45309;
  box-shadow: 0 10px 22px rgba(245, 158, 11, 0.12);
}

.excellent-filter-toggle .star-filter-btn {
  font-size: 22px;
  line-height: 1;
}

.excellent-filter-toggle .star-filter-btn.muted {
  color: #94a3b8;
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
  font-weight: 800;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.2);
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
}

.btn-light {
  background: #fff;
  color: #334155;
  border-color: #cbd5e1;
  font-weight: 800;
}

.btn-light:hover:not(:disabled) {
  background: #f8fafc;
}

.btn-danger {
  border-color: #fecaca;
  background: #fef2f2;
  color: #b91c1c;
  font-weight: 800;
}

.btn-danger:hover:not(:disabled) {
  background: #fee2e2;
}

.btn-success {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
  font-weight: 800;
}

.btn-success:hover:not(:disabled) {
  background: #dcfce7;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.audit-center-notice {
  position: fixed;
  inset: 0;
  z-index: 1800;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  pointer-events: none;
  background: rgba(15, 23, 42, 0.12);
  backdrop-filter: blur(2px);
}

.audit-center-card {
  width: min(420px, 100%);
  padding: 24px 22px;
  text-align: center;
  border-radius: 24px;
  box-shadow: 0 28px 58px rgba(15, 23, 42, 0.22);
}

.audit-center-icon {
  width: 54px;
  height: 54px;
  margin: 0 auto 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  background: #dcfce7;
  color: #15803d;
  font-size: 26px;
  font-weight: 950;
}

.audit-center-notice.danger .audit-center-icon {
  background: #fee2e2;
  color: #b91c1c;
}

.audit-center-card strong {
  display: block;
  color: #0f172a;
  font-size: 20px;
  font-weight: 950;
}

.audit-center-card p {
  margin: 8px 0 0;
  color: #475569;
  font-size: 14px;
  line-height: 1.8;
}

.audit-notice-fade-enter-active,
.audit-notice-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.audit-notice-fade-enter-from,
.audit-notice-fade-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

.message-toast {
  position: fixed;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: min(calc(100vw - 32px), 440px);
  z-index: 1500;
  padding: 14px 16px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 900;
  line-height: 1.7;
  text-align: center;
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.18);
  backdrop-filter: blur(10px);
  animation: toast-pulse 1.2s ease-in-out infinite;
}

.message-toast.error {
  border: 1px solid #fecaca;
  background: rgba(254, 242, 242, 0.98);
  color: #b91c1c;
}

.message-toast.success {
  border: 1px solid #bbf7d0;
  background: rgba(236, 253, 245, 0.98);
  color: #166534;
}

.message-toast.info {
  border: 1px solid #bfdbfe;
  background: rgba(239, 246, 255, 0.98);
  color: #1d4ed8;
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

@keyframes toast-pulse {

  0%,
  100% {
    box-shadow: 0 18px 36px rgba(15, 23, 42, 0.16);
  }

  50% {
    box-shadow: 0 22px 44px rgba(37, 99, 235, 0.22);
  }
}

.mobile-issue-list {
  display: none;
}

.mobile-pagination-bar {
  display: none;
}

.mobile-issue-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-issue-card {
  padding: 16px;
}

.mobile-issue-card.issue-audit-approved {
  border-color: #bbf7d0;
  background:
    radial-gradient(circle at 100% 0%, rgba(34, 197, 94, 0.12), transparent 30%),
    rgba(240, 253, 244, 0.94);
}

.mobile-issue-card.issue-audit-rejected {
  border-color: #fecaca;
  background:
    radial-gradient(circle at 100% 0%, rgba(239, 68, 68, 0.11), transparent 30%),
    rgba(254, 242, 242, 0.94);
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

.mobile-card-title-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex: 0 0 auto;
}

.mobile-card-category {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
}

.mobile-card-code {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
  color: #334155;
  font-weight: 700;
}

.mobile-card-code>span {
  color: #64748b;
  font-size: 12px;
  flex: 0 0 auto;
}

.mobile-card-meta {
  font-size: 12px;
  color: #64748b;
}

.mobile-card-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mobile-card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mobile-card-row span {
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
}

.mobile-card-row strong {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  text-align: right;
}

.mobile-card-row .standard-id-stack {
  align-items: flex-end;
}

.mobile-card-row-top {
  align-items: flex-start;
}

.mobile-card-text {
  flex: 1;
  font-size: 14px;
  line-height: 1.7;
  color: #334155;
  text-align: right;
}

.mobile-card-standard-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.mobile-card-standard-preview {
  width: 100%;
  text-align: left;
  white-space: pre-line;
}

.mobile-card-images {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.mobile-image-btn {
  border: 1px solid #dbe4ee;
  border-radius: 14px;
  background: #fff;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
}

.mobile-image-btn span {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
}

.mobile-thumb {
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
}

.mobile-thumb-placeholder,
.thumb-placeholder {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed #bfdbfe;
  background: linear-gradient(135deg, #f8fbff 0%, #eef6ff 100%);
  color: #2563eb;
  font-weight: 900;
}

.mobile-thumb-placeholder {
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: 10px;
  font-size: 12px;
}

.mobile-card-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed #dbe4ee;
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

.btn-secondary:hover {
  background: #f9fafb;
}

.btn-export {
  border-color: #99f6e4;
  background: linear-gradient(135deg, #ecfeff 0%, #f0fdf4 100%);
  color: #0f766e;
  font-weight: 900;
  box-shadow: 0 10px 20px rgba(15, 118, 110, 0.12);
}

.btn-export:hover:not(:disabled) {
  border-color: #5eead4;
  background: linear-gradient(135deg, #ccfbf1 0%, #dcfce7 100%);
}

.table-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.table-card-head h3 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
}

.table-view-actions {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.column-settings-wrap {
  position: relative;
}

.column-settings-btn {
  border-color: #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 900;
}

.column-settings-panel {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  z-index: 40;
  width: min(620px, calc(100vw - 48px));
  padding: 16px;
  box-shadow: 0 24px 58px rgba(15, 23, 42, 0.18);
}

.column-settings-panel::before {
  content: "";
  position: absolute;
  top: -7px;
  right: 42px;
  width: 14px;
  height: 14px;
  transform: rotate(45deg);
  border-top: 1px solid #dbe4ee;
  border-left: 1px solid #dbe4ee;
  background: rgba(255, 255, 255, 0.96);
}

.column-settings-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.column-settings-header strong {
  display: block;
  color: #0f172a;
  font-size: 18px;
  font-weight: 950;
}

.column-settings-header p {
  margin: 5px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.column-settings-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 14px 0;
}

.column-settings-groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  max-height: min(58vh, 520px);
  overflow: auto;
  padding-right: 2px;
}

.column-settings-group {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background:
    radial-gradient(circle at 100% 0%, rgba(37, 99, 235, 0.08), transparent 34%),
    #f8fafc;
}

.column-settings-group-title {
  margin-bottom: 9px;
  color: #334155;
  font-size: 13px;
  font-weight: 950;
}

.column-toggle-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  margin-top: 7px;
  padding: 0 10px;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  background: #fff;
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.18s ease;
}

.column-toggle-item input {
  accent-color: #2563eb;
}

.column-toggle-item.active {
  border-color: #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  box-shadow: 0 8px 16px rgba(37, 99, 235, 0.08);
}

.table-zoom-control {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0 12px;
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  background: #f8fafc;
  color: #475569;
  font-size: 13px;
  font-weight: 900;
}

.table-zoom-control input {
  width: 150px;
  accent-color: #2563eb;
}

.fullscreen-table-card {
  position: fixed;
  inset: 16px;
  z-index: 900;
  display: flex;
  flex-direction: column;
  padding: 18px;
  background:
    radial-gradient(circle at 8% 0%, rgba(37, 99, 235, 0.1), transparent 32%),
    rgba(255, 255, 255, 0.98);
}

.fullscreen-table-card:fullscreen {
  inset: 0;
  width: 100vw;
  height: 100vh;
  border-radius: 0;
  box-shadow: none;
}

.fullscreen-table-card .table-scroll-wrap {
  flex: 1;
  min-height: 0;
}

.fullscreen-table-card .table-scroll {
  max-height: none;
  height: 100%;
  overflow: auto;
}

.fullscreen-table-card .issues-table {
  zoom: var(--issue-table-zoom);
}

.fullscreen-overlay-host {
  display: none;
}

.fullscreen-table-card .fullscreen-overlay-host {
  position: absolute;
  inset: 0;
  z-index: 9000;
  display: block;
  pointer-events: none;
}

.fullscreen-overlay-host .image-modal,
.fullscreen-overlay-host .issue-photo-preview-overlay,
.fullscreen-overlay-host .audit-center-notice,
.fullscreen-overlay-host .message-toast {
  z-index: 9500;
}

.fullscreen-overlay-host .image-modal,
.fullscreen-overlay-host .issue-photo-preview-overlay {
  pointer-events: auto;
}

.fullscreen-overlay-host .message-toast {
  pointer-events: none;
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

.issues-table {
  width: 100%;
  min-width: var(--issue-table-min-width, 3140px);
  border-collapse: collapse;
}

.issues-table th,
.issues-table td {
  border: 1px solid #e5e7eb;
  padding: 10px 12px;
  text-align: center;
  vertical-align: middle;
  font-size: 14px;
  color: #111827;
}

.issues-table th {
  background: #f8fafc;
  font-weight: 700;
  white-space: nowrap;
}

.issues-table tr.issue-audit-approved td {
  background: rgba(240, 253, 244, 0.86);
}

.issues-table tr.issue-audit-rejected td {
  background: rgba(254, 242, 242, 0.9);
}

.issues-table tr.issue-audit-approved:hover td {
  background: rgba(220, 252, 231, 0.9);
}

.issues-table tr.issue-audit-rejected:hover td {
  background: rgba(254, 226, 226, 0.92);
}

.issue-id-cell {
  color: #475569;
  font-weight: 900;
}

.nowrap-col {
  white-space: nowrap;
}

.status-col {
  min-width: 92px;
}

.operation-col {
  width: 1%;
  min-width: 104px;
}

.audit-col {
  width: 1%;
  min-width: 108px;
}

.audit-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.audit-actions .btn {
  width: 100%;
  min-width: 76px;
  padding-inline: 10px;
}

.audit-status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-width: 76px;
  min-height: 34px;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid #dbe4ee;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
}

.audit-empty {
  color: #cbd5e1;
  font-size: 13px;
  font-weight: 900;
}

.audit-status-chip.approved {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
}

.audit-status-chip.rejected {
  border-color: #fecaca;
  background: #fef2f2;
  color: #b91c1c;
}

.table-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.table-actions .btn {
  width: 100%;
  min-width: 76px;
  flex: 0 0 auto;
  white-space: nowrap;
}

.locked-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  max-width: 148px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.35;
  text-align: center;
  white-space: normal;
}

.nowrap {
  white-space: nowrap;
}

.long-text {
  min-width: 240px;
  white-space: normal;
  line-height: 1.7;
  text-align: center;
}

.standard-detail-cell {
  min-width: 300px;
}

.standard-id-cell {
  min-width: 128px;
}

.standard-id-stack {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  white-space: normal;
}

.standard-id-stack.compact {
  gap: 5px;
}

.standard-id-stack span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 27px;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.standard-id-stack span.external {
  border-color: #ccfbf1;
  background: #ecfeff;
  color: #0f766e;
}

.standard-id-stack em {
  font-style: normal;
  opacity: 0.72;
}

.standard-id-stack strong {
  color: inherit;
  font-size: 12px;
}

.standard-detail-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.standard-detail-preview {
  width: 100%;
  text-align: center;
  white-space: pre-line;
}

.multiline-clamp {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.text-link-btn {
  border: none;
  background: transparent;
  padding: 0;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.multiline-cell {
  white-space: pre-line;
}

.thumb {
  width: 88px;
  height: 66px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
}

.thumb-placeholder {
  width: 88px;
  height: 66px;
  border-radius: 10px;
  font-size: 12px;
}

.image-btn {
  border: none;
  padding: 0;
  background: transparent;
  cursor: zoom-in;
}

.excellent-col {
  min-width: 72px;
}

.excellent-star {
  width: 34px;
  height: 34px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
  color: #cbd5e1;
  font-size: 21px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.18s ease;
}

.excellent-star:hover:not(:disabled),
.excellent-star.active {
  border-color: #f59e0b;
  background: radial-gradient(circle at 35% 25%, #fff7c2 0%, #fef3c7 42%, #fff7ed 100%);
  color: #d97706;
  box-shadow: 0 8px 18px rgba(245, 158, 11, 0.2);
  transform: translateY(-1px);
}

.excellent-star.locked {
  cursor: not-allowed;
  opacity: 0.5;
}

.excellent-star.mobile {
  width: 32px;
  height: 32px;
  border-radius: 11px;
  font-size: 20px;
  flex: 0 0 auto;
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

.pagination-btn,
.pagination-jump-btn {
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

.empty-row {
  text-align: center;
  color: #6b7280;
  padding: 0 !important;
  background:
    radial-gradient(circle at 50% 0%, rgba(37, 99, 235, 0.08), transparent 32%),
    #fff;
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

.status-tag.danger {
  background: #fef2f2;
  color: #dc2626;
}

.status-tag.audit {
  background: #f5f3ff;
  color: #7c3aed;
}

.status-tag.pending {
  background: #ecfeff;
  color: #0891b2;
}

.status-tag.warning {
  background: #fff7ed;
  color: #d97706;
}

.status-tag.success {
  background: #f0fdf4;
  color: #16a34a;
}

.status-tag.neutral {
  background: #f8fafc;
  color: #475569;
}

.image-modal {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}

.issue-photo-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.76);
}

.issue-photo-preview-dialog {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: min(980px, 96vw);
  max-height: 92vh;
  overflow: visible;
  cursor: zoom-in;
}

.issue-photo-preview-dialog img {
  display: block;
  max-width: 100%;
  max-height: 92vh;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 24px 54px rgba(15, 23, 42, 0.32);
  transform-origin: center center;
  transition: transform 0.12s ease-out;
  will-change: transform;
}

.image-modal-content {
  width: min(1000px, 100%);
  background: #fff;
  border-radius: 18px;
  overflow: hidden;
}

.image-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 700;
}

.close-btn {
  border: none;
  background: transparent;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
}

.image-modal-full {
  display: block;
  width: 100%;
  max-height: 78vh;
  object-fit: contain;
  background: #f8fafc;
}

.issue-export-modal {
  width: min(780px, 100%);
  max-height: min(88vh, 860px);
  overflow: auto;
}

.issue-export-body {
  padding: 20px;
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.12), transparent 34%),
    linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.export-notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border: 1px solid #ccfbf1;
  border-radius: 18px;
  background: #f0fdfa;
}

.export-notice strong,
.export-section-title {
  display: block;
  color: #0f172a;
  font-size: 14px;
  font-weight: 950;
}

.export-notice p {
  margin: 6px 0 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.8;
}

.export-notice>span {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 68px;
  height: 36px;
  border-radius: 999px;
  background: #0f766e;
  color: #fff;
  font-size: 13px;
  font-weight: 950;
}

.export-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.export-summary-card {
  min-width: 0;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: #fff;
}

.export-summary-card.primary {
  border-color: #bfdbfe;
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
}

.export-summary-card span,
.export-summary-card em,
.export-task-head span,
.export-task-head em {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.export-summary-card strong {
  display: block;
  margin: 6px 0 4px;
  color: #0f172a;
  font-size: 28px;
  font-weight: 950;
}

.export-filter-panel,
.export-field-panel,
.export-task-panel {
  margin-top: 14px;
  padding: 16px;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.92);
}

.export-field-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.export-field-panel p {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.8;
}

.export-field-panel p span {
  display: block;
  margin-top: 4px;
  color: #b45309;
  font-weight: 900;
}

.export-field-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.export-field-actions span {
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.export-field-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}

.export-field-group {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #f8fafc;
}

.export-field-group h4 {
  margin: 0 0 10px;
  color: #0f172a;
  font-size: 13px;
  font-weight: 950;
}

.export-field-options {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.export-field-option {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  grid-template-areas:
    "check title"
    "check help";
  align-items: start;
  column-gap: 9px;
  row-gap: 4px;
  min-height: 74px;
  padding: 12px;
  border: 1px solid #dbe4ee;
  border-radius: 16px;
  background: #fff;
  cursor: pointer;
}

.export-field-option.photo {
  border-color: #fde68a;
  background: #fffbeb;
}

.export-field-option input {
  grid-area: check;
  width: 16px;
  height: 16px;
  margin-top: 2px;
  accent-color: #2563eb;
}

.export-field-option span {
  grid-area: title;
  color: #0f172a;
  font-size: 13px;
  font-weight: 950;
}

.export-field-option em {
  grid-area: help;
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
  line-height: 1.6;
}

.export-field-option.disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.export-filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.export-filter-chips span {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
  word-break: break-word;
}

.export-empty-filter {
  margin-top: 10px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.8;
}

.export-task-panel.completed {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.export-task-panel.failed {
  border-color: #fecaca;
  background: #fef2f2;
}

.export-task-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.export-task-head strong {
  display: block;
  margin-top: 5px;
  color: #0f172a;
  font-size: 18px;
  font-weight: 950;
}

.export-progress {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.export-progress-bar {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb 0%, #14b8a6 100%);
  transition: width 0.35s ease;
}

.export-task-panel.running .export-progress-bar,
.export-task-panel.pending .export-progress-bar {
  background-size: 200% 100%;
  animation: exportProgressFlow 1.2s linear infinite;
}

.export-task-panel.failed .export-progress-bar {
  background: #ef4444;
}

.export-task-panel p {
  margin: 12px 0 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.8;
}

.export-error-text {
  color: #b91c1c !important;
  font-weight: 900;
}

.export-actions {
  margin: 0;
  padding: 16px 20px;
  border-top: 1px solid #e5e7eb;
  background: #fff;
}

@keyframes exportProgressFlow {
  0% {
    background-position: 0% 50%;
  }

  100% {
    background-position: 200% 50%;
  }
}

.issue-edit-modal {
  width: min(920px, 100%);
  max-height: min(88vh, 900px);
  overflow: auto;
}

.issue-edit-form {
  padding: 20px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.issue-edit-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.issue-edit-summary div {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid #dbe7ff;
  background: #eff6ff;
  min-width: 0;
}

.issue-edit-summary span,
.issue-edit-field span {
  display: block;
  margin-bottom: 7px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.issue-edit-summary strong {
  display: block;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.issue-edit-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.issue-edit-field {
  min-width: 0;
}

.issue-edit-field-wide {
  grid-column: 1 / -1;
}

.issue-edit-field textarea,
.issue-edit-field select,
.issue-edit-field input[type="file"] {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
  box-sizing: border-box;
}

.issue-edit-field textarea {
  resize: vertical;
  min-height: 92px;
  padding: 12px;
  line-height: 1.7;
}

.issue-edit-field select {
  height: 42px;
  padding: 0 12px;
}

.field-help {
  display: block;
  margin-top: 7px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.issue-edit-field input[type="file"] {
  padding: 10px 12px;
}

.issue-edit-field .search-select input {
  width: 100%;
  height: 44px;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  padding: 0 14px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
  box-sizing: border-box;
}

.edit-standard-panel {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid #dbe7ff;
  border-radius: 18px;
  background:
    radial-gradient(circle at 8% 0%, rgba(37, 99, 235, 0.1), transparent 34%),
    linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.edit-standard-mode {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.7;
}

.edit-standard-mode strong {
  color: #1d4ed8;
}

.edit-standard-mode span {
  display: inline;
  margin: 0;
  color: #475569;
}

.edit-standard-result {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.edit-standard-result>div {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
}

.edit-standard-result span {
  margin-bottom: 5px;
}

.edit-standard-result strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.upload-follow-anchor {
  scroll-margin-top: 72px;
}

.upload-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.upload-input {
  display: none;
}

.upload-dropzone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 10px;
  min-height: 168px;
  padding: 24px 20px;
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: linear-gradient(180deg, #f8fbff 0%, #f8fafc 100%);
  cursor: pointer;
  transition: all 0.18s ease;
  overflow: hidden;
}

.upload-dropzone:hover {
  border-color: #93c5fd;
  background: linear-gradient(180deg, #eff6ff 0%, #f8fafc 100%);
}

.upload-dropzone.drag-active {
  border-color: #2563eb;
  background:
    radial-gradient(circle at 50% 20%, rgba(37, 99, 235, 0.16), transparent 36%),
    linear-gradient(180deg, #eff6ff 0%, #f8fafc 100%);
  box-shadow: inset 0 0 0 2px rgba(37, 99, 235, 0.14), 0 18px 36px rgba(37, 99, 235, 0.12);
  transform: translateY(-1px);
}

.upload-icon {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 24px;
  font-weight: 800;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.upload-title {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}

.mobile-upload-title {
  display: none;
}

.upload-desc {
  max-width: 560px;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.upload-trigger-group {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}

.upload-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 96px;
  height: 38px;
  padding: 0 16px;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.upload-trigger-secondary {
  background: #eef4ff;
  color: #1d4ed8;
  border: 1px solid #bfd3ff;
}

.upload-trigger:hover {
  filter: brightness(0.98);
}

.upload-trigger-secondary:hover {
  background: #e0edff;
  border-color: #93c5fd;
}

.issue-edit-photo-grid {
  display: grid;
  gap: 12px;
}

.image-preview-panel {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid #bbf7d0;
  background: #f0fdf4;
}

.issue-current-photo-panel {
  border-color: #dbe4ee;
  background: #f8fafc;
}

.image-preview-thumb {
  width: 94px;
  height: 94px;
  border-radius: 14px;
  object-fit: cover;
  border: 1px solid #86efac;
  background: #fff;
}

.issue-current-photo-panel .image-preview-thumb {
  border-color: #cbd5e1;
}

.image-preview-meta {
  min-width: 0;
  flex: 1;
}

.image-preview-title {
  color: #166534;
  font-size: 14px;
  font-weight: 900;
  margin-bottom: 6px;
}

.issue-current-photo-panel .image-preview-title {
  color: #334155;
}

.image-preview-name {
  color: #15803d;
  font-size: 12px;
  line-height: 1.5;
  word-break: break-all;
}

.issue-current-photo-panel .image-preview-name {
  color: #64748b;
}

.image-preview-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.image-action-btn {
  min-height: 34px;
  height: 34px;
  padding: 0 12px;
  font-size: 12px;
}

.issue-edit-hint {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.7;
}

.rectification-photo-panel {
  display: grid;
  gap: 16px;
}

.rectification-photo-current {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.rectification-photo-current span {
  color: #475569;
  font-size: 13px;
  font-weight: 900;
}

.rectification-photo-preview {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid #bbf7d0;
  background: #f0fdf4;
}

.rectification-photo-preview img {
  width: 86px;
  height: 86px;
  border-radius: 14px;
  object-fit: cover;
  border: 1px solid #86efac;
  background: #fff;
}

.rectification-photo-preview strong,
.rectification-photo-preview span {
  display: block;
}

.rectification-photo-preview strong {
  color: #166534;
  font-size: 14px;
  margin-bottom: 6px;
}

.rectification-photo-preview span {
  color: #15803d;
  font-size: 12px;
  line-height: 1.5;
  word-break: break-all;
}

.form-error {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #dc2626;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.7;
}

.issue-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 18px;
  flex-wrap: wrap;
}

.standard-detail-modal {
  width: min(880px, 100%);
}

.standard-detail-modal-body {
  padding: 20px;
  max-height: 70vh;
  overflow: auto;
  line-height: 1.9;
  color: #334155;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.standard-detail-section {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid #bfdbfe;
  background: linear-gradient(180deg, #eff6ff, #ffffff);
}

.standard-detail-section.external {
  border-color: #99f6e4;
  background: linear-gradient(180deg, #ecfeff, #ffffff);
}

.standard-detail-section.muted {
  border-color: #e2e8f0;
  background: #ffffff;
}

.standard-detail-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.standard-detail-section-head span {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.standard-detail-section-head strong {
  color: #0f172a;
  font-size: 16px;
  font-weight: 950;
}

.standard-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(240px, 1fr));
  gap: 14px;
}

.standard-detail-card {
  padding: 16px 18px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid #e7edf4;
}

.standard-detail-card.internal {
  border-color: #dbeafe;
}

.standard-detail-card.external {
  border-color: #ccfbf1;
}

.standard-detail-card-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 8px;
}

.standard-detail-card-value {
  font-size: 14px;
  line-height: 1.9;
  color: #334155;
}

@media (max-width: 1200px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }
}

@media (max-width: 768px) {
  .page-shell {
    gap: 14px;
  }

  .page-header {
    order: 0;
  }

  .filter-card {
    order: 1;
  }

  .mobile-issue-list {
    order: 2;
  }

  .table-card {
    order: 3;
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
    padding: 14px;
    border-radius: 20px;
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
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .filter-item label {
    font-size: 13px;
  }

  .filter-item input,
  .filter-item select {
    height: 46px;
    font-size: 15px;
    padding: 0 12px;
  }

  .filter-item-wide {
    grid-column: span 1;
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

  .mobile-pagination-bar {
    margin-top: 12px;
    border-radius: 20px;
  }

  .mobile-pagination-bar .pagination-summary {
    text-align: center;
    font-weight: 900;
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

  .mobile-issue-list {
    display: block;
  }

  .mobile-pagination-bar {
    display: flex;
    padding: 14px;
  }

  .mobile-card-images {
    grid-template-columns: 1fr 1fr;
  }

  .mobile-issue-cards {
    gap: 14px;
  }

  .mobile-issue-card {
    padding: 15px;
    border-radius: 22px;
    background:
      radial-gradient(circle at 100% 0%, rgba(37, 99, 235, 0.1), transparent 28%),
      rgba(255, 255, 255, 0.98);
  }

  .mobile-issue-card.issue-audit-approved {
    background:
      radial-gradient(circle at 100% 0%, rgba(34, 197, 94, 0.12), transparent 30%),
      rgba(240, 253, 244, 0.96);
  }

  .mobile-issue-card.issue-audit-rejected {
    background:
      radial-gradient(circle at 100% 0%, rgba(239, 68, 68, 0.11), transparent 30%),
      rgba(254, 242, 242, 0.96);
  }

  .mobile-card-body {
    padding: 12px;
    border: 1px solid #edf2f7;
    border-radius: 16px;
    background: #f8fafc;
  }

  .mobile-card-row strong {
    max-width: 68%;
    word-break: break-word;
  }

  .mobile-card-row-top {
    flex-direction: column;
    gap: 7px;
  }

  .mobile-card-row-top>span {
    font-weight: 900;
  }

  .mobile-card-text,
  .mobile-card-standard-box {
    width: 100%;
    text-align: left;
    align-items: stretch;
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

  .image-modal {
    padding: 12px;
  }

  .issue-export-modal {
    max-height: 92vh;
  }

  .issue-export-body {
    padding: 14px;
  }

  .export-notice,
  .export-task-head {
    align-items: stretch;
    flex-direction: column;
  }

  .export-notice>span {
    width: fit-content;
  }

  .export-summary-grid {
    grid-template-columns: 1fr;
  }

  .export-field-panel-head {
    align-items: stretch;
    flex-direction: column;
  }

  .export-field-actions {
    justify-content: flex-start;
  }

  .export-field-options {
    grid-template-columns: 1fr;
  }

  .export-filter-chips span {
    width: 100%;
    justify-content: flex-start;
    border-radius: 12px;
    padding: 8px 10px;
  }

  .export-actions {
    flex-direction: column;
    padding: 14px;
  }

  .issue-edit-summary,
  .issue-edit-grid {
    grid-template-columns: 1fr;
  }

  .edit-standard-result {
    grid-template-columns: 1fr;
  }

  .upload-dropzone {
    min-height: 144px;
    padding: 20px 16px;
  }

  .desktop-upload-title {
    display: none;
  }

  .mobile-upload-title {
    display: inline;
  }

  .upload-desc {
    font-size: 12px;
  }

  .upload-trigger-group,
  .image-preview-actions {
    width: 100%;
  }

  .upload-trigger,
  .image-action-btn {
    flex: 1;
    min-width: 0;
  }

  .image-preview-panel {
    align-items: stretch;
    flex-direction: column;
  }

  .image-preview-thumb {
    width: 100%;
    height: auto;
    aspect-ratio: 4 / 3;
  }

  .issue-edit-actions {
    flex-direction: column;
  }

  .rectification-photo-current,
  .rectification-photo-preview {
    align-items: stretch;
    flex-direction: column;
  }

  .standard-detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
