import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Workflow, Play, Calendar, User, Code2, Plus, Zap
} from 'lucide-react'
import clsx from 'clsx'

const nav = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/workflows', icon: Workflow, label: 'Workflows' },
  { to: '/workflows/new', icon: Plus, label: 'Create Workflow' },
  { to: '/runs', icon: Play, label: 'Run Monitor', disabled: true },
  { to: '/scheduled', icon: Calendar, label: 'Scheduled' },
  { to: '/leetcode', icon: Code2, label: 'LeetCode' },
  { to: '/profile', icon: User, label: 'Profile' },
]

export default function Sidebar() {
  return (
    <aside className="w-60 flex-shrink-0 h-screen flex flex-col glass border-r border-white/10">
      <div className="px-5 py-5 border-b border-white/10">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand flex items-center justify-center shadow-lg shadow-brand/30">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-white leading-none">AI Workflow</p>
            <p className="text-xs text-slate-500 mt-0.5">Automation Platform</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {nav.map(({ to, icon: Icon, label, disabled }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150',
                isActive
                  ? 'bg-brand/20 text-brand font-medium border border-brand/30'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-white/5',
                disabled && 'pointer-events-none opacity-40'
              )
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-white/10">
        <p className="text-xs text-slate-600">Phase 3 — React SPA</p>
      </div>
    </aside>
  )
}
