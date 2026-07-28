import { request, unwrap } from './client'

export const twoFactorApi = {
  status: () => unwrap(request.get('auth/two-factor').json()),
  startEnrollment: (label) =>
    unwrap(request.post('auth/two-factor/enrollment', { json: { label } }).json()),
  confirm: (credentialId, otp) =>
    unwrap(request.post(`auth/two-factor/${credentialId}`, { json: { otp } }).json()),
  removeDevice: (credentialId) => unwrap(request.delete(`auth/two-factor/${credentialId}`).json()),
  regenerateRecoveryCodes: () =>
    unwrap(request.post('auth/two-factor/recovery-codes').json()),
}
