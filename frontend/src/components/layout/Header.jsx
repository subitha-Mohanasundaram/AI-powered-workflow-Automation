import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, User, Settings, ChevronDown } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { aiApi } from '../../api/ai'
import useAuthStore from '../../store/authStore'

function AIStatusPill() {
  const { data } = useQuery({
    queryKey: ['ai-status'],
    queryFn: () => aiApi.status().then(r => r.data),
    refetchInterval: 30_000,
    retry: false,
  })

  const ok = data?.status === 'available' || data?.available
  return (
    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border ${
      ok ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
         : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-emerald-400' : 'bg-amber-400'} animate-pulse`} />
      AI {ok ? 'Online' : 'Offline'}
    </div>
  )
}

export default function Header() {
  const [open, setOpen] = useState(false)
  const user = useAuthStore(s => s.user)
  const logout = useAuthStore(s => s.logout)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="h-14 flex items-center justify-between px-6 glass border-b border-white/10 flex-shrink-0">
      <div className="flex items-center gap-3">
        <AIStatusPill />
      </div>

      <div className="relative">
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors text-sm text-slate-300"
        >
          <div className="w-7 h-7 rounded-full bg-brand/30 flex items-center justify-center text-brand text-xs font-bold">
            {user?.email?.[0]?.toUpperCase() || 'U'}
          </div>
          <span className="hidden sm:block">{user?.display_name || user?.email || 'User'}</span>
          <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
        </button>

        {open && (
          <div className="absolute right-0 top-full mt-1 w-44 glass rounded-lg shadow-xl border border-white/10 py-1 z-50">
            <button
              onClick={() => { navigate('/profile'); setOpen(false) }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:text-white hover:bg-white/5"
            >
              <User className="w-4 h-4" /> Profile
            </button>
            <div className="h-px bg-white/10 my-1" />
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10"
            >
              <LogOut className="w-4 h-4" /> Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
