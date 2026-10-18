import { useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react'
import { useMediaQuery } from './hooks/useMediaQuery'
import { useTripPlanner } from './hooks/useTripPlanner'
import CheckpointDetail from './features/forecast/CheckpointDetail'
import ForecastBar from './features/forecast/ForecastBar'
import MapView from './features/map/MapView'
import TripForm from './features/planner/TripForm'
import TripSummary from './features/planner/TripSummary'
import { EmptyState, ErrorState, PlanningState } from './features/routes/PanelStates'
import Recommendation from './features/routes/Recommendation'
import RouteCard from './features/routes/RouteCard'
import type { TimeView, ViewMode } from './lib/forecast'
import { assign, track } from './lib/experiments'
import type { PlanRequest } from './lib/types'

const PANEL_WIDTH = 408
const PANEL_GAP = 16

interface Pinned {
  routeId: string
  index: number
}

export default function App() {
  const { request, plan, status, error, heat, heatStatus, submit, retryHeat } = useTripPlanner()
  const [whyExp] = useState(() => assign('why_default'))
  const [sliderUsed, setSliderUsed] = useState(false)
  const desktop = useMediaQuery('(min-width: 861px)')

  const [panelOpen, setPanelOpen] = useState(true)
  const [editing, setEditing] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const [pinned, setPinned] = useState<Pinned | null>(null)
  const [hour, setHour] = useState(0)
  const [mode, setMode] = useState<ViewMode>('eta')
  const [showHeat, setShowHeat] = useState(true)
  const [refitKey, setRefitKey] = useState(0)

  // The slider stays instant; map consumers follow a deferred value so scrubbing never blocks the thumb.
  const deferredHour = useDeferredValue(hour)
  const view = useMemo<TimeView>(() => ({ mode, hour: deferredHour }), [mode, deferredHour])

  // Reset interaction state when a new plan arrives (adjusting state during render avoids an extra effect pass).
  const [seenPlan, setSeenPlan] = useState(plan)
  if (plan !== seenPlan) {
    setSeenPlan(plan)
    if (plan) {
      setSelectedId(plan.recommended_id)
      setPinned(null)
      setActiveIndex(null)
      setHour(0)
      setMode('eta')
      setEditing(false)
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPinned(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const select = useCallback((id: string) => {
    track(whyExp, 'route_selected')
    setSelectedId(id)
    setPinned(null)
    setActiveIndex(null)
  }, [whyExp])

  const pick = useCallback(
    (index: number) => {
      track(whyExp, 'checkpoint_opened')
      if (selectedId) setPinned({ routeId: selectedId, index })
    },
    [selectedId, whyExp],
  )

  const changeHour = useCallback(
    (h: number) => {
      if (!sliderUsed) {
        setSliderUsed(true)
        track(whyExp, 'slider_used') // once per plan
      }
      setHour(h)
      setMode('forecast')
    },
    [sliderUsed, whyExp],
  )

  const handleSubmit = useCallback(
    (req: PlanRequest) => {
      track(whyExp, 'plan_submitted')
      setSliderUsed(false)
      setEditing(false)
      void submit(req)
    },
    [submit, whyExp],
  )

  const pinnedRoute = plan && pinned ? plan.routes.find((r) => r.id === pinned.routeId) : undefined
  const pinnedCheckpoint = pinnedRoute && pinned ? pinnedRoute.checkpoints[pinned.index] : undefined
  const showForm = status === 'idle' || status === 'error' || editing
  const leftInset = desktop && panelOpen ? PANEL_WIDTH + PANEL_GAP : 0

  return (
    <div className="app" style={{ ['--panel-offset' as string]: `${leftInset}px` }}>
      <MapView
        plan={plan}
        selectedId={selectedId}
        hoveredId={hoveredId}
        activeIndex={activeIndex}
        pinnedIndex={pinned && pinned.routeId === selectedId ? pinned.index : null}
        view={view}
        heat={heat}
        showHeat={showHeat}
        leftInset={leftInset}
        refitKey={refitKey}
        onSelect={select}
        onHover={setHoveredId}
        onActive={setActiveIndex}
        onPick={pick}
      />

      {!panelOpen && (
        <button type="button" className="btn panel-open" onClick={() => setPanelOpen(true)}>
          Show trip panel
        </button>
      )}

      {panelOpen && (
        <aside className="panel-shell" aria-label="Trip planner">
          <header className="panel-head">
            <div>
              <h1>Weather-Aware Truck Routing</h1>
              <p className="hint">Three routes, ranked by forecast weather at your ETA.</p>
            </div>
            <div className="head-actions">
              {plan && (
                <button type="button" className="btn ghost sm" onClick={() => setRefitKey((k) => k + 1)} title="Fit all routes in view">
                  Fit map
                </button>
              )}
              <button type="button" className="btn ghost sm" onClick={() => setPanelOpen(false)} aria-label="Hide trip panel">
                Hide
              </button>
            </div>
          </header>

          <div className="panel-body">
            {showForm ? (
              <TripForm busy={status === 'loading'} initial={request} onSubmit={handleSubmit} />
            ) : (
              request && <TripSummary request={request} onEdit={() => setEditing(true)} />
            )}

            {status === 'idle' && <EmptyState />}
            {status === 'loading' && <PlanningState />}
            {status === 'error' && <ErrorState message={error} onRetry={() => setEditing(true)} />}

            {plan && status === 'ready' && !editing && (
              <>
                <Recommendation
                  plan={plan}
                  defaultOpen={whyExp.variant === 'open'}
                  onExposed={() => track(whyExp, 'exposure')}
                  onToggled={() => track(whyExp, 'why_toggled')}
                />
                <section className="route-list" aria-label="Route options">
                  {[...plan.routes]
                    .sort((a, b) => a.rank - b.rank)
                    .map((r) => (
                      <RouteCard
                        key={r.id}
                        route={r}
                        selected={r.id === selectedId}
                        view={view}
                        activeIndex={r.id === selectedId ? activeIndex : null}
                        pinnedIndex={pinned && pinned.routeId === r.id ? pinned.index : null}
                        onSelect={select}
                        onHover={setHoveredId}
                        onActive={setActiveIndex}
                        onPick={pick}
                      />
                    ))}
                </section>
              </>
            )}
            <footer className="foot">Routing: OSRM. Weather: Open-Meteo. Map: OpenStreetMap contributors.</footer>
          </div>
        </aside>
      )}

      {pinnedRoute && pinnedCheckpoint && plan && (
        <CheckpointDetail route={pinnedRoute} checkpoint={pinnedCheckpoint} departure={plan.departure} view={view} onClose={() => setPinned(null)} />
      )}

      <ForecastBar
        departure={plan?.departure ?? null}
        heat={heat}
        heatStatus={heatStatus}
        hour={hour}
        mode={mode}
        showHeat={showHeat}
        onHour={changeHour}
        onMode={setMode}
        onShowHeat={setShowHeat}
        onRetry={retryHeat}
      />
    </div>
  )
}
