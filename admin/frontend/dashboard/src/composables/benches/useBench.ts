import { ref } from 'vue'

import { settingsApi } from '@/api/settings'

let cached = null

export const useBench = () => {
  const name = ref(cached?.name ?? '')
  const defaultBranch = ref(cached?.defaultBranch ?? '')

  const load = async () => {
    if (cached) return
    let settings
    try {
      settings = await settingsApi.get()
    } catch {
      return // labels only; callers render fine without them
    }
    const branch = settings.bench?.default_branch ?? ''
    cached = {
      name: settings.bench?.name || 'this bench',
      defaultBranch: branch,
    }
    name.value = cached.name
    defaultBranch.value = cached.defaultBranch
  }

  return { name, defaultBranch, load }
}
