import { apiUrl, request } from '@/api/client'

export const tasksApi = {
  list: (status) =>
    request.get('tasks', status && status !== 'all' ? { searchParams: { status } } : {}).json(),
  detail: (taskId) => request.get(`tasks/${taskId}`).json(),
  run: (command, args = {}) => request.post('tasks', { json: { command, ...args } }).json(),
  cancel: (taskId) => request.delete(`tasks/${taskId}`),
  retry: (taskId) => request.post(`tasks/${taskId}/actions/retry`).json(),
  output: async (taskId) => {
    const response = await request.get(`tasks/${taskId}/output/content`)
    return response.ok ? response.text() : ''
  },
  outputUrl: (taskId) => apiUrl(`tasks/${taskId}/output/content`),
  streamUrl: (taskId) => apiUrl(`tasks/${taskId}/events`),
  debugUrl: (taskId, refresh = false) =>
    apiUrl(`tasks/${taskId}/debug${refresh ? '?refresh=1' : ''}`),
}

export const taskWorkerApi = {
  detail: () => request.get('task-worker').json(),
  start: () => request.post('task-worker/actions/start').json(),
  stop: () => request.post('task-worker/actions/stop').json(),
}
