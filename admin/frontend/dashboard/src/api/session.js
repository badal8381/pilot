import { request } from './client'

export const sessionApi = {
  revoke: (jti) => request.post('session/revoke', { json: { jti } }),
}
