import { BaseEdge, EdgeLabelRenderer, getStraightPath } from '@xyflow/react'

export default function WorkflowEdge({
  id, sourceX, sourceY, targetX, targetY, label, selected
}) {
  const [edgePath, labelX, labelY] = getStraightPath({
    sourceX, sourceY, targetX, targetY,
  })

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: selected ? '#5eead4' : '#14b8a6',
          strokeWidth: selected ? 2.5 : 1.5,
          strokeDasharray: '4 2',
        }}
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
            }}
            className="absolute bg-surface-dark text-xs text-brand px-2 py-0.5 rounded border border-brand/30"
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}
