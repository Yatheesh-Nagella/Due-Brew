import type { Item } from './api'

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
