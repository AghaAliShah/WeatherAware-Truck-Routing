import { conditionsAt, MAX_HOUR, type TimeView } from '../../lib/forecast'
import { fmtDateTime } from '../../lib/format'
import { ROUTE_HEX, riskHex, riskLabel } from '../../lib/risk'
import RiskBadge from '../../components/ui/RiskBadge'
import type { Checkpoint, Route } from '../../lib/types'
import './forecast.css'

interface Props {
  route: Route
  checkpoint: Checkpoint
  departure: string
  view: TimeView
  onClose: () => void
}

/** Detailed card for one checkpoint: conditions at ETA vs the slider hour, and its 48 h risk timeline. */
export default function CheckpointDetail({ route, checkpoint: c, departure, view, onClose }: Props) {
  const atEta = conditionsAt(c, { mode: 'eta', hour: 0 })
  const atHour = conditionsAt(c, { mode: 'forecast', hour: view.hour })
  const etaHour = (new Date(c.eta).getTime() - new Date(departure).getTime()) / 3_600_000
  const step = 100 / (MAX_HOUR + 1)

  return (
    <aside className="cp-detail" aria-label={`Checkpoint at mile ${Math.round(c.mile)}`} style={{ ['--route' as string]: ROUTE_HEX[route.id] }}>
      <header>
        <div>
          <p className="eyebrow">
            {route.label} · checkpoint {c.index + 1} of {route.checkpoints.length}
          </p>
          <h2 className="tabular">Mile {Math.round(c.mile)}</h2>
        </div>
        <button type="button" className="btn ghost sm" onClick={onClose} aria-label="Close checkpoint details">
          Close
        </button>
      </header>

      <p className="hint tabular">
        {c.lat.toFixed(3)}, {c.lon.toFixed(3)} · covers {Math.round(c.segment_miles)} mi of the route
      </p>

      <table className="cond">
        <thead>
          <tr>
            <th />
            <th scope="col">At ETA {fmtDateTime(c.eta)}</th>
            <th scope="col">At +{view.hour} h</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Risk</th>
            <td>
              <RiskBadge level={atEta.level} />
            </td>
            <td>
              <RiskBadge level={atHour.level} />
            </td>
          </tr>
          <tr>
            <th scope="row">Wind</th>
            <td className="tabular">{atEta.wind.toFixed(1)} mph</td>
            <td className="tabular">{atHour.wind.toFixed(1)} mph</td>
          </tr>
          <tr>
            <th scope="row">Rain</th>
            <td className="tabular">{atEta.rain.toFixed(2)} in/hr</td>
            <td className="tabular">{atHour.rain.toFixed(2)} in/hr</td>
          </tr>
          <tr>
            <th scope="row">Snow</th>
            <td className="tabular">{atEta.snow.toFixed(2)} in/hr</td>
            <td className="tabular">{atHour.snow.toFixed(2)} in/hr</td>
          </tr>
        </tbody>
      </table>

      {c.drivers.length > 0 && (
        <div>
          <p className="field-label">Why {riskLabel(c.level)} at ETA</p>
          <ul className="drivers">
            {c.drivers.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <p className="field-label">Next 48 hours at this location</p>
        <div className="mini-timeline" role="img" aria-label="Risk by hour for the next 48 hours">
          {c.series.map(([level], h) => (
            <span key={h} style={{ background: riskHex(level), height: `${30 + level * 17}%`, width: `${step}%` }} />
          ))}
          <i className="mark mark-eta" style={{ left: `${Math.min(100, (etaHour + 0.5) * step)}%` }} title="Your ETA" />
          <i className="mark mark-now" style={{ left: `${(view.hour + 0.5) * step}%` }} title="Slider hour" />
        </div>
        <div className="mini-legend">
          <span>
            <i className="mark-eta-swatch" /> ETA
          </span>
          <span>
            <i className="mark-now-swatch" /> Slider
          </span>
        </div>
      </div>

      {c.forecast_forced && <p className="hint">ETA is beyond the forecast range; the nearest available hour is used.</p>}
    </aside>
  )
}
