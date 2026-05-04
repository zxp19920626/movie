// 当前选择的 App 租户 store
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { cpApi } from '../api'
import type { CpApp } from '../types'

export const useCpStore = defineStore('cp', () => {
  const apps = ref<CpApp[]>([])
  const currentAppId = ref<number | null>(
    Number(localStorage.getItem('mv_cp_current_app_id')) || null,
  )

  const currentApp = computed(() =>
    apps.value.find((a) => a.id === currentAppId.value) || null,
  )

  async function refreshApps() {
    const r = await cpApi.listApps()
    apps.value = r.items
    if (currentAppId.value && !apps.value.some((a) => a.id === currentAppId.value)) {
      currentAppId.value = apps.value[0]?.id ?? null
    } else if (!currentAppId.value && apps.value.length > 0) {
      setCurrentApp(apps.value[0].id)
    }
  }

  function setCurrentApp(id: number | null) {
    currentAppId.value = id
    if (id) localStorage.setItem('mv_cp_current_app_id', String(id))
    else localStorage.removeItem('mv_cp_current_app_id')
  }

  return { apps, currentAppId, currentApp, refreshApps, setCurrentApp }
})
