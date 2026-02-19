import { useState } from "react"
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom"
import {
  LayoutDashboard,
  LineChart,
  Settings,
  Star,
  FolderOpen,
  Plus,
  X,
} from "lucide-react"
import { useQuoteStatus } from "@/lib/quote-stream"
import { CommandSearch } from "@/components/command-search"
import { useGroups, useCreateGroup } from "@/lib/queries"
import { TooltipProvider } from "@/components/ui/tooltip"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar"
import { Input } from "@/components/ui/input"

const topNavItems = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/pseudo-etfs", label: "Pseudo-ETFs", icon: LineChart },
]

const STATUS_CONFIG = {
  connecting: { color: "bg-yellow-500", label: "Connecting..." },
  connected: { color: "bg-green-500", label: "Live" },
  reconnecting: { color: "bg-yellow-500 animate-pulse", label: "Reconnecting..." },
} as const

function GroupsSection() {
  const { data: groups } = useGroups()
  const createGroup = useCreateGroup()
  const location = useLocation()
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState("")
  const { state } = useSidebar()

  const handleCreate = () => {
    const name = newName.trim()
    if (!name) return
    createGroup.mutate(
      { name },
      {
        onSuccess: (group) => {
          setNewName("")
          setCreating(false)
          navigate(`/groups/${group.id}`)
        },
      },
    )
  }

  if (!groups) return null

  const defaultGroup = groups.find((g) => g.is_default)
  const customGroups = groups.filter((g) => !g.is_default)
  const isCollapsed = state === "collapsed"

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Groups</SidebarGroupLabel>
      {!isCollapsed && (
        <SidebarGroupAction
          onClick={() => setCreating(!creating)}
          title={creating ? "Cancel" : "New group"}
        >
          {creating ? <X /> : <Plus />}
        </SidebarGroupAction>
      )}
      <SidebarGroupContent>
        {creating && !isCollapsed && (
          <div className="px-2 pb-1">
            <Input
              placeholder="Group name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate()
                if (e.key === "Escape") {
                  setCreating(false)
                  setNewName("")
                }
              }}
              autoFocus
              className="h-7 text-xs"
            />
          </div>
        )}
        <SidebarMenu>
          {defaultGroup && (
            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                isActive={
                  location.pathname === `/groups/${defaultGroup.id}` ||
                  location.pathname === "/watchlist"
                }
                tooltip={defaultGroup.name}
              >
                <Link to={`/groups/${defaultGroup.id}`}>
                  <Star />
                  <span>{defaultGroup.name}</span>
                </Link>
              </SidebarMenuButton>
              {defaultGroup.assets.length > 0 && (
                <SidebarMenuBadge>{defaultGroup.assets.length}</SidebarMenuBadge>
              )}
            </SidebarMenuItem>
          )}
          {customGroups.map((group) => (
            <SidebarMenuItem key={group.id}>
              <SidebarMenuButton
                asChild
                isActive={location.pathname === `/groups/${group.id}`}
                tooltip={group.name}
              >
                <Link to={`/groups/${group.id}`}>
                  <FolderOpen />
                  <span>{group.name}</span>
                </Link>
              </SidebarMenuButton>
              {group.assets.length > 0 && (
                <SidebarMenuBadge>{group.assets.length}</SidebarMenuBadge>
              )}
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

function AppSidebar() {
  const location = useLocation()
  const quoteStatus = useQuoteStatus()

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="fibenchi">
              <Link to="/">
                <div className="bg-primary text-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg text-sm font-bold">
                  f
                </div>
                <span className="text-lg font-bold">fibenchi</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {topNavItems.map(({ to, label, icon: Icon }) => (
                <SidebarMenuItem key={to}>
                  <SidebarMenuButton
                    asChild
                    isActive={
                      to === "/"
                        ? location.pathname === "/"
                        : location.pathname.startsWith(to)
                    }
                    tooltip={label}
                  >
                    <Link to={to}>
                      <Icon />
                      <span>{label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <GroupsSection />
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              isActive={location.pathname === "/settings"}
              tooltip="Settings"
            >
              <Link to="/settings">
                <Settings />
                <span>Settings</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton size="sm" className="cursor-default hover:bg-transparent" tooltip={STATUS_CONFIG[quoteStatus].label}>
              <span
                className={`h-2 w-2 shrink-0 rounded-full ${STATUS_CONFIG[quoteStatus].color}`}
              />
              <span className="text-xs text-muted-foreground">
                {STATUS_CONFIG[quoteStatus].label}
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}

export function Layout() {
  return (
    <SidebarProvider>
      <TooltipProvider delayDuration={0}>
        <AppSidebar />
        <SidebarInset>
          <header className="flex h-14 items-center gap-2 border-b px-4">
            <SidebarTrigger className="-ml-1" />
            <div className="flex-1">
              <CommandSearch />
            </div>
          </header>
          <div className="flex-1 overflow-auto">
            <Outlet />
          </div>
        </SidebarInset>
      </TooltipProvider>
    </SidebarProvider>
  )
}
