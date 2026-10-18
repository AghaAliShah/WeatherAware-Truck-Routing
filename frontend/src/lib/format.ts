const dateTime = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})
const timeOnly = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' })

export const fmtDateTime = (iso: string) => dateTime.format(new Date(iso))
export const fmtTime = (iso: string) => timeOnly.format(new Date(iso))

export function fmtDuration(seconds: number): string {
  const totalMin = Math.round(seconds / 60)
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  return h ? `${h} h ${m.toString().padStart(2, '0')} m` : `${m} m`
}

export const fmtMiles = (mi: number) => `${Math.round(mi).toLocaleString()} mi`

/** Value for <input type="datetime-local">: local wall-clock time, minute precision. */
export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function defaultDeparture(): string {
  const d = new Date(Date.now() + 60 * 60 * 1000)
  d.setMinutes(0, 0, 0)
  return toLocalInputValue(d)
}

/** Wall-clock label for `hours` after `startIso`. */
export const fmtHourOffset = (startIso: string, hours: number) =>
  fmtDateTime(new Date(new Date(startIso).getTime() + hours * 3_600_000).toISOString())
