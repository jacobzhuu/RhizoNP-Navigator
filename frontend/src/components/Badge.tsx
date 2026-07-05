interface BadgeProps {
  label: string
  variant?: 'tier-a' | 'tier-b' | 'tier-c' | 'tier-d' | 'same-genus' | 'supported' | 'partial' | 'insufficient' | 'fixture' | 'mode'
}

export function Badge({ label, variant = 'mode' }: BadgeProps) {
  return <span className={`badge badge-${variant}`}>{label}</span>
}

export function tierBadgeVariant(tier: string): BadgeProps['variant'] {
  const normalized = tier.toUpperCase()
  if (normalized === 'A' || normalized === 'SUPPORTED') return 'tier-a'
  if (normalized === 'B') return 'tier-b'
  if (normalized === 'C' || normalized === 'PARTIALLY_SUPPORTED') return 'tier-c'
  if (normalized === 'D' || normalized === 'INSUFFICIENT_EVIDENCE') return 'tier-d'
  return 'mode'
}

export function distanceBadgeVariant(distance: string): BadgeProps['variant'] {
  if (distance.toUpperCase().includes('SAME_GENUS')) return 'same-genus'
  return 'mode'
}
