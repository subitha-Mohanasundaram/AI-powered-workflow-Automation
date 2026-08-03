import clsx from 'clsx'

export default function Card({ children, className, onClick, hover }) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        'glass rounded-xl p-4',
        hover && 'hover:border-brand/30 transition-all duration-200 cursor-pointer hover:shadow-lg hover:shadow-brand/10',
        className
      )}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className }) {
  return (
    <div className={clsx('flex items-center justify-between mb-3', className)}>
      {children}
    </div>
  )
}

export function CardTitle({ children, className }) {
  return (
    <h3 className={clsx('text-sm font-semibold text-slate-200', className)}>
      {children}
    </h3>
  )
}
