import { RISK_INK, riskHex, riskLabel } from '../../lib/risk'

export default function RiskBadge({ level, label }: { level: number; label?: string }) {
  return (
    <span className="risk-badge" style={{ background: riskHex(level), color: RISK_INK[level] }}>
      {label ?? riskLabel(level)}
    </span>
  )
}
