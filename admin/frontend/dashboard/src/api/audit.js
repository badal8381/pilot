import { request, unwrap } from './client'

export const auditApi = {
  list: (params) => unwrap(request.get('audit-events', { searchParams: params }).json()),
}
