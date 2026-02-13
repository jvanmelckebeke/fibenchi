import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import "./index.css"
import App from "./App.tsx"
import { QuoteStreamProvider } from "./lib/quote-stream.tsx"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <QuoteStreamProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QuoteStreamProvider>
    </QueryClientProvider>
  </StrictMode>
)
