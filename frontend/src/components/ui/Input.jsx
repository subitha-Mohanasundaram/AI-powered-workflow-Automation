import clsx from 'clsx'

export default function Input({
  label,
  error,
  className,
  textarea,
  ...props
}) {
  const base = clsx(
    'w-full rounded-lg bg-surface-dark border border-slate-700 text-slate-100',
    'px-3 py-2 text-sm placeholder:text-slate-500',
    'focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50',
    'transition-colors duration-150',
    error && 'border-red-500 focus:ring-red-500/50',
    className
  )

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-sm font-medium text-slate-300">{label}</label>
      )}
      {textarea ? (
        <textarea className={clsx(base, 'resize-y min-h-[80px]')} {...props} />
      ) : (
        <input className={base} {...props} />
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}
