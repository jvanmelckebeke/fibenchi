import { Routes, Route } from "react-router-dom"
import { Layout } from "@/components/layout"
import { PortfolioPage } from "@/pages/portfolio"
import { GroupDetailPage } from "@/pages/group-detail"
import { AssetDetailPage } from "@/pages/asset-detail"
import { PseudoEtfsPage } from "@/pages/pseudo-etfs"
import { PseudoEtfDetailPage } from "@/pages/pseudo-etf-detail"
import { SettingsPage } from "@/pages/settings"
import { WatchlistRedirect } from "@/pages/watchlist-redirect"

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<PortfolioPage />} />
        <Route path="/watchlist" element={<WatchlistRedirect />} />
        <Route path="/groups/:id" element={<GroupDetailPage />} />
        <Route path="/asset/:symbol" element={<AssetDetailPage />} />
        <Route path="/pseudo-etfs" element={<PseudoEtfsPage />} />
        <Route path="/pseudo-etf/:id" element={<PseudoEtfDetailPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
