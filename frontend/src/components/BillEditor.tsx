import { useState, type FormEvent } from 'react'
import type { Bill, BillInput, Recurrence, UserBrief } from '../api'
import { MONTHS, reminderLabel } from '../format'

const RECURRENCES: { value: Recurrence; label: string }[] = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Every 3 months' },
  { value: 'yearly', label: 'Yearly' },
  { value: 'once', label: 'One-off' },
]

// The spec keeps the reminder UI simple: two defaults plus a few extra choices.
const DEFAULT_REMINDERS = [3, 0]
const EXTRA_REMINDERS = [1, 2, 5, 7]

function todayIso(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

interface Props {
  bill?: Bill
  users: UserBrief[]
  me: UserBrief
  onSave: (input: BillInput) => Promise<void>
  onCancel: () => void
  onDelete?: () => Promise<void>
}

export default function BillEditor({ bill, users, me, onSave, onCancel, onDelete }: Props) {
  const [name, setName] = useState(bill?.name ?? '')
  const [amount, setAmount] = useState(bill?.amount == null ? '' : String(bill.amount))
  const [recurrence, setRecurrence] = useState<Recurrence>(bill?.recurrence ?? 'monthly')
  const [dueDay, setDueDay] = useState(String(bill?.due_day ?? 1))
  const [dueMonth, setDueMonth] = useState(String(bill?.due_month ?? 1))
  const [startDate, setStartDate] = useState(bill?.start_date ?? todayIso())
  const [endDate, setEndDate] = useState(bill?.end_date ?? '')
  const [active, setActive] = useState(bill?.active ?? true)
  const [notes, setNotes] = useState(bill?.notes ?? '')
  const [assignees, setAssignees] = useState<Set<string>>(
    new Set(bill ? bill.assignees.map((u) => u.id) : [me.id]),
  )
  const [reminders, setReminders] = useState<Set<number>>(new Set(bill?.reminder_days ?? DEFAULT_REMINDERS))
  // Every reminder option shown as a checkbox: the defaults, plus any added.
  const [shownReminders, setShownReminders] = useState<number[]>(() =>
    [...new Set([...DEFAULT_REMINDERS, ...(bill?.reminder_days ?? [])])].sort((a, b) => b - a),
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggle<T>(set: Set<T>, value: T): Set<T> {
    const next = new Set(set)
    if (next.has(value)) next.delete(value)
    else next.add(value)
    return next
  }

  function addReminder(days: number) {
    setShownReminders((shown) => [...new Set([...shown, days])].sort((a, b) => b - a))
    setReminders((r) => new Set(r).add(days))
  }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setBusy(false)
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (assignees.size === 0) {
      setError('Assign the bill to at least one person')
      return
    }
    run(() =>
      onSave({
        name,
        amount: amount === '' ? null : Number(amount),
        recurrence,
        due_day: recurrence === 'once' ? null : Number(dueDay),
        due_month: recurrence === 'yearly' ? Number(dueMonth) : null,
        start_date: startDate || null,
        end_date: recurrence === 'once' ? null : endDate || null,
        active,
        notes: notes || null,
        assignee_ids: [...assignees],
        reminder_days: [...reminders].sort((a, b) => b - a),
      }),
    )
  }

  const unusedExtras = EXTRA_REMINDERS.filter((d) => !shownReminders.includes(d))

  return (
    <form className="editor" onSubmit={submit}>
      <label className="span-2">
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} placeholder="Rent" />
      </label>
      <label>
        Amount
        <input
          type="number"
          inputMode="decimal"
          min="0"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Varies"
        />
      </label>
      <label>
        Repeats
        <select value={recurrence} onChange={(e) => setRecurrence(e.target.value as Recurrence)}>
          {RECURRENCES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </label>

      {recurrence === 'once' ? (
        <label className="span-2">
          Due on
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
        </label>
      ) : (
        <>
          {recurrence === 'yearly' && (
            <label>
              Month
              <select value={dueMonth} onChange={(e) => setDueMonth(e.target.value)}>
                {MONTHS.map((m, i) => (
                  <option key={m} value={i + 1}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className={recurrence === 'yearly' ? '' : 'span-2'}>
            Due day
            <select value={dueDay} onChange={(e) => setDueDay(e.target.value)}>
              {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
                <option key={d} value={d}>
                  {d}
                  {d >= 29 ? ' (or last day of month)' : ''}
                </option>
              ))}
            </select>
          </label>
          <label>
            Starts
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
          <label>
            Ends (optional)
            <input type="date" value={endDate} min={startDate} onChange={(e) => setEndDate(e.target.value)} />
          </label>
        </>
      )}
      {recurrence === 'quarterly' && (
        <p className="hint span-2">Repeats every 3 months, counting from the start date's month.</p>
      )}

      <fieldset className="span-2">
        <legend>Assigned to</legend>
        {users.map((u) => (
          <label key={u.id} className="check">
            <input
              type="checkbox"
              checked={assignees.has(u.id)}
              onChange={() => setAssignees((a) => toggle(a, u.id))}
            />
            {u.display_name}
          </label>
        ))}
      </fieldset>

      <fieldset className="span-2">
        <legend>Email reminders</legend>
        {shownReminders.map((d) => (
          <label key={d} className="check">
            <input
              type="checkbox"
              checked={reminders.has(d)}
              onChange={() => setReminders((r) => toggle(r, d))}
            />
            {reminderLabel(d)}
          </label>
        ))}
        {unusedExtras.length > 0 && (
          <select
            value=""
            onChange={(e) => e.target.value && addReminder(Number(e.target.value))}
            aria-label="Add reminder"
            className="add-reminder"
          >
            <option value="">+ Add reminder</option>
            {unusedExtras.map((d) => (
              <option key={d} value={d}>
                {reminderLabel(d)}
              </option>
            ))}
          </select>
        )}
      </fieldset>

      <label className="span-2">
        Notes
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
      </label>

      {bill && (
        <label className="check span-2">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          Active (uncheck to stop tracking it but keep its history)
        </label>
      )}

      {error && <p className="error span-2">{error}</p>}
      <div className="editor-actions span-2">
        {onDelete && (
          <button type="button" className="danger" onClick={() => run(onDelete)} disabled={busy}>
            Delete
          </button>
        )}
        <span className="spacer" />
        <button type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="submit" className="primary" disabled={busy || !name.trim()}>
          {bill ? 'Save' : 'Add bill'}
        </button>
      </div>
    </form>
  )
}
