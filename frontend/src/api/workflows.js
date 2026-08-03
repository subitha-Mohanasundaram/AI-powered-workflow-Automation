import client from './client'

export const workflowsApi = {
  list: (params) => client.get('/api/v1/workflows', { params }),

  get: (id) => client.get(`/api/v1/workflows/${id}`),

  create: (data) => client.post('/api/v1/workflows', data),

  update: (id, data) => client.put(`/api/v1/workflows/${id}`, data),

  delete: (id) => client.delete(`/api/v1/workflows/${id}`),

  run: (id, params) => client.post(`/api/v1/workflows/${id}/run`, params || {}),

  versions: (id) => client.get(`/api/v1/workflows/${id}/versions`),

  getVersion: (id, version) =>
    client.get(`/api/v1/workflows/${id}/versions/${version}`),

  generate: (prompt) =>
    client.post('/api/v1/workflows/generate', { prompt }),
}
