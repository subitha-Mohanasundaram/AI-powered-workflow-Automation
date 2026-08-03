import clsx from 'clsx'

const colors = {
  success: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  running: 'bg-brand/20 text-brand border-brand/30',
  pending: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  scheduled: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
  warning: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  default: 'bg-slate-700/50 text-slate-300 border-slate-600/30',
}

export default function Badge({ children, color = 'default', className }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border',
        colors[color] || colors.default,
        className
      )}
    >
      {children}
    </span>
  )
}
