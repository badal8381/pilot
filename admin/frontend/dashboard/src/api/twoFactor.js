import { request, unwrap } from './client'

// The device name is the key, so it has to be encoded for the URL path.
const path = (name) => `auth/two-factor/${encodeURIComponent(name)}`

export const twoFactorApi = {
  status: () => unwrap(request.get('auth/two-factor').json()),
  startEnrollment: (name) =>
    unwrap(request.post('auth/two-factor/enrollment', { json: { name } }).json()),
  confirm: (name, otp) => unwrap(request.post(path(name), { json: { otp } }).json()),
  removeDevice: (name) => unwrap(request.delete(path(name)).json()),
  regenerateRecoveryCodes: () => unwrap(request.post('auth/two-factor/recovery-codes').json()),
}
