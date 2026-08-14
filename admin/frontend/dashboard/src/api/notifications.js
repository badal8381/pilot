import { apiErrorMessage, request, unwrap } from './client'

const mutate = async (pending) => {
  const response = await pending

  if (response.ok) return

  const payload = await response.json().catch(() => null)
  throw new Error(apiErrorMessage(payload, 'Could not update the notification.'))
}

export const notificationsApi = {
  list: (params) => unwrap(request.get('notifications', { searchParams: params }).json()),
  markRead: (name) => mutate(request.post(`notifications/${encodeURIComponent(name)}/read`)),
  markAllRead: () => mutate(request.post('notifications/read-all')),
}
