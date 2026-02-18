import { useState } from "react"
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom"
import { LayoutDashboard, LineChart, Settings, Star, FolderOpen, Plus, X } from "lucide-react"
import { useQuoteStatus } from "@/lib/quote-stream"
import { CommandSearch } from "@/components/command-search"
import { useGroups, useCreateGroup } from "@/lib/queries"
import { Input } from "@/components/ui/input"

const topNavItems = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/pseudo-etfs", label: "Pseudo-ETFs", icon: LineChart },
]

const STATUS_CONFIG = {
  connecting: { color: "bg-yellow-500", label: "Connecting…" },
  connected: { color: "bg-green-500", label: "Live" },
  reconnecting: { color: "bg-yellow-500 animate-pulse", label: "Reconnecting…" },
} as const

function NavLink({ to, label, icon: Icon, active, badge }: {
  to: string
  label: string
  icon: React.ElementType
  active: boolean
  badge?: number
}) {
  return (
    <Link
      to={to}
      className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
        active
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      }`}
    >
      <Icon className="h-4 w-4" />
      <span className="truncate">{label}</span>
      {badge != null && badge > 0 && (
        <span className={`ml-auto text-xs tabular-nums ${
          active ? "text-primary-foreground/70" : "text-muted-foreground"
        }`}>
          {badge}
        </span>
      )}
    </Link>
  )
}

function GroupsSection() {
  const { data: groups } = useGroups()
  const createGroup = useCreateGroup()
  const location = useLocation()
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState("")

  const handleCreate = () => {
    const name = newName.trim()
    if (!name) return
    createGroup.mutate({ name }, {
      onSuccess: (group) => {
        setNewName("")
        setCreating(false)
        navigate(`/groups/${group.id}`)
      },
    })
  }

  if (!groups) return null

  const defaultGroup = groups.find((g) => g.is_default)
  const customGroups = groups.filter((g) => !g.is_default)

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between px-3 pt-3 pb-1">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Groups
        </span>
        <button
          onClick={() => setCreating(!creating)}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          {creating ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
        </button>
      </div>

      {creating && (
        <div className="px-2 pb-1">
          <Input
            placeholder="Group name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleCreate()
              if (e.key === "Escape") { setCreating(false); setNewName("") }
            }}
            autoFocus
            className="h-8 text-sm"
          />
        </div>
      )}

      {/* Default group — always first */}
      {defaultGroup && (
        <NavLink
          to={`/groups/${defaultGroup.id}`}
          label={defaultGroup.name}
          icon={Star}
          active={location.pathname === `/groups/${defaultGroup.id}` || location.pathname === "/watchlist"}
          badge={defaultGroup.assets.length}
        />
      )}

      {/* Custom groups */}
      {customGroups.map((group) => (
        <NavLink
          key={group.id}
          to={`/groups/${group.id}`}
          label={group.name}
          icon={FolderOpen}
          active={location.pathname === `/groups/${group.id}`}
          badge={group.assets.length}
        />
      ))}
    </div>
  )
}

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
        <nav className="flex-1 overflow-auto p-2 space-y-1">
          {topNavItems.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              label={label}
              icon={icon}
              active={to === "/" ? location.pathname === "/" : location.pathname.startsWith(to)}
            />
          ))}
          <GroupsSection />
        </nav>
        <div className="border-t p-2 space-y-1">
          <NavLink
            to="/settings"
            label="Settings"
            icon={Settings}
            active={location.pathname === "/settings"}
          />
          <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-muted-foreground">
            <span className={`h-2 w-2 rounded-full ${STATUS_CONFIG[quoteStatus].color}`} />
            {STATUS_CONFIG[quoteStatus].label}
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="flex h-14 items-center border-b px-6">
          <CommandSearch />
        </div>
        <Outlet />
      </main>
    </div>
  )
}
