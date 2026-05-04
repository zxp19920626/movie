<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { cpApi } from '../api'
import { useCpStore } from '../stores/cp'
import type { AppCreateResponse, CpApp } from '../types'

const cpStore = useCpStore()
const loading = ref(false)
const dialogVisible = ref(false)
const form = reactive({ name: '', package_name: '' })
const submitting = ref(false)

const secretsDialog = ref(false)
const secretsData = ref<AppCreateResponse | null>(null)

async function refresh() {
  loading.value = true
  try {
    await cpStore.refreshApps()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.name = ''
  form.package_name = ''
  dialogVisible.value = true
}

async function submit() {
  if (!form.name || !form.package_name) {
    ElMessage.warning('请填写所有字段')
    return
  }
  submitting.value = true
  try {
    const r = await cpApi.createApp({ name: form.name, package_name: form.package_name })
    dialogVisible.value = false
    secretsData.value = r
    secretsDialog.value = true
    await cpStore.refreshApps()
    cpStore.setCurrentApp(r.app.id)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    submitting.value = false
  }
}

async function regenerate(app: CpApp) {
  try {
    await ElMessageBox.confirm(
      `重生密钥后，已部署的 App SDK 必须更新 hmac_secret，否则升级检查接口会 401。是否继续？`,
      '危险操作',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    const r = await cpApi.regenerateKeys(app.id)
    secretsData.value = { app, api_key: r.api_key, hmac_secret: r.hmac_secret }
    secretsDialog.value = true
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function remove(app: CpApp) {
  try {
    await ElMessageBox.confirm(`确定删除 "${app.name}"（所有渠道/版本/规则一并删除）？`, '危险操作', {
      type: 'warning',
    })
    await cpApi.deleteApp(app.id)
    ElMessage.success('已删除')
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}

function selectApp(app: CpApp) {
  cpStore.setCurrentApp(app.id)
  ElMessage.success(`当前 App 切换为 ${app.name}`)
}

function copy(text: string) {
  navigator.clipboard.writeText(text)
  ElMessage.success('已复制')
}

onMounted(refresh)
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">App 租户管理</h1>
      <p class="mv-page-subtitle">每个租户 = 一个接入分发平台的 Android App。movie 是第一个租户；未来可加入其它工具类 App。</p>
    </div>
    <div>
      <el-button type="primary" @click="openCreate">+ 新建 App 租户</el-button>
      <el-button @click="refresh" :loading="loading">刷新</el-button>
    </div>
  </div>

  <div class="mv-card" style="padding: 16px">
    <el-table :data="cpStore.apps" v-loading="loading" border>
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="名称" prop="name" />
      <el-table-column label="包名" prop="package_name" />
      <el-table-column label="tenant_uuid" min-width="240">
        <template #default="{ row }">
          <span class="mv-mono">{{ row.tenant_uuid }}</span>
          <el-button size="small" link @click="copy(row.tenant_uuid)">复制</el-button>
        </template>
      </el-table-column>
      <el-table-column label="状态" prop="status" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="320">
        <template #default="{ row }">
          <el-button
            size="small"
            :type="cpStore.currentAppId === row.id ? 'success' : 'primary'"
            @click="selectApp(row)"
          >{{ cpStore.currentAppId === row.id ? '已选中' : '选为当前' }}</el-button>
          <el-button size="small" @click="regenerate(row)">重生密钥</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>

  <!-- 创建对话框 -->
  <el-dialog v-model="dialogVisible" title="新建 App 租户" width="480px">
    <el-form label-position="top">
      <el-form-item label="名称（仅展示）">
        <el-input v-model="form.name" placeholder="如：Movie Android" />
      </el-form-item>
      <el-form-item label="Android 包名">
        <el-input v-model="form.package_name" placeholder="如：com.movie.app" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">创建</el-button>
    </template>
  </el-dialog>

  <!-- 密钥一次性显示对话框 -->
  <el-dialog v-model="secretsDialog" title="租户密钥（仅显示一次）" width="640px" :close-on-click-modal="false">
    <el-alert type="warning" :closable="false" show-icon style="margin-bottom: 16px">
      <strong>这是唯一一次能看到明文密钥的机会。</strong>请立即复制保存到 1Password 或安全的地方；
      <code>hmac_secret</code> 要烧到 Android App 的 BuildConfig 里；<code>api_key</code>
      仅服务端调用使用，禁止入仓库。
    </el-alert>
    <div v-if="secretsData">
      <p><strong>App：</strong>{{ secretsData.app.name }} (id={{ secretsData.app.id }})</p>
      <p><strong>tenant_uuid：</strong></p>
      <el-input :model-value="secretsData.app.tenant_uuid" readonly>
        <template #append><el-button @click="copy(secretsData.app.tenant_uuid)">复制</el-button></template>
      </el-input>
      <p style="margin-top: 12px"><strong>api_key（服务端调用用）：</strong></p>
      <el-input :model-value="secretsData.api_key" readonly>
        <template #append><el-button @click="copy(secretsData.api_key)">复制</el-button></template>
      </el-input>
      <p style="margin-top: 12px"><strong>hmac_secret（App SDK 用）：</strong></p>
      <el-input :model-value="secretsData.hmac_secret" readonly>
        <template #append><el-button @click="copy(secretsData.hmac_secret)">复制</el-button></template>
      </el-input>
    </div>
    <template #footer>
      <el-button type="primary" @click="secretsDialog = false">已保存，关闭</el-button>
    </template>
  </el-dialog>
</template>
