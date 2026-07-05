import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Overview', end: true },
  { to: '/literature', label: 'Literature' },
  { to: '/evidence-grader', label: 'Evidence Grader' },
  { to: '/natural-products', label: 'Natural Products' },
  { to: '/own-data', label: 'Own Data' },
  { to: '/grounded-report', label: 'Grounded Report' },
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
          <nav className="app-nav">
            {navItems.map(({ to, label, end }) => (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? 'active' : undefined)}>
                {label}
              </NavLink>
            ))}
            <a href={docsUrl} target="_blank" rel="noopener noreferrer" className="external">
              API Docs ↗
            </a>
          </nav>
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
      <footer className="app-footer">
        Research demo workspace — bounded synthetic fixtures; not a production system.
      </footer>
    </div>
  )
}
