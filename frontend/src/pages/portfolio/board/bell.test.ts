import { describe, expect, it } from "vitest"
import { countdown } from "./bell"

const at = (iso: string) => new Date(iso)

describe("countdown", () => {
  const now = at("2026-08-12T09:00:00Z")

  it("prints minutes under the hour", () => {
    expect(countdown(at("2026-08-12T09:14:00Z"), now)).toBe("14m")
  })

  it("prints hours and zero-padded minutes above it", () => {
    expect(countdown(at("2026-08-12T11:12:00Z"), now)).toBe("2h12")
    expect(countdown(at("2026-08-12T11:05:00Z"), now)).toBe("2h05")
  })

  it("drops the minutes remainder cleanly on the hour", () => {
    expect(countdown(at("2026-08-12T12:00:00Z"), now)).toBe("3h00")
  })

  it("returns null once the bell has passed", () => {
    // A schedule that has gone stale must not print a negative countdown.
    expect(countdown(at("2026-08-12T08:30:00Z"), now)).toBeNull()
    expect(countdown(now, now)).toBeNull()
  })
})
