import { memo, useMemo } from 'react'
import L from 'leaflet'
import { Marker, Tooltip } from 'react-leaflet'
import type { LatLng } from '../../lib/geometry'

interface Props {
  position: LatLng
  heading: number
  color: string
  label: string
  detail: string
  emphasised: boolean
  arrived: boolean
}

// Top-down tractor-trailer pointing "up"; rotated to the direction of travel.
const TRUCK_SVG = `
<svg viewBox="0 0 24 40" width="22" height="36" aria-hidden="true">
  <rect x="5" y="14" width="14" height="24" rx="2" fill="currentColor" stroke="#fff" stroke-width="1.6"/>
  <path d="M6 12V5.5A2.5 2.5 0 0 1 8.5 3h7A2.5 2.5 0 0 1 18 5.5V12z" fill="currentColor" stroke="#fff" stroke-width="1.6"/>
  <rect x="8" y="5.5" width="8" height="3" rx="1" fill="#fff" opacity=".9"/>
</svg>`

/** One truck per route at the position implied by the forecast slider hour. */
function TruckMarker({ position, heading, color, label, detail, emphasised, arrived }: Props) {
  // Quantise heading so the icon is rebuilt only when the truck visibly turns.
  const snapped = Math.round(heading / 6) * 6
  const icon = useMemo(
    () =>
      L.divIcon({
        className: `truck${emphasised ? ' truck-lg' : ''}${arrived ? ' truck-arrived' : ''}`,
        html: `<div style="color:${color};transform:rotate(${snapped}deg)">${TRUCK_SVG}</div>`,
        iconSize: [28, 40],
        iconAnchor: [14, 20],
      }),
    [snapped, color, emphasised, arrived],
  )
  return (
    <Marker position={position} icon={icon} zIndexOffset={emphasised ? 800 : 500} keyboard={false}>
      <Tooltip direction="top" offset={[0, -18]}>
        <strong>{label}</strong>
        <br />
        {detail}
      </Tooltip>
    </Marker>
  )
}

export default memo(TruckMarker)
