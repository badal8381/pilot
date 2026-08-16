import { ref } from 'vue'

import { activitiesApi } from '@/api/activities'

const activities = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')
const cursor = ref(null)

export const useActivities = () => {
  const load = async (filters = {}) => {
    loading.value = true
    error.value = ''
    cursor.value = null
    try {
      const page = await activitiesApi.list(filters)
      activities.value = page.data
      cursor.value = page.meta.next_cursor
    } catch (caught) {
      error.value = caught.message || 'Failed to load activity'
      activities.value = []
    } finally {
      loading.value = false
    }
  }

  const loadMore = async (filters = {}) => {
    if (!cursor.value || loadingMore.value) return
    loadingMore.value = true
    try {
      const page = await activitiesApi.list({ ...filters, cursor: cursor.value })
      activities.value = [...activities.value, ...page.data]
      cursor.value = page.meta.next_cursor
    } catch (caught) {
      error.value = caught.message || 'Failed to load more activity'
    } finally {
      loadingMore.value = false
    }
  }

  return { activities, loading, loadingMore, error, hasMore: cursor, load, loadMore }
}
