import { useState, type FormEvent } from 'react'
import {
  getHealth,
  listNotifications,
  sendTestEmail,
  updateMe,
  type Notification,
  type NotifyMode,
  type User,
} from '../api'
import { useLoad } from '../useLoad'

function hourLabel(hour: number): string {
  if (hour === 0) return '12 AM (midnight)'
  if (hour === 12) return '12 PM (noon)'
  return hour < 12 ? `${hour} AM` : `${hour - 12} PM`
}

function formatAge(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)}s ago`
  if (seconds < 5400) return `${Math.round(seconds / 60)} min ago`
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`
  return `${Math.round(seconds / 86400)} days ago`
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

const KIND_LABEL: Record<Notification['kind'], string> = {
  reminder: 'Reminder',
  overdue: 'Overdue',
  digest: 'Digest',
  test: 'Test',
}

function describe(n: Notification): string {
  if (n.subject) return n.subject.replace(/^\[due-brew\] /, '')
  if (n.bill_name) return `${n.bill_name}${n.due_date ? `, due ${n.due_date}` : ''}`
  return KIND_LABEL[n.kind]
}

function PreferencesForm({ user, onSaved }: { user: User; onSaved: (u: User) => void }) {
  const [email, setEmail] = useState(user.email)
  const [mode, setMode] = useState<NotifyMode>(user.notify_mode)
  const [hour, setHour] = useState(user.digest_hour)
  const [enabled, setEnabled] = useState(user.email_enabled)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const dirty =
    email.trim() !== user.email || mode !== user.notify_mode || hour !== user.digest_hour || enabled !== user.email_enabled

  async function save(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      const saved = await updateMe({ email: email.trim(), notify_mode: mode, digest_hour: hour, email_enabled: enabled })
      onSaved(saved)
      setMessage({ ok: true, text: 'Saved' })
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : String(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="settings-form" onSubmit={save}>
      <label>
        Email
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
      </label>

      <fieldset>
        <legend>How</legend>
        <label className="check">
          <input type="radio" name="mode" checked={mode === 'individual'} onChange={() => setMode('individual')} />
          One email per reminder
        </label>
        <label className="check">
          <input type="radio" name="mode" checked={mode === 'digest'} onChange={() => setMode('digest')} />
          One daily digest
        </label>
      </fieldset>

      <label>
        {mode === 'digest' ? 'Send the digest at' : 'Send reminders at'}
        <select value={hour} onChange={(e) => setHour(Number(e.target.value))}>
          {Array.from({ length: 24 }, (_, h) => (
            <option key={h} value={h}>
              {hourLabel(h)}
            </option>
          ))}
        </select>
      </label>

      <label className="check">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        Email me about bills assigned to me
      </label>

      <div className="editor-actions">
        {message && <span className={message.ok ? 'saved' : 'error'}>{message.text}</span>}
        <span className="spacer" />
        <button type="submit" className="primary" disabled={busy || !dirty}>
          Save
        </button>
      </div>
    </form>
  )
}

export default function SettingsPage({ user: initialUser }: { user: User }) {
  const [user, setUser] = useState(initialUser)
  const health = useLoad(getHealth, [])
  const log = useLoad(() => listNotifications(50), [])
  const [testState, setTestState] = useState<{ busy: boolean; ok?: boolean; text?: string }>({ busy: false })

  async function test() {
    setTestState({ busy: true })
    try {
      await sendTestEmail()
      setTestState({ busy: false, ok: true, text: `Sent to ${user.email}. Check your inbox (and spam).` })
    } catch (err) {
      setTestState({ busy: false, ok: false, text: err instanceof Error ? err.message : String(err) })
    }
    await log.reload()
  }

  const age = health.data?.notifier_heartbeat_age_seconds ?? null
  const interval = health.data?.notifier_interval_seconds ?? 300
  // Healthy if it ticked within three intervals (allows for one slow tick).
  const notifierOk = age !== null && age <= interval * 3

  return (
    <section>
      <h1>Settings</h1>

      <div className="card">
        <h2>Your reminders</h2>
        <PreferencesForm user={user} onSaved={setUser} />
      </div>

      <div className="card">
        <h2>Test email</h2>
        <p className="muted">Checks that reminders can reach {user.email}.</p>
        <button onClick={test} disabled={testState.busy}>
          {testState.busy ? 'Sending…' : 'Send test email'}
        </button>
        {testState.text && <p className={testState.ok ? 'saved' : 'error'}>{testState.text}</p>}
      </div>

      <div className="card">
        <h2>System status</h2>
        {health.error && <p className="error">Health check failed: {health.error}</p>}
        {health.data && (
          <dl className="facts">
            <dt>Database</dt>
            <dd>{health.data.db}</dd>
            <dt>Notifier</dt>
            <dd className={notifierOk ? 'status-ok' : 'status-bad'}>
              {age === null
                ? 'has never run'
                : notifierOk
                  ? `running (last check ${formatAge(age)})`
                  : `not running? last check ${formatAge(age)}`}
            </dd>
          </dl>
        )}

        <div className="list-toolbar log-toolbar">
          <h2>Notification log</h2>
          <button className="link-button" onClick={() => log.reload()}>
            Refresh
          </button>
        </div>
        {log.error && <p className="error">{log.error}</p>}
        {log.data && log.data.length === 0 && <p className="muted">No emails yet.</p>}
        <ul className="notification-log">
          {log.data?.map((n) => (
            <li key={n.id} className={`log-row log-${n.status}`}>
              <div className="log-main">
                <span className="log-subject">{describe(n)}</span>
                <span className="log-meta">
                  {KIND_LABEL[n.kind]}
                  {n.kind === 'digest' && n.items > 0 && ` (${n.items} bill${n.items === 1 ? '' : 's'})`} · to{' '}
                  {n.user.display_name} · {formatWhen(n.sent_at ?? n.created_at)}
                  {n.attempts > 1 && ` · ${n.attempts} attempts`}
                </span>
                {n.last_error && <span className="log-error">{n.last_error}</span>}
              </div>
              <span className={`log-status status-${n.status}`}>{n.status}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
