import axios from 'axios'

const adminApi = axios.create({
  baseURL: '/api/admin',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor: attach JWT token from localStorage
adminApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: redirect to login on 401
adminApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token')
      window.location.href = '/admin/login'
    }
    return Promise.reject(error)
  }
)

export default adminApi

// --- Typed API functions ---

export const adminLogin = (username: string, password: string) =>
  adminApi.post<{ token: string; expires_at: string }>('/login', { username, password })

export const adminVerify = () =>
  adminApi.get<{ valid: boolean; username: string }>('/verify')

export const fetchOverview = () => adminApi.get('/overview')

export const fetchCrawl = () => adminApi.get('/crawl')

export const fetchMLOps = () => adminApi.get('/mlops')

export const fetchSystem = () => adminApi.get('/system')

export const fetchStats = () => adminApi.get('/stats')

export const fetchLogs = (params?: { level?: string; limit?: number }) =>
  adminApi.get('/logs', { params })

export const fetchSettings = () => adminApi.get('/settings')

export const fetchTraffic = (params?: { period?: string }) =>
  adminApi.get('/traffic', { params })
