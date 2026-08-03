import client from './client'

export const aiApi = {
  status: () => client.get('/api/v1/ai/status'),

  interpret: (prompt) => client.post('/api/v1/ai/interpret', { prompt }),
}
