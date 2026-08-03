import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Play, CheckCircle, XCircle, Calendar, Zap, Plus } from 'lucide-react'
import { runsApi } from '../api/runs'
import { workflowsApi } from '../api/workflows'
import Card, { CardHeader, CardTitle } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import RunCard from '../components/runs/RunCard'
import Spinner from '../components/ui/Spinner'

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <Card className="flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-white">{value ?? '—'}</p>
        <p className="text-xs text-slate-400">{label}</p>
      </div>
    </Card>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState('')

  const { data: runs, isLoading: runsLoading } = useQuery({
    queryKey: ['runs', { limit: 10 }],
    queryFn: () => runsApi.list({ limit: 10 }).then(r => r.data),
    refetchInterval: 15_000,
  })

  const { data: workflows } = useQuery({
    queryKey: ['workflows', { limit: 1 }],
    queryFn: () => workflowsApi.list({ limit: 100 }).then(r => r.data),
  })

  const quickRunMutation = useMutation({
    mutationFn: () => workflowsApi.generate(prompt).then(r => r.data),
    onSuccess: (data) => {
      if (data?.id) navigate(`/workflows/${data.id}/edit`)
    },
  })

  const runList = Array.isArray(runs) ? runs : runs?.items || []
  const totalRuns = runList.length
  const successRuns = runList.filter(r => r.status === 'success' || r.status === 'completed').length
  const failedRuns = runList.filter(r => r.status === 'failed').length
  const successRate = totalRuns > 0 ? Math.round((successRuns / totalRuns) * 100) : 0

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-0.5">Overview of your automation platform</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Play} label="Total Runs" value={totalRuns} color="bg-brand" />
        <StatCard icon={CheckCircle} label="Success Rate" value={`${successRate}%`} color="bg-emerald-600" />
        <StatCard icon={XCircle} label="Failed Runs" value={failedRuns} color="bg-red-600" />
        <StatCard icon={Calendar} label="Workflows" value={Array.isArray(workflows) ? workflows.length : workflows?.total || 0} color="bg-violet-600" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-brand" /> Quick Create Workflow
          </CardTitle>
        </CardHeader>
        <div className="flex gap-3">
          <Input
            className="flex-1"
            placeholder="Describe what you want to automate..."
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && prompt && quickRunMutation.mutate()}
          />
          <Button
            onClick={() => quickRunMutation.mutate()}
            disabled={!prompt}
            loading={quickRunMutation.isPending}
          >
            <Plus className="w-4 h-4" /> Create
          </Button>
        </div>
        {quickRunMutation.error && (
          <p className="text-xs text-red-400 mt-2">
            {quickRunMutation.error.response?.data?.detail || 'Failed to generate workflow'}
          </p>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Runs</CardTitle>
          <Button variant="ghost" size="sm" onClick={() => navigate('/workflows')}>
            View all
          </Button>
        </CardHeader>
        {runsLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : runList.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-8">No runs yet. Create a workflow to get started.</p>
        ) : (
          <div className="space-y-2">
            {runList.slice(0, 8).map(run => <RunCard key={run.id} run={run} />)}
          </div>
        )}
      </Card>
    </div>
  )
}
