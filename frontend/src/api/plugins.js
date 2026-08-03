import client from './client'

export const pluginsApi = {
  list: () => client.get('/api/v1/plugins'),

  get: (name) => client.get(`/api/v1/plugins/${name}`),
}
