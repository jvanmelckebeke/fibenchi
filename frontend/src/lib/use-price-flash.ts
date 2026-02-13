import { useEffect, useRef } from "react"

/**
 * Flashes attached DOM elements green or red when the price changes.
 * Returns refs to attach to the elements that should flash.
 *
 * @example
 * const flashRefs = usePriceFlash(quote?.price ?? null)
 * <span ref={flashRefs[0]} className="rounded px-1 -mx-1">{price}</span>
 * <span ref={flashRefs[1]} className="rounded px-1 -mx-1">{changePct}%</span>
 */
export function usePriceFlash(price: number | null) {
  const prevRef = useRef<number | null>(null)
  const ref1 = useRef<HTMLElement>(null)
  const ref2 = useRef<HTMLElement>(null)

  useEffect(() => {
    if (price == null || prevRef.current == null || price === prevRef.current) {
      prevRef.current = price
      return
    }
    const cls = price > prevRef.current ? "flash-green" : "flash-red"
    for (const el of [ref1.current, ref2.current]) {
      if (!el) continue
      el.classList.remove("flash-green", "flash-red")
      // force reflow so re-adding the same class restarts the animation
      void el.offsetWidth
      el.classList.add(cls)
    }
    prevRef.current = price
  }, [price])

  return [ref1, ref2] as const
}
