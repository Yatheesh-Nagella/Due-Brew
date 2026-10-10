const BASE = `${import.meta.env.BASE_URL.replace(/\/$/, '')}/api`

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// FastAPI sends `detail` as a string, or as a list of field errors on a 422.
function errorMessage(body: { detail?: unknown }, status: number): string {
  const { detail } = body
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
  return `Request failed: ${status}`
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, errorMessage(body, res.status))
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

// --- categories ---

export interface Category {
  id: string
  name: string
  sort_order: number
}

export function listCategories() {
  return request<Category[]>('/categories')
}

export function createCategory(name: string) {
  return request<Category>('/categories', { method: 'POST', body: JSON.stringify({ name }) })
}

export function updateCategory(id: string, data: Partial<Pick<Category, 'name' | 'sort_order'>>) {
  return request<Category>(`/categories/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteCategory(id: string) {
  return request<null>(`/categories/${id}`, { method: 'DELETE' })
}

// --- items ---

export type ItemStatus = 'needed' | 'low' | 'have'

export const STATUS_LABEL: Record<ItemStatus, string> = { needed: 'Need', low: 'Low', have: 'Have' }

export interface UserBrief {
  id: string
  display_name: string
}

export interface Item {
  id: string
  name: string
  category_id: string | null
  category: Category | null
  quantity: number | null
  unit: string | null
  status: ItemStatus
  store: string | null
  notes: string | null
  added_by_user: UserBrief
  updated_by_user: UserBrief
  created_at: string
  updated_at: string
}

export interface ItemFields {
  name: string
  category_id: string | null
  quantity: number | null
  unit: string | null
  status: ItemStatus
  store: string | null
  notes: string | null
}

export function listItems(filters: { status?: ItemStatus; category_id?: string } = {}) {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.category_id) params.set('category_id', filters.category_id)
  const qs = params.toString()
  return request<Item[]>(`/items${qs ? `?${qs}` : ''}`)
}

/** Creates an item; `created` is false when an existing item of the same name
 *  was put back on the list instead (the duplicate guard). */
export async function createItem(data: Partial<ItemFields> & { name: string }) {
  const res = await fetch(`${BASE}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, errorMessage(body, res.status))
  }
  return { item: (await res.json()) as Item, created: res.status === 201 }
}

export function updateItem(id: string, data: Partial<ItemFields>) {
  return request<Item>(`/items/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteItem(id: string) {
  return request<null>(`/items/${id}`, { method: 'DELETE' })
}

export function markBought(id: string) {
  return request<Item>(`/items/${id}/bought`, { method: 'POST' })
}

export function addToList(id: string) {
  return request<Item>(`/items/${id}/add-to-list`, { method: 'POST' })
}

export type GroupBy = 'category' | 'store'

export interface GroceryGroup {
  key: string | null
  label: string
  items: Item[]
}

export interface GroceryList {
  need_count: number
  low_count: number
  groups: GroceryGroup[]
}

export function getGroceryList(groupBy: GroupBy = 'category') {
  return request<GroceryList>(`/grocery-list?group_by=${groupBy}`)
}
