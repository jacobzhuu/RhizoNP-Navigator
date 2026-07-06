import type { ReactNode } from 'react'
import type { IconProps } from './icons'

type IconTheme = 'blue' | 'teal' | 'green' | 'purple' | 'slate' | 'red'

interface SectionCardProps {
  title: string
  description?: string
  icon: React.ComponentType<IconProps>
  iconTheme?: IconTheme
  action?: ReactNode
  children: ReactNode
  className?: string
}

export function SectionCard({
  title,
  description,
  icon: Icon,
  iconTheme = 'blue',
  action,
  children,
  className,
}: SectionCardProps) {
  return (
    <section className={['card', 'section-card', className].filter(Boolean).join(' ')}>
      <div className="section-card-header">
        <span className={`section-card-icon section-card-icon--${iconTheme}`}>
          <Icon size={20} />
        </span>
        <div className="section-card-heading">
          <h2 className="section-card-title">{title}</h2>
          {description && <p className="section-card-desc">{description}</p>}
        </div>
        {action && <div className="section-card-action">{action}</div>}
      </div>
      <div className="section-card-body">{children}</div>
    </section>
  )
}
