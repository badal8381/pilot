import { request } from './client'

export const processesApi = {
  list: () => request.get('runtime/processes').json(),
  control: (name, action) =>
    request.post(`runtime/actions/${action}/process`, { json: { name } }).json(),
}
