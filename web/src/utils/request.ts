/** axios 封装：自动带 Bearer token，统一解包 {code,message,data}。 */
import axios, { AxiosError } from 'axios'
import { useUserStore } from '@/store/user'
import { dialogError } from '@/utils/naive'

const TOKEN_KEY = 'plains_token'

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}
export function setToken(token: string | null): void {
  if (token) sessionStorage.setItem(TOKEN_KEY, token)
  else sessionStorage.removeItem(TOKEN_KEY)
}

const service = axios.create({
  baseURL: (window._config?.BASE_API || '') + '/api',
  timeout: 60000,
})

service.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export class ApiError extends Error {
  code: number
  status: number
  constructor(message: string, code = 1, status = 400) {
    super(message)
    this.code = code
    this.status = status
  }
}

service.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data
      throw new ApiError(body.message || '请求失败', body.code, response.status)
    }
    return body
  },
  (error: AxiosError) => {
    const body = error.response?.data as { code?: number; message?: string } | undefined
    const status = error.response?.status ?? 0
    if (status === 401) {
      // 登录失效：清 token 回登录页
      setToken(null)
      if (!location.hash.includes('/login')) {
        location.hash = '#/login'
      }
      throw new ApiError(body?.message || '登录已过期，请重新登录', 401, status)
    }
    throw new ApiError(body?.message || `请求失败(${status})`, body?.code ?? status, status)
  },
)

export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

/** 请求并弹出错误提示；silent=true 时仅抛出。 */
export async function request<T>(fn: () => Promise<T>, silent = false): Promise<T> {
  try {
    return await fn()
  } catch (err) {
    if (!silent && err instanceof ApiError && err.code !== 401) {
      dialogError(err.message)
    }
    throw err
  }
}

export function pageParams(page: number, pageSize: number, keyword?: string) {
  return { page, page_size: pageSize, keyword: keyword || undefined }
}

export function authOf(): void {
  const user = useUserStore()
  if (!user.isLogin) location.hash = '#/login'
}

/** 响应拦截器解包 {code,message,data} 后返回 data，因此对外类型即业务数据。 */
interface UnwrappedClient {
  get<T = unknown>(url: string, config?: Record<string, unknown>): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T>
  delete<T = unknown>(url: string, config?: Record<string, unknown>): Promise<T>
}

export default service as unknown as UnwrappedClient
