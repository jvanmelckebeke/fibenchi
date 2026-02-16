import { createContext, useContext, useEffect, useState, useCallback, useRef, type ReactNode } from "react"

export type AssetTypeFilter = "all" | "stock" | "etf"
export type WatchlistSortBy = "name" | "price" | "change_pct" | "rsi" | "macd_hist"
export type SortDir = "asc" | "desc"
export type MacdStyle = "classic" | "divergence"

export interface AppSettings {
  watchlist_show_rsi: boolean
  watchlist_show_macd: boolean
  watchlist_macd_style: MacdStyle
  watchlist_show_sparkline: boolean
  watchlist_type_filter: AssetTypeFilter
  watchlist_sort_by: WatchlistSortBy
  watchlist_sort_dir: SortDir
  detail_show_sma20: boolean
  detail_show_sma50: boolean
  detail_show_bollinger: boolean
  detail_show_rsi_chart: boolean
  detail_show_macd_chart: boolean
  chart_default_period: string
  chart_type: "candle" | "line"
  theme: "dark" | "light" | "system"
  compact_mode: boolean
  decimal_places: number
}

// eslint-disable-next-line react-refresh/only-export-components
export const DEFAULT_SETTINGS: AppSettings = {
  watchlist_show_rsi: true,
  watchlist_show_macd: true,
  watchlist_macd_style: "divergence",
  watchlist_show_sparkline: true,
  watchlist_type_filter: "all",
  watchlist_sort_by: "name",
  watchlist_sort_dir: "asc",
  detail_show_sma20: true,
  detail_show_sma50: true,
  detail_show_bollinger: true,
  detail_show_rsi_chart: true,
  detail_show_macd_chart: true,
  chart_default_period: "1y",
  chart_type: "candle",
  theme: "system",
  compact_mode: false,
  decimal_places: 2,
}

const STORAGE_KEY = "fibenchi-settings"
const OLD_THEME_KEY = "theme"

function loadFromStorage(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) }
    }
  } catch {
    // ignore corrupt storage
  }

  // Migrate old theme key
  const oldTheme = localStorage.getItem(OLD_THEME_KEY)
  if (oldTheme === "dark" || oldTheme === "light") {
    const migrated = { ...DEFAULT_SETTINGS, theme: oldTheme as "dark" | "light" }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated))
    localStorage.removeItem(OLD_THEME_KEY)
    return migrated
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
