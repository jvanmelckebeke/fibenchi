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

export function formatChangePct(v: number | null): { text: string | null; className: string } {
  if (v === null) return { text: null, className: "" }
  const sign = v >= 0 ? "+" : ""
  return {
    text: `${sign}${v.toFixed(2)}%`,
    className: v >= 0 ? "text-emerald-500" : "text-red-500",
  }
}

/**
 * Build a Yahoo Finance advanced chart URL with pre-configured indicators.
 * Config includes: candlestick + volume, Bollinger Bands (20,2), RSI (14), MACD (12,26,9), 1Y daily.
 */
export function buildYahooFinanceUrl(symbol: string): string {
  const config = {
    layout: {
      interval: "day",
      periodicity: 1,
      timeUnit: null,
      candleWidth: 7.77,
      flipped: false,
      volumeUnderlay: true,
      adj: true,
      crosshair: true,
      chartType: "candle",
      extended: true,
      marketSessions: { pre: true, post: true },
      aggregationType: "ohlc",
      chartScale: "linear",
      studies: {
        "\u200cvol undr\u200c": {
          type: "vol undr",
          inputs: { Series: "series", id: "\u200cvol undr\u200c", display: "\u200cvol undr\u200c" },
          outputs: { "Up Volume": "#0dbd6eee", "Down Volume": "#ff5547ee" },
          panel: "chart",
          parameters: { chartName: "chart", editMode: true, panelName: "chart" },
          disabled: false,
        },
        "\u200cBollinger Bands\u200c (20,2,ma,y)": {
          type: "Bollinger Bands",
          inputs: {
            Period: 20, Field: "field", "Standard Deviations": 2,
            "Moving Average Type": "ma", "Channel Fill": true,
            id: "\u200cBollinger Bands\u200c (20,2,ma,y)",
            display: "\u200cBollinger Bands\u200c (20,2,ma,y)",
          },
          outputs: { "Bollinger Bands Top": "auto", "Bollinger Bands Median": "auto", "Bollinger Bands Bottom": "auto" },
          panel: "chart",
          parameters: { chartName: "chart", editMode: true, panelName: "chart" },
          disabled: false,
        },
        "\u200crsi\u200c (14)": {
          type: "rsi",
          inputs: { Period: "14", Field: "field", id: "\u200crsi\u200c (14)", display: "\u200crsi\u200c (14)" },
          outputs: { RSI: "auto" },
          panel: "\u200crsi\u200c (14)",
          parameters: {
            studyOverZonesEnabled: true, studyOverBoughtValue: 80, studyOverBoughtColor: "auto",
            studyOverSoldValue: 20, studyOverSoldColor: "auto",
            chartName: "chart", editMode: true, panelName: "\u200crsi\u200c (14)",
          },
          disabled: false,
        },
        "\u200cmacd\u200c (12,26,9)": {
          type: "macd",
          inputs: {
            "Fast MA Period": 12, "Slow MA Period": 26, "Signal Period": 9,
            id: "\u200cmacd\u200c (12,26,9)", display: "\u200cmacd\u200c (12,26,9)",
          },
          outputs: { MACD: "auto", Signal: "#FF0000", "Increasing Bar": "#00DD00", "Decreasing Bar": "#FF0000" },
          panel: "\u200cmacd\u200c (12,26,9)",
          parameters: { chartName: "chart", editMode: true, panelName: "\u200cmacd\u200c (12,26,9)" },
          disabled: false,
        },
      },
      panels: {
        chart: {
          percent: 0.64, display: symbol, chartName: "chart", index: 0,
          yAxis: { name: "chart", position: null },
          yaxisLHS: [], yaxisRHS: ["chart", "\u200cvol undr\u200c"],
        },
        "\u200crsi\u200c (14)": {
          percent: 0.16, display: "\u200crsi\u200c (14)", chartName: "chart", index: 1,
          yAxis: { name: "\u200crsi\u200c (14)", position: null },
          yaxisLHS: [], yaxisRHS: ["\u200crsi\u200c (14)"],
        },
        "\u200cmacd\u200c (12,26,9)": {
          percent: 0.2, display: "\u200cmacd\u200c (12,26,9)", chartName: "chart", index: 2,
          yAxis: { name: "\u200cmacd\u200c (12,26,9)", position: null },
          yaxisLHS: [], yaxisRHS: ["\u200cmacd\u200c (12,26,9)"],
        },
      },
      setSpan: { multiplier: 1, base: "year", periodicity: { period: 1, timeUnit: "day" }, showEventsQuote: true, forceLoad: true },
      outliers: false,
      animation: true,
      headsUp: { static: true, dynamic: false, floating: false },
      lineWidth: 2,
      fullScreen: true,
      stripedBackground: true,
      color: "#0081f2",
      crosshairSticky: false,
      dontSaveRangeToLayout: true,
      symbols: [{
        symbol,
        symbolObject: { symbol, quoteType: "EQUITY", exchangeTimeZone: "America/New_York" },
        periodicity: 1, interval: "day", timeUnit: null,
        setSpan: { multiplier: 1, base: "year", periodicity: { period: 1, timeUnit: "day" }, showEventsQuote: true, forceLoad: true },
      }],
      renderers: [],
    },
    events: { divs: true, splits: true, tradingHorizon: "none", sigDevEvents: [] },
    drawings: null,
    preferences: {},
  }

  // btoa() only handles Latin1; encode UTF-8 bytes first for the \u200c characters in study keys
  const json = JSON.stringify(config)
  const bytes = new TextEncoder().encode(json)
  let binary = ""
  for (const b of bytes) binary += String.fromCharCode(b)
  const hash = btoa(binary)
  return `https://finance.yahoo.com/chart/${encodeURIComponent(symbol)}#${hash}`
}
