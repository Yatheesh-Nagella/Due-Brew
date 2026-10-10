import { useState, type FormEvent } from 'react'
import { createCategory, deleteCategory, updateCategory, type Category } from '../api'

/** Add, rename, reorder and delete categories (deleting leaves items uncategorized). */
export default function CategoryManager({
  categories,
  onChange,
}: {
  categories: Category[]
  onChange: () => Promise<void>
}) {
  const [newName, setNewName] = useState('')
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run(action: () => Promise<unknown>) {
    try {
      await action()
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
    await onChange()
  }

  function add(e: FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    run(async () => {
      await createCategory(newName)
      setNewName('')
    })
  }

  function rename(e: FormEvent) {
    e.preventDefault()
    if (!editing) return
    run(async () => {
      await updateCategory(editing.id, { name: editing.name })
      setEditing(null)
    })
  }

  // Swap sort_order with the neighbour; renumber first in case of ties.
  function move(index: number, delta: -1 | 1) {
    const other = index + delta
    if (other < 0 || other >= categories.length) return
    const order = categories.map((c) => c.id)
    ;[order[index], order[other]] = [order[other], order[index]]
    run(() =>
      Promise.all(
        order.flatMap((id, i) =>
          categories.find((c) => c.id === id)?.sort_order === i ? [] : [updateCategory(id, { sort_order: i })],
        ),
      ),
    )
  }

  function remove(category: Category) {
    if (window.confirm(`Delete "${category.name}"? Its items stay, as Uncategorized.`)) {
      run(() => deleteCategory(category.id))
    }
  }

  return (
    <div className="category-manager">
      <ul className="rows">
        {categories.map((c, i) => (
          <li key={c.id} className="row">
            {editing?.id === c.id ? (
              <form className="inline-form" onSubmit={rename}>
                <input
                  value={editing.name}
                  onChange={(e) => setEditing({ id: c.id, name: e.target.value })}
                  aria-label="Category name"
                  autoFocus
                />
                <button type="submit" className="primary">
                  Save
                </button>
                <button type="button" onClick={() => setEditing(null)}>
                  Cancel
                </button>
              </form>
            ) : (
              <>
                <span className="row-main">{c.name}</span>
                <div className="row-actions">
                  <button onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move ${c.name} up`}>
                    ↑
                  </button>
                  <button
                    onClick={() => move(i, 1)}
                    disabled={i === categories.length - 1}
                    aria-label={`Move ${c.name} down`}
                  >
                    ↓
                  </button>
                  <button onClick={() => setEditing({ id: c.id, name: c.name })}>Rename</button>
                  <button className="danger" onClick={() => remove(c)}>
                    Delete
                  </button>
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
      <form className="inline-form" onSubmit={add}>
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="New category"
          aria-label="New category name"
          maxLength={100}
        />
        <button type="submit" disabled={!newName.trim()}>
          Add
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
