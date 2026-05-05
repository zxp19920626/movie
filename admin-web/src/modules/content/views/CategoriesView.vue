<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { categoryApi } from '../api'
import type { CtCategory, I18nMap } from '../types'

const SUPPORTED_LANGS = ['en', 'zh', 'id', 'vi', 'th', 'ms', 'ar', 'pt', 'es']

const loading = ref(false)
const items = ref<CtCategory[]>([])

const editVisible = ref(false)
const editing = ref<CtCategory | null>(null)
const form = reactive<{
  code: string
  name_i18n: I18nMap
  parent_id: number | null
  sort_order: number
  status: 'active' | 'archived'
}>({
  code: '',
  name_i18n: {},
  parent_id: null,
  sort_order: 0,
  status: 'active',
})

async function refresh() {
  loading.value = true
  try {
    const r = await categoryApi.list(200, 0)
    items.value = r.items
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.code = ''
  form.name_i18n = {}
  form.parent_id = null
  form.sort_order = 0
  form.status = 'active'
  editVisible.value = true
}

function openEdit(row: CtCategory) {
  editing.value = row
  form.code = row.code
  form.name_i18n = { ...row.name_i18n }
  form.parent_id = row.parent_id
  form.sort_order = row.sort_order
  form.status = row.status
  editVisible.value = true
}

async function save() {
  try {
    if (editing.value) {
      await categoryApi.update(editing.value.id, {
        name_i18n: form.name_i18n,
        parent_id: form.parent_id,
        sort_order: form.sort_order,
        status: form.status,
      })
      ElMessage.success('已更新')
    } else {
      if (!form.code) return ElMessage.warning('请填 code')
      await categoryApi.create({
        code: form.code,
        name_i18n: form.name_i18n,
        parent_id: form.parent_id,
        sort_order: form.sort_order,
      })
      ElMessage.success('已创建')
    }
    editVisible.value = false
    await refresh()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function archive(row: CtCategory) {
  try {
    await ElMessageBox.confirm(`归档分类 "${row.code}"？`, '确认', { type: 'warning' })
    await categoryApi.delete(row.id)
    ElMessage.success('已归档')
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
      <h1 class="mv-page-title">影片分类</h1>
      <p class="mv-page-subtitle">支持多语言名称、父子分类、排序；归档不删除</p>
    </div>
    <el-button type="primary" @click="openCreate">新建分类</el-button>
  </div>

  <div class="mv-card" style="padding: 16px">
    <el-table :data="items" v-loading="loading" border stripe>
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="code" prop="code" width="160" />
      <el-table-column label="名称（en/zh）" min-width="240">
        <template #default="{ row }">
          <span>{{ row.name_i18n?.en || '—' }}</span>
          <span v-if="row.name_i18n?.zh" style="color: #909399; margin-left: 8px">/ {{ row.name_i18n.zh }}</span>
        </template>
      </el-table-column>
      <el-table-column label="父级" prop="parent_id" width="100" />
      <el-table-column label="sort" prop="sort_order" width="80" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="warning" @click="archive(row)" :disabled="row.status === 'archived'">归档</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>

  <el-dialog v-model="editVisible" :title="editing ? '编辑分类' : '新建分类'" width="640px">
    <el-form label-width="100px">
      <el-form-item label="code">
        <el-input v-model="form.code" :disabled="!!editing" placeholder="ascii 业务编码" />
      </el-form-item>
      <el-form-item label="多语言名称">
        <div style="width: 100%">
          <div v-for="lang in SUPPORTED_LANGS" :key="lang" style="display:flex; gap:8px; margin-bottom:6px">
            <el-tag size="small" type="info" style="width: 50px; text-align: center">{{ lang }}</el-tag>
            <el-input v-model="form.name_i18n[lang]" :placeholder="`name (${lang})`" />
          </div>
        </div>
      </el-form-item>
      <el-form-item label="父级 ID">
        <el-input-number v-model="form.parent_id" :min="0" style="width: 200px" />
        <span style="color:#909399; margin-left:8px">留空表示顶级</span>
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="form.sort_order" style="width: 200px" />
      </el-form-item>
      <el-form-item v-if="editing" label="状态">
        <el-select v-model="form.status" style="width: 160px">
          <el-option label="active" value="active" />
          <el-option label="archived" value="archived" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editVisible = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>
