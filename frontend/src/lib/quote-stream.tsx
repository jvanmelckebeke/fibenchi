import { createContext, useContext, useEffect, useRef, useState } from "react"
import type { Quote } from "./api"
import type { IntradayPoint } from "./types"

type QuoteMap = Record<string, Quote>
type IntradayMap = Record<string, IntradayPoint[]>
type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected"

interface QuoteStreamState {
  quotes: QuoteMap
  intraday: IntradayMap
  status: ConnectionStatus
}

const QuoteStreamContext = createContext<QuoteStreamState>({
  quotes: {},
  intraday: {},
  status: "connecting",
})

export function QuoteStreamProvider({ children }: { children: React.ReactNode }) {
  const [quotes, setQuotes] = useState<QuoteMap>({})
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
          setQuotes((prev) => ({ ...prev, ...data }))
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
  }, [])

  return (
    <QuoteStreamContext.Provider value={{ quotes, intraday, status }}>
      {children}
    </QuoteStreamContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useQuotes(): QuoteMap {
  return useContext(QuoteStreamContext).quotes
}

// eslint-disable-next-line react-refresh/only-export-components
export function useIntraday(): IntradayMap {
  return useContext(QuoteStreamContext).intraday
}

// eslint-disable-next-line react-refresh/only-export-components
export function useQuoteStatus(): ConnectionStatus {
  return useContext(QuoteStreamContext).status
}
