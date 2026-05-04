<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { cpApi } from '../api'
import { useCpStore } from '../stores/cp'
import { I18N_LOCALES, type CpVersion } from '../types'

const cpStore = useCpStore()
const loading = ref(false)
const items = ref<CpVersion[]>([])
const uploadDialog = ref(false)
const submitting = ref(false)
const uploadProgress = ref(0)

const form = reactive({
  apk_file: null as File | null,
  version_code: 1,
  version_name: '',
  min_supported_version_code: 0,
  changelog_i18n: { en: '' } as Record<string, string>,
})

const appId = computed(() => cpStore.currentAppId)

async function refresh() {
  if (!appId.value) {
    items.value = []
    return
  }
  loading.value = true
  try {
    const r = await cpApi.listVersions(appId.value)
    items.value = r.items
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

function openUpload() {
  const maxVc = items.value.reduce((m, v) => Math.max(m, v.version_code), 0)
  form.apk_file = null
  form.version_code = maxVc + 1
  form.version_name = ''
  form.min_supported_version_code = 0
  form.changelog_i18n = { en: '' }
  uploadProgress.value = 0
  uploadDialog.value = true
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  form.apk_file = input.files?.[0] || null
}

function addLocale() {
  const used = Object.keys(form.changelog_i18n)
  const next = I18N_LOCALES.find((l) => !used.includes(l.code))
  if (next) form.changelog_i18n[next.code] = ''
}

function removeLocale(code: string) {
  if (code === 'en') return
  delete form.changelog_i18n[code]
}

async function submit() {
  if (!appId.value || !form.apk_file) return ElMessage.warning('请选择 APK 文件')
  if (!form.version_code || !form.version_name) return ElMessage.warning('请填 version_code/name')
  submitting.value = true
  uploadProgress.value = 0
  try {
    await cpApi.uploadVersion(appId.value, form.apk_file, {
      version_code: form.version_code,
      version_name: form.version_name,
      min_supported_version_code: form.min_supported_version_code,
      changelog_i18n: form.changelog_i18n,
    }, (pct) => { uploadProgress.value = pct })
    uploadDialog.value = false
    ElMessage.success('上传成功，draft 状态；点 Finalize 触发渠道签名')
    await refresh()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    submitting.value = false
  }
}

async function finalize(row: CpVersion) {
  try {
    await ElMessageBox.confirm(
      `Finalize 会触发所有"自有渠道"的 APK 签名 fan-out（每个 enabled & 非 Play 渠道一个 job）。继续？`,
      '确认',
    )
    await cpApi.finalizeVersion(appId.value!, row.id)
    ElMessage.success('已触发签名，请到"签名任务"页查看进度')
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}

async function remove(row: CpVersion) {
  try {
    await ElMessageBox.confirm(`删除版本 ${row.version_name} (vc=${row.version_code})？`, '确认', {
      type: 'warning',
    })
    await cpApi.deleteVersion(appId.value!, row.id)
    ElMessage.success('已删除')
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}

type TagType = 'success' | 'warning' | 'info' | 'danger' | 'primary'
const statusType = (s: string): TagType => {
  const map: Record<string, TagType> = {
    draft: 'info',
    signing: 'warning',
    ready: 'success',
    archived: 'info',
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
      <h1 class="mv-page-title">版本管理</h1>
      <p class="mv-page-subtitle">
        当前 App：<b>{{ cpStore.currentApp?.name || '未选择' }}</b>
        — 上传母包 APK；version_code 必须严格递增（防灰度回滚）
      </p>
    </div>
    <div>
      <el-button type="primary" :disabled="!appId" @click="openUpload">+ 上传新版本</el-button>
      <el-button @click="refresh" :loading="loading">刷新</el-button>
    </div>
  </div>

  <el-alert v-if="!appId" type="info" :closable="false" show-icon style="margin-bottom: 12px">
    请先在 "App 租户" 页面选一个 App 作为当前操作目标
  </el-alert>

  <div class="mv-card" style="padding: 16px">
    <el-table :data="items" v-loading="loading" border>
      <el-table-column label="vc" prop="version_code" width="80" />
      <el-table-column label="version" prop="version_name" width="120" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="100">
        <template #default="{ row }">{{ fmtSize(row.master_apk_size) }}</template>
      </el-table-column>
      <el-table-column label="SHA256" min-width="200">
        <template #default="{ row }">
          <span class="mv-mono" :title="row.master_apk_sha256">{{ row.master_apk_sha256.slice(0, 16) }}…</span>
        </template>
      </el-table-column>
      <el-table-column label="changelog">
        <template #default="{ row }">
          <span v-if="row.changelog_i18n.en">{{ row.changelog_i18n.en }}</span>
          <span v-else style="color: #999">—</span>
        </template>
      </el-table-column>
      <el-table-column label="上传时间" width="170">
        <template #default="{ row }">{{ new Date(row.uploaded_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button v-if="row.status === 'draft' || row.status === 'signing'" size="small" type="primary" @click="finalize(row)">
            Finalize
          </el-button>
          <el-button v-if="row.status !== 'ready'" size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>

  <el-dialog v-model="uploadDialog" title="上传新版本" width="600px" :close-on-click-modal="false">
    <el-form label-position="top">
      <el-form-item label="APK 文件">
        <input type="file" accept=".apk" @change="onFileChange" />
        <div v-if="form.apk_file" style="margin-top: 8px; font-size: 12px; color: #666">
          已选：{{ form.apk_file.name }}（{{ fmtSize(form.apk_file.size) }}）
        </div>
      </el-form-item>
      <el-form-item label="version_code（必须严格大于历史最大）">
        <el-input-number v-model="form.version_code" :min="1" />
      </el-form-item>
      <el-form-item label="version_name（如 1.2.3）">
        <el-input v-model="form.version_name" />
      </el-form-item>
      <el-form-item label="min_supported_version_code（低于此值强升）">
        <el-input-number v-model="form.min_supported_version_code" :min="0" />
      </el-form-item>
      <el-form-item label="更新说明（多语言；en 必填）">
        <div v-for="(_, code) in form.changelog_i18n" :key="code" style="display: flex; gap: 8px; margin-bottom: 8px">
          <span style="width: 60px; font-size: 12px; color: #666; line-height: 32px">{{ code }}：</span>
          <el-input v-model="form.changelog_i18n[code]" />
          <el-button size="small" @click="removeLocale(code)" :disabled="code === 'en'">×</el-button>
        </div>
        <el-button size="small" @click="addLocale">+ 加语言</el-button>
      </el-form-item>
      <el-progress v-if="submitting" :percentage="uploadProgress" />
    </el-form>
    <template #footer>
      <el-button @click="uploadDialog = false" :disabled="submitting">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">上传</el-button>
    </template>
  </el-dialog>
</template>
