import { fmtDateTime } from '../../lib/format'
import type { PlanRequest } from '../../lib/types'

interface Props {
  request: PlanRequest
  onEdit: () => void
}

/** Compact recap of the submitted trip, shown in place of the form once results are on screen. */
export default function TripSummary({ request, onEdit }: Props) {
  return (
    <div className="trip-summary">
      <div className="trip-summary-main">
        <div className="trip-summary-route">
          <span className="pin pin-a">A</span>
          <span className="clip">{request.origin.label}</span>
        </div>
        <div className="trip-summary-route">
          <span className="pin pin-b">B</span>
          <span className="clip">{request.destination.label}</span>
        </div>
        <p className="hint tabular">
          {fmtDateTime(request.departure)} · {request.load_lb.toLocaleString()} lb
        </p>
      </div>
      <button type="button" className="btn sm" onClick={onEdit}>
        Edit trip
      </button>
    </div>
  )
}
