import { memo, useEffect, useMemo, useRef, useState } from 'react'
import Segmented from '../../components/ui/Segmented'
import Tip from '../../components/ui/Tip'
import { MAX_HOUR, type ViewMode } from '../../lib/forecast'
import { fmtHourOffset } from '../../lib/format'
import { RISK_HEX, RISK_INK, RISK_LABELS } from '../../lib/risk'
import type { HeatmapResponse } from '../../lib/types'
import './forecast.css'

interface Props {
  departure: string | null
  heat: HeatmapResponse | null
  heatStatus: 'idle' | 'loading' | 'ready' | 'error'
  hour: number
  mode: ViewMode
  showHeat: boolean
  onHour: (h: number) => void
  onMode: (m: ViewMode) => void
  onShowHeat: (v: boolean) => void
  onRetry: () => void
}

const SPEEDS = [
  { label: '1×', ms: 500 },
  { label: '2×', ms: 250 },
  { label: '4×', ms: 120 },
] as const

const MODE_OPTIONS = [
  { value: 'eta', label: 'At ETA', hint: 'Official risk: forecast at the moment the truck reaches each checkpoint' },
  { value: 'forecast', label: 'At forecast time', hint: 'Snapshot: every checkpoint and route colour at the slider hour' },
] as const

const peakLevel = (v: number) => Math.min(4, Math.floor(v / 25))

function ForecastBar({ departure, heat, heatStatus, hour, mode, showHeat, onHour, onMode, onShowHeat, onRetry }: Props) {
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(0)
  const hourRef = useRef(hour)
  useEffect(() => {
    hourRef.current = hour
  }, [hour])

  useEffect(() => {
    if (!playing) return
    const timer = setInterval(() => onHour(hourRef.current >= MAX_HOUR ? 0 : hourRef.current + 1), SPEEDS[speed].ms)
    return () => clearInterval(timer)
  }, [playing, speed, onHour])

  const peaks = useMemo(() => heat?.hours.map((h) => Math.max(...h)) ?? [], [heat])
  const gradient = useMemo(
    () => peaks.map((v, i) => `${RISK_HEX[peakLevel(v)]} ${(i / (MAX_HOUR + 1)) * 100}% ${((i + 1) / (MAX_HOUR + 1)) * 100}%`).join(','),
    [peaks],
  )
  const ready = heatStatus === 'ready' && departure !== null
  const peak = peakLevel(peaks[hour] ?? 0)

  return (
    <section className="forecast-bar" aria-label="Forecast timeline">
      <div className="fb-row">
        <label className="toggle">
          <input type="checkbox" checked={showHeat} onChange={(e) => onShowHeat(e.target.checked)} />
          Weather heatmap
        </label>
        {heatStatus === 'loading' && (
          <span className="hint">
            <span className="spinner" /> Loading forecast grid
          </span>
        )}
        {heatStatus === 'error' && (
          <span className="error-text">
            Forecast unavailable.{' '}
            <button type="button" className="btn ghost sm" onClick={onRetry}>
              Retry
            </button>
          </span>
        )}
        {ready && (
          <span className="fb-when tabular">
            <strong>+{hour} h</strong> {fmtHourOffset(departure, hour)}
            <span className="risk-badge" style={{ background: RISK_HEX[peak], color: RISK_INK[peak] }} title="Worst corridor condition at this hour">
              Peak {RISK_LABELS[peak]}
            </span>
          </span>
        )}
      </div>

      <div className="fb-slider">
        <Tip text={playing ? 'Pause the forecast animation' : 'Play the forecast animation'}>
          <button type="button" className="btn sm play" disabled={!ready} onClick={() => setPlaying((p) => !p)} aria-pressed={playing}>
            {playing ? 'Pause' : 'Play'}
          </button>
        </Tip>
        <div className="fb-track">
          {gradient && <div className="fb-peaks" style={{ background: `linear-gradient(90deg, ${gradient})` }} aria-hidden="true" />}
          <input
            type="range"
            min={0}
            max={MAX_HOUR}
            step={1}
            value={hour}
            disabled={!ready}
            onChange={(e) => onHour(Number(e.target.value))}
            aria-label="Forecast hour after departure"
            aria-valuetext={departure ? `${hour} hours after departure, ${fmtHourOffset(departure, hour)}` : `${hour} hours`}
          />
        </div>
        <Tip text="Animation speed">
          <button type="button" className="btn sm speed" disabled={!ready} onClick={() => setSpeed((s) => (s + 1) % SPEEDS.length)}>
            {SPEEDS[speed].label}
          </button>
        </Tip>
      </div>
      <div className="fb-ticks" aria-hidden="true">
        <span>Departure</span>
        <span>+12 h</span>
        <span>+24 h</span>
        <span>+36 h</span>
        <span>+48 h</span>
      </div>

      <div className="fb-row fb-foot">
        <Segmented label="Risk view" value={mode} options={MODE_OPTIONS} onChange={onMode} />
        <ul className="legend" aria-label="Risk legend">
          {RISK_LABELS.map((label, i) => (
            <li key={label}>
              <span className="dot" style={{ background: RISK_HEX[i] }} />
              {label}
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

export default memo(ForecastBar)
