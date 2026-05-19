<template>
  <div class="page-shell issues-page">
    <transition name="toast-fade">
      <div v-if="actionMessage" class="message-toast" :class="actionMessageType">{{ actionMessage }}</div>
    </transition>

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
        <div v-for="item in paginatedData" :key="item.id" class="mobile-issue-card card-surface">
          <div class="mobile-card-head">
            <div class="mobile-card-title-row">
              <span class="mobile-card-category">{{ item.inspection_table_name || '暂无' }}</span>
              <span :class="statusClass(item.status)">{{ item.status }}</span>
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

            <div class="mobile-card-row mobile-card-row-top">
              <span>规范详情</span>
              <div class="mobile-card-standard-box">
                <div class="mobile-card-standard-preview multiline-clamp">{{ getStandardDetailPreview(getCombinedStandardDetailText(item))
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
            <button class="mobile-image-btn" type="button" @click="preview(resolveImage(item.issue_photo), '问题照片')">
              <img :src="resolveImage(item.issue_photo)" class="mobile-thumb" alt="问题照片" />
              <span>问题照片</span>
            </button>

            <button v-if="item.rectification_photo" class="mobile-image-btn" type="button"
              @click="preview(resolveImage(item.rectification_photo), '站点反馈整改照片')">
              <img :src="resolveImage(item.rectification_photo)" class="mobile-thumb" alt="站点反馈整改照片" />
              <span>整改照片</span>
            </button>
            <button v-if="item.review_photo" class="mobile-image-btn" type="button"
              @click="preview(resolveImage(item.review_photo), '督导组复核照片')">
              <img :src="resolveImage(item.review_photo)" class="mobile-thumb" alt="督导组复核照片" />
              <span>复核照片</span>
            </button>
          </div>

          <div v-if="canManageIssues" class="mobile-card-actions">
            <button v-if="canEditIssueRow(item)" class="btn btn-secondary" type="button" @click="openEditDialog(item)">
              编辑问题
            </button>
            <button v-if="canUpdateRectificationPhotoRow(item)" class="btn btn-secondary" type="button"
              @click="openRectificationPhotoDialog(item)">
              更新整改照片
            </button>
            <button v-if="canDeleteIssueRow(item)" class="btn btn-danger" type="button"
              :disabled="deletingIssueId === item.id" @click="deleteIssue(item)">
              {{ deletingIssueId === item.id ? '删除中...' : '删除问题' }}
            </button>
            <span v-if="isClosedIssue(item) && currentRole !== 'root'" class="locked-action">已闭环锁定</span>
          </div>
        </div>
      </div>

      <div v-if="!loading && filteredData.length" class="pagination-bar mobile-pagination-bar card-surface">
        <div class="pagination-summary">共 {{ filteredData.length }} 条</div>
        <div class="pagination-controls">
          <label>每页显示</label>
          <select v-model.number="pageSize">
            <option v-for="size in pageSizeOptions" :key="`mobile-${size}`" :value="size">{{ size }}</option>
          </select>
          <button class="btn btn-secondary" :disabled="page <= 1" @click="prevPage">上一页</button>
          <div class="page-jump-strip" aria-label="页码跳转">
            <button v-for="pageNumber in visiblePageNumbers" :key="`mobile-page-${pageNumber}`" type="button"
              class="page-number-btn" :class="{ active: pageNumber === page }" @click="goToPage(pageNumber)">
              {{ pageNumber }}
            </button>
          </div>
          <span class="page-total-label">{{ page }} / {{ totalPage }}</span>
          <button class="btn btn-secondary" :disabled="page >= totalPage" @click="nextPage">下一页</button>
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
          <label>检查月度</label>
          <input v-model="filters.month" type="month" />
        </div>
        <div class="filter-item">
          <label>检查时间（按天）</label>
          <input v-model="filters.date" type="date" />
        </div>

        <div class="filter-item">
          <label>站点所属地</label>
          <div class="search-select" ref="regionSelectRef">
            <input v-model="filters.region" placeholder="搜索或选择站点所属地" @focus="openFilterDropdown('region')"
              @input="openFilterDropdown('region')" />
            <div v-if="dropdownVisible.region" class="search-select-dropdown">
              <div v-for="option in filteredRegionOptions" :key="option" class="search-select-option"
                @click="selectFilterOption('region', option)">
                <div class="option-main">{{ option }}</div>
              </div>
              <div v-if="filteredRegionOptions.length === 0" class="search-select-empty">无匹配站点所属地</div>
            </div>
          </div>
        </div>

        <div class="filter-item">
          <label>站点名称</label>
          <div class="search-select" ref="stationSelectRef">
            <input v-model="filters.station" placeholder="搜索或选择站点名称" @focus="openFilterDropdown('station')"
              @input="openFilterDropdown('station')" />
            <div v-if="dropdownVisible.station" class="search-select-dropdown">
              <div v-for="option in filteredStationOptions" :key="option" class="search-select-option"
                @click="selectFilterOption('station', option)">
                <div class="option-main">{{ option }}</div>
              </div>
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
          <div class="search-select" ref="inspectorSelectRef">
            <input v-model="filters.inspector" placeholder="搜索或选择检查人员" @focus="openFilterDropdown('inspector')"
              @input="openFilterDropdown('inspector')" />
            <div v-if="dropdownVisible.inspector" class="search-select-dropdown">
              <div v-for="option in filteredInspectorOptions" :key="option" class="search-select-option"
                @click="selectFilterOption('inspector', option)">
                <div class="option-main">{{ option }}</div>
              </div>
              <div v-if="filteredInspectorOptions.length === 0" class="search-select-empty">无匹配检查人员</div>
            </div>
          </div>
        </div>

        <div class="filter-item">
          <label>检查表</label>
          <div class="search-select" ref="inspectionTableSelectRef">
            <input v-model="filters.inspectionTableName" placeholder="搜索或选择检查表"
              @focus="openFilterDropdown('inspectionTableName')" @input="openFilterDropdown('inspectionTableName')" />
            <div v-if="dropdownVisible.inspectionTableName" class="search-select-dropdown">
              <div v-for="option in filteredInspectionTableOptions" :key="option" class="search-select-option"
                @click="selectFilterOption('inspectionTableName', option)">
                <div class="option-main">{{ option }}</div>
              </div>
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
            <option value="待整改">待整改</option>
            <option value="待复核">待复核</option>
            <option value="已闭环">已闭环</option>
            <option value="站经无法整改">站经无法整改</option>
          </select>
        </div>
      </div>

      <div class="filter-actions">
        <button v-if="isMobileView" class="btn btn-primary mobile-today-filter-btn" type="button"
          @click="filterMyTodayIssues">
          只看我今天检查的问题
        </button>
        <button class="btn btn-secondary" @click="resetFilters">重置筛选</button>
        <button class="btn btn-secondary" @click="fetchIssues" :disabled="loading">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
      </div>
    </div>

    <div class="table-card card-surface">
      <div class="table-scroll-wrap">
        <div class="table-scroll">
          <table class="issues-table">
            <thead>
              <tr>
                <th class="nowrap">检查月度</th>
                <th class="nowrap">检查时间</th>
                <th class="nowrap">站点所属地</th>
                <th class="nowrap">站点名称</th>
                <th class="nowrap">站点负责人</th>
                <th class="nowrap">站点负责人手机号</th>
                <th class="nowrap">检查人员</th>
                <th class="nowrap">检查人员手机号</th>
                <th class="nowrap">检查表</th>
                <th class="nowrap">规范ID（内/外）</th>
                <th>规范详情</th>
                <th>问题描述</th>
                <th class="nowrap">问题照片</th>
                <th class="nowrap">站经理整改结果</th>
                <th class="nowrap">站点反馈整改说明</th>
                <th class="nowrap">站点反馈整改照片</th>
                <th class="nowrap">督导组复核结果</th>
                <th class="nowrap">督导组复核说明</th>
                <th class="nowrap">督导组复核照片</th>
                <th class="nowrap-col status-col">问题状态</th>
                <th v-if="canManageIssues" class="nowrap operation-col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in paginatedData" :key="item.id">
                <td class="nowrap">{{ item.month }}</td>
                <td class="nowrap">{{ item.time }}</td>
                <td class="nowrap">{{ item.region }}</td>
                <td class="nowrap">{{ item.station }}</td>
                <td class="nowrap">{{ item.station_manager }}</td>
                <td class="nowrap">{{ item.station_manager_phone }}</td>
                <td class="nowrap">{{ item.inspector }}</td>
                <td class="nowrap">{{ item.inspector_phone }}</td>
                <td class="nowrap">{{ item.inspection_table_name || '暂无' }}</td>
                <td class="nowrap standard-id-cell">
                  <div class="standard-id-stack">
                    <span v-for="part in getStandardIdParts(item)" :key="`${item.id}-table-${part.type}`" :class="part.type">
                      <em>{{ part.label }}</em><strong>{{ part.value }}</strong>
                    </span>
                  </div>
                </td>
                <td class="standard-detail-cell">
                  <div class="standard-detail-box">
                    <div class="standard-detail-preview multiline-clamp">{{ getStandardDetailPreview(getCombinedStandardDetailText(item))
                    }}</div>
                    <button class="text-link-btn" type="button" @click="openStandardDetail(item)">查看详情</button>
                  </div>
                </td>
                <td class="long-text">{{ item.description }}</td>
                <td class="nowrap">
                  <button class="image-btn" type="button" @click="preview(resolveImage(item.issue_photo), '问题照片')">
                    <img :src="resolveImage(item.issue_photo)" class="thumb" alt="问题照片" />
                  </button>
                </td>
                <td class="nowrap">{{ item.rectification_result || '暂无' }}</td>
                <td class="nowrap">{{ item.rectification_note || '暂无' }}</td>
                <td class="nowrap">
                  <button v-if="item.rectification_photo" class="image-btn" type="button"
                    @click="preview(resolveImage(item.rectification_photo), '站点反馈整改照片')">
                    <img :src="resolveImage(item.rectification_photo)" class="thumb" alt="站点反馈整改照片" />
                  </button>
                  <span v-else>暂无</span>
                </td>
                <td class="nowrap">{{ item.review_result || '暂无' }}</td>
                <td class="nowrap">{{ item.review_note || '暂无' }}</td>
                <td class="nowrap">
                  <button v-if="item.review_photo" class="image-btn" type="button"
                    @click="preview(resolveImage(item.review_photo), '督导组复核照片')">
                    <img :src="resolveImage(item.review_photo)" class="thumb" alt="督导组复核照片" />
                  </button>
                  <span v-else>暂无</span>
                </td>
                <td class="nowrap-col status-col">
                  <span :class="statusClass(item.status)">{{ item.status }}</span>
                </td>
                <td v-if="canManageIssues" class="nowrap operation-col">
                  <div class="table-actions">
                    <button v-if="canEditIssueRow(item)" class="btn btn-secondary btn-sm" type="button"
                      @click="openEditDialog(item)">
                      编辑
                    </button>
                    <button v-if="canUpdateRectificationPhotoRow(item)" class="btn btn-secondary btn-sm" type="button"
                      @click="openRectificationPhotoDialog(item)">
                      更新整改照片
                    </button>
                    <button v-if="canDeleteIssueRow(item)" class="btn btn-danger btn-sm" type="button"
                      :disabled="deletingIssueId === item.id" @click="deleteIssue(item)">
                      {{ deletingIssueId === item.id ? '删除中' : '删除' }}
                    </button>
                    <span v-if="isClosedIssue(item) && currentRole !== 'root'" class="locked-action">已闭环锁定</span>
                  </div>
                </td>
              </tr>
              <tr v-if="!loading && paginatedData.length === 0">
                <td :colspan="issueTableColspan" class="empty-row">
                  <div class="empty-state-inline">
                    <div class="empty-state-orb"></div>
                    <div class="empty-state-kicker">暂无记录</div>
                    <h3>当前没有符合条件的问题记录</h3>
                    <p>可以调整筛选条件，或刷新后查看最新巡检问题。</p>
                    <button class="btn btn-secondary btn-sm empty-state-action" type="button" @click="resetFilters">重置筛选</button>
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
          <label>每页显示</label>
          <select v-model.number="pageSize">
            <option v-for="size in pageSizeOptions" :key="`desktop-${size}`" :value="size">{{ size }}</option>
          </select>
          <button class="btn btn-secondary" :disabled="page <= 1" @click="prevPage">上一页</button>
          <div class="page-jump-strip" aria-label="页码跳转">
            <button v-for="pageNumber in visiblePageNumbers" :key="`desktop-page-${pageNumber}`" type="button"
              class="page-number-btn" :class="{ active: pageNumber === page }" @click="goToPage(pageNumber)">
              {{ pageNumber }}
            </button>
          </div>
          <span class="page-total-label">{{ page }} / {{ totalPage }}</span>
          <button class="btn btn-secondary" :disabled="page >= totalPage" @click="nextPage">下一页</button>
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
                <span v-for="part in getStandardIdParts(editDialog.issue)" :key="`edit-${part.type}`" :class="part.type">
                  <em>{{ part.label }}</em><strong>{{ part.value }}</strong>
                </span>
              </div>
            </div>
          </div>

          <div class="issue-edit-grid">
            <label class="issue-edit-field issue-edit-field-wide">
              <span>问题描述</span>
              <textarea v-model="editDialog.form.description" rows="4" placeholder="请填写实际问题描述"></textarea>
            </label>
            <div class="issue-edit-field issue-edit-field-wide">
              <span>问题照片</span>
              <div class="rectification-photo-panel">
                <div v-if="editDialog.issue?.issue_photo" class="rectification-photo-current">
                  <span>当前问题照片</span>
                  <button class="image-btn" type="button"
                    @click="preview(resolveImage(editDialog.issue.issue_photo), '当前问题照片')">
                    <img :src="resolveImage(editDialog.issue.issue_photo)" class="thumb" alt="当前问题照片" />
                  </button>
                </div>

                <label class="issue-edit-field issue-edit-field-wide">
                  <span>上传新的问题照片</span>
                  <input type="file" accept="image/*" @change="handleIssuePhotoChange" />
                </label>

                <div v-if="editDialog.issuePhotoPreview" class="rectification-photo-preview issue-photo-preview">
                  <img :src="editDialog.issuePhotoPreview" alt="新的问题照片预览" />
                  <div>
                    <strong>已选择新问题照片</strong>
                    <span>{{ editDialog.issuePhotoFile?.name || '待上传图片' }}</span>
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
          <div v-if="!editDialog.issue?.can_edit_issue_workflow" class="issue-edit-hint">
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

    <div v-if="previewState.visible" class="image-modal" @click.self="closePreview">
      <div class="image-modal-content">
        <div class="image-modal-header">
          <span>{{ previewState.title }}</span>
          <button class="close-btn" type="button" @click="closePreview">×</button>
        </div>
        <img :src="previewState.url" class="image-modal-full" :alt="previewState.title" />
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
              <div v-for="entry in standardInternalEntries" :key="`internal-${entry.key}`" class="standard-detail-card internal">
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
              <div v-for="entry in standardExternalEntries" :key="`external-${entry.key}`" class="standard-detail-card external">
                <div class="standard-detail-card-label">{{ entry.label }}</div>
                <div class="standard-detail-card-value multiline-cell">{{ entry.value }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import {
  clearFileInput,
  prepareImagePreview,
  revokeObjectUrl
} from '@/utils/imageUpload'
import {
  getStandardDetailPreview,
  parseStandardDetailText
} from '@/utils/standardDetail'

const filters = ref({
  month: '',
  date: '',
  region: '',
  station: '',
  stationManager: '',
  inspector: '',
  inspectionTableName: '',
  standardId: '',
  standardDetail: '',
  rectificationResult: '',
  reviewResult: '',
  status: ''
})

const list = ref([])
const loading = ref(false)
const regionSelectRef = ref(null)
const stationSelectRef = ref(null)
const stationManagerSelectRef = ref(null)
const inspectorSelectRef = ref(null)
const inspectionTableSelectRef = ref(null)

const dropdownVisible = ref({
  region: false,
  station: false,
  stationManager: false,
  inspector: false,
  inspectionTableName: false
})

const isMobileView = ref(false)
const showMobileFilters = ref(false)
const page = ref(1)
const pageSize = ref(20)
const deletingIssueId = ref(null)
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

const editDialog = ref({
  visible: false,
  saving: false,
  error: '',
  issue: null,
  issuePhotoFile: null,
  issuePhotoPreview: '',
  form: {
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

const normalizedKeyword = (value) => String(value || '').toLowerCase()
const uniqueSortedOptions = (values) => {
  return [...new Set(values.map((item) => String(item || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
}

const filterOptionByKeyword = (options, keyword) => {
  const normalized = normalizedKeyword(keyword)
  return options.filter((item) => !normalized || normalizedKeyword(item).includes(normalized))
}

const filteredData = computed(() => {
  return list.value.filter((item) => {
    const matchedMonth = !filters.value.month || item.month === filters.value.month
    const matchedDate = !filters.value.date || String(item.time || '').startsWith(filters.value.date)
    const matchedRegion = !filters.value.region || normalizedKeyword(item.region).includes(normalizedKeyword(filters.value.region))
    const matchedStation = !filters.value.station || normalizedKeyword(item.station).includes(normalizedKeyword(filters.value.station))
    const matchedStationManager = !filters.value.stationManager || normalizedKeyword(item.station_manager).includes(normalizedKeyword(filters.value.stationManager))
    const matchedInspector = !filters.value.inspector || normalizedKeyword(item.inspector).includes(normalizedKeyword(filters.value.inspector))
    const matchedInspectionTableName = !filters.value.inspectionTableName || normalizedKeyword(item.inspection_table_name).includes(normalizedKeyword(filters.value.inspectionTableName))
    const matchedStandardId = !filters.value.standardId || normalizedKeyword(getStandardIdSearchText(item)).includes(normalizedKeyword(filters.value.standardId))
    const matchedStandardDetail = !filters.value.standardDetail || normalizedKeyword(getCombinedStandardDetailText(item)).includes(normalizedKeyword(filters.value.standardDetail))
    const matchedRectificationResult = !filters.value.rectificationResult || item.rectification_result === filters.value.rectificationResult
    const matchedReviewResult = !filters.value.reviewResult || item.review_result === filters.value.reviewResult
    const matchedStatus = !filters.value.status || item.status === filters.value.status

    return (
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
      matchedStatus
    )
  })
})

const regionOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.region)))
const stationOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.station)))
const stationManagerOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.station_manager)))
const inspectorOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.inspector)))
const inspectionTableOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.inspection_table_name)))

const filteredRegionOptions = computed(() => filterOptionByKeyword(regionOptions.value, filters.value.region))
const filteredStationOptions = computed(() => filterOptionByKeyword(stationOptions.value, filters.value.station))
const filteredStationManagerOptions = computed(() => filterOptionByKeyword(stationManagerOptions.value, filters.value.stationManager))
const filteredInspectorOptions = computed(() => filterOptionByKeyword(inspectorOptions.value, filters.value.inspector))
const filteredInspectionTableOptions = computed(() => filterOptionByKeyword(inspectionTableOptions.value, filters.value.inspectionTableName))

const activeFilterCount = computed(() => {
  return Object.values(filters.value).filter((value) => String(value || '').trim()).length
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

const visiblePageNumbers = computed(() => {
  const maxVisible = isMobileView.value ? 5 : 7
  const total = totalPage.value
  if (total <= maxVisible) {
    return Array.from({ length: total }, (_item, index) => index + 1)
  }
  const half = Math.floor(maxVisible / 2)
  let start = Math.max(1, page.value - half)
  let end = Math.min(total, start + maxVisible - 1)
  start = Math.max(1, end - maxVisible + 1)
  return Array.from({ length: end - start + 1 }, (_item, index) => start + index)
})

const canEditIssues = computed(() => currentRole === 'root' || Boolean(localPermissions.value.edit_inspection_issues))
const canDeleteIssues = computed(() => currentRole === 'root' || Boolean(localPermissions.value.delete_inspection_issues))
const canManageIssues = computed(() => (
  canEditIssues.value ||
  canDeleteIssues.value ||
  list.value.some((item) => (
    item?.can_edit_issue ||
    item?.can_delete_issue ||
    item?.can_update_rectification_photo
  ))
))
const issueTableColspan = computed(() => canManageIssues.value ? 21 : 20)

const isClosedIssue = (item) => item?.status === '已闭环'
const canEditIssueRow = (item) => Boolean(item?.can_edit_issue)
const canDeleteIssueRow = (item) => Boolean(item?.can_delete_issue)
const canUpdateRectificationPhotoRow = (item) => Boolean(item?.can_update_rectification_photo)

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

watch([filters, pageSize], () => {
  page.value = 1
}, { deep: true })

watch(totalPage, (value) => {
  if (page.value > value) {
    page.value = value
  }
})

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

const resetFilters = () => {
  filters.value = {
    month: '',
    date: '',
    region: '',
    station: '',
    stationManager: '',
    inspector: '',
    inspectionTableName: '',
    standardId: '',
    standardDetail: '',
    rectificationResult: '',
    reviewResult: '',
    status: ''
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
    month: '',
    date: formatLocalDate(),
    region: '',
    station: '',
    stationManager: '',
    inspector,
    inspectionTableName: '',
    standardId: '',
    standardDetail: '',
    rectificationResult: '',
    reviewResult: '',
    status: ''
  }
  closeAllDropdowns()
  showMobileFilters.value = false
  showActionMessage('已筛选我今天检查的问题。', 'success')
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

const createIssueEditForm = (item = {}) => ({
  description: item.description || '',
  status: item.status || '待整改',
  rectification_result: item.rectification_result || '',
  rectification_note: item.rectification_note || '',
  review_result: item.review_result || '',
  review_note: item.review_note || ''
})

const revokeIssuePhotoPreview = () => {
  revokeObjectUrl(editDialog.value.issuePhotoPreview)
}

const openEditDialog = (item) => {
  revokeIssuePhotoPreview()
  editDialog.value = {
    visible: true,
    saving: false,
    error: '',
    issue: item,
    issuePhotoFile: null,
    issuePhotoPreview: '',
    form: createIssueEditForm(item)
  }
}

const closeEditDialog = () => {
  if (editDialog.value.saving) return
  revokeIssuePhotoPreview()
  editDialog.value = {
    visible: false,
    saving: false,
    error: '',
    issue: null,
    issuePhotoFile: null,
    issuePhotoPreview: '',
    form: createIssueEditForm()
  }
}

const handleIssuePhotoChange = async (event) => {
  const file = event.target.files?.[0]
  revokeIssuePhotoPreview()
  if (!file) {
    editDialog.value.issuePhotoFile = null
    editDialog.value.issuePhotoPreview = ''
    return
  }

  try {
    const prepared = await prepareImagePreview(file)
    editDialog.value.issuePhotoFile = prepared.file
    editDialog.value.issuePhotoPreview = prepared.previewUrl
    editDialog.value.error = ''
  } catch (error) {
    clearFileInput(event)
    editDialog.value.issuePhotoFile = null
    editDialog.value.issuePhotoPreview = ''
    editDialog.value.error = error?.message || '图片处理失败，请更换图片后重试。'
  }
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

  try {
    rectificationPhotoDialog.value.saving = true
    rectificationPhotoDialog.value.error = ''
    const formData = new FormData()
    formData.append('user_id', localStorage.getItem('user_id') || '')
    formData.append('rectification_photo', rectificationPhotoDialog.value.file)
    await axios.post(`/api/issues/${issueId}/rectification-photo`, formData)
    closeRectificationPhotoDialog()
    showActionMessage('整改照片已更新。', 'success')
    await fetchIssues()
  } catch (error) {
    rectificationPhotoDialog.value.error = error?.response?.data?.error || '整改照片更新失败。'
  } finally {
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

  if (!editDialog.value.form.description.trim()) {
    editDialog.value.error = '请填写问题描述。'
    return
  }

  try {
    editDialog.value.saving = true
    editDialog.value.error = ''
    const userId = localStorage.getItem('user_id') || ''
    const formData = new FormData()
    formData.append('user_id', userId)
    Object.entries(editDialog.value.form).forEach(([key, value]) => {
      formData.append(key, value ?? '')
    })
    if (editDialog.value.issuePhotoFile) {
      formData.append('issue_photo', editDialog.value.issuePhotoFile)
    }
    await axios.put(`/api/issues/${issueId}`, formData)
    editDialog.value.saving = false
    closeEditDialog()
    showActionMessage('巡检问题已保存。', 'success')
    await fetchIssues()
  } catch (error) {
    editDialog.value.error = error?.response?.data?.error || '保存巡检问题失败。'
  } finally {
    if (editDialog.value.visible) {
      editDialog.value.saving = false
    }
  }
}

const deleteIssue = async (item) => {
  if (!item?.id) return

  const confirmed = window.confirm(`确认删除问题 #${item.id} 吗？删除后巡检记录的问题数量会自动重新计算。`)
  if (!confirmed) return

  try {
    deletingIssueId.value = item.id
    const userId = localStorage.getItem('user_id') || ''
    await axios.delete(`/api/issues/${item.id}`, {
      data: { user_id: userId }
    })
    showActionMessage('巡检问题已删除。', 'success')
    await fetchIssues()
  } catch (error) {
    showActionMessage(error?.response?.data?.error || '删除巡检问题失败。', 'error')
  } finally {
    deletingIssueId.value = null
  }
}


const nextPage = () => {
  if (page.value < totalPage.value) {
    page.value += 1
  }
}

const goToPage = (targetPage) => {
  const safePage = Math.min(Math.max(Number(targetPage) || 1, 1), totalPage.value)
  page.value = safePage
}

const prevPage = () => {
  if (page.value > 1) {
    page.value -= 1
  }
}

const previewState = ref({
  visible: false,
  url: '',
  title: ''
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
    title
  }
}

const closePreview = () => {
  previewState.value = {
    visible: false,
    url: '',
    title: ''
  }
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
}

const statusClass = (status) => {
  if (status === '待整改') return 'status-tag danger'
  if (status === '待复核') return 'status-tag warning'
  if (status === '已闭环') return 'status-tag success'
  if (status === '站经无法整改') return 'status-tag neutral'
  return 'status-tag'
}

const updateResponsiveState = () => {
  const nextIsMobile = window.matchMedia?.('(max-width: 768px)').matches ?? false
  if (nextIsMobile === isMobileView.value) return
  isMobileView.value = nextIsMobile
  pageSize.value = nextIsMobile ? 5 : 20
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  updateResponsiveState()
  window.addEventListener('resize', updateResponsiveState)
  fetchIssues()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('resize', updateResponsiveState)
  revokeIssuePhotoPreview()
  revokeRectificationPhotoPreview()
  if (actionMessageTimer) {
    clearTimeout(actionMessageTimer)
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

.mobile-today-filter-btn {
  display: none;
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

.filter-actions {
  margin-top: 16px;
  display: flex;
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
  font-weight: 800;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.2);
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
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

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
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

.mobile-card-code > span {
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
  min-width: 2940px;
  border-collapse: collapse;
}

.issues-table th,
.issues-table td {
  border: 1px solid #e5e7eb;
  padding: 12px 14px;
  text-align: left;
  vertical-align: top;
  font-size: 14px;
  color: #111827;
}

.issues-table th {
  background: #f8fafc;
  font-weight: 700;
  white-space: nowrap;
}

.nowrap-col {
  white-space: nowrap;
}

.status-col {
  min-width: 110px;
}

.operation-col {
  min-width: 280px;
}

.table-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
}

.table-actions .btn {
  width: auto;
  flex: 0 0 auto;
  white-space: nowrap;
}

.locked-action {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.nowrap {
  white-space: nowrap;
}

.long-text {
  min-width: 260px;
  white-space: normal;
  line-height: 1.7;
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
  align-items: flex-start;
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
  align-items: flex-start;
  gap: 6px;
}

.standard-detail-preview {
  width: 100%;
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

.image-btn {
  border: none;
  padding: 0;
  background: transparent;
  cursor: zoom-in;
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

.pagination-controls select {
  height: 40px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0 10px;
}

.page-jump-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: min(420px, 46vw);
  overflow-x: auto;
  padding: 2px;
}

.page-number-btn {
  min-width: 36px;
  height: 36px;
  border: 1px solid #dbe4ee;
  border-radius: 10px;
  background: #fff;
  color: #475569;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
  flex: 0 0 auto;
}

.page-number-btn.active {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.18);
}

.page-total-label {
  color: #475569;
  font-size: 13px;
  font-weight: 900;
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

.issue-edit-modal {
  width: min(820px, 100%);
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

.issue-edit-field input[type="file"] {
  padding: 10px 12px;
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

  .mobile-today-filter-btn {
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

  .mobile-pagination-bar .pagination-controls {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .mobile-pagination-bar .pagination-controls label {
    grid-column: 1;
    grid-row: 1;
    align-self: center;
    color: #64748b;
    font-size: 13px;
    font-weight: 900;
  }

  .mobile-pagination-bar .pagination-controls select {
    grid-column: 2;
    grid-row: 1;
    width: 100%;
    height: 42px;
  }

  .mobile-pagination-bar .pagination-controls > .btn:first-of-type {
    grid-column: 1;
    grid-row: 2;
  }

  .mobile-pagination-bar .pagination-controls > .btn:last-of-type {
    grid-column: 2;
    grid-row: 2;
  }

  .mobile-pagination-bar .page-jump-strip,
  .mobile-pagination-bar .page-total-label {
    grid-column: 1 / -1;
  }

  .mobile-pagination-bar .page-jump-strip {
    grid-row: 3;
    max-width: 100%;
    justify-content: flex-start;
    padding-bottom: 4px;
    padding-top: 2px;
  }

  .mobile-pagination-bar .page-total-label {
    grid-row: 4;
    padding-top: 2px;
    text-align: center;
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

  .mobile-card-row-top > span {
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

  .image-modal {
    padding: 12px;
  }

  .issue-edit-summary,
  .issue-edit-grid {
    grid-template-columns: 1fr;
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
