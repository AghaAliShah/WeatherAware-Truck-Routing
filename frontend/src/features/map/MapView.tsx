import { memo, useEffect, useMemo } from 'react'
import L from 'leaflet'
import { MapContainer, Marker, TileLayer, ZoomControl, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { conditionsAt, type TimeView } from '../../lib/forecast'
import { fmtDateTime } from '../../lib/format'
import { truckAt } from '../../lib/geometry'
import { ROUTE_HEX, riskLabel } from '../../lib/risk'
import type { HeatmapResponse, PlanResponse } from '../../lib/types'
import HeatLayer from './HeatLayer'
import RouteLayers from './RouteLayers'
import TruckMarker from './TruckMarker'
import './map.css'

interface Props {
  plan: PlanResponse | null
  selectedId: string | null
  hoveredId: string | null
  /** Checkpoint previewed by hover (selected route only). */
  activeIndex: number | null
  /** Checkpoint opened in the detail card. */
  pinnedIndex: number | null
  view: TimeView
  heat: HeatmapResponse | null
  showHeat: boolean
  /** Pixels of the map covered by the side panel, so fitting keeps routes visible. */
  leftInset: number
  refitKey: number
  onSelect: (id: string) => void
  onHover: (id: string | null) => void
  onActive: (index: number | null) => void
  onPick: (index: number) => void
}

const endpointIcon = (text: string, cls: string) =>
  L.divIcon({ className: `endpoint ${cls}`, html: `<span>${text}</span>`, iconSize: [32, 32], iconAnchor: [16, 16] })
const ICON_A = endpointIcon('A', 'endpoint-a')
const ICON_B = endpointIcon('B', 'endpoint-b')
const RING = L.divIcon({ className: 'ring-marker', html: '<span></span>', iconSize: [38, 38], iconAnchor: [19, 19] })

function FitToPlan({ plan, leftInset, refitKey }: { plan: PlanResponse | null; leftInset: number; refitKey: number }) {
  const map = useMap()
  useEffect(() => {
    if (!plan) return
    map.invalidateSize()
    const pts = plan.routes.flatMap((r) => r.geometry.map(([lat, lon]): [number, number] => [lat, lon]))
    const phone = window.innerWidth <= 860
    map.flyToBounds(L.latLngBounds(pts), {
      paddingTopLeft: phone ? [24, 150] : [leftInset + 40, 60],
      paddingBottomRight: phone ? [24, window.innerHeight * 0.48 + 24] : [60, 190],
      duration: 1.0,
    })
    // Refit only for a new plan or an explicit request, not when the panel is toggled.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan, refitKey, map])
  return null
}

function MapView(p: Props) {
  const { plan, selectedId, hoveredId, view } = p
  const selected = plan?.routes.find((r) => r.id === selectedId) ?? null
  const departureMs = plan ? new Date(plan.departure).getTime() : 0

  // Selected route renders last so it sits on top.
  const ordered = useMemo(
    () => (plan ? [...plan.routes].sort((a, b) => Number(a.id === selectedId) - Number(b.id === selectedId)) : []),
    [plan, selectedId],
  )

  const first = plan?.routes[0]
  const start = first?.geometry[0]
  const end = first?.geometry[first.geometry.length - 1]
  const focusIndex = p.activeIndex ?? p.pinnedIndex
  const focus = selected && focusIndex != null ? selected.checkpoints[focusIndex] : null

  return (
    <MapContainer center={[39.5, -98.35]} zoom={4} preferCanvas className="map" zoomControl={false} worldCopyJump>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        className="tiles"
        maxZoom={18}
      />
      <ZoomControl position="bottomright" />
      <FitToPlan plan={plan} leftInset={p.leftInset} refitKey={p.refitKey} />
      <HeatLayer heat={p.heat} hour={view.hour} visible={p.showHeat} />

      {ordered.map((r) => (
        <RouteLayers
          key={r.id}
          route={r}
          selected={r.id === selectedId}
          hovered={r.id === hoveredId}
          view={view}
          onSelect={p.onSelect}
          onHover={p.onHover}
          onActive={p.onActive}
          onPick={p.onPick}
        />
      ))}

      {focus && <Marker position={[focus.lat, focus.lon]} icon={RING} interactive={false} zIndexOffset={900} />}

      {plan?.routes.map((r) => {
        const truck = truckAt(r, departureMs, view.hour)
        const nearest = r.checkpoints.reduce((best, c) => {
          const d = Math.abs(new Date(c.eta).getTime() - (departureMs + view.hour * 3_600_000))
          return d < best.d ? { d, c } : best
        }, { d: Infinity, c: r.checkpoints[0] }).c
        const cond = conditionsAt(nearest, { mode: 'eta', hour: 0 })
        return (
          <TruckMarker
            key={r.id}
            position={truck.position}
            heading={truck.heading}
            color={ROUTE_HEX[r.id]}
            label={r.label}
            detail={
              truck.arrived
                ? `Arrived ${fmtDateTime(r.arrival)}`
                : `+${view.hour} h · near mile ${Math.round(nearest.mile)} · ${riskLabel(cond.level)} at ETA`
            }
            emphasised={r.id === selectedId}
            arrived={truck.arrived}
          />
        )
      })}

      {start && <Marker position={[start[0], start[1]]} icon={ICON_A} interactive={false} zIndexOffset={700} />}
      {end && <Marker position={[end[0], end[1]]} icon={ICON_B} interactive={false} zIndexOffset={700} />}
    </MapContainer>
  )
}

export default memo(MapView)
