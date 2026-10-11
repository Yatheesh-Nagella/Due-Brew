import { useState } from 'react'
import {
  ApiError,
  createBill,
  deleteBill,
  getUpcoming,
  listBills,
  listUsers,
  updateBill,
  type Bill,
  type User,
} from '../api'
import BillEditor from '../components/BillEditor'
import OccurrenceRow from '../components/OccurrenceRow'
import { money, names, relativeDue, scheduleText, shortDate } from '../format'
import { useLoad } from '../useLoad'

const UPCOMING_DAYS = 30

export default function BillsPage({ me }: { me: User }) {
  const upcoming = useLoad(() => getUpcoming(UPCOMING_DAYS), [])
  const bills = useLoad(listBills, [])
  const users = useLoad(listUsers, [])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  async function reloadAll() {
    await Promise.all([upcoming.reload(), bills.reload()])
  }

  // Deleting a bill with paid history needs a second, explicit confirmation;
  // deactivating is the gentler option the API suggests.
  async function remove(bill: Bill) {
    if (!window.confirm(`Delete ${bill.name}?`)) return
    try {
      await deleteBill(bill.id)
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 409)) throw err
      if (!window.confirm(`${err.message}\n\nDelete it and its payment history anyway?`)) return
      await deleteBill(bill.id, true)
    }
    setEditingId(null)
    await reloadAll()
  }

  const overdue = upcoming.data?.filter((o) => o.state === 'overdue') ?? []
  const soon = upcoming.data?.filter((o) => o.state !== 'overdue') ?? []

  return (
    <section>
      <div className="list-toolbar">
        <h1>Bills</h1>
        <button
          className="primary"
          onClick={() => {
            setAdding(true)
            setEditingId(null)
          }}
        >
          + Add bill
        </button>
      </div>

      {adding && users.data && (
        <div className="card">
          <BillEditor
            users={users.data}
            me={me}
            onCancel={() => setAdding(false)}
            onSave={async (input) => {
              await createBill(input)
              setAdding(false)
              await reloadAll()
            }}
          />
        </div>
      )}

      {upcoming.error && <p className="error">{upcoming.error}</p>}

      {overdue.length > 0 && (
        <div className="group">
          <h2 className="overdue-heading">Overdue</h2>
          <ul className="rows">
            {overdue.map((o) => (
              <OccurrenceRow key={o.id} occurrence={o} onChange={reloadAll} />
            ))}
          </ul>
        </div>
      )}

      <div className="group">
        <h2>Next {UPCOMING_DAYS} days</h2>
        {upcoming.data && soon.length === 0 && <p className="empty">Nothing due in the next {UPCOMING_DAYS} days.</p>}
        <ul className="rows">
          {soon.map((o) => (
            <OccurrenceRow key={o.id} occurrence={o} onChange={reloadAll} />
          ))}
        </ul>
      </div>

      <div className="group">
        <h2>All bills</h2>
        {bills.error && <p className="error">{bills.error}</p>}
        {bills.data && bills.data.length === 0 && (
          <p className="empty">No bills yet. Add rent, utilities, subscriptions…</p>
        )}
        <ul className="rows">
          {bills.data?.map((bill) =>
            editingId === bill.id && users.data ? (
              <li key={bill.id} className="row editing">
                <BillEditor
                  bill={bill}
                  users={users.data}
                  me={me}
                  onCancel={() => setEditingId(null)}
                  onSave={async (input) => {
                    await updateBill(bill.id, input)
                    setEditingId(null)
                    await reloadAll()
                  }}
                  onDelete={() => remove(bill)}
                />
              </li>
            ) : (
              <li key={bill.id} className={`row ${bill.active ? '' : 'inactive'}`}>
                <button className="row-main as-link" onClick={() => setEditingId(bill.id)}>
                  <span className="row-title">
                    {bill.name}
                    {!bill.active && <span className="badge">Inactive</span>}
                  </span>
                  <span className="row-meta">
                    {bill.amount === null ? 'Varies' : money(bill.amount)} · {scheduleText(bill)}
                  </span>
                  <span className="row-by">
                    For {names(bill.assignees)}
                    {bill.next_occurrence &&
                      ` · next ${shortDate(bill.next_occurrence.due_date)} (${relativeDue(bill.next_occurrence.days_until)})`}
                  </span>
                </button>
                <span className="chevron" aria-hidden>
                  ›
                </span>
              </li>
            ),
          )}
        </ul>
      </div>
    </section>
  )
}
