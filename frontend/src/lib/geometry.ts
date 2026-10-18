import type { Route } from './types'

export type LatLng = [number, number]

/** Position along a route polyline ([lat, lon, mile] vertices) at a given mile. */
export function pointAtMile(geometry: Route['geometry'], mile: number): LatLng {
  const last = geometry[geometry.length - 1]
  if (mile <= geometry[0][2]) return [geometry[0][0], geometry[0][1]]
  if (mile >= last[2]) return [last[0], last[1]]
  let lo = 0
  let hi = geometry.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (geometry[mid][2] <= mile) lo = mid
    else hi = mid
  }
  const [la0, lo0, m0] = geometry[lo]
  const [la1, lo1, m1] = geometry[hi]
  const t = m1 === m0 ? 0 : (mile - m0) / (m1 - m0)
  return [la0 + (la1 - la0) * t, lo0 + (lo1 - lo0) * t]
}

/** Compass bearing (degrees) between two points; used to point the truck icon along the road. */
export function bearing(a: LatLng, b: LatLng): number {
  const rad = Math.PI / 180
  const dLon = (b[1] - a[1]) * rad
  const y = Math.sin(dLon) * Math.cos(b[0] * rad)
  const x = Math.cos(a[0] * rad) * Math.sin(b[0] * rad) - Math.sin(a[0] * rad) * Math.cos(b[0] * rad) * Math.cos(dLon)
  return (Math.atan2(y, x) / rad + 360) % 360
}

/** Where is the truck `hours` after departure? Interpolates between checkpoint ETAs. */
export function truckAt(route: Route, departureMs: number, hours: number): { position: LatLng; heading: number; arrived: boolean } {
  const cps = route.checkpoints
  const t = departureMs + hours * 3_600_000
  const times = cps.map((c) => new Date(c.eta).getTime())
  let mile: number
  if (t <= times[0]) mile = cps[0].mile
  else if (t >= times[times.length - 1]) mile = cps[cps.length - 1].mile
  else {
    let i = 1
    while (times[i] < t) i++
    const span = times[i] - times[i - 1]
    const f = span === 0 ? 0 : (t - times[i - 1]) / span
    mile = cps[i - 1].mile + f * (cps[i].mile - cps[i - 1].mile)
  }
  const position = pointAtMile(route.geometry, mile)
  const ahead = pointAtMile(route.geometry, Math.min(route.distance_mi, mile + 2))
  const behind = pointAtMile(route.geometry, Math.max(0, mile - 2))
  return { position, heading: bearing(behind, ahead), arrived: t >= times[times.length - 1] }
}
