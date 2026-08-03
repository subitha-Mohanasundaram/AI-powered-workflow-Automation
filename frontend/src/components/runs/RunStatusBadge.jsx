import Badge from '../ui/Badge'
import { CheckCircle, XCircle, Clock, Loader2 } from 'lucide-react'

const config = {
  success: { color: 'success', icon: CheckCircle, label: 'Success' },
  completed: { color: 'success', icon: CheckCircle, label: 'Completed' },
  failed: { color: 'failed', icon: XCircle, label: 'Failed' },
  running: { color: 'running', icon: Loader2, label: 'Running' },
  pending: { color: 'pending', icon: Clock, label: 'Pending' },
  scheduled: { color: 'scheduled', icon: Clock, label: 'Scheduled' },
}

export default function RunStatusBadge({ status }) {
  const cfg = config[status] || config.pending
  const Icon = cfg.icon
  return (
    <Badge color={cfg.color}>
      <Icon className={`w-3 h-3 ${status === 'running' ? 'animate-spin' : ''}`} />
      {cfg.label}
    </Badge>
  )
}
