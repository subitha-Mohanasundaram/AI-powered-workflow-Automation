import { useCallback, useRef } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap,
  addEdge, useNodesState, useEdgesState,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import WorkflowNode from './WorkflowNode'
import WorkflowEdge from './WorkflowEdge'

const nodeTypes = { workflowNode: WorkflowNode }
const edgeTypes = { workflowEdge: WorkflowEdge }

let idCounter = 100

export default function FlowCanvas({
  initialNodes = [],
  initialEdges = [],
  onNodesChange: onNodesChangeProp,
  onEdgesChange: onEdgesChangeProp,
  onNodeClick,
  readOnly = false,
}) {
  const reactFlowWrapper = useRef(null)
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  const onConnect = useCallback(
    (params) => setEdges(eds => addEdge({ ...params, type: 'workflowEdge' }, eds)),
    [setEdges]
  )

  const onDragOver = useCallback((e) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    const type = e.dataTransfer.getData('application/reactflow')
    if (!type) return

    const bounds = reactFlowWrapper.current.getBoundingClientRect()
    const position = {
      x: e.clientX - bounds.left - 90,
      y: e.clientY - bounds.top - 30,
    }

    const id = `node_${++idCounter}`
    const newNode = {
      id,
      type: 'workflowNode',
      position,
      data: {
        label: type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        action_type: type,
        status: 'pending',
      },
    }
    setNodes(ns => [...ns, newNode])
  }, [setNodes])

  return (
    <div ref={reactFlowWrapper} className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={readOnly ? undefined : onConnect}
        onDrop={readOnly ? undefined : onDrop}
        onDragOver={readOnly ? undefined : onDragOver}
        onNodeClick={(_, node) => onNodeClick?.(node)}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        nodesDraggable={!readOnly}
        nodesConnectable={!readOnly}
        elementsSelectable={!readOnly}
        style={{ background: 'transparent' }}
      >
        <Background variant={BackgroundVariant.Dots} color="#1e293b" gap={20} />
        <Controls className="!bg-surface !border-white/10 !rounded-lg" />
        <MiniMap
          nodeColor={(n) => {
            const s = n.data?.status
            return s === 'success' ? '#10b981' : s === 'failed' ? '#ef4444' : s === 'running' ? '#14b8a6' : '#334155'
          }}
          style={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)' }}
        />
      </ReactFlow>
    </div>
  )
}
