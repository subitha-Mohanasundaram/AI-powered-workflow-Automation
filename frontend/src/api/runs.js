import client from './client'

export const runsApi = {
  list: (params) => client.get('/api/v1/runs', { params }),

  get: (id) => client.get(`/api/v1/runs/${id}`),

  logs: (id) => client.get(`/api/v1/runs/${id}/logs`),

  failureReport: (id) => client.get(`/api/v1/runs/${id}/failure-report`),

  cancel: (id) => client.post(`/api/v1/runs/${id}/cancel`),

  rerun: (id) => client.post(`/api/v1/runs/${id}/rerun`),
}
