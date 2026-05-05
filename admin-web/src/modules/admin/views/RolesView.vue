<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { rbacApi } from '../api'
import type { AdminRole, PermissionTree } from '../types'

const loading = ref(false)
const roles = ref<AdminRole[]>([])
const tree = ref<PermissionTree | null>(null)

const editVisible = ref(false)
const editing = ref<AdminRole | null>(null)
const form = reactive<{
  code: string
  name: string
  perms: Set<string>
}>({
  code: '',
  name: '',
  perms: new Set<string>(),
})

const flatPerms = computed(() => tree.value?.all_codes || [])

async function refresh() {
  loading.value = true
  try {
    const [rolesRes, t] = await Promise.all([
      rbacApi.listRoles(),
      tree.value ? Promise.resolve(tree.value) : rbacApi.permissionTree(),
    ])
    roles.value = rolesRes.items
    tree.value = t
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.code = ''
  form.name = ''
  form.perms = new Set<string>()
  editVisible.value = true
}

function openEdit(role: AdminRole) {
  editing.value = role
  form.code = role.code
  form.name = role.name
  form.perms = new Set<string>(role.permissions)
  editVisible.value = true
}

function toggleModule(moduleCode: string, on: boolean) {
  const m = tree.value?.tree.find((x) => x.module === moduleCode)
  if (!m) return
  for (const a of m.actions) {
    if (on) form.perms.add(a.code)
    else form.perms.delete(a.code)
  }
  // 触发响应式
  form.perms = new Set(form.perms)
}

function moduleAllChecked(moduleCode: string): boolean {
  const m = tree.value?.tree.find((x) => x.module === moduleCode)
  if (!m) return false
  return m.actions.every((a) => form.perms.has(a.code))
}

async function save() {
  if (editing.value?.is_super_admin) {
    ElMessage.warning('super_admin 角色不可改 permissions')
    return
  }
  try {
    const perms = Array.from(form.perms)
    if (editing.value) {
      await rbacApi.updateRole(editing.value.id, {
        name: form.name,
        permissions: perms,
      })
      ElMessage.success('已更新')
    } else {
      if (!form.code) return ElMessage.warning('请填 code')
      if (!form.name) return ElMessage.warning('请填 name')
      await rbacApi.createRole({ code: form.code, name: form.name, permissions: perms })
      ElMessage.success('已创建')
    }
    editVisible.value = false
    await refresh()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function deleteRole(role: AdminRole) {
  try {
    await ElMessageBox.confirm(`删除角色 "${role.code}"？`, '确认', { type: 'warning' })
    await rbacApi.deleteRole(role.id)
    ElMessage.success('已删除')
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}

onMounted(refresh)
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">角色与权限</h1>
      <p class="mv-page-subtitle">
        6 模块 × 多权限点；super_admin 角色短路所有检查；内置角色不可删
      </p>
    </div>
    <el-button type="primary" @click="openCreate">新建角色</el-button>
  </div>

  <div class="mv-card" style="padding: 16px">
    <el-table :data="roles" v-loading="loading" border stripe>
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="code" prop="code" width="180" />
      <el-table-column label="名称" prop="name" min-width="160" />
      <el-table-column label="标识" width="160">
        <template #default="{ row }">
          <el-tag v-if="row.is_super_admin" type="danger" size="small">super_admin</el-tag>
          <el-tag v-if="row.is_builtin" type="info" size="small" style="margin-left:4px">内置</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="权限点数" width="100">
        <template #default="{ row }">
          <span v-if="row.is_super_admin" style="color:#F56C6C">∞ (短路)</span>
          <span v-else>{{ row.permissions.length }} / {{ flatPerms.length }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">{{ row.is_super_admin ? '查看' : '编辑' }}</el-button>
          <el-button
            size="small"
            type="danger"
            :disabled="row.is_builtin"
            @click="deleteRole(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>

  <el-dialog v-model="editVisible" :title="editing ? `编辑角色 - ${editing.code}` : '新建角色'" width="900px" top="5vh">
    <el-form label-width="80px">
      <el-row :gutter="16">
        <el-col :span="10">
          <el-form-item label="code">
            <el-input v-model="form.code" :disabled="!!editing" placeholder="ascii 蛇形：content_manager" />
          </el-form-item>
        </el-col>
        <el-col :span="14">
          <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <div v-if="editing?.is_super_admin" style="padding:12px; background:#FEF3F0; border-radius:6px; margin-bottom:12px">
      ⚠️ super_admin 角色拥有所有权限（短路），permissions 列表不参与判定，无法编辑。
    </div>

    <h4 style="margin-top:0">权限矩阵</h4>
    <div class="mv-card" style="padding:0; overflow:hidden">
      <el-table :data="tree?.tree || []" border>
        <el-table-column label="模块" width="180">
          <template #default="{ row }">
            <strong>{{ row.label }}</strong>
            <div style="color:#909399; font-size:12px">{{ row.module }}</div>
          </template>
        </el-table-column>
        <el-table-column label="全选">
          <template #default="{ row }">
            <el-checkbox
              :model-value="moduleAllChecked(row.module)"
              :disabled="editing?.is_super_admin"
              @change="(v) => toggleModule(row.module, !!v)"
            />
          </template>
        </el-table-column>
        <el-table-column label="权限点" min-width="500">
          <template #default="{ row }">
            <el-checkbox
              v-for="a in row.actions"
              :key="a.code"
              :model-value="form.perms.has(a.code)"
              :disabled="editing?.is_super_admin"
              @change="(v) => {
                if (v) form.perms.add(a.code); else form.perms.delete(a.code)
                form.perms = new Set(form.perms)
              }"
              style="margin-right: 16px"
            >
              {{ a.label }}
              <span style="color:#909399; font-size:12px">({{ a.code }})</span>
            </el-checkbox>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <template #footer>
      <el-button @click="editVisible = false">取消</el-button>
      <el-button
        type="primary"
        :disabled="editing?.is_super_admin"
        @click="save"
      >保存</el-button>
    </template>
  </el-dialog>
</template>
