import axios from 'axios'
import useAuthStore from '../store/authStore'

const client = axios.create({ baseURL: '/' })

client.interceptors.request.use(config => {
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  r => r,
  async err => {
    if (err.response?.status === 401) {
      const refresh = useAuthStore.getState().refreshToken
      if (refresh) {
        try {
          const { data } = await axios.post('/api/v1/auth/refresh', {
            refresh_token: refresh,
          })
          useAuthStore.getState().setTokens(data.access_token, data.refresh_token)
          err.config.headers.Authorization = `Bearer ${data.access_token}`
          return client(err.config)
        } catch {
          useAuthStore.getState().logout()
        }
      }
    }
    return Promise.reject(err)
  }
)

export default client
