import { createContext, useContext, useEffect, useState, useCallback, useRef, type ReactNode } from "react"
import { INDICATOR_REGISTRY } from "@/lib/indicator-registry"

export type AssetTypeFilter = "all" | "stock" | "etf"
export type GroupSortBy = string
export type SortDir = "asc" | "desc"
export type MacdStyle = "classic" | "divergence"
export type GroupViewMode = "card" | "table"

export interface AppSettings {
  group_indicator_visibility: Record<string, boolean>
  group_macd_style: MacdStyle
  group_show_sparkline: boolean
  group_view_mode: GroupViewMode
  group_type_filter: AssetTypeFilter
  group_sort_by: GroupSortBy
  group_sort_dir: SortDir
  detail_indicator_visibility: Record<string, boolean>
  chart_default_period: string
  chart_type: "candle" | "line"
  theme: "dark" | "light" | "system"
  compact_mode: boolean
  decimal_places: number
}

function defaultVisibility(): Record<string, boolean> {
  return Object.fromEntries(INDICATOR_REGISTRY.map((d) => [d.id, true]))
}

// eslint-disable-next-line react-refresh/only-export-components
export const DEFAULT_SETTINGS: AppSettings = {
  group_indicator_visibility: defaultVisibility(),
  group_macd_style: "divergence",
  group_show_sparkline: true,
  group_view_mode: "card",
  group_type_filter: "all",
  group_sort_by: "name",
  group_sort_dir: "asc",
  detail_indicator_visibility: defaultVisibility(),
  chart_default_period: "1y",
  chart_type: "candle",
  theme: "system",
  compact_mode: false,
  decimal_places: 2,
}

const STORAGE_KEY = "fibenchi-settings"

function loadFromStorage(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) }
    }
  } catch {
    // ignore corrupt storage
  }
  return { ...DEFAULT_SETTINGS }
}

function saveToStorage(settings: AppSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
}

interface SettingsContextValue {
  settings: AppSettings
  updateSettings: (patch: Partial<AppSettings>) => void
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(loadFromStorage)
  const initializedRef = useRef(false)

  // On mount: fetch from backend and merge (backend wins)
  useEffect(() => {
    if (initializedRef.current) return
    initializedRef.current = true

    fetch("/api/settings")
      .then((res) => (res.ok ? res.json() : null))
      .then((body) => {
        if (body?.data && Object.keys(body.data).length > 0) {
          setSettings((prev) => {
            const merged = { ...prev, ...body.data }
            saveToStorage(merged)
            return merged
          })
        }
      })
      .catch(() => {
        // backend unavailable — use local settings
      })
  }, [])

  // Apply theme
  useEffect(() => {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)")
    const apply = () => {
      const isDark =
        settings.theme === "dark" || (settings.theme === "system" && prefersDark.matches)
      document.documentElement.classList.toggle("dark", isDark)
    }
    apply()

    if (settings.theme === "system") {
      prefersDark.addEventListener("change", apply)
      return () => prefersDark.removeEventListener("change", apply)
    }
  }, [settings.theme])

  const updateSettings = useCallback((patch: Partial<AppSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch }
      saveToStorage(next)
      // Fire-and-forget backend sync
      fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: next }),
      }).catch(() => {})
      return next
    })
  }, [])

  return (
    <SettingsContext.Provider value={{ settings, updateSettings }}>
      {children}
    </SettingsContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider")
  return ctx
}
