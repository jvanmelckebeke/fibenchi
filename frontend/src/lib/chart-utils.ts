import { useState, useEffect, useMemo } from "react"
import { ColorType } from "lightweight-charts"
import type { Indicator } from "@/lib/api"

export const STACK_COLORS = [
  "#6366f1", // indigo-500
  "#a78bfa", // violet-400
  "#2dd4bf", // teal-400
  "#fbbf24", // amber-400
  "#f87171", // red-400
  "#34d399", // emerald-400
  "#fb923c", // orange-400
  "#818cf8", // indigo-400
  "#94a3b8", // slate-400
  "#c084fc", // purple-400
]

function themeColors(isDark: boolean) {
  return {
    bg: isDark ? "#18181b" : "#ffffff",
    text: isDark ? "#a1a1aa" : "#71717a",
    grid: isDark ? "#27272a" : "#f4f4f5",
    border: isDark ? "#3f3f46" : "#e4e4e7",
    dark: isDark,
  }
}

function getChartTheme() {
  return themeColors(document.documentElement.classList.contains("dark"))
}

export function useChartTheme() {
  const [isDark, setIsDark] = useState(() =>
    document.documentElement.classList.contains("dark")
  )

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains("dark"))
    })
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    })
    return () => observer.disconnect()
  }, [])

  return useMemo(() => themeColors(isDark), [isDark])
}

export type ChartTheme = ReturnType<typeof useChartTheme>

export function chartThemeOptions(theme: ChartTheme) {
  return {
    layout: {
      background: { type: ColorType.Solid as const, color: theme.bg },
      textColor: theme.text,
    },
    grid: {
      vertLines: { color: theme.grid },
      horzLines: { color: theme.grid },
    },
    rightPriceScale: { borderColor: theme.border },
    timeScale: { borderColor: theme.border },
  }
}

export function baseChartOptions(container: HTMLElement, height: number) {
  const theme = getChartTheme()
  return {
    width: container.clientWidth,
    height,
    ...chartThemeOptions(theme),
    layout: {
      ...chartThemeOptions(theme).layout,
      attributionLogo: false,
    },
    timeScale: { borderColor: theme.border, timeVisible: false },
    crosshair: { mode: 0 as const },
    handleScroll: {
      horzTouchDrag: true,
      vertTouchDrag: false,
      mouseWheel: false,
      pressedMouseMove: true,
    },
    handleScale: {
      mouseWheel: true,
      pinch: true,
      axisPressedMouseMove: false as const,
      axisDoubleClickReset: { time: true, price: false },
    },
  }
}

/** Build a Map from date string to numeric indicator values, filtering out nulls/non-numbers. */
export function buildIndicatorTimeMap(indicators: Indicator[]): Map<string, Record<string, number>> {
  const map = new Map<string, Record<string, number>>()
  for (const i of indicators) {
    const vals: Record<string, number> = {}
    for (const [field, value] of Object.entries(i.values)) {
      if (value != null && typeof value === "number") {
        vals[field] = value
      }
    }
    map.set(i.date, vals)
  }
  return map
}
