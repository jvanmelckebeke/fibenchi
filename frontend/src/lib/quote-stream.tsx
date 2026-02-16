import { createContext, useContext, useEffect, useRef, useState } from "react"
import type { Quote } from "./api"

type QuoteMap = Record<string, Quote>

const QuoteStreamContext = createContext<QuoteMap>({})

export function QuoteStreamProvider({ children }: { children: React.ReactNode }) {
  const [quotes, setQuotes] = useState<QuoteMap>({})
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource("/api/quotes/stream")
    esRef.current = es

    es.addEventListener("quotes", (e) => {
      try {
        const data = JSON.parse(e.data) as QuoteMap
        setQuotes((prev) => ({ ...prev, ...data }))
      } catch {
        // ignore malformed events
      }
    })

    return () => {
      es.close()
      esRef.current = null
    }
  }, [])

  return (
    <QuoteStreamContext.Provider value={quotes}>
      {children}
    </QuoteStreamContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useQuotes(): QuoteMap {
  return useContext(QuoteStreamContext)
}
