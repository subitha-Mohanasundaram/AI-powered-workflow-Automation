import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Save, Play, ArrowLeft, Settings } from 'lucide-react'
import { useWorkflow, useUpdateWorkflow, useRunWorkflow } from '../hooks/useWorkflows'
import FlowCanvas from '../components/workflow/FlowCanvas'
import StepPalette from '../components/workflow/StepPalette'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Spinner from '../components/ui/Spinner'
import Card from '../components/ui/Card'

function NodeInspector({ node, onClose, onChange }) {
  if (!node) return null
  const d = node.data

  return (
    <div className="w-64 flex-shrink-0 glass border-l border-white/10 flex flex-col overflow-y-auto">
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Inspector</h3>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-xs">✕</button>
      </div>
      <div className="p-4 space-y-3">
        <Input
          label="Name"
          value={d.label || ''}
          onChange={e => onChange({ ...d, label: e.target.value })}
          size="sm"
        />
        <Input
          label="Description"
          textarea
          value={d.description || ''}
          onChange={e => onChange({ ...d, description: e.target.value })}
          className="min-h-[60px]"
        />
        <div>
          <label className="text-xs font-medium text-slate-400 block mb-1">Action Type</label>
          <p className="text-sm text-brand">{d.action_type || '—'}</p>
        </div>
        {d.params && (
          <div>
            <label className="text-xs font-medium text-slate-400 block mb-1">Parameters</label>
            <pre className="text-xs text-slate-400 bg-black/20 rounded p-2 overflow-x-auto">
              {JSON.stringify(d.params, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}

export default function WorkflowEditorPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data: workflow, isLoading } = useWorkflow(id)
  const updateMutation = useUpdateWorkflow(id)
  const runMutation = useRunWorkflow()
  const [selectedNode, setSelectedNode] = useState(null)
  const [name, setName] = useState('')
  const [showNameEdit, setShowNameEdit] = useState(false)
  const [nodes, setNodes] = useState([])
  const [edges, setEdges] = useState([])

  useEffect(() => {
    if (workflow) {
      setName(workflow.name || '')
      const steps = workflow.steps || []
      setNodes(steps.map((s, i) => ({
        id: s.id || `step_${i}`,
        type: 'workflowNode',
        position: s.position || { x: 250, y: i * 140 },
        data: { label: s.name, action_type: s.action_type, description: s.description, step_number: i, status: 'pending' },
      })))
      setEdges(steps.slice(1).map((_, i) => ({
        id: `e_${i}`, source: steps[i].id || `step_${i}`, target: steps[i + 1].id || `step_${i + 1}`, type: 'workflowEdge',
      })))
    }
  }, [workflow])

  const handleSave = () => {
    const steps = nodes.map((n, i) => ({
      id: n.id, name: n.data.label, action_type: n.data.action_type,
      description: n.data.description, position: n.position, order: i,
    }))
    updateMutation.mutate({ name, steps })
  }

  const handleRun = async () => {
    const result = await runMutation.mutateAsync({ id })
    if (result?.run_id) navigate(`/runs/${result.run_id}`)
  }

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>

  return (
    <div className="flex flex-col h-full -m-6">
      <div className="flex items-center justify-between px-6 py-3 glass border-b border-white/10 flex-shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/workflows')} className="text-slate-400 hover:text-white">
            <ArrowLeft className="w-5 h-5" />
          </button>
          {showNameEdit ? (
            <Input value={name} onChange={e => setName(e.target.value)} onBlur={() => setShowNameEdit(false)} className="w-64" />
          ) : (
            <button onClick={() => setShowNameEdit(true)} className="flex items-center gap-2 text-white font-semibold hover:text-brand">
              {name || 'Untitled Workflow'} <Settings className="w-3.5 h-3.5 text-slate-500" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={handleSave} loading={updateMutation.isPending}>
            <Save className="w-4 h-4" /> Save
          </Button>
          <Button size="sm" onClick={handleRun} loading={runMutation.isPending}>
            <Play className="w-4 h-4" /> Run
          </Button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <StepPalette />
        <div className="flex-1 relative">
          <FlowCanvas
            initialNodes={nodes}
            initialEdges={edges}
            onNodeClick={setSelectedNode}
          />
        </div>
        {selectedNode && (
          <NodeInspector
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
            onChange={(data) => setNodes(ns => ns.map(n => n.id === selectedNode.id ? { ...n, data } : n))}
          />
        )}
      </div>
    </div>
  )
}
