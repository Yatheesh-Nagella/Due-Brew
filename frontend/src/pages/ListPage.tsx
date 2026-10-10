import { useState } from 'react'
import { Link } from 'react-router-dom'
import { addToList, getGroceryList, getUpcoming, markBought, type GroupBy, type Item } from '../api'
import QuickAdd from '../components/QuickAdd'
import { useToast } from '../components/Toast'
import { amount, byline } from '../format'
import { useLoad } from '../useLoad'

function storedGroupBy(): GroupBy {
  try {
    return localStorage.getItem('groupBy') === 'store' ? 'store' : 'category'
  } catch {
    return 'category'
  }
}

export default function ListPage() {
  const [groupBy, setGroupBy] = useState<GroupBy>(storedGroupBy)
  const { data, error, reload } = useLoad(() => getGroceryList(groupBy), [groupBy])
  // "Bills this week": unpaid ones due in the next 7 days, plus any overdue.
  const week = useLoad(() => getUpcoming(7), [])
  const [pending, setPending] = useState<Set<string>>(new Set())
  const toast = useToast()

  function chooseGroupBy(value: GroupBy) {
    setGroupBy(value)
    try {
      localStorage.setItem('groupBy', value)
    } catch {
      // storage blocked: the choice still applies for this visit
    }
  }

  async function bought(item: Item) {
    setPending((p) => new Set(p).add(item.id))
    try {
      await markBought(item.id)
      toast.show({
        text: `Bought ${item.name}`,
        action: { label: 'Undo', run: () => addToList(item.id).then(reload) },
      })
    } catch (err) {
      toast.show({ text: err instanceof Error ? err.message : String(err) })
    } finally {
      await reload()
      setPending((p) => {
        const next = new Set(p)
        next.delete(item.id)
        return next
      })
    }
  }

  function added(item: Item, created: boolean) {
    reload()
    if (!created) toast.show({ text: `${item.name} was already in the inventory; it's back on the list` })
  }

  const toBuy = data ? data.need_count + data.low_count : null
  const unpaid = week.data?.filter((o) => o.state !== 'paid') ?? null
  const billsDue = unpaid ? unpaid.length : null
  const hasOverdue = unpaid?.some((o) => o.state === 'overdue') ?? false

  return (
    <section>
      <p className="summary-strip">
        <span>
          {toBuy === null ? '…' : toBuy === 0 ? 'Nothing to buy' : `${toBuy} item${toBuy === 1 ? '' : 's'} to buy`}
        </span>
        {billsDue !== null && (
          <>
            {' · '}
            <Link to="/bills" className={hasOverdue ? 'overdue-link' : ''}>
              {billsDue === 0 ? 'no bills this week' : `${billsDue} bill${billsDue === 1 ? '' : 's'} this week`}
              {hasOverdue && ' (overdue!)'}
            </Link>
          </>
        )}
      </p>

      <QuickAdd onAdded={added} />

      <div className="list-toolbar">
        <h1>Grocery list</h1>
        <div className="segmented" role="group" aria-label="Group by">
          {(['category', 'store'] as const).map((value) => (
            <button
              key={value}
              className={groupBy === value ? 'selected' : ''}
              aria-pressed={groupBy === value}
              onClick={() => chooseGroupBy(value)}
            >
              {value === 'category' ? 'Aisle' : 'Store'}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {data && data.groups.length === 0 && (
        <p className="empty">The list is empty. Add something above, or tap "Add to list" in Inventory.</p>
      )}

      {data?.groups.map((group) => (
        <div key={group.key ?? '_none'} className="group">
          <h2>{group.label}</h2>
          <ul className="rows">
            {group.items.map((item) => (
              <li key={item.id} className={`row ${item.status === 'low' ? 'is-low' : ''}`}>
                <div className="row-main">
                  <span className="row-title">
                    {item.name}
                    {item.status === 'low' && <span className="badge">Low</span>}
                  </span>
                  <span className="row-meta">
                    {[amount(item), groupBy === 'category' ? item.store : item.category?.name]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                  <span className="row-by">{byline(item)}</span>
                </div>
                <button
                  className="bought"
                  onClick={() => bought(item)}
                  disabled={pending.has(item.id)}
                  aria-label={`Bought ${item.name}`}
                >
                  ✓ Bought
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {toast.element}
    </section>
  )
}
