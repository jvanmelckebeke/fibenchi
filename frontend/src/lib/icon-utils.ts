import { icons, type LucideIcon } from "lucide-react"

/**
 * Convert PascalCase icon name to kebab-case for storage.
 * e.g. "BarChart3" → "bar-chart-3"
 */
export function toKebab(name: string): string {
  return name
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/([A-Z])([A-Z][a-z])/g, "$1-$2")
    .toLowerCase()
}

/**
 * Convert kebab-case stored name to PascalCase for lookup.
 * e.g. "bar-chart-3" → "BarChart3"
 */
export function toPascal(name: string): string {
  return name.replace(/(^|-)([a-z0-9])/g, (_, _sep, char) => char.toUpperCase())
}

/** Resolve a stored icon name (kebab-case) to a Lucide component. */
export function resolveIcon(name: string | null | undefined): LucideIcon {
  if (!name) return icons.Folder as LucideIcon
  const pascal = toPascal(name)
  return (icons[pascal as keyof typeof icons] as LucideIcon) ?? (icons.Folder as LucideIcon)
}
