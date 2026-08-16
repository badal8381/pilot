import { ref } from 'vue'

import { monitorApi } from '@/api/monitor'
import { formatBytes } from '@/utils/format'
import { siteStorageBytes } from '@/utils/storage'

// The breakdown shells out to `du` for every app and site directory, so pages
// share one result rather than each walking the disk on mount.
const REFRESH_AFTER_MS = 60_000

const breakdown = ref(null)
let fetchedAt = 0
let pending = null

export const useSiteStorage = () => {
  const load = (force = false) => {
    if (!force) {
      if (pending) return pending
      if (breakdown.value && Date.now() - fetchedAt < REFRESH_AFTER_MS) return Promise.resolve()
    }
    const request = monitorApi
      .storage()
      .then((data) => {
        breakdown.value = data
        fetchedAt = Date.now()
      })
      .catch(() => {}) // a size label; every caller renders fine without it
      .finally(() => {
        // A stale in-flight request may finish after a forced one replaced
        // it; only clear `pending` if it still points at this request.
        if (pending === request) pending = null
      })
    pending = request
    return pending
  }

  const storageLabel = (siteName) => {
    const bytes = breakdown.value ? siteStorageBytes(breakdown.value, siteName) : 0
    return bytes ? formatBytes(bytes) : ''
  }

  return { load, storageLabel }
}
