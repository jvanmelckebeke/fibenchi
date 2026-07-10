import { describe, it, expect } from "vitest"
import { compactSigFig, formatCompactNumber, formatCompactPrice } from "./format"

describe("compactSigFig", () => {
  it("keeps ~3 significant figures so low-thousands prices stay distinct (NKT.CO case)", () => {
    // The bug: 1,007 and 1,042 both collapsed to "1.0K" under fixed-1-decimal.
    expect(compactSigFig(1007)).toBe("1.01K")
    expect(compactSigFig(1042)).toBe("1.04K")
    expect(compactSigFig(1090)).toBe("1.09K")
    expect(compactSigFig(1122)).toBe("1.12K")
  })

  it("adapts decimals per magnitude band (2 → 1 → 0 integer digits)", () => {
    expect(compactSigFig(1010)).toBe("1.01K") // 1.xxK → 2 decimals
    expect(compactSigFig(72000)).toBe("72.0K") // xx.xK → 1 decimal
    expect(compactSigFig(148500)).toBe("149K") //  xxxK → 0 decimals
  })

  it("retains trailing zeros for uniform width (no .0 stripping)", () => {
    expect(compactSigFig(72000)).toBe("72.0K")
    expect(compactSigFig(1400000)).toBe("1.40M")
    expect(compactSigFig(2000000)).toBe("2.00M")
    expect(compactSigFig(1000000000)).toBe("1.00B")
  })

  it("handles negatives", () => {
    expect(compactSigFig(-1007)).toBe("-1.01K")
    expect(compactSigFig(-1400000)).toBe("-1.40M")
  })

  it("crosses K/M/B boundaries and promotes on round-up", () => {
    expect(compactSigFig(1000)).toBe("1.00K")
    expect(compactSigFig(999000)).toBe("999K")
    expect(compactSigFig(1000000)).toBe("1.00M")
    // 999,700 rounds to "1000K" at 0 decimals → promote to the M band.
    expect(compactSigFig(999700)).toBe("1.00M")
    // 999,900,000 → "1000M" at the M band → promote to B.
    expect(compactSigFig(999900000)).toBe("1.00B")
  })
})

describe("formatCompactNumber", () => {
  it("returns full integer precision below 1,000", () => {
    expect(formatCompactNumber(990)).toBe("990")
    expect(formatCompactNumber(500)).toBe("500")
    expect(formatCompactNumber(0)).toBe("0")
  })

  it("abbreviates at/above 1,000 with sig figs", () => {
    expect(formatCompactNumber(1007)).toBe("1.01K")
    expect(formatCompactNumber(72000)).toBe("72.0K")
    expect(formatCompactNumber(1400000)).toBe("1.40M")
    expect(formatCompactNumber(-1042)).toBe("-1.04K")
  })
})

describe("formatCompactPrice", () => {
  it("keeps full currency precision below 1,000", () => {
    expect(formatCompactPrice(990, "USD")).toBe("$990.00")
    expect(formatCompactPrice(990, "KRW")).toBe("₩990") // zero-decimal currency
  })

  it("prefixes the currency symbol on the abbreviated form", () => {
    expect(formatCompactPrice(1007, "USD")).toBe("$1.01K")
    expect(formatCompactPrice(1400000, "USD")).toBe("$1.40M")
    expect(formatCompactPrice(-1007, "USD")).toBe("$-1.01K")
  })

  it("handles currencies without a symbol (NKT.CO / DKK)", () => {
    expect(formatCompactPrice(1122, "DKK")).toBe("DKK 1.12K")
    expect(formatCompactPrice(72000, "DKK")).toBe("DKK 72.0K")
  })
})
