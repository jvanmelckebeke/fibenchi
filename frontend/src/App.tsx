import { lazy, Suspense } from "react"
import { Routes, Route } from "react-router-dom"
import { Layout } from "@/components/layout"
import { WatchlistRedirect } from "@/pages/watchlist-redirect"

const PortfolioPage = lazy(() =>
  import("@/pages/portfolio").then((m) => ({ default: m.PortfolioPage })),
)
const GroupDetailPage = lazy(() =>
  import("@/pages/group-detail").then((m) => ({ default: m.GroupDetailPage })),
)
const AssetDetailPage = lazy(() =>
  import("@/pages/asset-detail").then((m) => ({ default: m.AssetDetailPage })),
)
const PseudoEtfsPage = lazy(() =>
  import("@/pages/pseudo-etfs").then((m) => ({ default: m.PseudoEtfsPage })),
)
const PseudoEtfDetailPage = lazy(() =>
  import("@/pages/pseudo-etf-detail").then((m) => ({
    default: m.PseudoEtfDetailPage,
  })),
)
const SettingsPage = lazy(() =>
  import("@/pages/settings").then((m) => ({ default: m.SettingsPage })),
)

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route
          index
          element={
            <Suspense>
              <PortfolioPage />
            </Suspense>
          }
        />
        <Route path="/watchlist" element={<WatchlistRedirect />} />
        <Route
          path="/groups/:id"
          element={
            <Suspense>
              <GroupDetailPage />
            </Suspense>
          }
        />
        <Route
          path="/asset/:symbol"
          element={
            <Suspense>
              <AssetDetailPage />
            </Suspense>
          }
        />
        <Route
          path="/pseudo-etfs"
          element={
            <Suspense>
              <PseudoEtfsPage />
            </Suspense>
          }
        />
        <Route
          path="/pseudo-etf/:id"
          element={
            <Suspense>
              <PseudoEtfDetailPage />
            </Suspense>
          }
        />
        <Route
          path="/settings"
          element={
            <Suspense>
              <SettingsPage />
            </Suspense>
          }
        />
      </Route>
    </Routes>
  )
}
