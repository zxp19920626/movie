<script setup lang="ts">
import { computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import {
  POPUP_BUTTON_TYPES,
  POPUP_BUTTON_TYPE_LABELS,
  type PopupButton,
  type PopupButtonStyle,
  type PopupButtonType,
} from '../types'
import {
  I18N_FALLBACK_LOCALE,
  availableLocales,
  addLocale,
  removeLocale,
} from '../composables/useI18nLocales'

interface Props {
  modelValue: PopupButton[]
  allowedHosts: string[]
  isPlayStore: boolean
  locales: string[]
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: () => [],
  allowedHosts: () => [],
  isPlayStore: false,
  locales: () => [I18N_FALLBACK_LOCALE],
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: PopupButton[]): void
}>()

const MAX_BUTTONS = 5

// 给每个按钮算出当前展示的 locales（与父组件传入的活跃 locale 合并取并集，保证至少 en）
function buttonLocales(btn: PopupButton): string[] {
  const set = new Set<string>(props.locales)
  set.add(I18N_FALLBACK_LOCALE)
  for (const k of Object.keys(btn.text_i18n || {})) set.add(k)
  if (btn.url_i18n) for (const k of Object.keys(btn.url_i18n)) set.add(k)
  return Array.from(set)
}

function emitUpdate(next: PopupButton[]) {
  emit('update:modelValue', next)
}

function makeDefaultButton(): PopupButton {
  const seq = props.modelValue.length + 1
  return {
    id: `btn_${seq}`,
    type: 'browser',
    text_i18n: { [I18N_FALLBACK_LOCALE]: '' },
    url_i18n: { [I18N_FALLBACK_LOCALE]: '' },
    style: null,
    target: null,
  }
}

function addButton() {
  if (props.modelValue.length >= MAX_BUTTONS) return
  const next = [...props.modelValue, makeDefaultButton()]
  emitUpdate(next)
}

async function removeButton(idx: number) {
  try {
    await ElMessageBox.confirm(
      `删除按钮 "${props.modelValue[idx]?.id || idx + 1}"？`,
      '确认',
      { type: 'warning' },
    )
  } catch {
    return
  }
  const next = props.modelValue.filter((_, i) => i !== idx)
  emitUpdate(next)
}

function moveButton(idx: number, dir: -1 | 1) {
  const target = idx + dir
  if (target < 0 || target >= props.modelValue.length) return
  const next = [...props.modelValue]
  const [item] = next.splice(idx, 1)
  next.splice(target, 0, item)
  emitUpdate(next)
}

function updateField<K extends keyof PopupButton>(idx: number, key: K, value: PopupButton[K]) {
  const next = props.modelValue.map((b, i) => (i === idx ? { ...b, [key]: value } : b))
  emitUpdate(next)
}

function changeType(idx: number, newType: PopupButtonType) {
  const next = props.modelValue.map((b, i) => {
    if (i !== idx) return b
    const patched: PopupButton = { ...b, type: newType }
    // type='none' 时清空 url_i18n；从 none 切换到其它类型时确保 url_i18n 至少有 en 空串
    if (newType === 'none') {
      patched.url_i18n = null
    } else if (!patched.url_i18n || Object.keys(patched.url_i18n).length === 0) {
      patched.url_i18n = { [I18N_FALLBACK_LOCALE]: '' }
    }
    return patched
  })
  emitUpdate(next)
}

function updateTextI18n(idx: number, code: string, value: string) {
  const next = props.modelValue.map((b, i) => {
    if (i !== idx) return b
    return { ...b, text_i18n: { ...b.text_i18n, [code]: value } }
  })
  emitUpdate(next)
}

function updateUrlI18n(idx: number, code: string, value: string) {
  const next = props.modelValue.map((b, i) => {
    if (i !== idx) return b
    const url_i18n = b.url_i18n ? { ...b.url_i18n } : {}
    url_i18n[code] = value
    return { ...b, url_i18n }
  })
  emitUpdate(next)
}

function addButtonLocale(idx: number, code: string) {
  const next = props.modelValue.map((b, i) => {
    if (i !== idx) return b
    const patched: PopupButton = {
      ...b,
      text_i18n: addLocale(b.text_i18n, code),
    }
    if (b.type !== 'none') {
      patched.url_i18n = addLocale(b.url_i18n ?? {}, code)
    }
    return patched
  })
  emitUpdate(next)
}

function removeButtonLocale(idx: number, code: string) {
  if (code === I18N_FALLBACK_LOCALE) return
  const next = props.modelValue.map((b, i) => {
    if (i !== idx) return b
    const patched: PopupButton = {
      ...b,
      text_i18n: removeLocale(b.text_i18n, code),
    }
    if (b.url_i18n) {
      patched.url_i18n = removeLocale(b.url_i18n, code)
    }
    return patched
  })
  emitUpdate(next)
}

function pickAvailableLocales(btn: PopupButton): { code: string; label: string }[] {
  return availableLocales({ ...(btn.text_i18n || {}), ...(btn.url_i18n || {}) })
}

// ============ 实时业务校验 ============

function extractHost(url: string): string | null {
  try {
    const u = new URL(url)
    return u.hostname.toLowerCase()
  } catch {
    return null
  }
}

const validationErrors = computed<string[]>(() => {
  const errors: string[] = []
  const ids = new Map<string, number>()
  for (let i = 0; i < props.modelValue.length; i++) {
    const btn = props.modelValue[i]
    const label = `按钮 #${i + 1}（id=${btn.id || '空'}）`
    // 1. Play 渠道 + inapp_apk
    if (props.isPlayStore && btn.type === 'inapp_apk') {
      errors.push(`${label}：Play 渠道禁止选 inapp_apk（后端会 422）`)
    }
    // 2/3. url 校验
    if (btn.type !== 'none' && btn.url_i18n) {
      for (const [code, url] of Object.entries(btn.url_i18n)) {
        if (!url) continue
        if (!url.startsWith('https://')) {
          errors.push(`${label} [${code}]：url 必须 https`)
          continue
        }
        const host = extractHost(url)
        if (host === null) {
          errors.push(`${label} [${code}]：url 解析失败`)
          continue
        }
        if (props.allowedHosts.length > 0 && !props.allowedHosts.includes(host)) {
          errors.push(`${label} [${code}]：host 不在白名单：${host}`)
        }
      }
    }
    // 4. id 重复
    if (btn.id) {
      if (ids.has(btn.id)) {
        errors.push(`按钮 id 重复："${btn.id}"（第 ${ids.get(btn.id)! + 1} 个与第 ${i + 1} 个）`)
      } else {
        ids.set(btn.id, i)
      }
    }
  }
  return errors
})

defineExpose({ validationErrors })

// ============ 选语言对话框 ============
const addLocaleDialog = computed(() => null) // 占位，对话框逻辑由 ElMessageBox.prompt 替代下面 inline 实现

async function openAddLocale(idx: number) {
  const candidates = pickAvailableLocales(props.modelValue[idx])
  if (candidates.length === 0) return
  // 用 ElMessageBox.prompt 简单选 — 因为不引入新依赖，这里用一个临时 select 渲染
  // 但 ElMessageBox.prompt 仅支持输入框，所以用 confirm + select 不直接支持。
  // 退而求其次：让用户输入 locale code（候选展示在 message）。
  const message = `从候选选一个 locale code：\n${candidates.map((c) => `- ${c.code} (${c.label})`).join('\n')}`
  try {
    const { value } = await ElMessageBox.prompt(message, '+ 添加语言', {
      inputPattern: new RegExp(`^(${candidates.map((c) => c.code).join('|')})$`),
      inputErrorMessage: '请输入候选中的 locale code',
    })
    if (typeof value === 'string') addButtonLocale(idx, value)
  } catch {
    // 取消
  }
}

const POPUP_BUTTON_STYLES: PopupButtonStyle[] = ['primary', 'secondary', 'danger']
</script>

<template>
  <div class="popup-button-editor">
    <el-alert
      v-for="(err, i) in validationErrors"
      :key="i"
      type="error"
      :title="err"
      :closable="false"
      show-icon
      style="margin-bottom: 6px"
    />

    <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 8px">
      <el-tooltip
        :disabled="modelValue.length < 5"
        content="最多 5 个按钮"
        placement="top"
      >
        <span>
          <el-button
            type="primary"
            size="small"
            :disabled="modelValue.length >= 5"
            @click="addButton"
          >
            + 添加按钮
          </el-button>
        </span>
      </el-tooltip>
      <span style="color: #909399; font-size: 12px">已 {{ modelValue.length }} / 5</span>
    </div>

    <el-collapse v-if="modelValue.length > 0">
      <el-collapse-item
        v-for="(btn, idx) in modelValue"
        :key="idx"
        :name="String(idx)"
        :title="`${btn.id || '(无 id)'} (${POPUP_BUTTON_TYPE_LABELS[btn.type] || btn.type})`"
      >
        <el-form label-position="top" size="small">
          <el-row :gutter="12">
            <el-col :span="8">
              <el-form-item label="按钮 ID（≤32 字符，本规则内唯一）">
                <el-input
                  :model-value="btn.id"
                  maxlength="32"
                  @update:model-value="(v: string) => updateField(idx, 'id', v)"
                />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="类型">
                <el-select
                  :model-value="btn.type"
                  style="width: 100%"
                  @update:model-value="(v: PopupButtonType) => changeType(idx, v)"
                >
                  <el-option
                    v-for="t in POPUP_BUTTON_TYPES"
                    :key="t"
                    :label="POPUP_BUTTON_TYPE_LABELS[t]"
                    :value="t"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="样式">
                <el-select
                  :model-value="btn.style || ''"
                  clearable
                  style="width: 100%"
                  @update:model-value="(v: PopupButtonStyle | '') => updateField(idx, 'style', v || null)"
                >
                  <el-option v-for="s in POPUP_BUTTON_STYLES" :key="s" :label="s" :value="s" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="多语言文案">
            <el-tabs>
              <el-tab-pane
                v-for="code in buttonLocales(btn)"
                :key="code"
                :name="code"
              >
                <template #label>
                  <span>
                    {{ code }}
                    <el-button
                      v-if="code !== 'en'"
                      size="small"
                      link
                      type="danger"
                      :data-test="`remove-locale-${idx}-${code}`"
                      @click.stop="removeButtonLocale(idx, code)"
                    >×</el-button>
                  </span>
                </template>
                <el-input
                  placeholder="按钮文案 text（≤200）"
                  :model-value="btn.text_i18n[code] || ''"
                  maxlength="200"
                  style="margin-bottom: 6px"
                  @update:model-value="(v: string) => updateTextI18n(idx, code, v)"
                />
                <el-input
                  v-if="btn.type !== 'none'"
                  placeholder="跳转 url（https://... ≤500）"
                  :model-value="(btn.url_i18n && btn.url_i18n[code]) || ''"
                  maxlength="500"
                  @update:model-value="(v: string) => updateUrlI18n(idx, code, v)"
                />
              </el-tab-pane>
            </el-tabs>
            <div style="margin-top: 6px">
              <el-button
                size="small"
                :disabled="pickAvailableLocales(btn).length === 0"
                @click="openAddLocale(idx)"
              >+ 添加语言</el-button>
            </div>
          </el-form-item>

          <div style="display: flex; gap: 8px; justify-content: flex-end">
            <el-button
              size="small"
              :disabled="idx === 0"
              :data-test="`move-up-${idx}`"
              @click="moveButton(idx, -1)"
            >↑ 上移</el-button>
            <el-button
              size="small"
              :disabled="idx === modelValue.length - 1"
              :data-test="`move-down-${idx}`"
              @click="moveButton(idx, 1)"
            >↓ 下移</el-button>
            <el-button
              size="small"
              type="danger"
              :data-test="`remove-btn-${idx}`"
              @click="removeButton(idx)"
            >删除</el-button>
          </div>
        </el-form>
      </el-collapse-item>
    </el-collapse>

    <el-empty
      v-else
      description="尚未配置按钮（如不配，App 会用 confirm_text_i18n/cancel_text_i18n 兜底两个按钮）"
      :image-size="80"
    />
  </div>
</template>

<style scoped>
.popup-button-editor :deep(.el-collapse-item__content) {
  padding-bottom: 12px;
}
</style>
