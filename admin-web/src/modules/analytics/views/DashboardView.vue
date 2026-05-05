<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { statsApi } from '../api'
import type { StatsOverview, StatsTrends } from '../types'

const loading = ref(false)
const period = ref(24)
const days = ref(30)
const overview = ref<StatsOverview | null>(null)
const trends = ref<StatsTrends | null>(null)

const chartRefs: Record<string, HTMLDivElement | null> = {
  play_start: null,
  search: null,
  upgrade_check: null,
  ad_pv: null,
}
const chartInstances: Record<string, echarts.ECharts | null> = {}

const KPI_CARDS = [
  { code: 'dau', label: 'DAU（24h 登录用户）', color: '#409EFF' },
  { code: 'daa', label: 'DAA（24h 活跃设备）', color: '#67C23A' },
  { code: 'play_start_count', label: '播放次数', color: '#E6A23C' },
  { code: 'search_count', label: '搜索次数', color: '#F56C6C' },
  { code: 'ad_pv', label: '广告曝光', color: '#909399' },
  { code: 'upgrade_check_count', label: '升级检查', color: '#9d6cf5' },
] as const

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'k'
  return String(n)
}

async function loadAll() {
  loading.value = true
  try {
    const [o, t] = await Promise.all([
      statsApi.overview(period.value),
      statsApi.trends(days.value),
    ])
    overview.value = o
    trends.value = t
    renderCharts()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

function renderCharts() {
  if (!trends.value) return
  for (const s of trends.value.series) {
    const el = chartRefs[s.code]
    if (!el) continue
    if (!chartInstances[s.code]) {
      chartInstances[s.code] = echarts.init(el)
    }
    chartInstances[s.code]!.setOption({
      title: { text: s.label, textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 16, top: 36, bottom: 30 },
      xAxis: {
        type: 'category',
        data: s.points.map((p) => p.date.slice(5)), // MM-DD
        axisLabel: { fontSize: 10 },
      },
      yAxis: { type: 'value' },
      series: [
        {
          type: 'line',
          smooth: true,
          areaStyle: { opacity: 0.15 },
          data: s.points.map((p) => p.value),
        },
      ],
    })
  }
}

function handleResize() {
  for (const k in chartInstances) {
    chartInstances[k]?.resize()
  }
}

watch([period, days], loadAll)

onMounted(async () => {
  await loadAll()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  for (const k in chartInstances) {
    chartInstances[k]?.dispose()
    chartInstances[k] = null
  }
})
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">数据看板</h1>
      <p class="mv-page-subtitle">来自 s_analytics_events 实时聚合（小流量阶段直查；DAU > 5w 切预聚合）</p>
    </div>
    <div>
      <el-select v-model="period" style="width: 160px" @change="loadAll">
        <el-option label="近 24h" :value="24" />
        <el-option label="近 7 天" :value="168" />
        <el-option label="近 30 天" :value="720" />
      </el-select>
    </div>
  </div>

  <!-- KPI 卡 -->
  <el-row :gutter="16" v-loading="loading" style="margin-bottom: 16px">
    <el-col v-for="card in KPI_CARDS" :key="card.code" :span="4">
      <div class="mv-card kpi-card" :style="{ borderTop: `3px solid ${card.color}` }">
        <div class="kpi-label">{{ card.label }}</div>
        <div class="kpi-value">
          {{ overview ? fmt((overview as any)[card.code]) : '—' }}
        </div>
      </div>
    </el-col>
  </el-row>

  <!-- 趋势图 4 个 -->
  <div class="mv-page-header" style="margin-bottom: 8px">
    <div>
      <h2 style="margin: 0; font-size: 16px">趋势</h2>
      <p class="mv-page-subtitle">按天聚合（zero-fill 不断点）</p>
    </div>
    <div>
      <el-select v-model="days" style="width: 140px" @change="loadAll">
        <el-option label="7 天" :value="7" />
        <el-option label="14 天" :value="14" />
        <el-option label="30 天" :value="30" />
        <el-option label="90 天" :value="90" />
      </el-select>
    </div>
  </div>

  <el-row :gutter="16">
    <el-col :span="12" style="margin-bottom: 16px">
      <div class="mv-card chart-box">
        <div :ref="(el) => (chartRefs.play_start = el as HTMLDivElement)" class="chart-canvas" />
      </div>
    </el-col>
    <el-col :span="12" style="margin-bottom: 16px">
      <div class="mv-card chart-box">
        <div :ref="(el) => (chartRefs.search = el as HTMLDivElement)" class="chart-canvas" />
      </div>
    </el-col>
    <el-col :span="12" style="margin-bottom: 16px">
      <div class="mv-card chart-box">
        <div :ref="(el) => (chartRefs.upgrade_check = el as HTMLDivElement)" class="chart-canvas" />
      </div>
    </el-col>
    <el-col :span="12" style="margin-bottom: 16px">
      <div class="mv-card chart-box">
        <div :ref="(el) => (chartRefs.ad_pv = el as HTMLDivElement)" class="chart-canvas" />
      </div>
    </el-col>
  </el-row>
</template>

<style scoped>
.kpi-card {
  padding: 16px;
  background: #fff;
}
.kpi-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.kpi-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}
.chart-box {
  padding: 16px;
}
.chart-canvas {
  height: 240px;
}
</style>
