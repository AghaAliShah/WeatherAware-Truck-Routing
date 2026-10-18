import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, loadHeatmap, planTrip } from '../lib/api'
import type { HeatmapResponse, PlanRequest, PlanResponse } from '../lib/types'

export type PlanStatus = 'idle' | 'loading' | 'ready' | 'error'
export type HeatStatus = 'idle' | 'loading' | 'ready' | 'error'

export interface TripPlanner {
  request: PlanRequest | null
  plan: PlanResponse | null
  status: PlanStatus
  error: string
  heat: HeatmapResponse | null
  heatStatus: HeatStatus
  submit: (req: PlanRequest) => Promise<void>
  retryHeat: () => void
}

/** Owns the trip request lifecycle: route plan first, then the heatmap grid in the background. */
export function useTripPlanner(): TripPlanner {
  const [request, setRequest] = useState<PlanRequest | null>(null)
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [status, setStatus] = useState<PlanStatus>('idle')
  const [error, setError] = useState('')
  const [heat, setHeat] = useState<HeatmapResponse | null>(null)
  const [heatStatus, setHeatStatus] = useState<HeatStatus>('idle')

  const planAbort = useRef<AbortController | null>(null)
  const heatAbort = useRef<AbortController | null>(null)

  const fetchHeat = useCallback((p: PlanResponse) => {
    heatAbort.current?.abort()
    const ctrl = new AbortController()
    heatAbort.current = ctrl
    setHeatStatus('loading')
    loadHeatmap(p, ctrl.signal)
      .then((h) => {
        setHeat(h)
        setHeatStatus('ready')
      })
      .catch((err: Error) => {
        if (err.name !== 'AbortError') setHeatStatus('error')
      })
  }, [])

  const submit = useCallback(
    async (req: PlanRequest) => {
      planAbort.current?.abort()
      heatAbort.current?.abort()
      const ctrl = new AbortController()
      planAbort.current = ctrl
      setRequest(req)
      setStatus('loading')
      setError('')
      setPlan(null)
      setHeat(null)
      setHeatStatus('idle')
      try {
        const result = await planTrip(req, ctrl.signal)
        if (planAbort.current !== ctrl) return
        setPlan(result)
        setStatus('ready')
        fetchHeat(result)
      } catch (err) {
        if ((err as Error).name === 'AbortError') return
        setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
        setStatus('error')
      }
    },
    [fetchHeat],
  )

  const retryHeat = useCallback(() => {
    if (plan) fetchHeat(plan)
  }, [plan, fetchHeat])

  useEffect(
    () => () => {
      planAbort.current?.abort()
      heatAbort.current?.abort()
    },
    [],
  )

  return { request, plan, status, error, heat, heatStatus, submit, retryHeat }
}
