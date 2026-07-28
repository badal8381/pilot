import { request, unwrap } from './client'

export const sessionApi = {
  list: () => unwrap(request.get('sessions').json()),
  revoke: (jti) => request.post(`sessions/revoke/${jti}`),
  revokeAll: () => unwrap(request.post('sessions/revoke/all').json()),
}
