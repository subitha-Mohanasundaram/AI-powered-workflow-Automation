import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { authApi } from '../api/auth'

export function useAuth() {
  const { user, token, login, logout: storeLogout } = useAuthStore()
  const navigate = useNavigate()

  const loginMutation = useMutation({
    mutationFn: ({ email, password }) => authApi.login(email, password),
    onSuccess: ({ data }) => {
      login(data.user, data.access_token, data.refresh_token)
      navigate('/dashboard')
    },
  })

  const registerMutation = useMutation({
    mutationFn: ({ email, password, displayName }) =>
      authApi.register(email, password, displayName),
    onSuccess: ({ data }) => {
      login(data.user, data.access_token, data.refresh_token)
      navigate('/dashboard')
    },
  })

  const logoutMutation = useMutation({
    mutationFn: () => authApi.logout().catch(() => {}),
    onSettled: () => {
      storeLogout()
      navigate('/login')
    },
  })

  const { data: meData } = useQuery({
    queryKey: ['me'],
    queryFn: () => authApi.me().then(r => r.data),
    enabled: !!token,
    staleTime: 60_000,
  })

  return {
    user: meData || user,
    isAuthenticated: !!token,
    loginMutation,
    registerMutation,
    logoutMutation,
  }
}
