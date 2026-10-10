import { useCallback, useEffect, useState } from 'react'

/** Loads data on mount and whenever `deps` change; `reload` refetches quietly
 *  (keeps showing the current data while it runs). */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(load, deps)

  const reload = useCallback(async () => {
    try {
      setData(await run())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [run])

  useEffect(() => {
    reload()
  }, [reload])

  return { data, error, reload }
}
