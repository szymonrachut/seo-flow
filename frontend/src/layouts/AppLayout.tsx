import { NavLink, Outlet } from 'react-router-dom'

const navigationItems = [
  { to: '/jobs', label: 'Jobs' },
]

export function AppLayout() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-stone-300/80 bg-[#f7f2ea]/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-teal-700">Local SEO crawler</p>
            <p className="mt-1 text-lg font-semibold text-stone-950">Crawler Console</p>
          </div>
          <nav className="flex flex-wrap gap-2">
            {navigationItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-full px-4 py-2 text-sm font-medium transition ${
                    isActive
                      ? 'bg-stone-950 text-white'
                      : 'border border-stone-300 bg-white/80 text-stone-700 hover:bg-stone-100'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
