<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { userApi } from '../api'
import type { CUser, CUserDetail } from '../types'

const loading = ref(false)
const items = ref<CUser[]>([])
const total = ref(0)
const filter = reactive({
  search: '',
  status: '' as '' | 'active' | 'suspended' | 'deleted',
  limit: 20,
  offset: 0,
})

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<CUserDetail | null>(null)

type TagType = 'success' | 'warning' | 'info' | 'danger' | 'primary'
const statusType = (s: string): TagType => {
  const m: Record<string, TagType> = {
    active: 'success',
    suspended: 'warning',
    deleted: 'danger',
  }
  return m[s] || 'info'
}

async function refresh() {
  loading.value = true
  try {
    const r = await userApi.list({
      search: filter.search || undefined,
      status: filter.status || undefined,
      limit: filter.limit,
      offset: filter.offset,
    })
    items.value = r.items
    total.value = r.total
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

async function viewDetail(row: CUser) {
  detailVisible.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await userApi.get(row.id)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    detailLoading.value = false
  }
}

async function toggleStatus(row: CUser) {
  const next = row.status === 'active' ? 'suspended' : 'active'
  const verb = next === 'suspended' ? '禁用' : '解禁'
  try {
    await ElMessageBox.confirm(
      `确认${verb}用户 "${row.email || row.phone || row.display_name}"？`,
      '确认',
      { type: 'warning' },
    )
    await userApi.update(row.id, { status: next as 'active' | 'suspended' })
    ElMessage.success(`已${verb}`)
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}

function pageChange(p: number) {
  filter.offset = (p - 1) * filter.limit
  refresh()
}

const fmtTime = (s: string | null) => (s ? new Date(s).toLocaleString('zh-CN') : '—')

onMounted(refresh)
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">用户管理</h1>
      <p class="mv-page-subtitle">
        C 端用户列表 — 支持搜索 / 禁用 / 查看设备指纹（来自 u_users + u_devices 表）
      </p>
    </div>
  </div>

  <div class="mv-card" style="padding: 16px; margin-bottom: 12px">
    <el-form inline @submit.prevent="refresh">
      <el-form-item label="搜索">
        <el-input
          v-model="filter.search"
          placeholder="email / phone / 昵称"
          style="width: 240px"
          clearable
          @clear="refresh"
          @keyup.enter="refresh"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filter.status" placeholder="全部" clearable style="width: 140px" @change="refresh">
          <el-option label="active" value="active" />
          <el-option label="suspended" value="suspended" />
          <el-option label="deleted" value="deleted" />
        </el-select>
      </el-form-item>
      <el-button type="primary" @click="refresh" :loading="loading">查询</el-button>
    </el-form>
  </div>

  <div class="mv-card" style="padding: 16px">
    <el-table :data="items" v-loading="loading" border stripe>
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="邮箱 / 手机" min-width="200">
        <template #default="{ row }">
          <div v-if="row.email" class="mv-mono">{{ row.email }}</div>
          <div v-if="row.phone" class="mv-mono">{{ row.phone }}</div>
          <div v-if="!row.email && !row.phone" style="color:#909399">—</div>
        </template>
      </el-table-column>
      <el-table-column label="昵称" prop="display_name" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="国家" prop="country" width="80" />
      <el-table-column label="语言" prop="preferred_language" width="80" />
      <el-table-column label="App 租户" prop="app_id" width="90" />
      <el-table-column label="注册时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.registered_at) }}</template>
      </el-table-column>
      <el-table-column label="最后活跃" width="160">
        <template #default="{ row }">{{ fmtTime(row.last_active_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewDetail(row)">详情</el-button>
          <el-button
            size="small"
            :type="row.status === 'active' ? 'warning' : 'success'"
            @click="toggleStatus(row)"
            :disabled="row.status === 'deleted'"
          >{{ row.status === 'active' ? '禁用' : '解禁' }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top: 12px; text-align: right">
      <el-pagination
        background
        layout="prev, pager, next, total"
        :current-page="Math.floor(filter.offset / filter.limit) + 1"
        :page-size="filter.limit"
        :total="total"
        @current-change="pageChange"
      />
    </div>
  </div>

  <!-- 详情对话框 -->
  <el-dialog v-model="detailVisible" title="用户详情" width="720px">
    <div v-loading="detailLoading">
      <template v-if="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="UUID（公开）"><span class="mv-mono">{{ detail.uuid }}</span></el-descriptions-item>
          <el-descriptions-item label="昵称">{{ detail.display_name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(detail.status)">{{ detail.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ detail.email || '—' }}</el-descriptions-item>
          <el-descriptions-item label="手机">{{ detail.phone || '—' }}</el-descriptions-item>
          <el-descriptions-item label="国家">{{ detail.country || '—' }}</el-descriptions-item>
          <el-descriptions-item label="语言">{{ detail.preferred_language }}</el-descriptions-item>
          <el-descriptions-item label="App 租户">{{ detail.app_id ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="注册">{{ fmtTime(detail.registered_at) }}</el-descriptions-item>
          <el-descriptions-item label="最后活跃" :span="2">{{ fmtTime(detail.last_active_at) }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin-top:16px">设备列表（{{ detail.devices.length }}）</h4>
        <el-empty v-if="detail.devices.length === 0" description="未登记设备" :image-size="60" />
        <el-table v-else :data="detail.devices" border size="small">
          <el-table-column label="device_id" prop="device_id" min-width="160" />
          <el-table-column label="平台" prop="platform" width="80" />
          <el-table-column label="App ver" prop="app_version" width="100" />
          <el-table-column label="渠道" prop="channel" width="120" />
          <el-table-column label="国家" prop="country" width="80" />
          <el-table-column label="App 租户" prop="app_id" width="90" />
          <el-table-column label="last_seen" min-width="160">
            <template #default="{ row }">{{ fmtTime(row.last_seen_at) }}</template>
          </el-table-column>
        </el-table>
      </template>
    </div>
  </el-dialog>
</template>
