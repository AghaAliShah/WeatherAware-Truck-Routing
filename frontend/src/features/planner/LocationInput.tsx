import { useEffect, useId, useRef, useState } from 'react'
import { geocode } from '../../lib/api'
import type { Place } from '../../lib/types'

interface Props {
  label: string
  value: Place | null
  onChange: (place: Place | null) => void
  placeholder?: string
  marker: 'A' | 'B'
}

const MIN_CHARS = 2
const DEBOUNCE_MS = 200

// Shared by every input: repeated or backspaced queries resolve instantly without a request.
const cache = new Map<string, Place[]>()
const normalise = (q: string) => q.trim().toLowerCase().replace(/\s+/g, ' ')

type Status = 'idle' | 'loading' | 'empty' | 'error'

export default function LocationInput({ label, value, onChange, placeholder, marker }: Props) {
  const id = useId()
  const [text, setText] = useState(value?.label ?? '')
  const [options, setOptions] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [status, setStatus] = useState<Status>('idle')
  const abortRef = useRef<AbortController | null>(null)

  // Reflect places set from outside (example trip, swap) without an extra effect pass.
  const [seenValue, setSeenValue] = useState(value)
  if (value !== seenValue) {
    setSeenValue(value)
    setText(value?.label ?? '')
  }

  useEffect(() => {
    abortRef.current?.abort()
    const query = text.trim()
    if (query.length < MIN_CHARS || (value && value.label === text)) {
      setStatus('idle')
      return
    }
    const key = normalise(query)
    const show = (results: Place[]) => {
      setOptions(results)
      setActive(results.length ? 0 : -1)
      setStatus(results.length ? 'idle' : 'empty')
      setOpen(true)
    }
    const cached = cache.get(key)
    if (cached) {
      show(cached)
      return
    }
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setStatus('loading')
    const timer = setTimeout(() => {
      geocode(query, ctrl.signal)
        .then((results) => {
          cache.set(key, results)
          show(results)
        })
        .catch((err: Error) => {
          if (err.name !== 'AbortError') setStatus('error')
        })
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      ctrl.abort()
    }
  }, [text, value])

  const choose = (place: Place) => {
    setText(place.label)
    setOpen(false)
    onChange(place)
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown' && options.length) {
      e.preventDefault()
      setOpen(true)
      setActive((a) => (a + 1) % options.length)
    } else if (e.key === 'ArrowUp' && options.length) {
      e.preventDefault()
      setActive((a) => (a - 1 + options.length) % options.length)
    } else if (e.key === 'Enter' && open && active >= 0) {
      e.preventDefault()
      choose(options[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const listId = `${id}-list`
  return (
    <div className="field combo">
      <label htmlFor={id}>{label}</label>
      <div className="combo-input">
        <span className={`pin pin-${marker.toLowerCase()}`} aria-hidden="true">
          {marker}
        </span>
        <input
          id={id}
          className="input"
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${id}-opt-${active}` : undefined}
          autoComplete="off"
          placeholder={placeholder}
          value={text}
          maxLength={200}
          onChange={(e) => {
            setText(e.target.value)
            if (value) onChange(null)
          }}
          onFocus={() => options.length > 0 && text.trim().length >= MIN_CHARS && !value && setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
        />
        {status === 'loading' && <span className="spinner combo-spin" aria-label="Searching" />}
      </div>
      <div className="hint" aria-live="polite">
        {status === 'empty' && 'No matches. Try a city or a full address.'}
        {status === 'error' && 'Search is unavailable right now.'}
      </div>
      {open && options.length > 0 && (
        <ul id={listId} role="listbox" className="options">
          {options.map((o, i) => (
            <li
              key={`${o.lat},${o.lon}`}
              id={`${id}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? 'active' : ''}
              onMouseDown={(e) => {
                e.preventDefault()
                choose(o)
              }}
              onMouseEnter={() => setActive(i)}
            >
              {o.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
