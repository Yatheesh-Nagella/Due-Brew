import { useEffect, useState } from 'react'
import { getHealth, type Health, type User } from '../api'

function formatAge(seconds: number | null): string {
  if (seconds === null) return 'never'
  if (seconds < 90) return `${Math.round(seconds)}s ago`
  if (seconds < 5400) return `${Math.round(seconds / 60)} min ago`
  return `${Math.round(seconds / 3600)} h ago`
}

export default function SettingsPage({ user }: { user: User }) {
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err: Error) => setHealthError(err.message))
  }, [])

  return (
    <section>
      <h1>Settings</h1>

      <div className="card">
        <h2>You</h2>
        <dl className="facts">
          <dt>Name</dt>
          <dd>{user.display_name}</dd>
          <dt>Tailscale login</dt>
          <dd>{user.tailscale_login}</dd>
          <dt>Email</dt>
          <dd>{user.email}</dd>
          <dt>Reminders</dt>
          <dd>
            {user.notify_mode === 'digest' ? 'Daily digest' : 'Individual emails'} at{' '}
            {String(user.digest_hour).padStart(2, '0')}:00
          </dd>
        </dl>
      </div>

      <div className="card">
        <h2>System status</h2>
        {healthError && <p className="muted">Health check failed: {healthError}</p>}
        {health && (
          <dl className="facts">
            <dt>Database</dt>
            <dd>{health.db}</dd>
            <dt>Notifier heartbeat</dt>
            <dd>{formatAge(health.notifier_heartbeat_age_seconds)}</dd>
          </dl>
        )}
      </div>
    </section>
  )
}
