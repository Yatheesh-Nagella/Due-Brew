import { useState, type FormEvent } from 'react'
import { createItem, type Item } from '../api'

/** One text box: type a name, get a Need item. A name that already exists is
 *  put back on the list instead (the API's duplicate guard). */
export default function QuickAdd({ onAdded }: { onAdded: (item: Item, created: boolean) => void }) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim() || busy) return
    setBusy(true)
    try {
      const { item, created } = await createItem({ name })
      setName('')
      setError(null)
      onAdded(item, created)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="quick-add" onSubmit={submit}>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Add an item, e.g. oat milk"
        aria-label="Item name"
        enterKeyHint="done"
        autoComplete="off"
        maxLength={100}
      />
      <button type="submit" className="primary" disabled={busy || !name.trim()}>
        Add
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  )
}
