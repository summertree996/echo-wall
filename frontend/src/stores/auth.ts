import { defineStore } from 'pinia'
import { api } from '../services/api'
import type { User } from '../types'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('talon_token') as string | null,
    user: JSON.parse(localStorage.getItem('talon_user') || 'null') as User | null,
    loading: false,
  }),
  actions: {
    setSession(data: { access_token: string; user: User }) {
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('talon_token', data.access_token)
      localStorage.setItem('talon_user', JSON.stringify(data.user))
    },
    async refreshSession() {
      if (!this.token) {
        this.clearSession()
        return null
      }
      try {
        const user = await api.me()
        this.user = user
        localStorage.setItem('talon_user', JSON.stringify(user))
        return user
      } catch {
        this.clearSession()
        return null
      }
    },
    async login(email = 'demo@talon.wall', password = 'demo123') {
      this.loading = true
      try {
        const data = await api.login(email, password)
        this.setSession(data)
      } finally {
        this.loading = false
      }
    },
    async register(email: string, password: string, nickname: string) {
      this.loading = true
      try {
        const data = await api.register(email, password, nickname)
        this.setSession(data)
      } finally {
        this.loading = false
      }
    },
    async logout() {
      try {
        if (this.token) await api.logout()
      } finally {
        this.clearSession()
      }
    },
    clearSession() {
      this.token = null
      this.user = null
      localStorage.removeItem('talon_token')
      localStorage.removeItem('talon_user')
    },
  },
})
