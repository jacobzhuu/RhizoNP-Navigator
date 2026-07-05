import { NavLink, Outlet } from 'react-router-dom'
import { StatusPill } from './StatusPill'

const navItems = [
  { to: '/', label: '科研问答', end: true },
  { to: '/overview', label: '概览' },
  { to: '/literature', label: '文献检索' },
  { to: '/evidence-grader', label: '证据分级' },
  { to: '/natural-products', label: '天然产物' },
  { to: '/own-data', label: '自有数据' },
  { to: '/grounded-report', label: '证据报告' },
]

export function Layout() {
  const docsUrl = import.meta.env.DEV
    ? 'http://127.0.0.1:8000/docs'
    : `${import.meta.env.VITE_API_BASE_URL || ''}/docs`

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <NavLink to="/" className="app-brand">
            RhizoNP Navigator
          </NavLink>
          <nav className="app-nav" aria-label="主导航">
            {navItems.map(({ to, label, end }) => (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? 'active' : undefined)}>
                {label}
              </NavLink>
            ))}
            <NavLink to="/about/limitations" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              数据范围
            </NavLink>
            <a href={docsUrl} target="_blank" rel="noopener noreferrer" className="external">
              API 文档 ↗
            </a>
          </nav>
          <StatusPill />
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
      <footer className="app-footer">
        RhizoNP Navigator · 证据约束型根际微生物天然产物研究平台
      </footer>
    </div>
  )
}
