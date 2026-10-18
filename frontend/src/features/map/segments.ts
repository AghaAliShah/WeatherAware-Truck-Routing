import { conditionsAt, type TimeView } from '../../lib/forecast'
import { pointAtMile, type LatLng } from '../../lib/geometry'
import type { Route, RiskLevel } from '../../lib/types'

export interface RiskSegment {
  level: RiskLevel
  positions: LatLng[]
}

/**
 * Splits a route polyline into runs of equal risk for the given time view. Each
 * checkpoint owns the stretch of road halfway to its neighbours, the same
 * attribution the server uses for "Severe miles", so what is drawn matches what is scored.
 */
export function riskSegments(route: Route, view: TimeView): RiskSegment[] {
  const cps = route.checkpoints
  const runs: { level: RiskLevel; lo: number; hi: number }[] = []
  cps.forEach((c, i) => {
    const lo = i === 0 ? 0 : (cps[i - 1].mile + c.mile) / 2
    const hi = i === cps.length - 1 ? route.distance_mi : (c.mile + cps[i + 1].mile) / 2
    const level = conditionsAt(c, view).level
    const last = runs[runs.length - 1]
    if (last && last.level === level) last.hi = hi
    else runs.push({ level, lo, hi })
  })

  return runs.map(({ level, lo, hi }) => {
    const positions: LatLng[] = [pointAtMile(route.geometry, lo)]
    for (const [lat, lon, mile] of route.geometry) if (mile > lo && mile < hi) positions.push([lat, lon])
    positions.push(pointAtMile(route.geometry, hi))
    return { level, positions }
  })
}
