interface Option<T extends string> {
  value: T
  label: string
  hint?: string
}

interface Props<T extends string> {
  label: string
  value: T
  options: readonly Option<T>[]
  onChange: (value: T) => void
}

export default function Segmented<T extends string>({ label, value, options, onChange }: Props<T>) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          title={o.hint}
          className={o.value === value ? 'on' : ''}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
