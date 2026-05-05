<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { categoryApi, videoApi, vodApi } from '../api'
import type {
  CtCategory,
  CtVideo,
  I18nMap,
  RegionVisibilityResp,
} from '../types'

const SUPPORTED_LANGS = ['en', 'zh', 'id', 'vi', 'th', 'ms', 'ar', 'pt', 'es']
// 主要目标地区
const TARGET_COUNTRIES = [
  // SEA
  'ID', 'VN', 'PH', 'TH', 'MM', 'MY', 'KH', 'LA',
  // 中东
  'SA', 'AE', 'EG', 'JO', 'LB', 'IQ', 'YE',
  // 非洲
  'NG', 'ZA', 'KE', 'ET', 'TZ',
  // 拉美
  'BR', 'MX', 'AR', 'CL', 'CO', 'PE', 'VE',
]

const loading = ref(false)
const items = ref<CtVideo[]>([])
const total = ref(0)
const categories = ref<CtCategory[]>([])
const filter = reactive({
  status: '',
  secondary_review_status: '',
  category_id: null as number | null,
  q: '',
  limit: 20,
  offset: 0,
})

// === 编辑对话框 ===
const editVisible = ref(false)
const editing = ref<CtVideo | null>(null)
const editTab = ref('basic')
const form = reactive<{
  code: string
  type: string
  category_id: number | null
  rating: string
  release_year: number | null
  duration_min: number | null
  director: string
  cast_csv: string
  studio: string
  cover_url: string
  poster_url: string
  trailer_url: string
  vod_file_id: string
  required_tier: string
  status: string
  featured: boolean
  trending: boolean
  recommend_priority: number
  score: number | null
  tags_csv: string
  title_i18n: I18nMap
  description_i18n: I18nMap
}>({
  code: '',
  type: 'movie',
  category_id: null,
  rating: '',
  release_year: null,
  duration_min: null,
  director: '',
  cast_csv: '',
  studio: '',
  cover_url: '',
  poster_url: '',
  trailer_url: '',
  vod_file_id: '',
  required_tier: 'free',
  status: 'draft',
  featured: false,
  trending: false,
  recommend_priority: 0,
  score: null,
  tags_csv: '',
  title_i18n: {},
  description_i18n: {},
})

// === 地区可见性对话框 ===
const regionVisible = ref(false)
const regionTarget = ref<CtVideo | null>(null)
const regionMap = ref<Record<string, boolean>>({})

// === 二审对话框 ===
const reviewVisible = ref(false)
const reviewTarget = ref<CtVideo | null>(null)
const reviewAction = ref<'submit' | 'approve' | 'reject'>('submit')
const reviewNote = ref('')

const categoryName = computed(() => {
  const m: Record<number, string> = {}
  for (const c of categories.value) {
    m[c.id] = c.name_i18n.en || c.name_i18n.zh || c.code
  }
  return m
})

type TagType = 'success' | 'warning' | 'info' | 'danger' | 'primary'
const statusType = (s: string): TagType => {
  const m: Record<string, TagType> = {
    draft: 'info',
    online: 'success',
    offline: 'warning',
    archived: 'danger',
    pending: 'warning',
    approved: 'success',
    rejected: 'danger',
    ready: 'success',
    transcoding: 'warning',
    failed: 'danger',
  }
  return m[s] || 'info'
}

async function refresh() {
  loading.value = true
  try {
    const r = await videoApi.list({
      status: filter.status || undefined,
      secondary_review_status: filter.secondary_review_status || undefined,
      category_id: filter.category_id ?? undefined,
      q: filter.q || undefined,
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

async function loadCategories() {
  try {
    const r = await categoryApi.list(200, 0)
    categories.value = r.items.filter((c) => c.status === 'active')
  } catch (e) {
    // 静默：分类管理页加载不影响视频列表使用
    console.warn('categories load failed:', (e as Error).message)
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    code: '',
    type: 'movie',
    category_id: null,
    rating: '',
    release_year: null,
    duration_min: null,
    director: '',
    cast_csv: '',
    studio: '',
    cover_url: '',
    poster_url: '',
    trailer_url: '',
    vod_file_id: '',
    required_tier: 'free',
    status: 'draft',
    featured: false,
    trending: false,
    recommend_priority: 0,
    score: null,
    tags_csv: '',
    title_i18n: {},
    description_i18n: {},
  })
  editTab.value = 'basic'
  editVisible.value = true
}

function openEdit(row: CtVideo) {
  editing.value = row
  Object.assign(form, {
    code: row.code,
    type: row.type,
    category_id: row.category_id,
    rating: row.rating,
    release_year: row.release_year,
    duration_min: row.duration_min,
    director: row.director,
    cast_csv: row.cast_list.join(', '),
    studio: row.studio,
    cover_url: row.cover_url,
    poster_url: row.poster_url,
    trailer_url: row.trailer_url,
    vod_file_id: row.vod_file_id || '',
    required_tier: row.required_tier,
    status: row.status,
    featured: row.featured,
    trending: row.trending,
    recommend_priority: row.recommend_priority,
    score: row.score,
    tags_csv: row.tags.join(', '),
    title_i18n: { ...row.title_i18n },
    description_i18n: { ...row.description_i18n },
  })
  editTab.value = 'basic'
  editVisible.value = true
}

async function save() {
  try {
    const tags = form.tags_csv.split(',').map((s) => s.trim()).filter(Boolean)
    const cast_list = form.cast_csv.split(',').map((s) => s.trim()).filter(Boolean)
    const payload = {
      code: form.code,
      title_i18n: form.title_i18n,
      description_i18n: form.description_i18n,
      type: form.type,
      category_id: form.category_id,
      tags,
      rating: form.rating,
      release_year: form.release_year,
      duration_min: form.duration_min,
      director: form.director,
      cast_list,
      studio: form.studio,
      cover_url: form.cover_url,
      poster_url: form.poster_url,
      trailer_url: form.trailer_url,
      vod_file_id: form.vod_file_id || null,
      required_tier: form.required_tier,
    }
    if (editing.value) {
      await videoApi.update(editing.value.id, {
        ...payload,
        status: form.status as 'draft' | 'online' | 'offline' | 'archived',
        featured: form.featured,
        trending: form.trending,
        recommend_priority: form.recommend_priority,
        score: form.score,
      })
      ElMessage.success('已更新')
    } else {
      if (!form.code) return ElMessage.warning('请填 code')
      await videoApi.create(payload)
      ElMessage.success('已创建')
    }
    editVisible.value = false
    await refresh()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function archive(row: CtVideo) {
  try {
    await ElMessageBox.confirm(`归档影片 "${row.code}"？（软删，不会破坏观看历史）`, '确认', {
      type: 'warning',
    })
    await videoApi.delete(row.id)
    ElMessage.success('已归档')
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}

// === 地区可见性 ===
async function openRegionDialog(row: CtVideo) {
  regionTarget.value = row
  regionMap.value = {}
  for (const c of TARGET_COUNTRIES) regionMap.value[c] = false
  try {
    const r: RegionVisibilityResp = await videoApi.getRegions(row.id)
    for (const c of r.visible_countries) regionMap.value[c] = true
    for (const c of r.hidden_countries) regionMap.value[c] = false
  } catch (e) {
    ElMessage.warning((e as Error).message)
  }
  regionVisible.value = true
}

async function saveRegions() {
  if (!regionTarget.value) return
  try {
    const entries = Object.entries(regionMap.value).map(([country_code, visible]) => ({
      country_code,
      visible,
    }))
    await videoApi.setRegions(regionTarget.value.id, entries)
    ElMessage.success('地区可见性已更新')
    regionVisible.value = false
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

function regionToggleAll(visible: boolean) {
  for (const c of TARGET_COUNTRIES) regionMap.value[c] = visible
}

// === 二审 ===
function openReview(row: CtVideo, action: 'submit' | 'approve' | 'reject') {
  reviewTarget.value = row
  reviewAction.value = action
  reviewNote.value = ''
  reviewVisible.value = true
}

async function doReview() {
  if (!reviewTarget.value) return
  try {
    await videoApi.review(reviewTarget.value.id, {
      action: reviewAction.value,
      note: reviewNote.value,
    })
    ElMessage.success('二审状态已更新')
    reviewVisible.value = false
    await refresh()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

function pageChange(p: number) {
  filter.offset = (p - 1) * filter.limit
  refresh()
}

// === VOD 同步 ===
async function pullFromVod(row: CtVideo) {
  if (!row.vod_file_id) return ElMessage.warning('该影片未挂 vod_file_id')
  try {
    const r = await vodApi.pullOne(row.id)
    if (r.note?.startsWith('stub')) {
      ElMessage.warning(`stub 模式（VOD SDK 未接入）：${r.note}`)
    } else {
      ElMessage.success(`已刷新 vod_status = ${r.new_status}`)
      await refresh()
    }
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function syncAll() {
  try {
    const r = await vodApi.syncAll()
    ElMessage.success(r.message)
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

async function reconcile() {
  try {
    const r = await vodApi.reconcile()
    if (!r.ran) {
      ElMessage.warning(`对账未跑：${r.reason || 'unknown'}`)
      return
    }
    const ml = r.missing_remote?.length || 0
    const er = r.extra_remote?.length || 0
    ElMessageBox.alert(
      `本地 ${r.local_count} 条 / 远程 ${r.remote_count} 条\n本地有 VOD 没（${ml}）：\n${(r.missing_remote || []).slice(0, 10).join('\n')}\n\nVOD 有本地没（${er}）：\n${(r.extra_remote || []).slice(0, 10).join('\n')}`,
      '对账结果',
      { confirmButtonText: '关闭' },
    )
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

const fmtTime = (s: string | null) => (s ? new Date(s).toLocaleString('zh-CN') : '—')

onMounted(async () => {
  await Promise.all([loadCategories(), refresh()])
})
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">影片管理</h1>
      <p class="mv-page-subtitle">
        编辑业务字段 / 多语言文案 / 地区可见性 / 二审流转（来自 ct_videos + ct_region_visibility）
      </p>
    </div>
    <div>
      <el-button @click="syncAll">Sync All（VOD）</el-button>
      <el-button @click="reconcile">对账</el-button>
      <el-button type="primary" @click="openCreate">新建影片</el-button>
    </div>
  </div>

  <div class="mv-card" style="padding: 16px; margin-bottom: 12px">
    <el-form inline @submit.prevent="refresh">
      <el-form-item label="搜索">
        <el-input v-model="filter.q" placeholder="按 code 模糊匹配" style="width: 200px" clearable @clear="refresh" @keyup.enter="refresh" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filter.status" placeholder="全部" clearable style="width: 140px" @change="refresh">
          <el-option label="draft" value="draft" />
          <el-option label="online" value="online" />
          <el-option label="offline" value="offline" />
          <el-option label="archived" value="archived" />
        </el-select>
      </el-form-item>
      <el-form-item label="二审">
        <el-select v-model="filter.secondary_review_status" placeholder="全部" clearable style="width: 140px" @change="refresh">
          <el-option label="draft" value="draft" />
          <el-option label="pending" value="pending" />
          <el-option label="approved" value="approved" />
          <el-option label="rejected" value="rejected" />
        </el-select>
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="filter.category_id" placeholder="全部" clearable style="width: 200px" @change="refresh">
          <el-option v-for="c in categories" :key="c.id" :label="categoryName[c.id]" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-button type="primary" @click="refresh" :loading="loading">查询</el-button>
    </el-form>
  </div>

  <div class="mv-card" style="padding: 16px">
    <el-table :data="items" v-loading="loading" border stripe>
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="code" prop="code" width="140" />
      <el-table-column label="标题（en/zh）" min-width="220">
        <template #default="{ row }">
          <div>{{ row.title_i18n?.en || '—' }}</div>
          <div style="color: #909399; font-size: 12px">{{ row.title_i18n?.zh || '' }}</div>
        </template>
      </el-table-column>
      <el-table-column label="类型" prop="type" width="80" />
      <el-table-column label="分类" width="120">
        <template #default="{ row }">{{ row.category_id ? categoryName[row.category_id] : '—' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><el-tag :type="statusType(row.status)">{{ row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column label="二审" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.secondary_review_status)" size="small">{{ row.secondary_review_status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="VOD" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType(row.vod_status)" size="small">{{ row.vod_status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="推荐" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.featured" type="warning" size="small">置顶</el-tag>
          <el-tag v-if="row.trending" type="primary" size="small" style="margin-left:4px">热门</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="380" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" @click="openRegionDialog(row)">地区</el-button>
          <el-button size="small" @click="pullFromVod(row)" :disabled="!row.vod_file_id">同步</el-button>
          <el-dropdown @command="(cmd: 'submit' | 'approve' | 'reject') => openReview(row, cmd)" trigger="click">
            <el-button size="small" type="success">二审</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="submit">提交</el-dropdown-item>
                <el-dropdown-item command="approve">通过</el-dropdown-item>
                <el-dropdown-item command="reject">驳回</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button size="small" type="warning" @click="archive(row)" :disabled="row.status === 'archived'">归档</el-button>
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

  <!-- 编辑对话框 -->
  <el-dialog v-model="editVisible" :title="editing ? '编辑影片' : '新建影片'" width="900px" top="5vh">
    <el-tabs v-model="editTab">
      <el-tab-pane label="基础" name="basic">
        <el-form label-width="120px">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="code"><el-input v-model="form.code" :disabled="!!editing" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="类型">
                <el-select v-model="form.type" style="width: 100%">
                  <el-option label="movie" value="movie" />
                  <el-option label="series" value="series" />
                  <el-option label="short" value="short" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="分类">
                <el-select v-model="form.category_id" clearable filterable style="width: 100%">
                  <el-option v-for="c in categories" :key="c.id" :label="categoryName[c.id]" :value="c.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="评级"><el-input v-model="form.rating" placeholder="PG / PG-13 / R" /></el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="发行年"><el-input-number v-model="form.release_year" :min="1900" :max="2100" style="width: 100%" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="时长(分)"><el-input-number v-model="form.duration_min" :min="0" style="width: 100%" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="评分"><el-input-number v-model="form.score" :min="0" :max="10" :precision="1" :step="0.1" style="width: 100%" /></el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="导演"><el-input v-model="form.director" /></el-form-item>
          <el-form-item label="主演（逗号）"><el-input v-model="form.cast_csv" /></el-form-item>
          <el-form-item label="制作方"><el-input v-model="form.studio" /></el-form-item>
          <el-form-item label="标签（逗号）"><el-input v-model="form.tags_csv" /></el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="多语言文案" name="i18n">
        <el-row :gutter="16">
          <el-col :span="12">
            <h4>标题</h4>
            <div v-for="lang in SUPPORTED_LANGS" :key="lang" style="display:flex; gap:8px; margin-bottom:6px">
              <el-tag size="small" type="info" style="width: 50px; text-align: center">{{ lang }}</el-tag>
              <el-input v-model="form.title_i18n[lang]" :placeholder="`title (${lang})`" />
            </div>
          </el-col>
          <el-col :span="12">
            <h4>简介</h4>
            <div v-for="lang in SUPPORTED_LANGS" :key="lang" style="display:flex; gap:8px; margin-bottom:6px">
              <el-tag size="small" type="info" style="width: 50px; text-align: center">{{ lang }}</el-tag>
              <el-input v-model="form.description_i18n[lang]" type="textarea" :rows="2" :placeholder="`description (${lang})`" />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="资源 + VOD" name="resources">
        <el-form label-width="120px">
          <el-form-item label="封面 URL"><el-input v-model="form.cover_url" /></el-form-item>
          <el-form-item label="海报 URL"><el-input v-model="form.poster_url" /></el-form-item>
          <el-form-item label="预告片 URL"><el-input v-model="form.trailer_url" /></el-form-item>
          <el-form-item label="VOD file_id"><el-input v-model="form.vod_file_id" placeholder="阿里云 VOD 文件 ID" /></el-form-item>
          <el-form-item label="会员等级">
            <el-select v-model="form.required_tier" style="width: 200px">
              <el-option label="free" value="free" />
              <el-option label="vip1" value="vip1" />
              <el-option label="vip2" value="vip2" />
            </el-select>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane v-if="editing" label="上下线 + 推荐" name="ops">
        <el-form label-width="120px">
          <el-form-item label="状态">
            <el-select v-model="form.status" style="width: 200px">
              <el-option label="draft" value="draft" />
              <el-option label="online" value="online" />
              <el-option label="offline" value="offline" />
              <el-option label="archived" value="archived" />
            </el-select>
            <span style="color:#E6A23C; margin-left:8px">⚠️ online 必须 secondary_review = approved</span>
          </el-form-item>
          <el-form-item label="推荐位">
            <el-checkbox v-model="form.featured">置顶 (featured)</el-checkbox>
            <el-checkbox v-model="form.trending">热门 (trending)</el-checkbox>
          </el-form-item>
          <el-form-item label="推荐优先级"><el-input-number v-model="form.recommend_priority" /></el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <el-button @click="editVisible = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>

  <!-- 地区可见性对话框 -->
  <el-dialog v-model="regionVisible" :title="`地区可见性 - ${regionTarget?.code || ''}`" width="780px">
    <div style="margin-bottom: 12px">
      <el-button size="small" @click="regionToggleAll(true)">全选</el-button>
      <el-button size="small" @click="regionToggleAll(false)">全不选</el-button>
      <span style="color:#909399; margin-left: 12px">提示：未列出的国家默认不可见（黑名单制）</span>
    </div>
    <el-row :gutter="8">
      <el-col v-for="cc in TARGET_COUNTRIES" :key="cc" :span="6" style="margin-bottom: 6px">
        <el-checkbox v-model="regionMap[cc]">{{ cc }}</el-checkbox>
      </el-col>
    </el-row>
    <template #footer>
      <el-button @click="regionVisible = false">取消</el-button>
      <el-button type="primary" @click="saveRegions">保存</el-button>
    </template>
  </el-dialog>

  <!-- 二审对话框 -->
  <el-dialog v-model="reviewVisible" :title="`二审 - ${reviewTarget?.code || ''}`" width="520px">
    <el-form label-width="80px">
      <el-form-item label="动作">
        <el-tag :type="reviewAction === 'approve' ? 'success' : reviewAction === 'reject' ? 'danger' : 'info'">
          {{ reviewAction }}
        </el-tag>
        <div style="color:#909399; font-size: 12px; margin-top: 4px">
          submit: 提交进入审核 / approve: 审核通过 / reject: 驳回
        </div>
      </el-form-item>
      <el-form-item label="备注"><el-input v-model="reviewNote" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="reviewVisible = false">取消</el-button>
      <el-button type="primary" @click="doReview">提交</el-button>
    </template>
  </el-dialog>
</template>
