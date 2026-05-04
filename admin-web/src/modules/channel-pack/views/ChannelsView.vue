<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { cpApi } from '../api'
import { useCpStore } from '../stores/cp'
import type { CpChannel, ChannelCreatePayload } from '../types'

const cpStore = useCpStore()
const loading = ref(false)
const items = ref<CpChannel[]>([])
const dialogVisible = ref(false)
const editing = ref<CpChannel | null>(null)
const form = reactive<ChannelCreatePayload>({
  code: '',
  name: '',
  is_play_store: false,
  signing_strategy: 'walle',
  enabled: true,
  priority: 10,
})
const submitting = ref(false)

const appId = computed(() => cpStore.currentAppId)

async function refresh() {
  if (!appId.value) {
    items.value = []
    return
  }
  loading.value = true
  try {
    const r = await cpApi.listChannels(appId.value)
    items.value = r.items
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    code: '',
    name: '',
    is_play_store: false,
    signing_strategy: 'walle',
    enabled: true,
    priority: 10,
  })
  dialogVisible.value = true
}

function openEdit(row: CpChannel) {
  editing.value = row
  Object.assign(form, {
    code: row.code,
    name: row.name,
    is_play_store: row.is_play_store,
    signing_strategy: row.signing_strategy,
    enabled: row.enabled,
    priority: row.priority,
  })
  dialogVisible.value = true
}

async function submit() {
  if (!appId.value) return
  if (!form.code || !form.name) return ElMessage.warning('请填 code 和 name')
  if (!/^[a-z0-9_]+$/.test(form.code)) return ElMessage.warning('code 只能用小写字母 / 数字 / 下划线')
  if (form.is_play_store && form.signing_strategy === 'walle') {
    return ElMessage.warning('Play Store 渠道不能用 walle（应该是 play_signed），且后端会硬关自升级')
  }

  submitting.value = true
  try {
    if (editing.value) {
      await cpApi.updateChannel(appId.value, editing.value.id, form)
      ElMessage.success('已更新')
    } else {
      await cpApi.createChannel(appId.value, form)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await refresh()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    submitting.value = false
  }
}

async function remove(row: CpChannel) {
  try {
    await ElMessageBox.confirm(`删除渠道 "${row.code}"？`, '确认', { type: 'warning' })
    await cpApi.deleteChannel(appId.value!, row.id)
    ElMessage.success('已删除')
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}

watch(appId, refresh, { immediate: true })
onMounted(() => {
  if (cpStore.apps.length === 0) cpStore.refreshApps().then(refresh)
})
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">渠道管理</h1>
      <p class="mv-page-subtitle">
        当前 App：<b>{{ cpStore.currentApp?.name || '未选择' }}</b>
        — 一个渠道 = 一个 APK 注入身份（自有渠道走 Walle，Play 渠道编译期 flavor 隔离自升级）
      </p>
    </div>
    <div>
      <el-button type="primary" :disabled="!appId" @click="openCreate">+ 新建渠道</el-button>
      <el-button @click="refresh" :loading="loading">刷新</el-button>
    </div>
  </div>

  <el-alert v-if="!appId" type="info" :closable="false" show-icon style="margin-bottom: 12px">
    请先在 "App 租户" 页面选一个 App 作为当前操作目标
  </el-alert>

  <div class="mv-card" style="padding: 16px">
    <el-table :data="items" v-loading="loading" border>
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="code" prop="code" width="160" />
      <el-table-column label="名称" prop="name" />
      <el-table-column label="Play Store" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.is_play_store" type="warning">Play 渠道（自升级硬关）</el-tag>
          <el-tag v-else type="success">自有渠道</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="签名策略" prop="signing_strategy" width="120" />
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '✓' : '✗' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="优先级" prop="priority" width="80" />
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑渠道' : '新建渠道'" width="520px">
    <el-form label-position="top">
      <el-form-item label="code（小写字母/数字/下划线，同 App 内唯一）">
        <el-input v-model="form.code" :disabled="!!editing" placeholder="如：direct / xiaomi_intl" />
      </el-form-item>
      <el-form-item label="名称">
        <el-input v-model="form.name" placeholder="如：自有官网下载" />
      </el-form-item>
      <el-form-item label="是否 Google Play 渠道">
        <el-switch v-model="form.is_play_store" />
        <span class="hint" v-if="form.is_play_store">⚠️ Play 渠道：后端硬拒升级（编译期 flavor 应隔离自升级模块）</span>
      </el-form-item>
      <el-form-item label="签名策略">
        <el-select v-model="form.signing_strategy" style="width: 100%">
          <el-option label="walle（自有渠道注入）" value="walle" />
          <el-option label="play_signed（Play 上架已签）" value="play_signed" />
          <el-option label="none（不签）" value="none" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
      <el-form-item label="优先级（数字越大签名越靠前）">
        <el-input-number v-model="form.priority" :min="0" :max="999" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">提交</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint {
  margin-left: 12px;
  font-size: 12px;
  color: var(--el-color-warning);
}
</style>
