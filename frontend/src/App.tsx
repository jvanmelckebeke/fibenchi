import { Routes, Route } from "react-router-dom"
import { Layout } from "@/components/layout"
import { DashboardPage } from "@/pages/dashboard"
import { AssetDetailPage } from "@/pages/asset-detail"
import { GroupsPage } from "@/pages/groups"

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="/asset/:symbol" element={<AssetDetailPage />} />
        <Route path="/groups" element={<GroupsPage />} />
      </Route>
    </Routes>
  )
}
