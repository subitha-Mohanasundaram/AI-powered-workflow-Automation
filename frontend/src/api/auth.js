import client from './client'

export const authApi = {
  login: (email, password) =>
    client.post('/api/v1/auth/login', { email, password }),

  register: (email, password, displayName) =>
    client.post('/api/v1/auth/register', {
      email,
      password,
      display_name: displayName,
    }),

  refresh: (refreshToken) =>
    client.post('/api/v1/auth/refresh', { refresh_token: refreshToken }),

  logout: () => client.post('/api/v1/auth/logout'),

  me: () => client.get('/api/v1/auth/me'),

  updateProfile: (data) => client.put('/api/v1/auth/profile', data),
}
