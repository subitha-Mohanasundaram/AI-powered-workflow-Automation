import clsx from 'clsx'

const variants = {
  primary: 'bg-brand hover:bg-brand-dark text-white shadow-lg hover:shadow-brand/30',
  secondary: 'bg-surface-light hover:bg-slate-600 text-slate-200 border border-slate-600',
  danger: 'bg-red-600 hover:bg-red-700 text-white',
  ghost: 'hover:bg-surface-light text-slate-300 hover:text-white',
  outline: 'border border-brand text-brand hover:bg-brand hover:text-white',
}

const sizes = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  className,
  disabled,
  loading,
  ...props
}) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center gap-2 rounded-lg font-medium transition-all duration-150',
        'focus:outline-none focus:ring-2 focus:ring-brand/50',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className
      )}
    >
      {loading && (
        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      )}
      {children}
    </button>
  )
}
