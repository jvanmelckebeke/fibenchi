const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$",
  EUR: "\u20ac",
  GBP: "\u00a3",
  JPY: "\u00a5",
  CHF: "CHF\u00a0",
}

export function currencySymbol(currency: string): string {
  return CURRENCY_SYMBOLS[currency.toUpperCase()] ?? `${currency}\u00a0`
}

export function formatPrice(value: number, currency: string, decimals = 2): string {
  return `${currencySymbol(currency)}${value.toFixed(decimals)}`
}
