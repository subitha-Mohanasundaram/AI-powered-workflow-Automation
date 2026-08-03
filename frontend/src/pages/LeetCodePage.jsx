import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Code2, Play, RefreshCw, CheckCircle, XCircle, Clock } from 'lucide-react'
import client from '../api/client'
import Card, { CardHeader, CardTitle } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Badge from '../components/ui/Badge'
import Spinner from '../components/ui/Spinner'

const DIFFICULTIES = ['Easy', 'Medium', 'Hard']

export default function LeetCodePage() {
  const [username, setUsername] = useState('')
  const [difficulty, setDifficulty] = useState('Medium')
  const [topic, setTopic] = useState('')
  const [result, setResult] = useState(null)

  const { data: history, isLoading: histLoading } = useQuery({
    queryKey: ['leetcode-history'],
    queryFn: () => client.get('/api/v1/leetcode/history').then(r => r.data),
    retry: false,
  })

  const solveMutation = useMutation({
    mutationFn: (payload) => client.post('/api/v1/leetcode/solve', payload).then(r => r.data),
    onSuccess: setResult,
  })

  const fetchMutation = useMutation({
    mutationFn: (u) => client.get(`/api/v1/leetcode/user/${u}`).then(r => r.data),
    onSuccess: setResult,
  })

  const histList = Array.isArray(history) ? history : history?.items || []

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Code2 className="w-6 h-6 text-brand" /> LeetCode Assistant
        </h1>
        <p className="text-slate-400 text-sm mt-0.5">AI-powered LeetCode problem solver and stats tracker</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Solve a Problem</CardTitle>
          </CardHeader>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-slate-400 block mb-1.5">Difficulty</label>
              <div className="flex gap-2">
                {DIFFICULTIES.map(d => (
                  <button
                    key={d}
                    onClick={() => setDifficulty(d)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                      difficulty === d
                        ? 'bg-brand text-white border-brand'
                        : 'border-slate-700 text-slate-400 hover:border-brand/50'
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
            <Input
              label="Topic (optional)"
              placeholder="arrays, trees, dynamic programming..."
              value={topic}
              onChange={e => setTopic(e.target.value)}
            />
            <Button
              onClick={() => solveMutation.mutate({ difficulty, topic })}
              loading={solveMutation.isPending}
              className="w-full justify-center"
            >
              <Play className="w-4 h-4" /> Get Problem
            </Button>
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Fetch User Stats</CardTitle>
          </CardHeader>
          <div className="space-y-3">
            <Input
              label="LeetCode Username"
              placeholder="your-username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && username && fetchMutation.mutate(username)}
            />
            <Button
              onClick={() => fetchMutation.mutate(username)}
              loading={fetchMutation.isPending}
              disabled={!username}
              variant="secondary"
              className="w-full justify-center"
            >
              <RefreshCw className="w-4 h-4" /> Fetch Stats
            </Button>
          </div>
        </Card>
      </div>

      {(solveMutation.isPending || fetchMutation.isPending) && (
        <div className="flex justify-center py-8"><Spinner size="lg" /></div>
      )}

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Result</CardTitle>
          </CardHeader>
          <pre className="text-sm text-slate-300 bg-black/30 rounded-lg p-4 overflow-x-auto whitespace-pre-wrap break-all">
            {typeof result === 'object' ? JSON.stringify(result, null, 2) : String(result)}
          </pre>
        </Card>
      )}

      {(solveMutation.error || fetchMutation.error) && (
        <Card className="border-red-500/30">
          <p className="text-sm text-red-400">
            {(solveMutation.error || fetchMutation.error)?.response?.data?.detail || 'Request failed'}
          </p>
        </Card>
      )}

      {histList.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recent History</CardTitle>
          </CardHeader>
          <div className="space-y-2">
            {histList.slice(0, 10).map((h, i) => (
              <div key={i} className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0">
                {h.solved
                  ? <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  : h.status === 'failed'
                  ? <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  : <Clock className="w-4 h-4 text-slate-500 flex-shrink-0" />}
                <span className="text-sm text-slate-300 flex-1 truncate">{h.problem || h.title || h.query}</span>
                <Badge color={h.difficulty === 'Easy' ? 'success' : h.difficulty === 'Hard' ? 'failed' : 'warning'}>
                  {h.difficulty || '—'}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
