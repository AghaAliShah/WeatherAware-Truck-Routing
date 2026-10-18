import { memo, useMemo } from 'react'
import { CircleMarker, Polyline, Tooltip } from 'react-leaflet'
import { conditionsAt, type TimeView } from '../../lib/forecast'
import { fmtDuration, fmtTime } from '../../lib/format'
import type { LatLng } from '../../lib/geometry'
import { ROUTE_HEX, riskHex, riskLabel } from '../../lib/risk'
import type { Route } from '../../lib/types'
import { riskSegments } from './segments'

interface Props {
  route: Route
  selected: boolean
  hovered: boolean
  view: TimeView
  onSelect: (id: string) => void
  onHover: (id: string | null) => void
  onActive: (index: number | null) => void
  onPick: (index: number) => void
}

function RouteLayers({ route, selected, hovered, view, onSelect, onHover, onActive, onPick }: Props) {
  const line = useMemo(() => route.geometry.map(([lat, lon]): LatLng => [lat, lon]), [route])
  const segments = useMemo(() => (selected ? riskSegments(route, view) : []), [route, selected, view])

  if (!selected) {
    return (
      <Polyline
        positions={line}
        pathOptions={{
          color: ROUTE_HEX[route.id],
          weight: hovered ? 8 : 5,
          opacity: hovered ? 0.95 : 0.6,
          dashArray: hovered ? undefined : '2 9',
          lineCap: 'round',
        }}
        eventHandlers={{ click: () => onSelect(route.id), mouseover: () => onHover(route.id), mouseout: () => onHover(null) }}
      >
        <Tooltip sticky>
          <strong>{route.label}</strong> · {fmtDuration(route.duration_s)}
          <br />
          {Math.round(route.metrics.severe_miles + route.metrics.no_travel_miles)} mi Severe or worse. Click to select.
        </Tooltip>
      </Polyline>
    )
  }

  return (
    <>
      <Polyline positions={line} pathOptions={{ color: '#fff', weight: 12, opacity: 0.95 }} interactive={false} />
      {segments.map((s, i) => (
        <Polyline
          key={i}
          positions={s.positions}
          pathOptions={{ color: riskHex(s.level), weight: 7, opacity: 1, lineCap: 'butt' }}
          interactive={false}
        />
      ))}
      {route.checkpoints.map((c) => {
        const cond = conditionsAt(c, view)
        return (
          <CircleMarker
            key={c.index}
            center={[c.lat, c.lon]}
            radius={6.5}
            pathOptions={{ color: '#0e1f3d', weight: 1.5, fillColor: riskHex(cond.level), fillOpacity: 1 }}
            eventHandlers={{
              click: () => onPick(c.index),
              mouseover: () => onActive(c.index),
              mouseout: () => onActive(null),
            }}
          >
            <Tooltip direction="top" offset={[0, -6]}>
              <strong>Mile {Math.round(c.mile)}</strong> · {fmtTime(c.eta)}
              <br />
              {riskLabel(cond.level)} · {cond.wind.toFixed(1)} mph. Click for details.
            </Tooltip>
          </CircleMarker>
        )
      })}
    </>
  )
}

export default memo(RouteLayers)
