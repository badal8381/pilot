import { ref } from 'vue'
import { notificationsApi } from '@/api/notifications'
import type { Notification } from '@/types/notification'

interface NotificationFilters {
  category?: string
  unreadOnly?: boolean
}

interface NotificationPage {
  data: Notification[]
  meta: { limit: number; next_cursor: string | null; unread: number }
}

const pageSize = 20

const notifications = ref<Notification[]>([])
const unread = ref(0)
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')
const cursor = ref<string | null>(null)

let shownFilters: NotificationFilters = {}

const searchParams = (filters: NotificationFilters, forCursor?: string | null) => {
  const params: Record<string, string | number> = { limit: pageSize }

  if (filters.category) params.category = filters.category
  if (filters.unreadOnly) params.unread_only = '1'
  if (forCursor) params.cursor = forCursor

  return params
}

export const useNotifications = () => {
  const load = async (filters: NotificationFilters = {}) => {
    shownFilters = filters
    loading.value = true
    error.value = ''
    cursor.value = null

    try {
      const page: NotificationPage = await notificationsApi.list(searchParams(filters))

      notifications.value = page.data
      cursor.value = page.meta.next_cursor
      unread.value = page.meta.unread
    } catch (caught: any) {
      error.value = caught.message || 'Failed to load notifications'
      notifications.value = []
    } finally {
      loading.value = false
    }
  }

  const loadMore = async (filters: NotificationFilters = {}) => {
    if (!cursor.value || loadingMore.value) return

    loadingMore.value = true

    try {
      const page: NotificationPage = await notificationsApi.list(
        searchParams(filters, cursor.value),
      )

      notifications.value = [...notifications.value, ...page.data]
      cursor.value = page.meta.next_cursor
      unread.value = page.meta.unread
    } catch (caught: any) {
      error.value = caught.message || 'Failed to load more notifications'
    } finally {
      loadingMore.value = false
    }
  }

  const refreshBadge = async () => {
    const page: NotificationPage | null = await notificationsApi.list({ limit: 1 }).catch(() => null)

    if (page) unread.value = page.meta.unread
  }

  const markAsRead = async (name: string) => {
    const row = notifications.value.find((item) => item.name === name)

    if (!row || row.is_read) return

    row.is_read = true
    unread.value = Math.max(0, unread.value - 1)

    try {
      await notificationsApi.markRead(name)
    } catch {
      await load(shownFilters)
    }
  }

  const markAllAsRead = async () => {
    for (const item of notifications.value) item.is_read = true
    unread.value = 0

    try {
      await notificationsApi.markAllRead()
    } catch {
      await load(shownFilters)
    }
  }

  return {
    notifications,
    unread,
    loading,
    loadingMore,
    error,
    hasMore: cursor,
    load,
    loadMore,
    refreshBadge,
    markAsRead,
    markAllAsRead,
  }
}
