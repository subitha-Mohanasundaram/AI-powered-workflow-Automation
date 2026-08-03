import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,

      setTokens: (token, refreshToken) => set({ token, refreshToken }),

      login: (user, token, refreshToken) => set({ user, token, refreshToken }),

      logout: () => {
        set({ user: null, token: null, refreshToken: null })
      },

      setUser: (user) => set({ user }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    }
  )
)

export default useAuthStore
