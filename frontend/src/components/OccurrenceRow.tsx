import { useState, type FormEvent } from 'react'
import { markPaid, setOccurrenceAmount, undoPaid, type Occurrence } from '../api'
import { money, names, relativeDue, shortDate } from '../format'

/** One due instance of a bill: when, how much, who, and Mark paid / Undo. */
export default function OccurrenceRow({
  occurrence: occ,
  onChange,
}: {
  occurrence: Occurrence
  onChange: () => Promise<void>
}) {
  const [busy, setBusy] = useState(false)
  const [editingAmount, setEditingAmount] = useState(false)
  const [amount, setAmount] = useState(occ.amount === null ? '' : String(occ.amount))
  const [error, setError] = useState<string | null>(null)

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    try {
      await action()
      setError(null)
      await onChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  function saveAmount(e: FormEvent) {
    e.preventDefault()
    run(async () => {
      await setOccurrenceAmount(occ.id, amount === '' ? null : Number(amount))
      setEditingAmount(false)
    })
  }

  const paid = occ.state === 'paid'

  return (
    <li className={`row occurrence state-${occ.state}`}>
      <div className="row-main">
        <span className="row-title">
          {occ.bill_name}
          {occ.state === 'overdue' && <span className="badge badge-overdue">Overdue</span>}
          {occ.state === 'due_today' && <span className="badge badge-today">Due today</span>}
        </span>
        <span className="row-meta">
          {shortDate(occ.due_date)} · {paid ? 'paid' : relativeDue(occ.days_until)}
        </span>
        {editingAmount ? (
          <form className="inline-form amount-form" onSubmit={saveAmount}>
            <input
              type="number"
              inputMode="decimal"
              min="0"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              aria-label={`Amount for ${occ.bill_name}`}
              autoFocus
            />
            <button type="submit" className="primary" disabled={busy}>
              Save
            </button>
            <button type="button" onClick={() => setEditingAmount(false)}>
              Cancel
            </button>
          </form>
        ) : (
          <span className={`amount ${occ.amount === null ? 'amount-missing' : ''}`}>
            {money(occ.amount)}
            {!paid && (occ.variable || occ.amount === null) && (
              <button className="link-button" onClick={() => setEditingAmount(true)}>
                {occ.amount === null ? 'Set amount' : 'Change'}
              </button>
            )}
          </span>
        )}
        <span className="row-by">
          {paid && occ.paid_by_user ? `Paid by ${occ.paid_by_user.display_name}` : `For ${names(occ.assignees)}`}
        </span>
        {error && <span className="error">{error}</span>}
      </div>
      {paid ? (
        <button className="link-button" onClick={() => run(() => undoPaid(occ.id))} disabled={busy}>
          Undo
        </button>
      ) : (
        <button className="bought" onClick={() => run(() => markPaid(occ.id))} disabled={busy}>
          ✓ Paid
        </button>
      )}
    </li>
  )
}
