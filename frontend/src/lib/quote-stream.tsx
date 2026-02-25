import { createContext, useCallback, useContext, useEffect, useRef, useState, useSyncExternalStore } from "react"
import type { Quote } from "./api"
import type { IntradayPoint } from "./types"

type QuoteMap = Record<string, Quote>
type IntradayMap = Record<string, IntradayPoint[]>
type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected"

// ---------------------------------------------------------------------------
// Per-symbol subscription store (avoids full-map re-renders)
// ---------------------------------------------------------------------------

type Listener = () => void

/** Ref-based store that tracks per-symbol subscribers and only notifies
 *  listeners whose symbol actually changed in the latest SSE tick. */
class QuoteStore {
  private _quotes: QuoteMap = {}
  private _listeners = new Map<string, Set<Listener>>()
  private _globalListeners = new Set<Listener>()

  getQuotes(): QuoteMap {
    return this._quotes
  }

  getQuote(symbol: string): Quote | undefined {
    return this._quotes[symbol]
  }

  /** Merge incoming delta and notify only affected subscribers. */
  merge(delta: QuoteMap) {
    const changedSymbols = Object.keys(delta)
    if (changedSymbols.length === 0) return

    this._quotes = { ...this._quotes, ...delta }

    // Notify per-symbol listeners for changed symbols only
    for (const sym of changedSymbols) {
      const listeners = this._listeners.get(sym)
      if (listeners) {
        for (const cb of listeners) cb()
      }
    }
    // Notify global listeners (useQuotes consumers)
    for (const cb of this._globalListeners) cb()
  }

  subscribeSymbol(symbol: string, listener: Listener): () => void {
    let set = this._listeners.get(symbol)
    if (!set) {
      set = new Set()
      this._listeners.set(symbol, set)
    }
    set.add(listener)
    return () => {
      set!.delete(listener)
      if (set!.size === 0) this._listeners.delete(symbol)
    }
  }

  subscribeAll(listener: Listener): () => void {
    this._globalListeners.add(listener)
    return () => {
      this._globalListeners.delete(listener)
    }
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface QuoteStreamState {
  store: QuoteStore
  intraday: IntradayMap
  status: ConnectionStatus
}

const defaultStore = new QuoteStore()
const QuoteStreamContext = createContext<QuoteStreamState>({
  store: defaultStore,
  intraday: {},
  status: "connecting",
})

export function QuoteStreamProvider({ children }: { children: React.ReactNode }) {
  const [storeRef] = useState(() => new QuoteStore())
  const [intraday, setIntraday] = useState<IntradayMap>({})
  const [status, setStatus] = useState<ConnectionStatus>("connecting")
  const esRef = useRef<EventSource | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const backoffMs = useRef(1_000)

  useEffect(() => {
    function connect() {
      const es = new EventSource("/api/quotes/stream")
      esRef.current = es

      es.addEventListener("quotes", (e) => {
        try {
          const data = JSON.parse(e.data) as QuoteMap
          const count = Object.keys(data).length
          if (count === 0) return
          storeRef.merge(data)
          setStatus("connected")
          backoffMs.current = 1_000 // reset backoff on successful data
        } catch (err) {
          console.error("[QuoteStream] Failed to parse SSE event:", err, "raw:", e.data?.slice(0, 200))
        }
      })

      es.addEventListener("intraday", (e) => {
        try {
          const data = JSON.parse(e.data) as IntradayMap
          setIntraday((prev) => {
            const next = { ...prev }
            for (const [sym, points] of Object.entries(data)) {
              if (!points.length) continue
              const existing = next[sym]
              if (!existing || !existing.length) {
                // First push for this symbol — set full data
                next[sym] = points
              } else if (points[0].time <= existing[0].time) {
                // Full refresh (e.g. reconnect or day boundary) — replace
                next[sym] = points
              } else {
                // Delta — append new points, dedup by timestamp
                const lastTime = existing[existing.length - 1].time
                const newPoints = points.filter((p) => p.time > lastTime)
                if (newPoints.length > 0) {
                  next[sym] = [...existing, ...newPoints]
                }
              }
            }
            return next
          })
        } catch (err) {
          console.error("[QuoteStream] Failed to parse intraday SSE event:", err)
        }
      })

      es.addEventListener("message", (e) => {
        // SSE events without an "event:" field arrive as "message" — log if this happens
        console.warn("[QuoteStream] Received unnamed SSE event (expected 'quotes'):", e.data?.slice(0, 200))
      })

      es.addEventListener("open", () => {
        setStatus("connected")
        backoffMs.current = 1_000 // reset backoff on successful connection
      })

      es.onerror = () => {
        if (es.readyState === EventSource.CONNECTING) {
          // Browser is auto-retrying
          setStatus("reconnecting")
        } else if (es.readyState === EventSource.CLOSED) {
          // Browser gave up — manually reconnect with exponential backoff
          setStatus("disconnected")
          es.close()
          esRef.current = null

          const delay = backoffMs.current
          console.warn(`[QuoteStream] Connection closed. Reconnecting in ${delay}ms...`)
          reconnectTimer.current = setTimeout(() => {
            backoffMs.current = Math.min(backoffMs.current * 2, 30_000)
            setStatus("reconnecting")
            connect()
          }, delay)
        }
      }
    }

    connect()

    return () => {
      esRef.current?.close()
      esRef.current = null
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [storeRef])

  return (
    <QuoteStreamContext.Provider value={{ store: storeRef, intraday, status }}>
      {children}
    </QuoteStreamContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** Return the full quote map. Re-renders on every SSE tick.
 *  Prefer `useQuote(symbol)` when only one symbol is needed. */
// eslint-disable-next-line react-refresh/only-export-components
export function useQuotes(): QuoteMap {
  const { store } = useContext(QuoteStreamContext)
  const subscribe = useCallback((cb: Listener) => store.subscribeAll(cb), [store])
  const getSnapshot = useCallback(() => store.getQuotes(), [store])
  return useSyncExternalStore(subscribe, getSnapshot)
}

/** Return a single symbol's quote. Only re-renders when that symbol changes. */
// eslint-disable-next-line react-refresh/only-export-components
export function useQuote(symbol: string): Quote | undefined {
  const { store } = useContext(QuoteStreamContext)
  const subscribe = useCallback(
    (cb: Listener) => store.subscribeSymbol(symbol, cb),
    [store, symbol],
  )
  const getSnapshot = useCallback(() => store.getQuote(symbol), [store, symbol])
  return useSyncExternalStore(subscribe, getSnapshot)
}

// eslint-disable-next-line react-refresh/only-export-components
export function useIntraday(): IntradayMap {
  return useContext(QuoteStreamContext).intraday
}

// eslint-disable-next-line react-refresh/only-export-components
export function useQuoteStatus(): ConnectionStatus {
  return useContext(QuoteStreamContext).status
}
