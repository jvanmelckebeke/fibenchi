import { Outlet } from "react-router-dom"
import { CommandSearch } from "@/components/command-search"
import { AppSidebar } from "@/components/app-sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"

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
