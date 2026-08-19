// GENERATED FILE — do not edit by hand.
//
// Source of truth is Python. Regenerate with:
//
//     cd backend && python -m scripts.export_shared_constants
//
// CI regenerates this file and fails if it moves, so an edit here without a
// matching change on the Python side cannot merge.

/**
 * Fractional tolerance for corroborating a session identity from prices.
 *
 * Not the primary test — since #626 both sides carry explicit session
 * dates and identity is exact. This is the fallback for a degraded quote
 * with no `session_date`, or a venue with no calendar.
 *
 * Shared because the backend's trailing-bar heal uses the same tolerance
 * to decide a stored bar is unreconciled and needs refetching. A drift
 * here means the heal and the display disagree about which bars are
 * usable, and σ stays blank on symbols the heal reports as repaired.
 *
 * @see backend/app/services/price_sync.py
 */
export const SESSION_MATCH_TOL = 0.005

/**
 * Sessions of history before the EWMA vol baseline is trustworthy.
 *
 * Enforced backend-side in `compute_indicators`, which returns no σ
 * below this. The frontend needs the same number to say *why* the
 * column is blank rather than just leaving a dash.
 *
 * @see backend/app/services/compute/indicators.py
 */
export const VNR_WARMUP_SESSIONS = 60
