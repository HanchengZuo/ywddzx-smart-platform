<template>
  <div class="service-reading">
    <section>
      <h3>检查基本情况</h3>
      <p>{{ report.overview_text }}</p>
      <p>{{ report.focus_text }}</p>
      <div class="metrics">
        <article v-for="mode in report.mode_summaries" :key="mode.mode">
          <b>{{ mode.mode === 'video' ? '视频巡检' : '现场巡检' }}</b
          ><strong>{{ mode.station_count }} 座 · {{ mode.issue_count }} 项</strong
          ><span>站均问题 {{ mode.average_issue_count }} 项</span>
        </article>
      </div>
    </section>
    <section>
      <h3>截至报告期末问题整改情况</h3>
      <p>{{ report.cumulative_rectification?.narrative }}</p>
      <div class="table">
        <table>
          <thead>
            <tr>
              <th>片区 / 单位</th>
              <th>累计问题</th>
              <th>已整改（闭环）</th>
              <th>站级无法整改</th>
              <th>尚未闭环</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in report.cumulative_rectification?.units" :key="row.unit_name">
              <th>{{ row.unit_name }}</th>
              <td>{{ row.total_count }}</td>
              <td>{{ row.rectified_count }}</td>
              <td>{{ row.unable_count }}</td>
              <td>{{ row.pending_count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <section>
      <h3>区域概况</h3>
      <div class="table">
        <table>
          <thead>
            <tr>
              <th>片区 / 单位</th>
              <th>站点数</th>
              <th>问题数</th>
              <th>站均问题</th>
              <th>加油站</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in report.scope?.units" :key="row.unit_name">
              <th>{{ row.unit_name }}</th>
              <td>{{ row.station_count }}</td>
              <td>{{ row.issue_count }}</td>
              <td>{{ row.average_issue_count }}</td>
              <td>{{ row.station_names.join('、') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <section v-for="mode in report.mode_summaries" :key="mode.mode">
      <h3>{{ mode.mode === 'video' ? '视频' : '现场' }}问题类别与环节</h3>
      <div class="columns">
        <div>
          <h4>问题类别</h4>
          <article v-for="row in mode.categories" :key="row.name" class="bar">
            <span>{{ row.name }}</span>
            <div><i :style="{ width: `${row.percentage}%` }" /></div>
            <b>{{ row.count }} 项 · {{ row.percentage }}%</b>
          </article>
        </div>
        <div>
          <h4>问题环节</h4>
          <article v-for="row in mode.stages" :key="row.name" class="bar">
            <span>{{ row.name }}</span>
            <div><i :style="{ width: `${row.percentage}%` }" /></div>
            <b>{{ row.count }} 项 · {{ row.percentage }}%</b>
          </article>
        </div>
      </div>
    </section>
    <section>
      <h3>问题具体表现</h3>
      <div class="table">
        <table>
          <thead>
            <tr>
              <th>问题具体表现</th>
              <th>问题数</th>
              <th>占比</th>
              <th>代表照片</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="group in report.behavior_analysis?.groups" :key="group.name">
              <th>{{ group.name }}</th>
              <td>{{ group.count }}</td>
              <td>{{ group.percentage }}%</td>
              <td>
                <button
                  v-for="id in report.behavior_examples?.[group.name] || []"
                  :key="id"
                  @click="$emit('photo', findIssue(id))"
                >
                  <img :src="resolveImage(findIssue(id)?.issue_photo)" :alt="`代表问题 #${id}`" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
<script setup>
const props = defineProps({ report: Object, resolveImage: Function })
defineEmits(['photo'])
const findIssue = (id) => props.report.service_issues?.find((row) => row.issue_id === id)
</script>
<style scoped>
.service-reading {
  display: grid;
  gap: 22px;
  color: #233f55;
}
.service-reading section {
  padding: 26px;
  background: #fff;
  border: 1px solid #d5e2ed;
  border-radius: 18px;
}
.service-reading h3 {
  font-size: 22px;
  color: #174a69;
  border-left: 5px solid #237d96;
  padding-left: 14px;
  margin: 0 0 22px;
}
.service-reading p {
  line-height: 1.9;
}
.metrics,
.columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
.metrics article {
  display: grid;
  gap: 10px;
  padding: 20px;
  background: #edf6fa;
  border-radius: 12px;
}
.metrics strong {
  font-size: 24px;
}
.table {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
th,
td {
  padding: 13px;
  border-bottom: 1px solid #e0e8ef;
  text-align: left;
}
thead {
  background: #eaf3f9;
  color: #245777;
}
td img {
  width: 92px;
  height: 64px;
  object-fit: contain;
}
td button {
  border: 0;
  background: transparent;
  cursor: zoom-in;
}
.bar {
  display: grid;
  grid-template-columns: minmax(100px, 1fr) 2fr auto;
  gap: 14px;
  margin: 18px 0;
  align-items: center;
  font-size: 13px;
}
.bar > div {
  height: 8px;
  background: #e2ecf2;
  border-radius: 5px;
  overflow: hidden;
}
.bar i {
  display: block;
  background: #248db4;
  height: 100%;
}
.bar b {
  white-space: nowrap;
}
.columns > div:last-child i {
  background: #2b9989;
}
@media (max-width: 768px) {
  .metrics,
  .columns {
    grid-template-columns: 1fr;
  }
  .bar {
    grid-template-columns: 1fr 1fr;
  }
  .bar > div {
    grid-row: 2;
    grid-column: 1/-1;
  }
  .service-reading section {
    padding: 18px;
  }
}
</style>
