/**
 * Minimal A/B testing client.
 *
 * - A random visitor id (no personal data) lives in localStorage.
 * - Variants are assigned by hashing visitor id + experiment name, so a visitor always sees the same
 *   variant and no server round trip is needed to assign.
 * - Events go to /api/events with sendBeacon so they survive page unloads.
 * - Do Not Track disables event sending (assignment still works, so the UI stays consistent).
 * - `?exp_<name>=<variant>` forces a variant for QA and is not tracked.
 */

export const EXPERIMENTS = {
  /** Does showing the ranking criteria table by default change engagement with routes? */
  why_default: ['control', 'open'],
} as const

export type ExperimentName = keyof typeof EXPERIMENTS
export type EventName = 'exposure' | 'plan_submitted' | 'route_selected' | 'checkpoint_opened' | 'why_toggled' | 'slider_used'

const VISITOR_KEY = 'vid'

function visitorId(): string {
  try {
    const existing = localStorage.getItem(VISITOR_KEY)
    if (existing && /^[A-Za-z0-9_-]{8,64}$/.test(existing)) return existing
    const fresh = crypto.randomUUID()
    localStorage.setItem(VISITOR_KEY, fresh)
    return fresh
  } catch {
    return `anon-${Math.random().toString(36).slice(2, 12)}` // storage blocked: assignment lasts one page view
  }
}

/** FNV-1a 32-bit: small, fast, and well distributed for short strings. */
export function hash32(input: string): number {
  let h = 0x811c9dc5
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

export function variantFor(experiment: ExperimentName, visitor: string): string {
  const options = EXPERIMENTS[experiment]
  return options[hash32(`${experiment}:${visitor}`) % options.length]
}

export interface Assignment {
  experiment: ExperimentName
  variant: string
  /** True when forced through the query string; such traffic is never tracked. */
  forced: boolean
}

export function assign(experiment: ExperimentName): Assignment {
  const forced = new URLSearchParams(window.location.search).get(`exp_${experiment}`)
  if (forced && (EXPERIMENTS[experiment] as readonly string[]).includes(forced)) {
    return { experiment, variant: forced, forced: true }
  }
  return { experiment, variant: variantFor(experiment, visitorId()), forced: false }
}

const trackingAllowed = () => navigator.doNotTrack !== '1'

export function track(a: Assignment, event: EventName): void {
  if (a.forced || !trackingAllowed()) return
  const body = JSON.stringify({ visitor: visitorId(), experiment: a.experiment, variant: a.variant, event })
  try {
    const sent = navigator.sendBeacon?.('/api/events/', new Blob([body], { type: 'application/json' }))
    if (!sent) void fetch('/api/events/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true })
  } catch {
    /* analytics must never affect the app */
  }
}
