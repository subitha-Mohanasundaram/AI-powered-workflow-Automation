import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Sparkles, Check, Edit3 } from 'lucide-react'
import { workflowsApi } from '../api/workflows'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Card, { CardHeader, CardTitle } from '../components/ui/Card'
import Spinner from '../components/ui/Spinner'
import FlowCanvas from '../components/workflow/FlowCanvas'

function stepsToFlow(steps = []) {
  const nodes = steps.map((step, i) => ({
    id: `step_${i}`,
    type: 'workflowNode',
    position: { x: 250, y: i * 140 },
    data: {
      label: step.name || step.action_type,
      action_type: step.action_type,
      description: step.description,
      step_number: i,
      status: 'pending',
    },
  }))
  const edges = steps.slice(1).map((_, i) => ({
    id: `e_${i}`,
    source: `step_${i}`,
    target: `step_${i + 1}`,
    type: 'workflowEdge',
  }))
  return { nodes, edges }
}

export default function WorkflowCreatorPage() {
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState('')
  const [generated, setGenerated] = useState(null)

  const generateMutation = useMutation({
    mutationFn: (p) => workflowsApi.create({ prompt: p }).then(r => r.data),
    onSuccess: (data) => setGenerated(data),
  })

  const runMutation = useMutation({
    mutationFn: (id) => workflowsApi.run(id).then(r => r.data),
    onSuccess: (data) => {
      if (data?.run_id) navigate(`/runs/${data.run_id}`)
    },
  })

  const steps = generated?.steps || []
  const { nodes, edges } = stepsToFlow(steps)

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Create Workflow</h1>
        <p className="text-slate-400 text-sm mt-0.5">Describe your automation in natural language</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-brand" /> Natural Language Input
          </CardTitle>
        </CardHeader>
        <div className="space-y-4">
          <Input
            textarea
            placeholder="e.g. Every morning at 8am, check the top 3 Python repos on GitHub and email me a summary with the stars count and description..."
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            className="min-h-[120px]"
          />
          <Button
            onClick={() => generateMutation.mutate(prompt)}
            disabled={!prompt.trim()}
            loading={generateMutation.isPending}
          >
            <Sparkles className="w-4 h-4" /> Generate Workflow
          </Button>
        </div>
        {generateMutation.error && (
          <p className="text-sm text-red-400 mt-3 bg-red-500/10 rounded-lg px-3 py-2">
            {generateMutation.error.response?.data?.detail || 'Generation failed'}
          </p>
        )}
      </Card>

      {generateMutation.isPending && (
        <div className="flex flex-col items-center gap-3 py-12">
          <Spinner size="lg" />
          <p className="text-slate-400">Generating your workflow with AI...</p>
        </div>
      )}

      {generated && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Generated: {generated.name}</CardTitle>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => navigate(`/workflows/${generated.id}/edit`)}
                >
                  <Edit3 className="w-3.5 h-3.5" /> Edit
                </Button>
                <Button
                  size="sm"
                  onClick={() => runMutation.mutate(generated.id)}
                  loading={runMutation.isPending}
                >
                  <Check className="w-3.5 h-3.5" /> Approve & Run
                </Button>
              </div>
            </CardHeader>
            {generated.description && (
              <p className="text-sm text-slate-400 mb-4">{generated.description}</p>
            )}
            <div className="text-xs text-slate-500 mb-3">{steps.length} steps generated</div>
          </Card>

          {steps.length > 0 && (
            <Card className="p-0 overflow-hidden">
              <div style={{ height: Math.max(400, steps.length * 140 + 100) }}>
                <FlowCanvas initialNodes={nodes} initialEdges={edges} readOnly />
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
