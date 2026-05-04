<script setup lang="ts">
import { useAuthStore } from '@/shared/stores/auth'
const auth = useAuthStore()
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">数据看板</h1>
      <p class="mv-page-subtitle">仪表盘占位页 — 实现见 P5+ 阶段任务（KPI + ECharts）</p>
    </div>
  </div>
  <div class="mv-card" style="padding: 24px">
    <p>欢迎回来，<b>{{ auth.user?.display_name || auth.user?.email }}</b></p>
    <el-empty description="数据看板将在 P5+ 阶段接入" />
  </div>
</template>
