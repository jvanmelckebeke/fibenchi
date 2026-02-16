import { Link, Outlet, useLocation } from "react-router-dom"
import { LayoutDashboard, FolderOpen, LineChart, List, Settings } from "lucide-react"
import { useQuoteStatus } from "@/lib/quote-stream"

const navItems = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/watchlist", label: "Watchlist", icon: List },
  { to: "/groups", label: "Groups", icon: FolderOpen },
  { to: "/pseudo-etfs", label: "Pseudo-ETFs", icon: LineChart },
]

const STATUS_CONFIG = {
  connecting: { color: "bg-yellow-500", label: "Connecting…" },
  connected: { color: "bg-green-500", label: "Live" },
  reconnecting: { color: "bg-yellow-500 animate-pulse", label: "Reconnecting…" },
} as const

export function Layout() {
  const location = useLocation()
  const quoteStatus = useQuoteStatus()

  return (
    <div className="flex h-screen bg-background">
      <aside className="flex w-56 flex-col border-r bg-card">
        <div className="flex h-14 items-center border-b px-4">
          <Link to="/" className="text-lg font-bold text-foreground">
            fibenchi
          </Link>
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {navItems.map(({ to, label, icon: Icon }) => {
            const active = to === "/" ? location.pathname === "/" : location.pathname.startsWith(to)
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            )
          })}
        </nav>
        <div className="border-t p-2 space-y-1">
          <Link
            to="/settings"
            className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              location.pathname === "/settings"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            <Settings className="h-4 w-4" />
            Settings
          </Link>
          <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-muted-foreground">
            <span className={`h-2 w-2 rounded-full ${STATUS_CONFIG[quoteStatus].color}`} />
            {STATUS_CONFIG[quoteStatus].label}
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
