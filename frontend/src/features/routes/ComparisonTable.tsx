import { fmtDuration } from '../../lib/format'
import { ROUTE_HEX } from '../../lib/risk'
import type { Route } from '../../lib/types'

interface Row {
  key: string
  label: string
  hint: string
  values: number[]
  format: (v: number) => string
  /** Values closer than this are treated as a tie when finding the deciding criterion. */
  tolerance: number
}

function buildRows(routes: Route[]): Row[] {
  const pick = (f: (r: Route) => number) => routes.map(f)
  return [
    { key: 'nt', label: 'No Travel miles', hint: 'Miles forecast to be impassable', values: pick((r) => r.metrics.no_travel_miles), format: (v) => `${Math.round(v)} mi`, tolerance: 0.5 },
    { key: 'sv', label: 'Severe miles', hint: 'Criterion 1', values: pick((r) => r.metrics.severe_miles), format: (v) => `${Math.round(v)} mi`, tolerance: 0.5 },
    { key: 'hi', label: 'High miles', hint: 'Criterion 2', values: pick((r) => r.metrics.high_miles), format: (v) => `${Math.round(v)} mi`, tolerance: 0.5 },
    { key: 'av', label: 'Average risk', hint: 'Criterion 3 (0 = Low, 4 = No Travel)', values: pick((r) => r.metrics.avg_risk), format: (v) => v.toFixed(2), tolerance: 0.005 },
    { key: 'tm', label: 'Drive time', hint: 'Criterion 4', values: pick((r) => r.duration_s), format: (v) => fmtDuration(v), tolerance: 30 },
  ]
}

/**
 * Side-by-side criteria in ranking order. The best value in each row is
 * highlighted and the first row where routes actually differ is tagged
 * "decides" - that is the reason the recommended route won.
 */
export default function ComparisonTable({ routes }: { routes: Route[] }) {
  const rows = buildRows(routes)
  const deciding = rows.find((r) => Math.max(...r.values) - Math.min(...r.values) > r.tolerance)?.key

  return (
    <table className="compare">
      <caption className="sr-only">Route comparison by ranking criteria</caption>
      <thead>
        <tr>
          <th scope="col">Criterion</th>
          {routes.map((r) => (
            <th key={r.id} scope="col" className={r.recommended ? 'win' : ''}>
              <span className="dot" style={{ background: ROUTE_HEX[r.id] }} />
              {r.id.toUpperCase()}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const best = Math.min(...row.values)
          return (
            <tr key={row.key} className={row.key === deciding ? 'decides' : ''}>
              <th scope="row" title={row.hint}>
                {row.label}
                {row.key === deciding && <span className="tag">decides</span>}
              </th>
              {row.values.map((v, i) => (
                <td key={routes[i].id} className={`tabular${v - best <= row.tolerance ? ' best' : ''}`}>
                  {row.format(v)}
                </td>
              ))}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
