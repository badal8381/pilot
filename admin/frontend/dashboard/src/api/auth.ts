import { request } from '@/api/client'

export const authApi = {
  bootstrap: () => request.get('bootstrap').json(),
  session: () => request.get('auth/session').json(),
  login: (password, otp) => request.post('auth/session', { json: { password, otp } }).json(),
  loginWithSid: (sid) => request.post('auth/session', { json: { sid } }).json(),
  logout: () => request.delete('auth/session'),
}
