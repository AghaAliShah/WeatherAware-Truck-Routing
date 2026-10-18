import { memo } from 'react'
import Tip from '../../components/ui/Tip'
import RiskBadge from '../../components/ui/RiskBadge'
import { conditionsAt, type TimeView } from '../../lib/forecast'
import { fmtDateTime, fmtDuration, fmtMiles, fmtTime } from '../../lib/format'
import { ROUTE_HEX, riskHex, riskLabel, riskVar } from '../../lib/risk'
import type { Route } from '../../lib/types'
import RiskProfile from './RiskProfile'

interface Props {
  route: Route
  selected: boolean
  view: TimeView
  activeIndex: number | null
  pinnedIndex: number | null
  onSelect: (id: string) => void
  onHover: (id: string | null) => void
  onActive: (index: number | null) => void
  onPick: (index: number) => void
}

function RiskStrip({ route, view }: { route: Route; view: TimeView }) {
  const total = route.distance_mi || 1
  return (
    <div className="strip" aria-hidden="true">
      {route.checkpoints.map((c) => (
        <span key={c.index} style={{ width: `${(c.segment_miles / total) * 100}%`, background: riskHex(conditionsAt(c, view).level) }} />
      ))}
    </div>
  )
}

function Metric({ label, value, level, tip }: { label: string; value: string; level?: number; tip: string }) {
  const hit = level !== undefined
  return (
    <Tip text={tip}>
      <span className={`metric${hit ? ' hit' : ''}`} style={hit ? { ['--lvl' as string]: riskVar(level) } : undefined} tabIndex={0}>
        <b className="tabular">{value}</b> {label}
      </span>
    </Tip>
  )
}

function RouteCard({ route, selected, view, activeIndex, pinnedIndex, onSelect, onHover, onActive, onPick }: Props) {
  const m = route.metrics
  const worst = Math.max(...route.checkpoints.map((c) => c.level))
  return (
    <article
      className={`route-card${selected ? ' selected' : ''}${route.recommended ? ' recommended' : ''}`}
      style={{ ['--route' as string]: ROUTE_HEX[route.id] }}
      onMouseEnter={() => onHover(route.id)}
      onMouseLeave={() => onHover(null)}
    >
      <button type="button" className="route-head" onClick={() => onSelect(route.id)} aria-pressed={selected}>
        <span className="route-name">
          <span className="swatch" />
          {route.label}
        </span>
        {route.recommended && <span className="tag good">Recommended</span>}
        {route.fastest && <span className="tag">Fastest</span>}
        <span className="route-worst">
          <RiskBadge level={worst} label={`Worst: ${riskLabel(worst)}`} />
        </span>
      </button>
      <p className="route-via">{route.summary}</p>

      <dl className="route-stats">
        <div>
          <dt>Distance</dt>
          <dd className="tabular">{fmtMiles(route.distance_mi)}</dd>
        </div>
        <div>
          <dt>Drive time</dt>
          <dd className="tabular">{fmtDuration(route.duration_s)}</dd>
        </div>
        <div>
          <dt>ETA</dt>
          <dd className="tabular">{fmtDateTime(route.arrival)}</dd>
        </div>
      </dl>

      <RiskStrip route={route} view={view} />

      <div className="metrics">
        <Metric label="No Travel" value={fmtMiles(m.no_travel_miles)} level={m.no_travel_miles ? 4 : undefined} tip="Miles of road forecast to be impassable at your ETA" />
        <Metric label="Severe" value={fmtMiles(m.severe_miles)} level={m.severe_miles ? 3 : undefined} tip="Miles at Severe risk: the first ranking criterion" />
        <Metric label="High" value={fmtMiles(m.high_miles)} level={m.high_miles ? 2 : undefined} tip="Miles at High risk: the second ranking criterion" />
        <Metric label="avg risk" value={m.avg_risk.toFixed(2)} tip="Mile-weighted average, 0 = Low to 4 = No Travel" />
      </div>

      {selected && (
        <div className="route-detail">
          <RiskProfile route={route} view={view} activeIndex={activeIndex} onActive={onActive} onPick={onPick} />
          <details className="cp-table">
            <summary>{route.checkpoints.length} checkpoints</summary>
            <div className="table-wrap" onMouseLeave={() => onActive(null)}>
              <table>
                <thead>
                  <tr>
                    <th>Mile</th>
                    <th>ETA</th>
                    <th>Wind</th>
                    <th>Rain</th>
                    <th>Snow</th>
                    <th>Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {route.checkpoints.map((c) => {
                    const cond = conditionsAt(c, view)
                    return (
                      <tr
                        key={c.index}
                        className={activeIndex === c.index || pinnedIndex === c.index ? 'active' : ''}
                        tabIndex={0}
                        onMouseEnter={() => onActive(c.index)}
                        onClick={() => onPick(c.index)}
                        onKeyDown={(e) => e.key === 'Enter' && onPick(c.index)}
                      >
                        <td className="tabular">{Math.round(c.mile)}</td>
                        <td className="tabular">{fmtTime(c.eta)}</td>
                        <td className="tabular">{cond.wind.toFixed(1)} mph</td>
                        <td className="tabular">{cond.rain.toFixed(2)}</td>
                        <td className="tabular">{cond.snow.toFixed(2)}</td>
                        <td>
                          <RiskBadge level={cond.level} />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      )}
    </article>
  )
}

export default memo(RouteCard)
