import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { BrandMark, IconCrown, IconChevronDown, IconFlask, IconHome, IconInfo, IconMessage } from './icons'
import { StatusPill } from './StatusPill'

const navItems = [
  { to: '/', label: '首页', end: true, icon: IconHome },
  { to: '/ask', label: '科研问答', icon: IconMessage },
  { to: '/results', label: '结果解释', icon: IconFlask },
  { to: '/about', label: '关于', icon: IconInfo },
]

export function Layout() {
  const { pathname } = useLocation()
  const isHome = pathname === '/' || pathname === '/overview'

  return (
    <div className={`app-shell${isHome ? ' app-shell--home' : ''}`}>
      <header className="app-header">
        <div className="app-header-inner">
          <NavLink to="/" className="app-brand">
            <BrandMark size={34} />
            <span className="app-brand-text">
              <span className="app-brand-rhizonp">RhizoNP</span>{' '}
              <span className="app-brand-navigator">Navigator</span>
            </span>
          </NavLink>
          <nav className="app-nav" aria-label="主导航">
            {navItems.map(({ to, label, end, icon: NavIcon }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) => (isActive ? 'active' : undefined)}
              >
                <NavIcon size={16} />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="service-level" title="后端服务状态">
            <IconCrown size={15} />
            <span>服务等级</span>
            <StatusPill />
            <IconChevronDown size={14} className="service-level-chevron" />
          </div>
        </div>
      </header>
      <main className={`app-main${isHome ? ' app-main--home' : ''}`}>
        <Outlet />
      </main>
      <footer className="app-footer">
        <p>RhizoNP Navigator · 证据约束型根际微生物天然产物研究平台</p>
        <p className="app-footer-copy">© 2024 All rights reserved.</p>
      </footer>
    </div>
  )
}
