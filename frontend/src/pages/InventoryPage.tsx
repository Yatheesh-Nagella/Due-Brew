import { useState } from 'react'
import {
  STATUS_LABEL,
  addToList,
  createItem,
  deleteItem,
  listCategories,
  listItems,
  updateItem,
  type Item,
  type ItemStatus,
} from '../api'
import CategoryManager from '../components/CategoryManager'
import ItemEditor from '../components/ItemEditor'
import { useToast } from '../components/Toast'
import { amount, byline } from '../format'
import { useLoad } from '../useLoad'

const STATUSES: ItemStatus[] = ['needed', 'low', 'have']

export default function InventoryPage() {
  const [status, setStatus] = useState<ItemStatus | ''>('')
  const [categoryId, setCategoryId] = useState('')
  const [search, setSearch] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [showCategories, setShowCategories] = useState(false)
  const toast = useToast()

  const items = useLoad(
    () => listItems({ status: status || undefined, category_id: categoryId || undefined }),
    [status, categoryId],
  )
  const categories = useLoad(listCategories, [])

  async function act(action: () => Promise<unknown>) {
    try {
      await action()
    } catch (err) {
      toast.show({ text: err instanceof Error ? err.message : String(err) })
    }
    await items.reload()
  }

  const query = search.trim().toLowerCase()
  const visible = (items.data ?? []).filter((item) => !query || item.name.toLowerCase().includes(query))

  return (
    <section>
      <div className="list-toolbar">
        <h1>Inventory</h1>
        <button
          className="primary"
          onClick={() => {
            setAdding(true)
            setEditingId(null)
          }}
        >
          + Add item
        </button>
      </div>

      {adding && (
        <div className="card">
          <ItemEditor
            categories={categories.data ?? []}
            onCancel={() => setAdding(false)}
            onSave={async (fields) => {
              const { item, created } = await createItem(fields)
              setAdding(false)
              if (!created) toast.show({ text: `${item.name} already existed; it's been put back on the list` })
              await items.reload()
            }}
          />
        </div>
      )}

      <div className="filters">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search"
          aria-label="Search items"
        />
        <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <div className="segmented" role="group" aria-label="Status filter">
          {(['', ...STATUSES] as const).map((s) => (
            <button
              key={s || 'all'}
              className={status === s ? 'selected' : ''}
              aria-pressed={status === s}
              onClick={() => setStatus(s)}
            >
              {s ? STATUS_LABEL[s] : 'All'}
            </button>
          ))}
        </div>
      </div>

      {items.error && <p className="error">{items.error}</p>}
      {items.data && visible.length === 0 && <p className="empty">No items match.</p>}

      <ul className="rows">
        {visible.map((item: Item) =>
          editingId === item.id ? (
            <li key={item.id} className="row editing">
              <ItemEditor
                item={item}
                categories={categories.data ?? []}
                onCancel={() => setEditingId(null)}
                onSave={async (fields) => {
                  await updateItem(item.id, fields)
                  setEditingId(null)
                  await items.reload()
                }}
                onDelete={async () => {
                  await deleteItem(item.id)
                  setEditingId(null)
                  await items.reload()
                }}
              />
              <p className="row-by">{byline(item)}</p>
            </li>
          ) : (
            <li key={item.id} className="row inventory-row">
              <button className="row-main as-link" onClick={() => setEditingId(item.id)}>
                <span className="row-title">{item.name}</span>
                <span className="row-meta">
                  {[item.category?.name ?? 'Uncategorized', amount(item), item.store].filter(Boolean).join(' · ')}
                </span>
                <span className="row-by">{byline(item)}</span>
              </button>
              <div className="row-actions">
                <div className="segmented status-toggle" role="group" aria-label={`Status of ${item.name}`}>
                  {STATUSES.map((s) => (
                    <button
                      key={s}
                      className={item.status === s ? `selected status-${s}` : ''}
                      aria-pressed={item.status === s}
                      onClick={() => item.status !== s && act(() => updateItem(item.id, { status: s }))}
                    >
                      {STATUS_LABEL[s]}
                    </button>
                  ))}
                </div>
                {item.status === 'have' && (
                  <button className="add-to-list" onClick={() => act(() => addToList(item.id))}>
                    Add to list
                  </button>
                )}
              </div>
            </li>
          ),
        )}
      </ul>

      <div className="card collapsible">
        <button className="collapsible-toggle" onClick={() => setShowCategories((v) => !v)} aria-expanded={showCategories}>
          {showCategories ? '▾' : '▸'} Categories
        </button>
        {showCategories && categories.data && (
          <CategoryManager
            categories={categories.data}
            onChange={async () => {
              await categories.reload()
              await items.reload()
            }}
          />
        )}
      </div>

      {toast.element}
    </section>
  )
}
