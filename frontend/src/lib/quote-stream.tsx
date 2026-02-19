import { createContext, useContext, useEffect, useRef, useState } from "react"
import type { Quote } from "./api"

type QuoteMap = Record<string, Quote>
type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected"

interface QuoteStreamState {
  quotes: QuoteMap
  status: ConnectionStatus
}

const QuoteStreamContext = createContext<QuoteStreamState>({
  quotes: {},
  status: "connecting",
})

export function QuoteStreamProvider({ children }: { children: React.ReactNode }) {
  const [quotes, setQuotes] = useState<QuoteMap>({})
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
    <QuoteStreamContext.Provider value={{ quotes, status }}>
      {children}
    </QuoteStreamContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useQuotes(): QuoteMap {
  return useContext(QuoteStreamContext).quotes
}

// eslint-disable-next-line react-refresh/only-export-components
export function useQuoteStatus(): ConnectionStatus {
  return useContext(QuoteStreamContext).status
}
