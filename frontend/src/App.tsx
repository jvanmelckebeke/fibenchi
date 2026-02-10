import { Routes, Route } from "react-router-dom"
import { Layout } from "@/components/layout"
import { PortfolioPage } from "@/pages/portfolio"
import { DashboardPage } from "@/pages/dashboard"
import { AssetDetailPage } from "@/pages/asset-detail"
import { GroupsPage } from "@/pages/groups"
import { PseudoEtfsPage } from "@/pages/pseudo-etfs"
import { PseudoEtfDetailPage } from "@/pages/pseudo-etf-detail"

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<PortfolioPage />} />
        <Route path="/watchlist" element={<DashboardPage />} />
        <Route path="/asset/:symbol" element={<AssetDetailPage />} />
        <Route path="/groups" element={<GroupsPage />} />
        <Route path="/pseudo-etfs" element={<PseudoEtfsPage />} />
        <Route path="/pseudo-etf/:id" element={<PseudoEtfDetailPage />} />
      </Route>
    </Routes>
  )
}
