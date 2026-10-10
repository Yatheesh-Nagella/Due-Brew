import { useState, type FormEvent } from 'react'
import { STATUS_LABEL, type Category, type Item, type ItemFields, type ItemStatus } from '../api'

interface Props {
  item?: Item
  categories: Category[]
  onSave: (fields: ItemFields) => Promise<void>
  onCancel: () => void
  onDelete?: () => Promise<void>
}

/** Form for every item field; used both to add an item and to edit one. */
export default function ItemEditor({ item, categories, onSave, onCancel, onDelete }: Props) {
  const [name, setName] = useState(item?.name ?? '')
  const [categoryId, setCategoryId] = useState(item?.category_id ?? '')
  const [quantity, setQuantity] = useState(item?.quantity === null || !item ? '' : String(item.quantity))
  const [unit, setUnit] = useState(item?.unit ?? '')
  const [status, setStatus] = useState<ItemStatus>(item?.status ?? 'have')
  const [store, setStore] = useState(item?.store ?? '')
  const [notes, setNotes] = useState(item?.notes ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    run(() =>
      onSave({
        name,
        category_id: categoryId || null,
        quantity: quantity === '' ? null : Number(quantity),
        unit: unit || null,
        status,
        store: store || null,
        notes: notes || null,
      }),
    )
  }

  function remove() {
    if (onDelete && window.confirm(`Delete ${item?.name}? This removes it from the inventory.`)) {
      run(onDelete)
    }
  }

  return (
    <form className="editor" onSubmit={submit}>
      <label className="span-2">
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} />
      </label>
      <label>
        Category
        <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          <option value="">Uncategorized</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Status
        <select value={status} onChange={(e) => setStatus(e.target.value as ItemStatus)}>
          {(Object.keys(STATUS_LABEL) as ItemStatus[]).map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
      </label>
      <label>
        Quantity
        <input
          type="number"
          inputMode="decimal"
          min="0"
          step="any"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
      </label>
      <label>
        Unit
        <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="lb, ct, bottle…" />
      </label>
      <label className="span-2">
        Store
        <input value={store} onChange={(e) => setStore(e.target.value)} placeholder="Any store" />
      </label>
      <label className="span-2">
        Notes
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
      </label>
      {error && <p className="error span-2">{error}</p>}
      <div className="editor-actions span-2">
        {onDelete && (
          <button type="button" className="danger" onClick={remove} disabled={busy}>
            Delete
          </button>
        )}
        <span className="spacer" />
        <button type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="submit" className="primary" disabled={busy || !name.trim()}>
          {item ? 'Save' : 'Add item'}
        </button>
      </div>
    </form>
  )
}
