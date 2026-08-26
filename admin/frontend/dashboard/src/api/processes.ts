import { request } from '@/api/client'

export const processesApi = {
  list: () => request.get('processes').json(),
  restart: (name) => request.post(`processes/${encodeURIComponent(name)}/actions/restart`).json(),
  restartWorkload: () => request.post('processes/actions/restart').json(),
}
