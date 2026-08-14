import { request, unwrap } from './client'

export const notificationsApi = {
  list: (params) => unwrap(request.get('notifications', { searchParams: params }).json()),
  markRead: (name) => request.post(`notifications/${encodeURIComponent(name)}/read`),
  markAllRead: () => request.post('notifications/read-all'),
}
