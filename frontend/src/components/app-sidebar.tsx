import { Link, useLocation } from "react-router-dom"
import { LayoutDashboard, LineChart, Settings } from "lucide-react"
import { useQuoteStatus } from "@/lib/quote-stream"
import { GroupsSection } from "@/components/groups-section"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"

const topNavItems = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/pseudo-etfs", label: "Pseudo-ETFs", icon: LineChart },
]

const STATUS_CONFIG = {
  connecting: { color: "bg-yellow-500", label: "Connecting..." },
  connected: { color: "bg-green-500", label: "Live" },
  reconnecting: { color: "bg-yellow-500 animate-pulse", label: "Reconnecting..." },
  disconnected: { color: "bg-red-500", label: "Disconnected" },
} as const

export function AppSidebar() {
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
