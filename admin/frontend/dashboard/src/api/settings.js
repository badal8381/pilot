import { request, unwrap } from './client'

export const settingsApi = {
  get: () => unwrap(request.get('settings').json()),
  update: (data) => unwrap(request.patch('settings', { json: data }).json()),
  changeAdminPassword: (data) => unwrap(request.post('auth/password', { json: data }).json()),
  myIp: () => request.get('network/client').json(),
  llmModels: (provider, apiKey = '') =>
    request.post('settings/llm/models', { json: { provider, api_key: apiKey } }).json(),
}

export const cliUpdatesApi = {
  status: () => unwrap(request.get('cli-updates').json()),
  check: () => unwrap(request.post('cli-update-checks').json()),
}
