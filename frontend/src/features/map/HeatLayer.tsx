import { memo, useEffect, useMemo } from 'react'
import { useMap } from 'react-leaflet'
import type { HeatmapResponse } from '../../lib/types'
import { HeatCanvasLayer } from './HeatCanvasLayer'

interface Props {
  heat: HeatmapResponse | null
  hour: number
  visible: boolean
}

/** The canvas layer is created once; slider moves only swap its data and repaint it (no React work per frame). */
function HeatLayer({ heat, hour, visible }: Props) {
  const map = useMap()
  const layer = useMemo(() => new HeatCanvasLayer(), [])

  useEffect(() => {
    if (!visible || !heat) return
    map.invalidateSize()
    layer.addTo(map)
    return () => {
      layer.remove()
    }
  }, [layer, map, visible, heat])

  useEffect(() => {
    layer.setData(
      heat ? { points: heat.points, values: heat.hours[Math.min(hour, heat.hours.length - 1)], cellDeg: heat.cell_deg } : null,
    )
  }, [heat, hour, layer])

  return null
}

export default memo(HeatLayer)
