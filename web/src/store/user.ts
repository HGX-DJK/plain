import { defineStore } from 'pinia'
import service, { getToken, setToken } from '@/utils/request'

export interface UserInfo {
  id: number
  username: string
  real_name: string | null
  dept: string | null
  is_active: boolean
  roles: string[]
  permissions: string[]
}

interface BootstrapInfo {
  app_name: string
  /** 底图瓦片地址在前端 public/js/config.js 配置，后端只提供视图参数 */
  center: [number, number]
  zoom: number
  max_zoom: number
  default_threshold_m: number
}

interface UserState {
  token: string | null
  info: UserInfo | null
  // 系统启动配置（bootstrap）
  bootstrap: BootstrapInfo | null
}

export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    token: getToken(),
    info: null,
    bootstrap: null,
  }),
  getters: {
    isLogin: (s) => !!s.token,
    hasPerm: (s) => (code: string) => {
      if (!s.info) return false
      if (s.info.roles.includes('super_admin')) return true
      return s.info.permissions.includes(code)
    },
  },
  actions: {
    async loadBootstrap() {
      this.bootstrap = await service.get<BootstrapInfo>('/v1/public/bootstrap')
      return this.bootstrap
    },
    async login(username: string, password: string) {
      const data = await service.post<{ access_token: string; user: UserInfo }>('/v1/login', {
        username,
        password,
      })
      this.token = data.access_token
      this.info = data.user
      setToken(this.token)
    },
    async fetchMe() {
      this.info = await service.get<UserInfo>('/v1/me')
    },
    async logout() {
      try {
        await service.post('/v1/logout')
      } catch {
        /* 忽略登出接口异常 */
      }
      this.token = null
      this.info = null
      setToken(null)
      location.hash = '#/login'
    },
  },
})
