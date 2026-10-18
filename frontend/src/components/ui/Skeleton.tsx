interface Props {
  height?: number
  width?: string
  className?: string
}

export default function Skeleton({ height = 16, width = '100%', className = '' }: Props) {
  return <span className={`skeleton ${className}`} style={{ height, width }} aria-hidden="true" />
}
