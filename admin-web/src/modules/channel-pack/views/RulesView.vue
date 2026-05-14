<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { cpApi } from '../api'
import { useCpStore } from '../stores/cp'
import PopupButtonEditor from '../components/PopupButtonEditor.vue'
import {
  POPUP_STRATEGY_LABELS,
  TARGET_COUNTRIES,
  type CpChannel,
  type CpRule,
  type CpVersion,
  type RuleCreatePayload,
  type RulePreviewResponse,
} from '../types'
import {
  I18N_FALLBACK_LOCALE,
  addLocale,
  availableLocales,
  collectActiveLocales,
  removeLocale,
} from '../composables/useI18nLocales'

const cpStore = useCpStore()
const loading = ref(false)
const items = ref<CpRule[]>([])
const channels = ref<CpChannel[]>([])
const versions = ref<CpVersion[]>([])

const dialogVisible = ref(false)
const editing = ref<CpRule | null>(null)
const submitting = ref(false)

const previewDialog = ref(false)
const previewForm = reactive({ version_code: 1, channel: '', country: 'ID', device_id: 'preview-001' })
const previewResult = ref<RulePreviewResponse | null>(null)

const newRule = (): RuleCreatePayload => ({
  name: '',
  enabled: true,
  version_code_min: 1,
  version_code_max: 99,
  channel_codes: [],
  country_codes: [],
  device_id_hash_mod_min: 0,
  device_id_hash_mod_max: 99,
  target_version_code: 0,
  is_force: false,
  can_skip: true,
  popup_strategy: 'once_per_session',
  popup_interval_hours: null,
  popup_title_i18n: { en: '' },
  popup_content_i18n: { en: '' },
  confirm_text_i18n: { en: 'Update' },
  cancel_text_i18n: { en: 'Later' },
  popup_buttons: [],
  priority: 10,
  effective_from: null,
  effective_to: null,
})

const form = reactive<RuleCreatePayload>(newRule())
const popupEditorRef = ref<{ validationErrors: string[] } | null>(null)

const appId = computed(() => cpStore.currentAppId)

const isPlayStoreHit = computed(() => {
  if (form.channel_codes.length === 0) {
    // apply-to-all：只要 channels 中存在 play store 即可能命中
    return channels.value.some((c) => c.is_play_store)
  }
  return channels.value
    .filter((c) => form.channel_codes.includes(c.code))
    .some((c) => c.is_play_store)
})

const activeLocales = computed(() =>
  collectActiveLocales([
    form.popup_title_i18n,
    form.popup_content_i18n,
    form.confirm_text_i18n,
    form.cancel_text_i18n,
  ]),
)

const addLocaleDialog = reactive({
  visible: false,
  selected: '' as string,
  candidates: [] as { code: string; label: string }[],
})

function openAddLocaleDialog() {
  // 候选基于 4 个 i18n record 的并集
  const merged: Record<string, string> = {
    ...form.popup_title_i18n,
    ...form.popup_content_i18n,
    ...form.confirm_text_i18n,
    ...form.cancel_text_i18n,
  }
  addLocaleDialog.candidates = availableLocales(merged)
  addLocaleDialog.selected = addLocaleDialog.candidates[0]?.code || ''
  addLocaleDialog.visible = true
}

function confirmAddLocale() {
  const code = addLocaleDialog.selected
  if (!code) return
  form.popup_title_i18n = addLocale(form.popup_title_i18n, code)
  form.popup_content_i18n = addLocale(form.popup_content_i18n, code)
  form.confirm_text_i18n = addLocale(form.confirm_text_i18n, code)
  form.cancel_text_i18n = addLocale(form.cancel_text_i18n, code)
  addLocaleDialog.visible = false
}

function removeRuleLocale(code: string) {
  if (code === I18N_FALLBACK_LOCALE) return
  form.popup_title_i18n = removeLocale(form.popup_title_i18n, code)
  form.popup_content_i18n = removeLocale(form.popup_content_i18n, code)
  form.confirm_text_i18n = removeLocale(form.confirm_text_i18n, code)
  form.cancel_text_i18n = removeLocale(form.cancel_text_i18n, code)
}

async function refresh() {
  if (!appId.value) return
  loading.value = true
  try {
    const [r, c, v] = await Promise.all([
      cpApi.listRules(appId.value),
      cpApi.listChannels(appId.value),
      cpApi.listVersions(appId.value),
    ])
    items.value = r.items
    channels.value = c.items
    versions.value = v.items.filter((x) => x.status === 'ready')
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, newRule())
  dialogVisible.value = true
}

function openEdit(row: CpRule) {
  editing.value = row
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  dialogVisible.value = true
}

async function submit() {
  if (!appId.value) return
  if (!form.name) return ElMessage.warning('请填规则名')
  if (!form.target_version_code) return ElMessage.warning('请选目标版本')
  if (form.version_code_min > form.version_code_max) return ElMessage.warning('版本范围非法')
  if (form.device_id_hash_mod_min > form.device_id_hash_mod_max) return ElMessage.warning('灰度区间非法')
  const editorErrors = popupEditorRef.value?.validationErrors ?? []
  if (editorErrors.length > 0) {
    return ElMessage.error(`PopupButton 配置有误：${editorErrors[0]}（共 ${editorErrors.length} 条）`)
  }
  submitting.value = true
  try {
    if (editing.value) {
      await cpApi.updateRule(appId.value, editing.value.id, form)
      ElMessage.success('已更新')
    } else {
      await cpApi.createRule(appId.value, form)
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

async function remove(row: CpRule) {
  try {
    await ElMessageBox.confirm(`删除规则 "${row.name}"？`, '确认', { type: 'warning' })
    await cpApi.deleteRule(appId.value!, row.id)
    ElMessage.success('已删除')
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error((e as Error).message)
  }
}

function openPreview() {
  previewForm.version_code = 1
  previewForm.channel = channels.value.find((c) => !c.is_play_store)?.code || ''
  previewForm.country = 'ID'
  previewForm.device_id = 'preview-001'
  previewResult.value = null
  previewDialog.value = true
}

async function runPreview() {
  if (!appId.value) return
  try {
    previewResult.value = await cpApi.previewRule(appId.value, previewForm)
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

const grayPercent = (rule: CpRule) =>
  rule.device_id_hash_mod_max - rule.device_id_hash_mod_min + 1

watch(appId, refresh, { immediate: true })
onMounted(() => {
  if (cpStore.apps.length === 0) cpStore.refreshApps().then(refresh)
})
</script>

<template>
  <div class="mv-page-header">
    <div>
      <h1 class="mv-page-title">升级规则</h1>
      <p class="mv-page-subtitle">
        当前 App：<b>{{ cpStore.currentApp?.name || '未选择' }}</b>
        — target × policy 表达 强制 / 灰度 / 分国家。priority 高优先匹配；命中第一条即返回
      </p>
    </div>
    <div>
      <el-button :disabled="!appId" @click="openPreview">规则预览</el-button>
      <el-button type="primary" :disabled="!appId" @click="openCreate">+ 新建规则</el-button>
      <el-button @click="refresh" :loading="loading">刷新</el-button>
    </div>
  </div>

  <el-alert v-if="!appId" type="info" :closable="false" show-icon style="margin-bottom: 12px">
    请先在 "App 租户" 页面选一个 App 作为当前操作目标
  </el-alert>

  <div class="mv-card" style="padding: 16px">
    <el-table :data="items" v-loading="loading" border>
      <el-table-column label="ID" prop="id" width="60" />
      <el-table-column label="名称" prop="name" min-width="160" />
      <el-table-column label="启用" width="70">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '✓' : '✗' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="目标版本" prop="target_version_code" width="100" />
      <el-table-column label="覆盖版本">
        <template #default="{ row }">{{ row.version_code_min }}–{{ row.version_code_max }}</template>
      </el-table-column>
      <el-table-column label="渠道">
        <template #default="{ row }">
          <span v-if="row.channel_codes.length === 0" style="color: #909399">全部</span>
          <el-tag v-for="c in row.channel_codes" :key="c" size="small" style="margin-right: 4px">{{ c }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="国家">
        <template #default="{ row }">
          <span v-if="row.country_codes.length === 0" style="color: #909399">全部</span>
          <span v-else>{{ row.country_codes.join(', ') }}</span>
        </template>
      </el-table-column>
      <el-table-column label="灰度" width="100">
        <template #default="{ row }">
          {{ grayPercent(row) }}%
        </template>
      </el-table-column>
      <el-table-column label="强升" width="70">
        <template #default="{ row }">
          <el-tag v-if="row.is_force" type="danger" size="small">强升</el-tag>
          <el-tag v-else type="info" size="small">弱提示</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="弹窗策略">
        <template #default="{ row }">
          {{ POPUP_STRATEGY_LABELS[row.popup_strategy as keyof typeof POPUP_STRATEGY_LABELS] }}
        </template>
      </el-table-column>
      <el-table-column label="按钮数" width="80" class-name="popup-buttons-count-col">
        <template #default="{ row }">
          <el-tag size="small" :type="row.popup_buttons?.length ? 'primary' : 'info'">
            {{ row.popup_buttons?.length ?? 0 }}
          </el-tag>
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

  <!-- 规则编辑对话框 -->
  <el-dialog v-model="dialogVisible" :title="editing ? '编辑规则' : '新建规则'" width="720px" :close-on-click-modal="false">
    <el-form label-position="top">
      <el-form-item label="名称">
        <el-input v-model="form.name" placeholder="如：印尼东南亚 1.0→1.1 灰度 30%" />
      </el-form-item>

      <el-divider content-position="left">命中条件（target）</el-divider>

      <el-row :gutter="12">
        <el-col :span="8">
          <el-form-item label="覆盖版本下界">
            <el-input-number v-model="form.version_code_min" :min="0" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="覆盖版本上界">
            <el-input-number v-model="form.version_code_max" :min="0" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="目标版本（必须 ready）">
            <el-select v-model="form.target_version_code" placeholder="选 ready 版本">
              <el-option v-for="v in versions" :key="v.id" :label="`vc=${v.version_code} (${v.version_name})`" :value="v.version_code" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="渠道（空 = 所有；不能选 Play 渠道）">
        <el-select v-model="form.channel_codes" multiple style="width: 100%">
          <el-option
            v-for="c in channels.filter((x) => !x.is_play_store)"
            :key="c.code"
            :label="`${c.code} — ${c.name}`"
            :value="c.code"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="国家（空 = 所有；ISO-3166 alpha-2）">
        <el-select v-model="form.country_codes" multiple filterable style="width: 100%">
          <el-option v-for="c in TARGET_COUNTRIES" :key="c.code" :label="`${c.code} — ${c.label}`" :value="c.code" />
        </el-select>
      </el-form-item>

      <el-row :gutter="12">
        <el-col :span="8">
          <el-form-item label="灰度区间下界（0-99）">
            <el-input-number v-model="form.device_id_hash_mod_min" :min="0" :max="99" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="灰度区间上界（0-99）">
            <el-input-number v-model="form.device_id_hash_mod_max" :min="0" :max="99" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="覆盖比例">
            <el-tag>{{ form.device_id_hash_mod_max - form.device_id_hash_mod_min + 1 }}%</el-tag>
          </el-form-item>
        </el-col>
      </el-row>

      <el-divider content-position="left">命中后策略（policy）</el-divider>

      <el-row :gutter="12">
        <el-col :span="8">
          <el-form-item label="强制升级">
            <el-switch v-model="form.is_force" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="可跳过">
            <el-switch v-model="form.can_skip" :disabled="form.is_force" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="优先级（高 = 优先匹配）">
            <el-input-number v-model="form.priority" :min="0" :max="999" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="弹窗策略">
            <el-select v-model="form.popup_strategy" style="width: 100%">
              <el-option v-for="(label, code) in POPUP_STRATEGY_LABELS" :key="code" :label="label" :value="code" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item v-if="form.popup_strategy === 'custom_interval'" label="自定义间隔（小时）">
            <el-input-number v-model="form.popup_interval_hours" :min="1" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="弹窗多语言文案（en 必填；可 + 添加语言 / × 删除）">
        <div style="margin-bottom: 8px; display: flex; gap: 8px; flex-wrap: wrap">
          <el-tag
            v-for="code in activeLocales"
            :key="code"
            :closable="code !== 'en'"
            :data-test="`rule-locale-${code}`"
            @close="removeRuleLocale(code)"
          >
            {{ code }}
          </el-tag>
          <el-button size="small" data-test="rule-add-locale" @click="openAddLocaleDialog">+ 添加语言</el-button>
        </div>
        <el-tabs>
          <el-tab-pane label="标题">
            <el-input v-for="code in activeLocales" :key="code" v-model="form.popup_title_i18n[code]" :placeholder="`[${code}] 标题`" style="margin-bottom: 4px" />
          </el-tab-pane>
          <el-tab-pane label="内容">
            <el-input v-for="code in activeLocales" :key="code" v-model="form.popup_content_i18n[code]" type="textarea" :rows="2" :placeholder="`[${code}] 内容`" style="margin-bottom: 4px" />
          </el-tab-pane>
          <el-tab-pane label="确定按钮">
            <el-input v-for="code in activeLocales" :key="code" v-model="form.confirm_text_i18n[code]" :placeholder="`[${code}] 确定`" style="margin-bottom: 4px" />
          </el-tab-pane>
          <el-tab-pane label="取消按钮">
            <el-input v-for="code in activeLocales" :key="code" v-model="form.cancel_text_i18n[code]" :placeholder="`[${code}] 取消`" style="margin-bottom: 4px" />
          </el-tab-pane>
        </el-tabs>
      </el-form-item>

      <el-divider content-position="left">PopupButton（最多 5 个；不配则用上面 confirm/cancel 兜底）</el-divider>
      <el-form-item>
        <PopupButtonEditor
          ref="popupEditorRef"
          v-model="form.popup_buttons"
          :allowed-hosts="cpStore.currentApp?.allowed_upgrade_hosts ?? []"
          :is-play-store="isPlayStoreHit"
          :locales="activeLocales"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">提交</el-button>
    </template>
  </el-dialog>

  <!-- 添加语言对话框 -->
  <el-dialog v-model="addLocaleDialog.visible" title="+ 添加语言" width="360px">
    <el-form label-position="top">
      <el-form-item label="选择 locale">
        <el-select v-model="addLocaleDialog.selected" placeholder="locale" style="width: 100%">
          <el-option
            v-for="l in addLocaleDialog.candidates"
            :key="l.code"
            :label="`${l.code} — ${l.label}`"
            :value="l.code"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="addLocaleDialog.visible = false">取消</el-button>
      <el-button type="primary" :disabled="!addLocaleDialog.selected" @click="confirmAddLocale">添加</el-button>
    </template>
  </el-dialog>

  <!-- 规则预览对话框 -->
  <el-dialog v-model="previewDialog" title="规则预览（模拟设备调 /upgrade/check）" width="640px">
    <el-form label-position="top">
      <el-row :gutter="12">
        <el-col :span="6">
          <el-form-item label="version_code">
            <el-input-number v-model="previewForm.version_code" :min="0" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="channel">
            <el-input v-model="previewForm.channel" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="country">
            <el-input v-model="previewForm.country" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="device_id">
            <el-input v-model="previewForm.device_id" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-button type="primary" @click="runPreview">运行预览</el-button>
    </el-form>
    <div v-if="previewResult" style="margin-top: 16px">
      <el-alert :type="previewResult.has_update ? 'success' : 'info'" :closable="false">
        <template v-if="previewResult.has_update">
          ✓ 命中规则 #{{ previewResult.matched_rule_id }}（{{ previewResult.matched_rule_name }}）
          → 升级到 vc={{ previewResult.target_version_code }}
          {{ previewResult.is_force ? '【强升】' : '【弱提示】' }}
        </template>
        <template v-else>无规则命中（不升级）</template>
      </el-alert>
      <h4 style="margin-top: 12px">引擎执行步骤</h4>
      <pre class="mv-mono" style="background: #f7f7f7; padding: 12px; border-radius: 4px">{{ previewResult.debug_steps.join('\n') }}</pre>
    </div>
  </el-dialog>
</template>
