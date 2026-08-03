import { Handle, Position } from '@xyflow/react'
import {
  Globe, Mail, Code2, Bell, Clock, Database, Zap, FileText, Search, BarChart2
} from 'lucide-react'
import clsx from 'clsx'

const actionIcons = {
  http_request: Globe,
  send_email: Mail,
  run_script: Code2,
  send_notification: Bell,
  wait: Clock,
  database_query: Database,
  trigger: Zap,
  parse_data: FileText,
  web_search: Search,
  transform: BarChart2,
}

const statusColors = {
  pending: 'border-slate-600 bg-surface',
  running: 'border-brand bg-brand/10 node-running',
  success: 'border-emerald-500 bg-emerald-500/10',
  failed: 'border-red-500 bg-red-500/10',
}

const statusDots = {
  pending: 'bg-slate-500',
  running: 'bg-brand animate-pulse',
  success: 'bg-emerald-400',
  failed: 'bg-red-400',
}

export default function WorkflowNode({ data, selected }) {
  const { label, action_type, status = 'pending', step_number, description } = data
  const Icon = actionIcons[action_type] || Zap

  return (
    <div
      className={clsx(
        'px-4 py-3 rounded-xl border-2 min-w-[180px] max-w-[220px] glass transition-all duration-200',
        statusColors[status] || statusColors.pending,
        selected && 'ring-2 ring-brand/60'
      )}
    >
      <Handle type="target" position={Position.Top} />

      <div className="flex items-start gap-2.5">
        <div className={clsx(
          'flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-white',
          status === 'running' ? 'bg-brand' :
          status === 'success' ? 'bg-emerald-500' :
          status === 'failed' ? 'bg-red-500' : 'bg-slate-700'
        )}>
          <Icon className="w-4 h-4" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            {step_number !== undefined && (
              <span className="text-xs text-brand font-bold">#{step_number + 1}</span>
            )}
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${statusDots[status] || statusDots.pending}`}
            />
          </div>
          <p className="text-xs font-semibold text-slate-100 truncate">{label}</p>
          {description && (
            <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{description}</p>
          )}
          <p className="text-xs text-slate-600 mt-0.5 capitalize">{action_type?.replace(/_/g, ' ')}</p>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}
