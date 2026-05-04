<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">{{ route.meta.title }}</h1>
      <p class="mv-page-subtitle">channel_pack 模块占位页 — 实现见 P2 阶段任务</p>
    </div>
  </div>
  <div class="mv-card" style="padding: 24px">
    <el-empty description="即将开发">
      <template #description>
        <p>当前路由：<code>{{ route.path }}</code></p>
        <p>详见 <code>docs/channel-module-design.md</code> + <code>TASKS.md P2</code></p>
      </template>
    </el-empty>
  </div>
</template>
