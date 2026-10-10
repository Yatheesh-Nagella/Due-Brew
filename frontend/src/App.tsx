import { NavLink, Route, Routes } from 'react-router-dom'
import BillsPage from './pages/BillsPage'
import InventoryPage from './pages/InventoryPage'
import ListPage from './pages/ListPage'
import SettingsPage from './pages/SettingsPage'
import { useMe } from './useMe'
import { useTheme } from './useTheme'

const NAV = [
  { to: '/', label: 'List' },
  { to: '/inventory', label: 'Inventory' },
  { to: '/bills', label: 'Bills' },
  { to: '/settings', label: 'Settings' },
]

export default function App() {
  const [theme, toggleTheme] = useTheme()
  const me = useMe()

  return (
    <div className="app">
      <header>
        <span className="brand">Due and Brew</span>
        <div className="header-right">
          {me.status === 'ok' && <span className="muted">Hi, {me.user.display_name}</span>}
          <button onClick={toggleTheme} aria-label="Toggle dark mode">
            {theme === 'dark' ? 'Light' : 'Dark'}
          </button>
        </div>
      </header>

      <main>
        {me.status === 'loading' && <p className="muted">Loading…</p>}
        {me.status === 'unknown' && (
          <div className="card">
            <h2>Not recognized</h2>
            <p>
              This device's Tailscale login isn't one of the housemates. Ask the owner to add it to
              SEED_USERS.
            </p>
          </div>
        )}
        {me.status === 'error' && (
          <div className="card">
            <h2>Can't reach the server</h2>
            <p className="muted">{me.message}</p>
          </div>
        )}
        {me.status === 'ok' && (
          <Routes>
            <Route path="/" element={<ListPage />} />
            <Route path="/inventory" element={<InventoryPage />} />
            <Route path="/bills" element={<BillsPage />} />
            <Route path="/settings" element={<SettingsPage user={me.user} />} />
          </Routes>
        )}
      </main>

      <nav className="tabbar" aria-label="Primary">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'}>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
