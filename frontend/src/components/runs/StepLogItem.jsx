import { CheckCircle, XCircle, Loader2, Clock } from 'lucide-react'
import clsx from 'clsx'

const icons = {
  success: <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />,
  completed: <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />,
  failed: <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />,
  running: <Loader2 className="w-4 h-4 text-brand flex-shrink-0 animate-spin" />,
  pending: <Clock className="w-4 h-4 text-slate-500 flex-shrink-0" />,
}

export default function StepLogItem({ step, index }) {
  const { step_name, action_type, status, output, error, duration_ms } = step

  return (
    <div
      className={clsx(
        'flex gap-3 p-3 rounded-lg border text-sm',
        status === 'success' || status === 'completed'
          ? 'bg-emerald-500/5 border-emerald-500/20'
          : status === 'failed'
          ? 'bg-red-500/5 border-red-500/20'
          : status === 'running'
          ? 'bg-brand/5 border-brand/20'
          : 'bg-surface border-white/5'
      )}
    >
      {icons[status] || icons.pending}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-1">
          <span className="font-medium text-slate-200">
            {index !== undefined ? `${index + 1}. ` : ''}{step_name || action_type}
          </span>
          {duration_ms !== undefined && (
            <span className="text-xs text-slate-500 flex-shrink-0">{duration_ms}ms</span>
          )}
        </div>
        {output && (
          <pre className="text-xs text-slate-400 bg-black/30 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all mt-1">
            {typeof output === 'object' ? JSON.stringify(output, null, 2) : String(output)}
          </pre>
        )}
        {error && (
          <p className="text-xs text-red-400 mt-1">{error}</p>
        )}
      </div>
    </div>
  )
}
