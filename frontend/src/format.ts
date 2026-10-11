import type { Bill, Item } from './api'

/** "2 lb", "12", "lb", or "" — quantity and unit as typed, trailing .0 dropped. */
export function amount(item: Pick<Item, 'quantity' | 'unit'>): string {
  const qty = item.quantity === null ? '' : String(Number(item.quantity))
  return [qty, item.unit ?? ''].filter(Boolean).join(' ')
}

/** "added by Alex", or "added by Alex · updated by Sam" when they differ. */
export function byline(item: Pick<Item, 'added_by_user' | 'updated_by_user'>): string {
  const added = `added by ${item.added_by_user.display_name}`
  return item.updated_by_user.id === item.added_by_user.id
    ? added
    : `${added} · updated by ${item.updated_by_user.display_name}`
}

const USD = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const USD_WHOLE = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

/** "$1,200" or "$87.45"; null means the amount isn't known yet. */
export function money(value: number | null): string {
  if (value === null) return 'amount not set'
  return Number.isInteger(value) ? USD_WHOLE.format(value) : USD.format(value)
}

/** Parse "2026-11-01" as a local calendar date (not UTC midnight). */
export function parseDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function shortDate(iso: string): string {
  return parseDate(iso).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

export function relativeDue(daysUntil: number): string {
  if (daysUntil === 0) return 'today'
  if (daysUntil === 1) return 'tomorrow'
  if (daysUntil > 1) return `in ${daysUntil} days`
  if (daysUntil === -1) return '1 day overdue'
  return `${-daysUntil} days overdue`
}

export const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

const SUFFIX: Record<number, string> = { 1: 'st', 2: 'nd', 3: 'rd' }

export function ordinal(n: number): string {
  const teen = n % 100 >= 11 && n % 100 <= 13
  return `${n}${teen ? 'th' : (SUFFIX[n % 10] ?? 'th')}`
}

/** "Monthly on the 1st", "Every 3 months on the 15th", "Yearly on Mar 3", "Once, Nov 2". */
export function scheduleText(bill: Pick<Bill, 'recurrence' | 'due_day' | 'due_month' | 'start_date'>): string {
  switch (bill.recurrence) {
    case 'monthly':
      return `Monthly on the ${ordinal(bill.due_day)}`
    case 'quarterly':
      return `Every 3 months on the ${ordinal(bill.due_day)}`
    case 'yearly':
      return `Yearly on ${MONTHS[(bill.due_month ?? 1) - 1].slice(0, 3)} ${bill.due_day}`
    case 'once':
      return `Once, ${shortDate(bill.start_date)}`
  }
}

/** "Alice", "Alice & Bob". */
export function names(users: { display_name: string }[]): string {
  return users.map((u) => u.display_name).join(' & ')
}

/** "On due date", "1 day before", "3 days before". */
export function reminderLabel(days: number): string {
  if (days === 0) return 'On due date'
  return `${days} day${days === 1 ? '' : 's'} before`
}
