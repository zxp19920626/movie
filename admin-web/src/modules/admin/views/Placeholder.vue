<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">{{ route.meta.title }}</h1>
      <p class="mv-page-subtitle">admin 模块占位页 — 实现见 P3.14a-d</p>
    </div>
  </div>
  <div class="mv-card" style="padding: 24px">
    <el-empty description="即将开发">
      <template #description>
        <p>设计参考：<code>nextstream/admin/src/views/PermissionsView.vue</code></p>
      </template>
    </el-empty>
  </div>
</template>
