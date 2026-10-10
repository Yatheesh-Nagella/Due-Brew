import { useCallback, useEffect, useRef, useState } from 'react'

export interface ToastMessage {
  text: string
  action?: { label: string; run: () => void }
}

/** One message at a time, bottom of the screen above the tab bar, gone after 5s. */
export function useToast() {
  const [toast, setToast] = useState<ToastMessage | null>(null)
  const timer = useRef<number | undefined>(undefined)

  const show = useCallback((message: ToastMessage) => {
    window.clearTimeout(timer.current)
    setToast(message)
    timer.current = window.setTimeout(() => setToast(null), 5000)
  }, [])

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const element = toast && (
    <div className="toast" role="status">
      <span>{toast.text}</span>
      {toast.action && (
        <button
          className="link-button"
          onClick={() => {
            toast.action?.run()
            setToast(null)
          }}
        >
          {toast.action.label}
        </button>
      )}
    </div>
  )

  return { show, element }
}
