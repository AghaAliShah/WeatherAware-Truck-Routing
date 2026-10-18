import L from 'leaflet'
import { RISK_HEX } from '../../lib/risk'

/**
 * Canvas weather surface. Unlike a density heatmap, overlapping grid points are
 * *averaged* (Gaussian-weighted), so the colour at any pixel is the interpolated
 * risk there - a Low area is green no matter how many points surround it.
 * The layer is created once; slider moves call `setData`, which only repaints.
 */

const CELL_PX = 8 // raster resolution; the canvas is upscaled with smoothing
const ALPHA = 0.62

const hex = (c: string): [number, number, number] => [
  parseInt(c.slice(1, 3), 16),
  parseInt(c.slice(3, 5), 16),
  parseInt(c.slice(5, 7), 16),
]
const PALETTE = RISK_HEX.map(hex)

/** Severity 0..4 (continuous) -> RGB, blending between adjacent band colours. */
function colorFor(sev: number): [number, number, number] {
  const i = Math.min(3, Math.floor(sev))
  const t = sev - i
  const a = PALETTE[i]
  const b = PALETTE[i + 1]
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]
}

export interface HeatData {
  points: [number, number][]
  values: number[] // 0-100 severity per point
  cellDeg: number
}

export class HeatCanvasLayer extends L.Layer {
  private canvas = document.createElement('canvas')
  private data: HeatData | null = null
  private raf = 0

  onAdd(map: L.Map): this {
    this.canvas.className = 'heat-canvas leaflet-layer'
    this.canvas.style.pointerEvents = 'none'
    map.getPanes().overlayPane.appendChild(this.canvas)
    map.on('moveend zoomend resize', this.schedule, this)
    map.on('zoomstart', this.hide, this)
    this.schedule()
    return this
  }

  onRemove(map: L.Map): this {
    cancelAnimationFrame(this.raf)
    this.canvas.remove()
    map.off('moveend zoomend resize', this.schedule, this)
    map.off('zoomstart', this.hide, this)
    return this
  }

  setData(data: HeatData | null): void {
    this.data = data
    this.schedule()
  }

  private hide = () => {
    this.canvas.style.opacity = '0'
  }

  private schedule = () => {
    if (this.raf) return
    this.raf = requestAnimationFrame(() => {
      this.raf = 0
      this.draw()
    })
  }

  private draw(): void {
    const map = (this as unknown as { _map?: L.Map })._map
    if (!map) return
    const size = map.getSize()
    if (size.x === 0 || size.y === 0) return

    L.DomUtil.setPosition(this.canvas, map.containerPointToLayerPoint([0, 0]))
    this.canvas.style.opacity = '1'
    this.canvas.style.width = `${size.x}px`
    this.canvas.style.height = `${size.y}px`
    const cols = Math.ceil(size.x / CELL_PX)
    const rows = Math.ceil(size.y / CELL_PX)
    if (this.canvas.width !== cols || this.canvas.height !== rows) {
      this.canvas.width = cols
      this.canvas.height = rows
    }
    const ctx = this.canvas.getContext('2d')!
    ctx.clearRect(0, 0, cols, rows)
    const d = this.data
    if (!d || d.points.length === 0) return

    // Kernel width: one grid cell expressed in screen pixels (in raster cells).
    const mpp = (156543.03 * Math.cos((map.getCenter().lat * Math.PI) / 180)) / 2 ** map.getZoom()
    const cellPx = (d.cellDeg * 111_000) / mpp
    const sigma = Math.max(1.5, (cellPx * 0.75) / CELL_PX)
    const reach = sigma * 2.4
    const inv = 1 / (2 * sigma * sigma)

    // Project points into raster coordinates once.
    const px = d.points.map(([lat, lon]) => {
      const p = map.latLngToContainerPoint([lat, lon])
      return [p.x / CELL_PX, p.y / CELL_PX] as const
    })

    const img = ctx.createImageData(cols, rows)
    const out = img.data
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        let sumW = 0
        let sumV = 0
        for (let i = 0; i < px.length; i++) {
          const dx = x - px[i][0]
          if (dx > reach || dx < -reach) continue
          const dy = y - px[i][1]
          if (dy > reach || dy < -reach) continue
          const w = Math.exp(-(dx * dx + dy * dy) * inv)
          sumW += w
          sumV += w * d.values[i]
        }
        if (sumW < 0.02) continue
        const sev = Math.min(4, (sumV / sumW) / 25)
        const [r, g, b] = colorFor(sev)
        const o = (y * cols + x) * 4
        out[o] = r
        out[o + 1] = g
        out[o + 2] = b
        // Fade at the corridor edge (coverage) and keep Low areas subtler.
        out[o + 3] = 255 * ALPHA * Math.min(1, sumW / 0.9) * (0.55 + 0.45 * Math.min(1, sev))
      }
    }
    ctx.putImageData(img, 0, 0)
  }
}
