import type { RiskLevel } from './types'

export const RISK_LABELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel'] as const

/** Mirrors --risk-0..4 in tokens.css (canvas and Leaflet paths cannot read CSS variables). */
export const RISK_HEX = ['#22a35a', '#f2b705', '#f47c14', '#e03a2f', '#8e1f4a'] as const

/** Text colour that stays legible on each risk fill. */
export const RISK_INK = ['#ffffff', '#3a2d00', '#ffffff', '#ffffff', '#ffffff'] as const

export const ROUTE_HEX: Record<string, string> = { a: '#2f5bea', b: '#0e9f8e', c: '#8b5cf6' }

export const riskHex = (level: number): string => RISK_HEX[level] ?? RISK_HEX[0]
export const riskVar = (level: number): string => `var(--risk-${Math.min(4, Math.max(0, level))})`
export const riskLabel = (level: number): string => RISK_LABELS[level as RiskLevel] ?? RISK_LABELS[0]
