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
  /** Declare that a mounted component will draw bars for these symbols.
   *  Returns an unsubscribe. See `useIntradaySubscription`. */
  subscribeIntraday: (symbols: string[]) => () => void
}

const defaultStore = new QuoteStore()
const QuoteStreamContext = createContext<QuoteStreamState>({
  store: defaultStore,
  intraday: {},
  status: "connecting",
  subscribeIntraday: () => () => {},
})

/** How long to wait after the demand set changes before reconnecting.
 *  Navigation unmounts one live view and mounts another in quick succession;
 *  without this, that lands as two reconnects instead of one. */
const RESUBSCRIBE_DEBOUNCE_MS = 400

export function QuoteStreamProvider({ children }: { children: React.ReactNode }) {
  const [storeRef] = useState(() => new QuoteStore())
  const [intraday, setIntraday] = useState<IntradayMap>({})
  const [status, setStatus] = useState<ConnectionStatus>("connecting")
  const esRef = useRef<EventSource | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const backoffMs = useRef(1_000)
  const mountedRef = useRef(true)

  // Who currently wants bars, and for what. Keyed by an identity token per
  // subscriber so two views asking for the same symbol both have to leave
  // before it drops out of the union.
  const demands = useRef(new Map<symbol, string[]>())
  const demandTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  // The `intraday=` query param, and the effect dependency that reopens the
  // stream when it changes. Sorted so an unchanged set can't reorder into a
  // different string and trigger a pointless reconnect.
  const [intradayParam, setIntradayParam] = useState("")

  const subscribeIntraday = useCallback((symbols: string[]) => {
    const token = Symbol("intraday-demand")
    const recompute = () => {
      if (demandTimer.current) clearTimeout(demandTimer.current)
      demandTimer.current = setTimeout(() => {
        const union = new Set<string>()
        for (const list of demands.current.values()) {
          for (const s of list) union.add(s.toUpperCase())
        }
        setIntradayParam([...union].sort().join(","))
      }, RESUBSCRIBE_DEBOUNCE_MS)
    }
    demands.current.set(token, symbols)
    recompute()
    return () => {
      demands.current.delete(token)
      recompute()
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true

    function connect() {
      if (!mountedRef.current) return
      const url = intradayParam
        ? `/api/quotes/stream?intraday=${encodeURIComponent(intradayParam)}`
        : "/api/quotes/stream"
      const es = new EventSource(url)
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
          if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
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
      mountedRef.current = false
      esRef.current?.close()
      esRef.current = null
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
    // intradayParam: a changed selection reopens the stream, which is how the
    // server learns about it. Quotes survive that — the new connection's first
    // push is a full payload and QuoteStore.merge keeps the previous values,
    // so nothing on screen blanks.
  }, [storeRef, intradayParam])

  return (
    <QuoteStreamContext.Provider value={{ store: storeRef, intraday, status, subscribeIntraday }}>
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

/** Ask the stream for 1-minute bars while this component is mounted.
 *
 * Bars are opt-in: a connection that doesn't ask receives none, because the
 * first frame is large (738 KiB for the full roster, #615) and most views
 * never draw one. Call this from anything that renders an `IntradayChart`,
 * then read the data with `useIntraday()`.
 *
 * Changing the set reopens the SSE connection, so the bars arrive after a
 * round-trip rather than being there already. Debounced, so navigating
 * between two live views costs one reconnect, not two.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useIntradaySubscription(symbols: string[]): void {
  const { subscribeIntraday } = useContext(QuoteStreamContext)
  // The array identity changes every render at most call sites; the joined
  // string is what actually decides whether the demand changed.
  const key = symbols.join(",")
  useEffect(
    () => subscribeIntraday(key ? key.split(",") : []),
    [subscribeIntraday, key],
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useQuoteStatus(): ConnectionStatus {
  return useContext(QuoteStreamContext).status
}
