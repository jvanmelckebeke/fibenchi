import { createContext, useContext, useEffect, useRef, useState } from "react"
import type { Quote } from "./api"

type QuoteMap = Record<string, Quote>
type ConnectionStatus = "connecting" | "connected" | "reconnecting"

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

  useEffect(() => {
    const es = new EventSource("/api/quotes/stream")
    esRef.current = es

    es.addEventListener("quotes", (e) => {
      try {
        const data = JSON.parse(e.data) as QuoteMap
        setQuotes((prev) => ({ ...prev, ...data }))
        setStatus("connected")
      } catch {
        // ignore malformed events
      }
    })

    es.addEventListener("open", () => {
      setStatus("connected")
    })

    es.onerror = () => {
      // EventSource auto-reconnects; readyState CONNECTING means it's retrying
      if (es.readyState === EventSource.CONNECTING) {
        setStatus("reconnecting")
      }
    }

    return () => {
      es.close()
      esRef.current = null
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
