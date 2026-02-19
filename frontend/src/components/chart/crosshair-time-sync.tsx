import { createContext, useContext, useRef, useCallback, type ReactNode } from "react"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TimeListener = (time: string | null) => void

interface CrosshairTimeSyncContextValue {
  /**
   * Subscribe to shared crosshair time changes. The `identity` object is used
   * to skip the subscriber when it is also the broadcast source, preventing
   * feedback loops. Returns an unsubscribe function.
   */
  subscribe: (listener: TimeListener, identity: object) => () => void
  /**
   * Broadcast a crosshair time to all subscribers except those registered
   * with the same `sourceIdentity`.
   */
  broadcast: (time: string | null, sourceIdentity: object) => void
}

const CrosshairTimeSyncContext = createContext<CrosshairTimeSyncContextValue | null>(null)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface CrosshairTimeSyncProviderProps {
  enabled: boolean
  children: ReactNode
}

interface ListenerEntry {
  listener: TimeListener
  identity: object
}

/**
 * Shares crosshair time position across multiple independent ChartSyncProvider
 * instances. When disabled, renders children without the context so each
 * ChartSyncProvider operates independently.
 *
 * Uses a pub/sub pattern (not React state) to avoid re-renders on every
 * crosshair move -- subscribers are called imperatively.
 */
export function CrosshairTimeSyncProvider({ enabled, children }: CrosshairTimeSyncProviderProps) {
  const entriesRef = useRef<ListenerEntry[]>([])

  const subscribe = useCallback((listener: TimeListener, identity: object): (() => void) => {
    const entry: ListenerEntry = { listener, identity }
    entriesRef.current = [...entriesRef.current, entry]
    return () => {
      entriesRef.current = entriesRef.current.filter((e) => e !== entry)
    }
  }, [])

  const broadcast = useCallback((time: string | null, sourceIdentity: object) => {
    for (const entry of entriesRef.current) {
      if (entry.identity !== sourceIdentity) {
        entry.listener(time)
      }
    }
  }, [])

  if (!enabled) return <>{children}</>

  return (
    <CrosshairTimeSyncContext.Provider value={{ subscribe, broadcast }}>
      {children}
    </CrosshairTimeSyncContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Consumer hook
// ---------------------------------------------------------------------------

/**
 * Returns the crosshair time sync context, or null if not within a
 * CrosshairTimeSyncProvider (or if sync is disabled).
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useCrosshairTimeSync(): CrosshairTimeSyncContextValue | null {
  return useContext(CrosshairTimeSyncContext)
}
