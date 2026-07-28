import { request } from './client'

export const authApi = {
  bootstrap: () => request.get('bootstrap').json(),
  session: () => request.get('auth/session').json(),
  login: (password) => request.post('auth/session', { json: { password } }).json(),
  loginWithSid: (sid) => request.post('auth/session', { json: { sid } }).json(),
  logout: () => request.delete('auth/session'),
}
