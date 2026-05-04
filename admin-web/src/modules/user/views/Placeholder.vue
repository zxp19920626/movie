<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">{{ route.meta.title }}</h1>
      <p class="mv-page-subtitle">user 模块占位页 — 实现见 P3 阶段任务</p>
    </div>
  </div>
  <div class="mv-card" style="padding: 24px">
    <el-empty description="即将开发" />
  </div>
</template>
