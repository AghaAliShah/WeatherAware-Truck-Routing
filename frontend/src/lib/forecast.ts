import type { Checkpoint, RiskLevel } from './types'

/** 'eta': conditions when the truck actually arrives. 'forecast': a snapshot of the whole corridor at one forecast hour. */
export type ViewMode = 'eta' | 'forecast'

export interface TimeView {
  mode: ViewMode
  /** Hours after departure, 0-48. */
  hour: number
}

export interface Conditions {
  level: RiskLevel
  wind: number
  rain: number
  snow: number
}

export const MAX_HOUR = 48

export function conditionsAt(cp: Checkpoint, view: TimeView): Conditions {
  if (view.mode === 'eta') {
    return { level: cp.level, wind: cp.wind_mph, rain: cp.rain_in_hr, snow: cp.snow_in_hr }
  }
  const [level, wind, rain, snow] = cp.series[Math.min(view.hour, cp.series.length - 1)] ?? [cp.level, cp.wind_mph, cp.rain_in_hr, cp.snow_in_hr]
  return { level, wind, rain, snow }
}
