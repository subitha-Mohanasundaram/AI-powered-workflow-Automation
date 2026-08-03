import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Calendar, Plus, Pause, Play, Trash2 } from 'lucide-react'
import client from '../api/client'
import Card, { CardHeader, CardTitle } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Spinner from '../components/ui/Spinner'
import EmptyState from '../components/ui/EmptyState'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'

export default function ScheduledPage() {
  const qc = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState({ workflow_id: '', cron: '', name: '' })

  const { data, isLoading } = useQuery({
    queryKey: ['scheduled'],
    queryFn: () => client.get('/api/scheduled').then(r => r.data),
    refetchInterval: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: (d) => client.post('/api/scheduled', d).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scheduled'] }); setCreateOpen(false) },
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, paused }) =>
      client.post(`/api/scheduled/${id}/${paused ? 'resume' : 'pause'}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduled'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => client.delete(`/api/scheduled/${id}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduled'] }),
  })

  const schedules = Array.isArray(data) ? data : data?.items || []

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Scheduled Workflows</h1>
          <p className="text-slate-400 text-sm mt-0.5">{schedules.length} active schedules</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="w-4 h-4" /> New Schedule
        </Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : schedules.length === 0 ? (
        <EmptyState
          icon={Calendar}
          title="No schedules yet"
          description="Automate your workflows on a cron schedule"
          action={<Button onClick={() => setCreateOpen(true)}><Plus className="w-4 h-4" /> Create Schedule</Button>}
        />
      ) : (
        <div className="space-y-3">
          {schedules.map(s => (
            <Card key={s.id} className="flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <p className="font-medium text-slate-100">{s.name || s.workflow_name || s.workflow_id}</p>
                  <Badge color={s.paused || s.is_paused ? 'pending' : 'success'}>
                    {s.paused || s.is_paused ? 'Paused' : 'Active'}
                  </Badge>
                </div>
                <p className="text-sm text-slate-500 font-mono">{s.cron_expression || s.cron}</p>
                {s.next_run && (
                  <p className="text-xs text-slate-600 mt-0.5">
                    Next: {new Date(s.next_run).toLocaleString()}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost" size="sm"
                  onClick={() => toggleMutation.mutate({ id: s.id, paused: s.paused || s.is_paused })}
                >
                  {s.paused || s.is_paused
                    ? <><Play className="w-4 h-4" /> Resume</>
                    : <><Pause className="w-4 h-4" /> Pause</>}
                </Button>
                <Button
                  variant="ghost" size="sm"
                  onClick={() => confirm('Delete this schedule?') && deleteMutation.mutate(s.id)}
                  className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New Schedule">
        <div className="space-y-4">
          <Input
            label="Workflow ID"
            placeholder="workflow-id"
            value={form.workflow_id}
            onChange={e => setForm({ ...form, workflow_id: e.target.value })}
          />
          <Input
            label="Cron Expression"
            placeholder="0 8 * * * (every day at 8am)"
            value={form.cron}
            onChange={e => setForm({ ...form, cron: e.target.value })}
          />
          <Input
            label="Name (optional)"
            value={form.name}
            onChange={e => setForm({ ...form, name: e.target.value })}
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              onClick={() => createMutation.mutate(form)}
              loading={createMutation.isPending}
              disabled={!form.workflow_id || !form.cron}
            >
              Create
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
