import { request } from './client'

export const activitiesApi = {
  list: ({ type, site, status, cursor, limit = 50 } = {}) => {
    const searchParams = { limit }
    if (type) searchParams.type = type
    if (site) searchParams.site = site
    if (status) searchParams.status = status
    if (cursor) searchParams.cursor = cursor
    return request.get('audit-events', { searchParams }).json()
  },
}
