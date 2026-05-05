<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { rbacApi } from '../api'
import type { AdminRole, AdminUserRow } from '../types'

const loading = ref(false)
const items = ref<AdminUserRow[]>([])
const roles = ref<AdminRole[]>([])

const editVisible = ref(false)
const editing = ref<AdminUserRow | null>(null)
const form = reactive<{
  email: string
  password: string
  display_name: string
  role_id: number | null
  app_scope_csv: string
  status: 'active' | 'suspended'
}>({
  email: '',
  password: '',
  display_name: '',
  role_id: null,
  app_scope_csv: '',
  status: 'active',
})

async function refresh() {
  loading.value = true
  try {
    const [a, r] = await Promise.all([rbacApi.listAdmins(), rbacApi.listRoles()])
    items.value = a.items
    roles.value = r.items
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.email = ''
  form.password = ''
  form.display_name = ''
  form.role_id = null
  form.app_scope_csv = ''
  form.status = 'active'
  editVisible.value = true
}

function openEdit(row: AdminUserRow) {
  editing.value = row
  form.email = row.email
  form.password = ''
  form.display_name = row.display_name
  form.role_id = row.role_id
  form.app_scope_csv = (row.app_scope || []).join(', ')
  form.status = row.status
  editVisible.value = true
}

async function save() {
  try {
    const app_scope = form.app_scope_csv
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    if (editing.value) {
      const payload: Record<string, unknown> = {
        display_name: form.display_name,
        role_id: form.role_id ?? undefined,
        app_scope,
        status: form.status,
      }
      if (form.password) payload.password = form.password
      await rbacApi.updateAdmin(editing.value.id, payload)
      ElMessage.success('已更新')
    } else {
      if (!form.email) return ElMessage.warning('请填 email')
      if (!form.password || form.password.length < 8) {
        return ElMessage.warning('密码至少 8 位')
      }
      if (!form.role_id) return ElMessage.warning('请选角色')
      await rbacApi.createAdmin({
        email: form.email,
        password: form.password,
        display_name: form.display_name,
        role_id: form.role_id,
        app_scope,
      })
      ElMessage.success('已创建')
    }
    editVisible.value = false
    await refresh()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function disable(row: AdminUserRow) {
  try {
    await ElMessageBox.confirm(`禁用管理员 "${row.email}"？`, '确认', { type: 'warning' })
    await rbacApi.disableAdmin(row.id)
    ElMessage.success('已禁用')
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}

const fmtTime = (s: string | null) => (s ? new Date(s).toLocaleString('zh-CN') : '—')

onMounted(refresh)
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">管理员账号</h1>
      <p class="mv-page-subtitle">分配角色 + app_scope 多租户权限隔离；禁用为软删（保留审计）</p>
    </div>
    <el-button type="primary" @click="openCreate">新建管理员</el-button>
  </div>

  <div class="mv-card" style="padding: 16px">
    <el-table :data="items" v-loading="loading" border stripe>
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="邮箱" prop="email" min-width="220" />
      <el-table-column label="昵称" prop="display_name" />
      <el-table-column label="角色" min-width="180">
        <template #default="{ row }">
          {{ row.role_name }}
          <el-tag v-if="row.is_super_admin" type="danger" size="small" style="margin-left: 4px">super</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="App 租户作用域" min-width="200">
        <template #default="{ row }">
          <el-tag v-for="s in row.app_scope" :key="s" size="small" style="margin-right:4px">{{ s }}</el-tag>
          <span v-if="!row.app_scope?.length" style="color:#909399">全部</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'warning'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后登录" width="160">
        <template #default="{ row }">{{ fmtTime(row.last_login_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="warning" @click="disable(row)" :disabled="row.status === 'suspended'">禁用</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>

  <el-dialog v-model="editVisible" :title="editing ? '编辑管理员' : '新建管理员'" width="640px">
    <el-form label-width="100px">
      <el-form-item label="邮箱">
        <el-input v-model="form.email" :disabled="!!editing" />
      </el-form-item>
      <el-form-item :label="editing ? '新密码' : '密码'">
        <el-input v-model="form.password" type="password" show-password :placeholder="editing ? '留空则不改' : '至少 8 位'" />
      </el-form-item>
      <el-form-item label="昵称"><el-input v-model="form.display_name" /></el-form-item>
      <el-form-item label="角色">
        <el-select v-model="form.role_id" placeholder="选择角色" style="width: 100%">
          <el-option v-for="r in roles" :key="r.id" :label="`${r.name} (${r.code})${r.is_super_admin ? ' ★super' : ''}`" :value="r.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="App 租户">
        <el-input v-model="form.app_scope_csv" placeholder="tenant_uuid 逗号分隔；留空 = 全部" />
      </el-form-item>
      <el-form-item v-if="editing" label="状态">
        <el-select v-model="form.status" style="width: 200px">
          <el-option label="active" value="active" />
          <el-option label="suspended" value="suspended" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editVisible = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>
