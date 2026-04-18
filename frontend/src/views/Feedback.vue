<template>
    <div class="page-shell">
        <div class="page-header card-surface">
            <div>
                <div class="page-kicker">系统反馈</div>
                <h2>平台建议与问题反馈中心</h2>
                <p class="page-desc">
                    用于收集各类系统使用反馈，包括功能建议、界面体验、流程问题、异常报错及优化需求。当前页面为前端样板展示，未接入真实提交与工单流转。
                </p>
            </div>
            <div class="header-actions">
                <button class="ghost-btn" type="button">查看反馈记录</button>
                <button class="primary-btn" type="button">提交反馈</button>
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
                                <div class="section-kicker">提交反馈</div>
                                <h3>反馈表单示例</h3>
                            </div>
                            <span class="tag info">所有角色可见</span>
                        </div>

                        <div class="form-grid">
                            <div class="field-block">
                                <label class="field-label">反馈类型</label>
                                <div class="fake-input">请选择：功能建议 / Bug反馈 / 界面优化 / 其他</div>
                            </div>

                            <div class="field-block">
                                <label class="field-label">问题模块</label>
                                <div class="fake-input">请选择：巡检系统 / 考核系统 / 培训系统 / 车辆系统 / 公共功能</div>
                            </div>

                            <div class="field-block">
                                <label class="field-label">问题标题</label>
                                <div class="fake-input">例如：巡检记录页面移动端显示错位</div>
                            </div>

                            <div class="field-block">
                                <label class="field-label">联系方式</label>
                                <div class="fake-input">手机号 / 邮箱 / 内部联系方式</div>
                            </div>

                            <div class="field-block full-width">
                                <label class="field-label">详细说明</label>
                                <div class="fake-textarea">
                                    请描述问题现象、出现步骤、期望效果或改进建议。若为 Bug，可补充发生时间、页面位置和操作过程。
                                </div>
                            </div>

                            <div class="field-block full-width">
                                <label class="field-label">截图或附件</label>
                                <div class="upload-box">
                                    <div class="upload-icon">↑</div>
                                    <div class="upload-title">上传截图 / 错误图片 / 说明附件</div>
                                    <div class="upload-desc">样板示例：支持拖拽或点击上传，便于快速反馈问题。</div>
                                </div>
                            </div>
                        </div>

                        <div class="form-actions">
                            <button class="ghost-btn" type="button">保存草稿</button>
                            <button class="primary-btn" type="button">提交反馈</button>
                        </div>
                    </div>

                    <div class="card-surface section-card">
                        <div class="section-head">
                            <div>
                                <div class="section-kicker">反馈分类</div>
                                <h3>常见反馈方向</h3>
                            </div>
                        </div>

                        <div class="category-grid">
                            <div v-for="item in feedbackTypes" :key="item.title" class="category-card">
                                <div class="category-icon">{{ item.icon }}</div>
                                <div class="category-title">{{ item.title }}</div>
                                <div class="category-desc">{{ item.desc }}</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="right-column">
                    <div class="card-surface section-card">
                        <div class="section-head compact">
                            <div>
                                <div class="section-kicker">最近反馈</div>
                                <h3>反馈记录示例</h3>
                            </div>
                        </div>

                        <div class="feedback-list">
                            <div v-for="item in feedbackRecords" :key="item.title" class="feedback-item">
                                <div class="feedback-top">
                                    <div>
                                        <div class="feedback-title">{{ item.title }}</div>
                                        <div class="feedback-meta">{{ item.user }} · {{ item.module }} · {{ item.time }}
                                        </div>
                                    </div>
                                    <span :class="['status-chip', item.statusClass]">{{ item.status }}</span>
                                </div>
                                <div class="feedback-desc">{{ item.desc }}</div>
                            </div>
                        </div>
                    </div>

                    <div class="card-surface section-card">
                        <div class="section-head compact">
                            <div>
                                <div class="section-kicker">处理流程</div>
                                <h3>反馈流转示例</h3>
                            </div>
                        </div>

                        <div class="flow-list">
                            <div v-for="(step, index) in flowSteps" :key="step.title" class="flow-step">
                                <div class="flow-index">{{ index + 1 }}</div>
                                <div class="flow-content">
                                    <div class="flow-title">{{ step.title }}</div>
                                    <div class="flow-desc">{{ step.desc }}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="card-surface section-card highlight-card">
                        <div class="section-kicker highlight-kicker">页面定位</div>
                        <h3>公共反馈入口样板</h3>
                        <p>
                            本页面面向所有系统使用人员开放，后续可继续扩展接入真实反馈提交、状态流转、管理员回复、附件上传、处理留痕与反馈统计分析等功能。
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
const statCards = [
    { label: '本月反馈数', value: '18', desc: '包含建议、Bug 与优化意见', descClass: '' },
    { label: '待处理', value: '5', desc: '建议尽快查看并分派', descClass: 'warning-text' },
    { label: '处理中', value: '7', desc: '已有责任人跟进', descClass: '' },
    { label: '已解决', value: '6', desc: '可回访确认效果', descClass: 'success-text' }
]

const feedbackTypes = [
    { icon: '功', title: '功能建议', desc: '对新功能、现有功能增强提出建议。' },
    { icon: '错', title: 'Bug反馈', desc: '反馈报错、页面异常、按钮失效等问题。' },
    { icon: '界', title: '界面优化', desc: '反馈布局、显示、移动端适配等体验问题。' },
    { icon: '流', title: '流程建议', desc: '反馈业务流转、权限设计、审批逻辑优化。' }
]

const feedbackRecords = [
    {
        title: '巡检记录页面移动端表格显示过窄',
        user: '站点账号',
        module: '巡检系统',
        time: '2026-04-20 09:12',
        status: '处理中',
        statusClass: 'warning',
        desc: '在小屏手机上查看巡检记录时，部分字段显示拥挤，建议优化移动端布局。'
    },
    {
        title: '车辆管理系统建议增加归还确认提醒',
        user: '督导组测试账号',
        module: '车辆系统',
        time: '2026-04-19 17:48',
        status: '待处理',
        statusClass: 'neutral',
        desc: '建议对出车后未归还的记录增加到期提醒或高亮提示。'
    },
    {
        title: '培训系统建议增加历史培训档案导出',
        user: '督导组成员',
        module: '培训系统',
        time: '2026-04-18 14:20',
        status: '已解决',
        statusClass: 'success',
        desc: '希望支持按人员导出培训档案，便于后续归档与检查。'
    }
]

const flowSteps = [
    { title: '用户提交反馈', desc: '填写问题类型、模块、说明及附件信息。' },
    { title: '管理员查看分派', desc: '对反馈内容进行分类并安排处理人。' },
    { title: '处理中/回复', desc: '针对反馈进行修复、优化或答复说明。' },
    { title: '关闭归档', desc: '问题解决后关闭反馈，并保留处理记录。' }
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
.category-desc,
.feedback-desc,
.flow-desc {
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
.primary-btn {
    border-radius: 10px;
    font-size: 13px;
    font-weight: 700;
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

.success-text {
    color: #15803d;
}

.content-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.45fr) minmax(320px, 1fr);
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

.form-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
}

.field-block.full-width {
    grid-column: 1 / -1;
}

.field-label {
    display: block;
    margin-bottom: 8px;
    font-size: 13px;
    font-weight: 700;
    color: #475569;
}

.fake-input,
.fake-textarea {
    border: 1px solid #cbd5e1;
    border-radius: 14px;
    background: #fff;
    color: #64748b;
    font-size: 14px;
    line-height: 1.7;
    padding: 14px 16px;
}

.fake-textarea {
    min-height: 110px;
}

.upload-box {
    border: 1px dashed #93c5fd;
    border-radius: 18px;
    background: #f8fbff;
    padding: 24px;
    text-align: center;
}

.upload-icon {
    font-size: 28px;
    font-weight: 800;
    color: #2563eb;
    margin-bottom: 8px;
}

.upload-title {
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
}

.upload-desc {
    margin-top: 8px;
    font-size: 13px;
    line-height: 1.8;
    color: #64748b;
}

.form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 18px;
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

.status-chip.warning {
    background: #fff7ed;
    color: #c2410c;
}

.status-chip.success {
    background: #ecfdf5;
    color: #15803d;
}

.category-grid,
.quick-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}

.category-card,
.quick-entry {
    padding: 18px 16px;
    border: 1px solid #dbe4ee;
    border-radius: 18px;
    background: #f8fafc;
}

.category-icon,
.quick-icon,
.flow-index {
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

.category-title,
.quick-title,
.feedback-title,
.flow-title {
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
}

.feedback-list,
.flow-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.feedback-item,
.flow-step {
    padding: 16px;
    border-radius: 18px;
    background: #f8fafc;
    border: 1px solid #dbe4ee;
}

.feedback-top {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: flex-start;
}

.feedback-meta {
    margin-top: 6px;
    font-size: 13px;
    color: #64748b;
}

.flow-step {
    display: flex;
    gap: 12px;
    align-items: flex-start;
}

.flow-index {
    margin-bottom: 0;
    flex-shrink: 0;
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
    .form-grid,
    .category-grid,
    .quick-grid {
        grid-template-columns: 1fr;
    }

    .section-head,
    .header-actions,
    .feedback-top,
    .form-actions {
        flex-direction: column;
        align-items: stretch;
    }
}
</style>