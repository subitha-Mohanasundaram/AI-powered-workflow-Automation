import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, RefreshCw, AlertTriangle } from 'lucide-react'
import { runsApi } from '../api/runs'
import { useSSE } from '../hooks/useSSE'
import Card, { CardHeader, CardTitle } from '../components/ui/Card'
import Button from '../components/ui/Button'
import RunStatusBadge from '../components/runs/RunStatusBadge'
import StepLogItem from '../components/runs/StepLogItem'
import Spinner from '../components/ui/Spinner'
import FlowCanvas from '../components/workflow/FlowCanvas'

function stepsToFlow(steps = [], stepStatuses = {}) {
  const nodes = steps.map((s, i) => ({
    id: s.id || `step_${i}`,
    type: 'workflowNode',
    position: { x: 250, y: i * 140 },
    data: {
      label: s.name || s.action_type,
      action_type: s.action_type,
      step_number: i,
      status: stepStatuses[s.id] || stepStatuses[i] || 'pending',
    },
  }))
  const edges = steps.slice(1).map((_, i) => ({
    id: `e_${i}`,
    source: steps[i].id || `step_${i}`,
    target: steps[i + 1].id || `step_${i + 1}`,
    type: 'workflowEdge',
  }))
  return { nodes, edges }
}

export default function RunMonitorPage() {
  const { runId } = useParams()
  const navigate = useNavigate()
  const { data: sseData, connected, closed } = useSSE(runId)

  const { data: run, isLoading } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => runsApi.get(runId).then(r => r.data),
    refetchInterval: closed ? false : 3000,
  })

  const { data: logs } = useQuery({
    queryKey: ['run-logs', runId],
    queryFn: () => runsApi.logs(runId).then(r => r.data),
    refetchInterval: closed ? false : 5000,
  })

  const { data: failureReport } = useQuery({
    queryKey: ['run-failure', runId],
    queryFn: () => runsApi.failureReport(runId).then(r => r.data),
    enabled: run?.status === 'failed',
    retry: false,
  })

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  if (!run) return <p className="text-slate-400">Run not found</p>

  const steps = run.workflow?.steps || []
  const stepStatuses = {}
  const logList = Array.isArray(logs) ? logs : logs?.items || []
  logList.forEach(l => { stepStatuses[l.step_id] = l.status })

  const { nodes, edges } = stepsToFlow(steps, stepStatuses)
  const liveSteps = sseData?.steps || []

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-slate-400 hover:text-white">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-white">Run Monitor</h1>
            <RunStatusBadge status={run.status} />
            {!closed && <span className={`w-2 h-2 rounded-full ${connected ? 'bg-brand animate-pulse' : 'bg-amber-400'}`} />}
          </div>
          <p className="text-xs text-slate-500 font-mono mt-0.5">{runId}</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 text-sm">
        <Card>
          <p className="text-slate-500 text-xs mb-1">Started</p>
          <p className="text-slate-200">{run.started_at ? new Date(run.started_at).toLocaleString() : '—'}</p>
        </Card>
        <Card>
          <p className="text-slate-500 text-xs mb-1">Duration</p>
          <p className="text-slate-200">
            {run.completed_at && run.started_at
              ? ((new Date(run.completed_at) - new Date(run.started_at)) / 1000).toFixed(2) + 's'
              : 'Running...'}
          </p>
        </Card>
        <Card>
          <p className="text-slate-500 text-xs mb-1">Steps</p>
          <p className="text-slate-200">{steps.length || liveSteps.length}</p>
        </Card>
      </div>

      {steps.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <div style={{ height: Math.max(300, steps.length * 140 + 80) }}>
            <FlowCanvas initialNodes={nodes} initialEdges={edges} readOnly />
          </div>
        </Card>
      )}

      {(liveSteps.length > 0 || logList.length > 0) && (
        <Card>
          <CardHeader>
            <CardTitle>Execution Log</CardTitle>
            {!closed && <RefreshCw className="w-4 h-4 text-brand animate-spin" />}
          </CardHeader>
          <div className="space-y-2">
            {(liveSteps.length > 0 ? liveSteps : logList).map((step, i) => (
              <StepLogItem key={step.id || i} step={step} index={i} />
            ))}
          </div>
        </Card>
      )}

      {failureReport && (
        <Card className="border-red-500/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-4 h-4" /> Failure Report
            </CardTitle>
          </CardHeader>
          <div className="text-sm text-slate-300 space-y-2">
            {failureReport.summary && <p>{failureReport.summary}</p>}
            {failureReport.failed_step && (
              <p className="text-red-400">Failed at: <span className="font-mono">{failureReport.failed_step}</span></p>
            )}
            {failureReport.suggestion && (
              <p className="text-amber-400 bg-amber-500/10 rounded-lg px-3 py-2">{failureReport.suggestion}</p>
            )}
          </div>
        </Card>
      )}
    </div>
  )
}
