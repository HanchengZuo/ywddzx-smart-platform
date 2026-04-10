<template>
  <div class="page-shell">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">考核系统</div>
        <h2>我的考核结果</h2>
        <div class="page-subtitle">查看个人本期综合评分、维度表现、群体对比和 AI 成长分析。</div>
      </div>
      <div class="period-chip">2026年第二季度</div>
    </div>

    <div v-if="hasPermission" class="content-layout">
      <div class="main-column">
        <div class="summary-grid">
          <div class="card-surface summary-card summary-card-primary">
            <div class="summary-label">综合评分</div>
            <div class="summary-value">4.3</div>
            <div class="summary-desc">在本期参评人员中高于平均水平，整体表现稳定。</div>
          </div>

          <div class="card-surface summary-card">
            <div class="summary-label">参评人数</div>
            <div class="summary-value">18</div>
            <div class="summary-desc">本期共收集到 18 份有效互评结果。</div>
          </div>

          <div class="card-surface summary-card">
            <div class="summary-label">群体定位</div>
            <div class="summary-value summary-value-small">中上水平</div>
            <div class="summary-desc">责任心、执行稳定性明显高于群体均值。</div>
          </div>
        </div>

        <div class="card-surface section-card">
          <div class="section-header">
            <div>
              <div class="section-kicker">维度表现</div>
              <h3>本期维度得分概览</h3>
            </div>
          </div>

          <div class="dimension-list">
            <div v-for="item in dimensionScores" :key="item.name" class="dimension-item">
              <div class="dimension-head">
                <div>
                  <div class="dimension-name">{{ item.name }}</div>
                  <div class="dimension-meta">个人得分 {{ item.score }} / 群体均值 {{ item.avg }}</div>
                </div>
                <div :class="['dimension-badge', item.diff >= 0 ? 'positive' : 'negative']">
                  {{ item.diff >= 0 ? `+${item.diff.toFixed(1)}` : item.diff.toFixed(1) }}
                </div>
              </div>

              <div class="bar-group">
                <div class="bar-row">
                  <span>个人</span>
                  <div class="bar-track">
                    <div class="bar-fill personal" :style="{ width: `${(item.score / 5) * 100}%` }"></div>
                  </div>
                </div>
                <div class="bar-row">
                  <span>均值</span>
                  <div class="bar-track">
                    <div class="bar-fill average" :style="{ width: `${(item.avg / 5) * 100}%` }"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="card-surface section-card">
          <div class="section-header">
            <div>
              <div class="section-kicker">AI 分析</div>
              <h3>个人成长反馈</h3>
            </div>
          </div>

          <div class="analysis-block">
            <div class="analysis-title">综合评价</div>
            <div class="analysis-text">
              你本期整体表现稳定，工作责任心和执行可靠性得到了较多正向反馈。AI 根据他人提交的匿名短语评价和各维度评分进行汇总分析后认为：多数评价都指向“认真负责、执行较稳、配合度较高”这几个关键词，说明你在可靠性和任务落实方面具备较强优势。从群体对比来看，你在“工作态度”“执行落实”方面优于平均水平，但在“主动沟通”和“反馈及时性”方面仍有进一步提升空间。
            </div>
          </div>

          <div class="analysis-block phrase-block">
            <div class="analysis-title">匿名短语评价摘要</div>
            <div class="analysis-text">
              系统不会直接展示任何单条原始评价内容，也不会显示评价人身份。下面内容由 AI 对他人提交的匿名短语评价进行聚合提炼，仅用于帮助你理解外界对你的整体印象。
            </div>
            <div class="phrase-group">
              <span v-for="item in phraseHighlights" :key="item" class="phrase-chip">{{ item }}</span>
            </div>
          </div>

          <div class="insight-grid">
            <div class="insight-card insight-strong">
              <div class="insight-title">优势项</div>
              <ul>
                <li>责任心较强，工作可靠度高</li>
                <li>执行稳定，任务落实情况较好</li>
                <li>团队评价中“配合度”获得较多肯定</li>
              </ul>
            </div>

            <div class="insight-card insight-improve">
              <div class="insight-title">待提升项</div>
              <ul>
                <li>在任务推进中可更主动同步进度</li>
                <li>遇到问题时反馈还可以更及时</li>
                <li>跨人协作时建议强化阶段性沟通</li>
              </ul>
            </div>
          </div>

          <div class="analysis-block recommendation-block">
            <div class="analysis-title">下一阶段建议</div>
            <div class="analysis-text">
              建议你在后续工作中继续保持执行稳定、责任心强的优势，同时可以把“主动沟通”作为重点改进方向。例如，在任务开始、中途和完成三个节点主动同步进展；当遇到困难时，尽量提前说明问题与所需支持。这样不仅有助于提升个人评价，也能增强团队对你工作的可预期性和信任感。
            </div>
          </div>
        </div>
      </div>

      <div class="side-column">
        <div class="card-surface side-card">
          <div class="side-title">我的标签画像</div>
          <div class="tag-group">
            <span v-for="tag in profileTags" :key="tag" class="profile-tag">{{ tag }}</span>
          </div>
        </div>

        <div class="card-surface side-card">
          <div class="side-title">群体对比提示</div>
          <div class="compare-list">
            <div class="compare-item">
              <div class="compare-name">责任心</div>
              <div class="compare-value positive">高于均值 +0.6</div>
            </div>
            <div class="compare-item">
              <div class="compare-name">执行落实</div>
              <div class="compare-value positive">高于均值 +0.4</div>
            </div>
            <div class="compare-item">
              <div class="compare-name">主动沟通</div>
              <div class="compare-value negative">低于均值 -0.5</div>
            </div>
            <div class="compare-item">
              <div class="compare-name">反馈及时性</div>
              <div class="compare-value negative">低于均值 -0.3</div>
            </div>
          </div>
        </div>

        <div class="card-surface side-card">
          <div class="side-title">本期提醒</div>
          <div class="side-note">
            当前页面为普通用户视角示例页，仅展示本人可见的汇总结果和 AI 分析，不展示任何他人原始评分，不展示逐条原话，也不展示评价人身份。系统只会对匿名短语评价进行聚合提炼后生成摘要。
          </div>
        </div>
      </div>
    </div>

    <div v-else class="permission-card card-surface">
      <div class="permission-icon">!</div>
      <div class="permission-title">无权限访问</div>
      <div class="permission-desc">当前账号无权访问考核结果页，请使用普通用户账号登录后查看个人结果。</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const currentRole = localStorage.getItem('user_role') || ''
const hasPermission = computed(() => currentRole === 'station_manager' || currentRole === 'employee' || currentRole === 'user')

const dimensionScores = [
  { name: '工作态度', score: 4.7, avg: 4.1, diff: 0.6 },
  { name: '执行落实', score: 4.5, avg: 4.1, diff: 0.4 },
  { name: '沟通协作', score: 3.8, avg: 4.0, diff: -0.2 },
  { name: '主动反馈', score: 3.5, avg: 4.0, diff: -0.5 },
  { name: '职业素养', score: 4.4, avg: 4.1, diff: 0.3 }
]

const profileTags = ['责任心强', '执行稳定', '配合度较高', '值得信任', '沟通可提升']
const phraseHighlights = ['认真负责', '执行比较稳', '做事靠谱', '配合度高', '值得信任', '沟通可以更主动']
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
  gap: 16px;
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

.page-subtitle {
  margin-top: 10px;
  font-size: 14px;
  line-height: 1.8;
  color: #64748b;
}

.period-chip {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 0 14px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #dbe4ee;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.content-layout {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(320px, 0.95fr);
  gap: 20px;
}

.main-column,
.side-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.summary-card {
  padding: 22px;
}

.summary-card-primary {
  background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%);
  border-color: transparent;
  color: #fff;
}

.summary-label {
  font-size: 13px;
  font-weight: 700;
  color: #64748b;
}

.summary-card-primary .summary-label,
.summary-card-primary .summary-desc,
.summary-card-primary .summary-value {
  color: #fff;
}

.summary-value {
  margin-top: 10px;
  font-size: 34px;
  font-weight: 800;
  color: #0f172a;
}

.summary-value-small {
  font-size: 24px;
}

.summary-desc {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.section-card,
.side-card,
.permission-card {
  padding: 24px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.section-kicker {
  font-size: 12px;
  font-weight: 700;
  color: #2563eb;
  margin-bottom: 8px;
}

.section-header h3,
.side-title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
}

.dimension-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dimension-item {
  padding: 16px;
  border-radius: 18px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.dimension-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.dimension-name {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}

.dimension-meta {
  margin-top: 4px;
  font-size: 13px;
  color: #64748b;
}

.dimension-badge {
  flex-shrink: 0;
  min-width: 58px;
  text-align: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.dimension-badge.positive {
  background: #ecfdf5;
  color: #15803d;
}

.dimension-badge.negative {
  background: #fef2f2;
  color: #b91c1c;
}

.bar-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bar-row {
  display: grid;
  grid-template-columns: 42px 1fr;
  align-items: center;
  gap: 10px;
}

.bar-row span {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.bar-track {
  height: 10px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 999px;
}

.bar-fill.personal {
  background: linear-gradient(90deg, #2563eb 0%, #3b82f6 100%);
}

.bar-fill.average {
  background: linear-gradient(90deg, #94a3b8 0%, #cbd5e1 100%);
}

.analysis-block {
  padding: 16px 18px;
  border-radius: 18px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.analysis-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 10px;
}

.analysis-text,
.side-note {
  font-size: 14px;
  line-height: 1.9;
  color: #475569;
}

.insight-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.insight-card {
  padding: 18px;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
}

.insight-strong {
  background: #f0fdf4;
}

.insight-improve {
  background: #fff7ed;
}

.insight-title {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 10px;
}

.insight-card ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-size: 14px;
  line-height: 1.9;
}

.phrase-block,
.recommendation-block {
  margin-top: 18px;
}

.phrase-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.phrase-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #dbe4ee;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.profile-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 700;
}

.compare-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}

.compare-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: #f8fafc;
}

.compare-name {
  font-size: 14px;
  font-weight: 700;
  color: #334155;
}

.compare-value {
  font-size: 13px;
  font-weight: 800;
}

.compare-value.positive {
  color: #15803d;
}

.compare-value.negative {
  color: #b91c1c;
}

.permission-card {
  min-height: 320px;
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

@media (max-width: 1100px) {
  .content-layout {
    grid-template-columns: 1fr;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .insight-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .page-shell {
    gap: 14px;
  }

  .page-header,
  .section-card,
  .side-card,
  .permission-card {
    padding: 18px 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .page-header h2 {
    font-size: 28px;
  }

  .summary-value {
    font-size: 30px;
  }

  .section-header h3,
  .side-title {
    font-size: 20px;
  }

  .dimension-head,
  .compare-item {
    flex-direction: column;
    align-items: flex-start;
  }

  .bar-row {
    grid-template-columns: 36px 1fr;
  }
}
</style>