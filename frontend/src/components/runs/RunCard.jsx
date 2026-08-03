import { useNavigate } from 'react-router-dom'
import { Clock, ChevronRight } from 'lucide-react'
import Card from '../ui/Card'
import RunStatusBadge from './RunStatusBadge'

export default function RunCard({ run }) {
  const navigate = useNavigate()

  const duration = run.completed_at && run.started_at
    ? ((new Date(run.completed_at) - new Date(run.started_at)) / 1000).toFixed(1) + 's'
    : run.started_at ? 'running...' : 'queued'

  return (
    <Card
      hover
      onClick={() => navigate(`/runs/${run.id}`)}
      className="flex items-center gap-4"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <p className="text-sm font-medium text-slate-200 truncate">
            {run.workflow_name || run.workflow_id || 'Workflow'}
          </p>
          <RunStatusBadge status={run.status} />
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {duration}
          </span>
          <span>
            {run.started_at
              ? new Date(run.started_at).toLocaleString()
              : 'Not started'}
          </span>
        </div>
      </div>
      <ChevronRight className="w-4 h-4 text-slate-600 flex-shrink-0" />
    </Card>
  )
}
