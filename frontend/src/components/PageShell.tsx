import type { ComponentType, ReactNode } from 'react'
import type { IconProps } from './icons'

type IconTheme = 'blue' | 'teal' | 'green' | 'purple' | 'slate'

interface PageHeaderProps {
  title: string
  subtitle?: string
  className?: string
  icon?: ComponentType<IconProps>
  iconTheme?: IconTheme
  action?: ReactNode
}

export function PageHeader({ title, subtitle, className, icon: Icon, iconTheme = 'blue', action }: PageHeaderProps) {
  return (
    <header className={['page-header', Icon && 'page-header--with-icon', action && 'page-header--with-action', className].filter(Boolean).join(' ')}>
      <div className="page-header-main">
        {Icon && (
          <span className={`page-header-icon page-header-icon--${iconTheme}`}>
            <Icon size={24} />
          </span>
        )}
        <div className="page-header-text">
          <h1>{title}</h1>
          {subtitle && <p className="subtitle">{subtitle}</p>}
        </div>
      </div>
      {action && <div className="page-header-action">{action}</div>}
    </header>
  )
}

interface FeaturePageProps {
  children: ReactNode
  className?: string
}

export function FeaturePage({ children, className }: FeaturePageProps) {
  return (
    <div className={['feature-page', className].filter(Boolean).join(' ')}>
      <div className="feature-page-content">{children}</div>
    </div>
  )
}

interface EmptyStateProps {
  title: string
  description?: string
  children?: ReactNode
}

export function EmptyState({ title, description, children }: EmptyStateProps) {
  return (
    <div className="empty-state card">
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {children}
    </div>
  )
}
