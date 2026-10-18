import { memo } from 'react'
import { conditionsAt, type Conditions, type TimeView } from '../../lib/forecast'
import { fmtTime } from '../../lib/format'
import { riskHex, riskLabel } from '../../lib/risk'
import type { Checkpoint, Route } from '../../lib/types'

interface Props {
  route: Route
  view: TimeView
  activeIndex: number | null
  onActive: (index: number | null) => void
  onPick: (index: number) => void
}

const W = 400
const H = 92
const TOP = 6
const BOTTOM = 18
const PLOT = H - TOP - BOTTOM

/**
 * Risk along the trip: bar width = miles a checkpoint covers, height = its risk level.
 * Hover or arrow-key to preview a checkpoint on the map; click or Enter to open its details.
 */
function RiskProfile({ route, view, activeIndex, onActive, onPick }: Props) {
  const total = route.distance_mi || 1
  const bars = route.checkpoints.reduce<{ c: Checkpoint; x: number; w: number; cond: Conditions }[]>((acc, c) => {
    const prev = acc[acc.length - 1]
    acc.push({ c, x: prev ? prev.x + prev.w : 0, w: (c.segment_miles / total) * W, cond: conditionsAt(c, view) })
    return acc
  }, [])
  const active = activeIndex == null ? null : bars[activeIndex]

  const indexAt = (clientX: number, el: SVGSVGElement) => {
    const rect = el.getBoundingClientRect()
    const px = ((clientX - rect.left) / rect.width) * W
    return (bars.find((b) => px >= b.x && px <= b.x + b.w) ?? bars[bars.length - 1]).c.index
  }

  const onKey = (e: React.KeyboardEvent) => {
    const n = bars.length
    if (e.key === 'ArrowRight') onActive(Math.min(n - 1, (activeIndex ?? -1) + 1))
    else if (e.key === 'ArrowLeft') onActive(Math.max(0, (activeIndex ?? 1) - 1))
    else if ((e.key === 'Enter' || e.key === ' ') && activeIndex != null) onPick(activeIndex)
    else return
    e.preventDefault()
  }

  return (
    <figure className="profile">
      <figcaption className="tabular">
        {active ? (
          <>
            <strong>Mile {Math.round(active.c.mile)}</strong> · {fmtTime(active.c.eta)} ·{' '}
            <span style={{ color: riskHex(active.cond.level), fontWeight: 700 }}>{riskLabel(active.cond.level)}</span> ·{' '}
            {active.cond.wind.toFixed(1)} mph
          </>
        ) : (
          <span className="hint">Hover the chart to inspect checkpoints, click to open one.</span>
        )}
      </figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        tabIndex={0}
        aria-label={`Risk profile for ${route.label}. Use left and right arrows, Enter to open a checkpoint.`}
        onMouseMove={(e) => onActive(indexAt(e.clientX, e.currentTarget))}
        onMouseLeave={() => onActive(null)}
        onClick={(e) => onPick(indexAt(e.clientX, e.currentTarget))}
        onBlur={() => onActive(null)}
        onKeyDown={onKey}
      >
        {[1, 2, 3, 4].map((lvl) => {
          const y = TOP + PLOT - ((lvl + 0.6) / 4.6) * PLOT
          return <line key={lvl} x1={0} x2={W} y1={y} y2={y} className="grid" />
        })}
        {bars.map(({ c, x, w, cond }) => {
          const h = ((cond.level + 0.6) / 4.6) * PLOT
          return (
            <rect
              key={c.index}
              x={x + 0.4}
              y={TOP + PLOT - h}
              width={Math.max(0.8, w - 0.8)}
              height={h}
              rx={1.5}
              fill={riskHex(cond.level)}
              opacity={activeIndex == null || activeIndex === c.index ? 1 : 0.4}
            />
          )
        })}
        {active && <line x1={active.x + active.w / 2} x2={active.x + active.w / 2} y1={TOP} y2={TOP + PLOT} className="cursor" />}
        <text x={0} y={H - 4} className="axis">
          {fmtTime(route.checkpoints[0].eta)}
        </text>
        <text x={W / 2} y={H - 4} className="axis" textAnchor="middle">
          {Math.round(total)} mi
        </text>
        <text x={W} y={H - 4} className="axis" textAnchor="end">
          {fmtTime(route.checkpoints[route.checkpoints.length - 1].eta)}
        </text>
      </svg>
    </figure>
  )
}

export default memo(RiskProfile)
