import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Plus, Edit3, Play, Trash2, Workflow } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { useWorkflows, useDeleteWorkflow } from '../hooks/useWorkflows'
import { workflowsApi } from '../api/workflows'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Badge from '../components/ui/Badge'
import Spinner from '../components/ui/Spinner'
import EmptyState from '../components/ui/EmptyState'

export default function WorkflowLibraryPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const { data, isLoading } = useWorkflows()
  const deleteMutation = useDeleteWorkflow()

  const runMutation = useMutation({
    mutationFn: (id) => workflowsApi.run(id).then(r => r.data),
    onSuccess: (data) => { if (data?.run_id) navigate(`/runs/${data.run_id}`) },
  })

  const workflows = Array.isArray(data) ? data : data?.items || []
  const filtered = workflows.filter(w =>
    !search || w.name?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Workflows</h1>
          <p className="text-slate-400 text-sm mt-0.5">{workflows.length} workflows</p>
        </div>
        <Button onClick={() => navigate('/workflows/new')}>
          <Plus className="w-4 h-4" /> New Workflow
        </Button>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <Input
          className="pl-9"
          placeholder="Search workflows..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Workflow}
          title="No workflows found"
          description={search ? 'Try a different search term' : 'Create your first workflow to get started'}
          action={!search && <Button onClick={() => navigate('/workflows/new')}><Plus className="w-4 h-4" /> Create Workflow</Button>}
        />
      ) : (
        <div className="grid gap-3">
          {filtered.map(w => (
            <Card key={w.id} className="flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <p className="font-medium text-slate-100 truncate">{w.name}</p>
                  {w.is_active !== undefined && (
                    <Badge color={w.is_active ? 'success' : 'default'}>
                      {w.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  )}
                </div>
                {w.description && (
                  <p className="text-sm text-slate-500 truncate">{w.description}</p>
                )}
                <p className="text-xs text-slate-600 mt-1">
                  {w.steps?.length || 0} steps
                  {w.last_run_at && ` · Last run ${new Date(w.last_run_at).toLocaleDateString()}`}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate(`/workflows/${w.id}/edit`)}
                >
                  <Edit3 className="w-4 h-4" />
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => runMutation.mutate(w.id)}
                  loading={runMutation.isPending && runMutation.variables === w.id}
                >
                  <Play className="w-4 h-4" /> Run
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (confirm(`Delete "${w.name}"?`)) deleteMutation.mutate(w.id)
                  }}
                  className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
