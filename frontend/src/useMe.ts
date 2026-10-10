import { useEffect, useState } from 'react'
import { ApiError, getMe, type User } from './api'

export type MeState =
  | { status: 'loading' }
  | { status: 'ok'; user: User }
  | { status: 'unknown' } // 401/403: not a recognized housemate
  | { status: 'error'; message: string }

export function useMe(): MeState {
  const [state, setState] = useState<MeState>({ status: 'loading' })

  useEffect(() => {
    getMe()
      .then((user) => setState({ status: 'ok', user }))
      .catch((err: unknown) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          setState({ status: 'unknown' })
        } else {
          setState({ status: 'error', message: err instanceof Error ? err.message : String(err) })
        }
      })
  }, [])

  return state
}
