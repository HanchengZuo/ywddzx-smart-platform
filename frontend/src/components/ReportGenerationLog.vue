<template>
  <details class="report-generation-log">
    <summary>
      <div class="log-heading">
        <span class="log-mark" aria-hidden="true">AI</span>
        <div>
          <strong>报告生成日志</strong
          ><small>{{ running ? '当前后台任务的处理记录' : '本份报告生成时的处理记录' }}</small>
        </div>
      </div>
      <div v-if="events.length" class="log-counts">
        <span
          >AI 请求 <b>{{ log.summary?.ai_calls || 0 }}</b> 次</span
        >
        <span class="reuse-count"
          >历史复用 <b>{{ log.summary?.reuse_steps || 0 }}</b> 步</span
        >
        <span v-if="log.summary?.fallback_steps" class="warning-count"
          >需关注 <b>{{ log.summary.fallback_steps }}</b></span
        >
      </div>
      <span class="log-toggle">查看明细</span>
    </summary>
    <div class="log-body">
      <p v-if="!events.length" class="log-empty">
        {{
          running
            ? '正在准备生成任务，日志将随进度更新。'
            : '这份历史报告生成于日志功能启用前，未记录当时的 AI 调用信息。'
        }}
      </p>
      <template v-else>
        <p class="log-note">
          历史复用不会发起新的 AI
          请求。调用次数按应用请求记录，服务重试不单独计数；费用为估算值，以服务商账单为准。
        </p>
        <ol>
          <li v-for="event in events" :key="event.sequence">
            <time>{{ formatTime(event.at) }}</time>
            <div class="log-event">
              <div class="event-title">
                <strong>{{ event.stage }}</strong
                ><span :class="['event-badge', event.outcome]">{{ outcomeLabel(event) }}</span>
              </div>
              <p>{{ event.message }}</p>
              <div class="event-meta">
                <span v-if="event.issue_count !== undefined">问题 {{ event.issue_count }} 项</span>
                <span v-if="event.elapsed_ms !== undefined"
                  >耗时 {{ (event.elapsed_ms / 1000).toFixed(1) }} 秒</span
                >
                <span v-if="event.model">{{ event.model }}</span>
                <span v-if="event.ai_called"
                  >估算费用 ¥{{ Number(event.cost_est || 0).toFixed(6) }}</span
                >
                <span v-if="event.source_generated_at"
                  >原结果生成于 {{ formatTime(event.source_generated_at) }}</span
                >
              </div>
            </div>
          </li>
        </ol>
      </template>
    </div>
  </details>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  log: { type: Object, default: () => ({}) },
  running: { type: Boolean, default: false },
})
const events = computed(() => props.log?.events || [])
const formatTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}
const outcomeLabel = (event) =>
  ({
    info: '任务开始',
    pending: '检查 / 处理',
    cache_hit: '历史分析复用',
    classification_reuse: '历史分类复用',
    ai_result: event.ai_called ? '已调用 AI' : '处理完成',
    fallback: '本地兜底',
    error: '处理异常',
  })[event.outcome] || '处理记录'
</script>

<style scoped>
.report-generation-log {
  margin: 20px 0;
  border: 1px solid #dce6ef;
  border-radius: 18px;
  background: #f8fbfd;
  color: #20354c;
  overflow: hidden;
}
summary {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 18px 22px;
  cursor: pointer;
  list-style: none;
}
summary::-webkit-details-marker {
  display: none;
}
summary:focus-visible {
  outline: 2px solid #2587b9;
  outline-offset: -3px;
}
.log-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}
.log-heading small {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #728298;
}
.log-mark {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 11px;
  background: #e6f1f8;
  color: #247398;
  font-size: 12px;
  font-weight: 800;
}
.log-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  color: #667b91;
}
.log-counts b {
  margin: 0 3px;
  color: #20354c;
}
.reuse-count {
  color: #207a6b;
}
.warning-count {
  color: #a86617;
}
.log-toggle {
  font-size: 12px;
  color: #287ca2;
}
.report-generation-log[open] .log-toggle {
  color: #728298;
}
.log-body {
  padding: 0 22px 18px;
  border-top: 1px solid #e3ebf2;
  background: white;
}
.log-note,
.log-empty {
  font-size: 12px;
  line-height: 1.7;
  color: #758498;
}
ol {
  margin: 18px 0 0;
  padding: 0;
  list-style: none;
  max-height: 460px;
  overflow-y: auto;
}
li {
  display: grid;
  grid-template-columns: 156px minmax(0, 1fr);
  gap: 18px;
  padding: 14px 0;
  border-top: 1px solid #edf1f5;
}
time {
  font-size: 12px;
  color: #718198;
  padding-top: 3px;
}
.event-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 13px;
}
.event-badge {
  border-radius: 6px;
  padding: 3px 7px;
  background: #edf3f8;
  color: #5a728c;
  font-size: 11px;
  font-weight: 500;
}
.event-badge.cache_hit,
.event-badge.classification_reuse {
  background: #e8f5ef;
  color: #21795b;
}
.event-badge.ai_result {
  background: #e9f2fd;
  color: #2963a0;
}
.event-badge.fallback,
.event-badge.error {
  background: #fff2e4;
  color: #a86617;
}
.log-event p {
  margin: 8px 0;
  font-size: 13px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.event-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  font-size: 11px;
  color: #718198;
}
@media (max-width: 700px) {
  summary {
    flex-wrap: wrap;
    gap: 12px;
    padding: 16px;
  }
  .log-heading {
    flex-basis: calc(100% - 80px);
  }
  .log-toggle {
    margin-left: auto;
  }
  .log-counts {
    order: 3;
    width: 100%;
  }
  .log-body {
    padding: 0 16px 16px;
  }
  li {
    grid-template-columns: 1fr;
    gap: 8px;
  }
  ol {
    max-height: 420px;
  }
}
</style>
