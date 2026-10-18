import type { HeatmapResponse, Place, PlanRequest, PlanResponse, Route } from './types'

export class ApiError extends Error {}

/** Flattens `{error}` or DRF's `{field: [messages]}` payloads into one readable line. */
function messageFrom(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const obj = body as Record<string, unknown>
    if (typeof obj.error === 'string') return obj.error
    const parts: string[] = []
    const walk = (value: unknown, path: string) => {
      if (typeof value === 'string') parts.push(path ? `${path}: ${value}` : value)
      else if (Array.isArray(value)) value.forEach((v) => walk(v, path))
      else if (value && typeof value === 'object')
        Object.entries(value).forEach(([k, v]) => walk(v, path ? `${path}.${k}` : k))
    }
    walk(body, '')
    if (parts.length) return parts.join('; ')
  }
  if (status === 429) return 'Too many requests - please wait a moment and try again.'
  return `Request failed (HTTP ${status})`
}

async function request<T>(url: string, init: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err
    throw new ApiError('Cannot reach the server. Check your connection and try again.')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(messageFrom(body, res.status))
  return body as T
}

const post = (body: unknown, signal?: AbortSignal): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
  signal,
})

export const geocode = (q: string, signal?: AbortSignal) =>
  request<{ results: Place[] }>(`/api/geocode/?q=${encodeURIComponent(q)}`, { signal }).then((r) => r.results)

export const planTrip = (req: PlanRequest, signal?: AbortSignal) =>
  request<PlanResponse>('/api/plan/', post(req, signal))

/** Keeps the payload small: the corridor grid does not need full-resolution geometry. */
function thin(geometry: Route['geometry'], max = 400): [number, number][] {
  const step = Math.max(1, Math.ceil(geometry.length / max))
  const out = geometry.filter((_, i) => i % step === 0 || i === geometry.length - 1)
  return out.map(([lat, lon]) => [lat, lon])
}

export const loadHeatmap = (plan: PlanResponse, signal?: AbortSignal) =>
  request<HeatmapResponse>(
    '/api/heatmap/',
    post({ polylines: plan.routes.map((r) => thin(r.geometry)), start: plan.departure, load_lb: plan.load_lb }, signal),
  )
