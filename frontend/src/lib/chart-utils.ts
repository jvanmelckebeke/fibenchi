import { useState, useEffect, useMemo } from "react"
import { ColorType } from "lightweight-charts"

export const STACK_COLORS = [
  "#2563eb", "#dc2626", "#16a34a", "#d97706", "#9333ea",
  "#0891b2", "#e11d48", "#65a30d", "#c026d3", "#0d9488",
  "#ea580c", "#4f46e5", "#059669", "#db2777", "#ca8a04",
  "#7c3aed", "#0284c7", "#be123c", "#15803d", "#a21caf",
]

export function getChartTheme() {
  const dark = document.documentElement.classList.contains("dark")
  return {
    bg: dark ? "#18181b" : "#ffffff",
    text: dark ? "#a1a1aa" : "#71717a",
    grid: dark ? "#27272a" : "#f4f4f5",
    border: dark ? "#3f3f46" : "#e4e4e7",
    dark,
  }
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

  return useMemo(
    () => ({
      bg: isDark ? "#18181b" : "#ffffff",
      text: isDark ? "#a1a1aa" : "#71717a",
      grid: isDark ? "#27272a" : "#f4f4f5",
      border: isDark ? "#3f3f46" : "#e4e4e7",
      dark: isDark,
    }),
    [isDark]
  )
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
    layout: {
      background: { type: ColorType.Solid, color: theme.bg },
      textColor: theme.text,
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: theme.grid },
      horzLines: { color: theme.grid },
    },
    rightPriceScale: { borderColor: theme.border },
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
