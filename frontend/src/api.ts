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

export function listUsers() {
  return request<UserBrief[]>('/users')
}

// --- bills ---

export type Recurrence = 'monthly' | 'quarterly' | 'yearly' | 'once'

export type OccurrenceState = 'paid' | 'overdue' | 'due_today' | 'upcoming'

export interface Occurrence {
  id: string
  bill_id: string
  bill_name: string
  due_date: string // YYYY-MM-DD, a calendar date in the house's time zone
  amount: number | null
  variable: boolean
  paid_at: string | null
  paid_by_user: UserBrief | null
  assignees: UserBrief[]
  days_until: number
  state: OccurrenceState
}

export interface Bill {
  id: string
  name: string
  amount: number | null
  recurrence: Recurrence
  due_day: number
  due_month: number | null
  start_date: string
  end_date: string | null
  active: boolean
  notes: string | null
  assignees: UserBrief[]
  reminder_days: number[]
  next_occurrence: Occurrence | null
  paid_count: number
}

export interface BillInput {
  name: string
  amount: number | null
  recurrence: Recurrence
  due_day: number | null
  due_month: number | null
  start_date: string | null
  end_date: string | null
  active: boolean
  notes: string | null
  assignee_ids: string[]
  reminder_days: number[]
}

export function listBills() {
  return request<Bill[]>('/bills')
}

export function createBill(data: BillInput) {
  return request<Bill>('/bills', { method: 'POST', body: JSON.stringify(data) })
}

export function updateBill(id: string, data: Partial<BillInput>) {
  return request<Bill>(`/bills/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteBill(id: string, confirm = false) {
  return request<null>(`/bills/${id}${confirm ? '?confirm=true' : ''}`, { method: 'DELETE' })
}

export function getUpcoming(days = 30) {
  return request<Occurrence[]>(`/bills/upcoming?days=${days}`)
}

export function markPaid(occurrenceId: string) {
  return request<Occurrence>(`/occurrences/${occurrenceId}/paid`, { method: 'POST' })
}

export function undoPaid(occurrenceId: string) {
  return request<Occurrence>(`/occurrences/${occurrenceId}/paid`, { method: 'DELETE' })
}

export function setOccurrenceAmount(occurrenceId: string, amount: number | null) {
  return request<Occurrence>(`/occurrences/${occurrenceId}`, {
    method: 'PATCH',
    body: JSON.stringify({ amount }),
  })
}
