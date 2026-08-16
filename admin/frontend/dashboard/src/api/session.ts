import { request, unwrap } from '@/api/client'

export const sessionApi = {
  list: () => unwrap(request.get('auth/sessions').json()),
  revoke: (jti) => request.post(`auth/sessions/revoke/${jti}`),
  revokeAll: () => unwrap(request.post('auth/sessions/revoke/all').json()),
}
