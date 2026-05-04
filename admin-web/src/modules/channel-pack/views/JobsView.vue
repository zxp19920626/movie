<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { cpApi } from '../api'
import { useCpStore } from '../stores/cp'
import type { CpSigningJob } from '../types'

const cpStore = useCpStore()
const loading = ref(false)
const items = ref<CpSigningJob[]>([])
const filterStatus = ref<string>('')
const filterVc = ref<number | undefined>(undefined)

const appId = computed(() => cpStore.currentAppId)

async function refresh() {
  if (!appId.value) return
  loading.value = true
  try {
    const r = await cpApi.listJobs(appId.value, {
      status: filterStatus.value || undefined,
      version_code: filterVc.value,
    })
    items.value = r.items
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

async function retry(row: CpSigningJob) {
  try {
    await cpApi.retryJob(appId.value!, row.id)
    ElMessage.success('已重新调度，刷新查看状态')
    await refresh()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

type TagType = 'success' | 'warning' | 'info' | 'danger' | 'primary'
const statusType = (s: string): TagType => {
  const map: Record<string, TagType> = {
    pending: 'info',
    running: 'warning',
    success: 'success',
    failed: 'danger',
  }
  return map[s] || 'info'
}

const fmtSize = (b: number) => {
  if (b < 1024) return `${b}B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)}KB`
  return `${(b / 1024 / 1024).toFixed(1)}MB`
}

watch(appId, refresh, { immediate: true })
onMounted(() => {
  if (cpStore.apps.length === 0) cpStore.refreshApps().then(refresh)
})
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">签名任务</h1>
      <p class="mv-page-subtitle">
        当前 App：<b>{{ cpStore.currentApp?.name || '未选择' }}</b>
        — Walle 渠道签名任务的状态（每个 enabled 非 Play 渠道一个 job）
      </p>
    </div>
    <div>
      <el-input v-model.number="filterVc" placeholder="version_code" type="number" style="width: 140px; margin-right: 8px" clearable />
      <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 140px; margin-right: 8px">
        <el-option label="pending" value="pending" />
        <el-option label="running" value="running" />
        <el-option label="success" value="success" />
        <el-option label="failed" value="failed" />
      </el-select>
      <el-button @click="refresh" :loading="loading">查询</el-button>
    </div>
  </div>

  <el-alert v-if="!appId" type="info" :closable="false" show-icon style="margin-bottom: 12px">
    请先在 "App 租户" 页面选一个 App 作为当前操作目标
  </el-alert>

  <div class="mv-card" style="padding: 16px">
    <el-table :data="items" v-loading="loading" border>
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="vc" prop="version_code" width="80" />
      <el-table-column label="渠道" prop="channel_code" width="140" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="尝试次数" prop="attempts" width="100" />
      <el-table-column label="输出大小" width="100">
        <template #default="{ row }">{{ row.output_size ? fmtSize(row.output_size) : '—' }}</template>
      </el-table-column>
      <el-table-column label="输出 SHA256" min-width="200">
        <template #default="{ row }">
          <span v-if="row.output_sha256" class="mv-mono" :title="row.output_sha256">{{ row.output_sha256.slice(0, 16) }}…</span>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="错误" min-width="200">
        <template #default="{ row }">
          <span v-if="row.last_error" style="color: var(--el-color-danger); font-size: 12px">{{ row.last_error }}</span>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="完成时间" width="170">
        <template #default="{ row }">
          {{ row.finished_at ? new Date(row.finished_at).toLocaleString('zh-CN') : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button v-if="row.status === 'failed'" size="small" type="primary" @click="retry(row)">重试</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
