export interface Place {
  label: string
  lat: number
  lon: number
}

export type RiskLevel = 0 | 1 | 2 | 3 | 4

export type ForecastSample = [level: RiskLevel, wind: number, rain: number, snow: number]

export interface Checkpoint {
  index: number
  mile: number
  lat: number
  lon: number
  eta: string
  segment_miles: number
  level: RiskLevel
  level_label: string
  wind_mph: number
  rain_in_hr: number
  snow_in_hr: number
  drivers: string[]
  forecast_forced: boolean
  /** Conditions at this location for hours 0-48 after departure: [level, wind mph, rain in/hr, snow in/hr] */
  series: ForecastSample[]
}

export interface RouteMetrics {
  no_travel_miles: number
  severe_miles: number
  high_miles: number
  avg_risk: number
  max_level: string
}

export interface Route {
  id: string
  label: string
  summary: string
  distance_mi: number
  duration_s: number
  arrival: string
  rank: number
  recommended: boolean
  fastest: boolean
  metrics: RouteMetrics
  /** [lat, lon, mile along route] */
  geometry: [number, number, number][]
  checkpoints: Checkpoint[]
}

export interface PlanRequest {
  origin: Place
  destination: Place
  departure: string
  load_lb: number
  interval_mi: 10 | 25 | 50 | null
}

export interface PlanResponse {
  departure: string
  load_lb: number
  interval_mi: number
  recommended_id: string
  recommendation: string
  notes: string[]
  routes: Route[]
}

export interface HeatmapResponse {
  start: string
  cell_deg: number
  points: [number, number][]
  /** hours[h][i] = severity 0-100 of points[i] at start + h hours */
  hours: number[][]
}
