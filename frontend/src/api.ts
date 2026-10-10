const BASE = `${import.meta.env.BASE_URL.replace(/\/$/, '')}/api`

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail || `Request failed: ${res.status}`)
  }
  if (res.status === 204) return null as T
  return res.json()
}

export type NotifyMode = 'individual' | 'digest'

export interface User {
  id: string
  tailscale_login: string
  display_name: string
  email: string
  notify_mode: NotifyMode
  digest_hour: number
  email_enabled: boolean
}

export interface Health {
  status: string
  db: string
  notifier_heartbeat_age_seconds: number | null
}

export function getMe() {
  return request<User>('/me')
}

export function getHealth() {
  return request<Health>('/health')
}
