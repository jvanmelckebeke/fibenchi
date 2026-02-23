import { useCallback, useMemo, useRef } from "react"
import { useSettings } from "@/lib/settings"

const MIN_WIDTH = 40

export function useColumnResize() {
  const { settings, updateSettings } = useSettings()
  const widths = useMemo(
    () => settings.group_table_column_widths ?? {},
    [settings.group_table_column_widths],
  )
  const draggingRef = useRef(false)

  const getColumnStyle = useCallback(
    (key: string): React.CSSProperties => {
      const w = widths[key]
      return w != null ? { width: w, minWidth: MIN_WIDTH } : { minWidth: MIN_WIDTH }
    },
    [widths],
  )

  const startResize = useCallback(
    (key: string, e: React.PointerEvent) => {
      e.preventDefault()
      e.stopPropagation()

      const th = (e.target as HTMLElement).closest("th")
      if (!th) return

      draggingRef.current = true
      const startX = e.clientX
      const startWidth = th.getBoundingClientRect().width

      document.body.style.cursor = "col-resize"
      document.body.style.userSelect = "none"

      const onMove = (ev: PointerEvent) => {
        const newWidth = Math.max(MIN_WIDTH, startWidth + ev.clientX - startX)
        th.style.width = `${newWidth}px`
      }

      const onUp = (ev: PointerEvent) => {
        document.removeEventListener("pointermove", onMove)
        document.removeEventListener("pointerup", onUp)
        document.body.style.cursor = ""
        document.body.style.userSelect = ""
        draggingRef.current = false

        const finalWidth = Math.max(MIN_WIDTH, startWidth + ev.clientX - startX)
        updateSettings({
          group_table_column_widths: { ...widths, [key]: Math.round(finalWidth) },
        })
      }

      document.addEventListener("pointermove", onMove)
      document.addEventListener("pointerup", onUp)
    },
    [widths, updateSettings],
  )

  const resetWidth = useCallback(
    (key: string, e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()

      const { [key]: _, ...rest } = widths
      void _
      updateSettings({ group_table_column_widths: rest })

      const th = (e.target as HTMLElement).closest("th")
      if (th) th.style.width = ""
    },
    [widths, updateSettings],
  )

  return { getColumnStyle, startResize, resetWidth }
}
