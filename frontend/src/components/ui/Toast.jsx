import { useState, useEffect, createContext, useContext, useCallback } from 'react'
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'

const ToastContext = createContext(null)

const icons = {
  success: <CheckCircle className="w-4 h-4 text-emerald-400" />,
  error: <AlertCircle className="w-4 h-4 text-red-400" />,
  info: <Info className="w-4 h-4 text-brand" />,
  warning: <AlertTriangle className="w-4 h-4 text-amber-400" />,
}

const colors = {
  success: 'border-emerald-500/30',
  error: 'border-red-500/30',
  info: 'border-brand/30',
  warning: 'border-amber-500/30',
}

function ToastItem({ toast, onRemove }) {
  useEffect(() => {
    const t = setTimeout(() => onRemove(toast.id), toast.duration || 4000)
    return () => clearTimeout(t)
  }, [toast.id, toast.duration, onRemove])

  return (
    <div className={clsx('glass rounded-lg px-4 py-3 flex items-start gap-3 shadow-xl border min-w-[280px] max-w-sm', colors[toast.type] || colors.info)}>
      {icons[toast.type] || icons.info}
      <div className="flex-1 text-sm text-slate-200">{toast.message}</div>
      <button onClick={() => onRemove(toast.id)} className="text-slate-500 hover:text-slate-300">
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const add = useCallback((message, type = 'info', duration = 4000) => {
    const id = Date.now()
    setToasts(t => [...t, { id, message, type, duration }])
  }, [])

  const remove = useCallback((id) => {
    setToasts(t => t.filter(x => x.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ add }}>
      {children}
      <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-50">
        {toasts.map(t => <ToastItem key={t.id} toast={t} onRemove={remove} />)}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be inside ToastProvider')
  return {
    toast: ctx.add,
    success: (msg) => ctx.add(msg, 'success'),
    error: (msg) => ctx.add(msg, 'error'),
    info: (msg) => ctx.add(msg, 'info'),
    warning: (msg) => ctx.add(msg, 'warning'),
  }
}
