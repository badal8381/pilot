import { request, unwrap } from '@/api/client'

export const auditApi = {
  list: (params) => unwrap(request.get('audit-events', { searchParams: params }).json()),
}
