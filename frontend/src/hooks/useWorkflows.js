import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workflowsApi } from '../api/workflows'

export function useWorkflows(params) {
  return useQuery({
    queryKey: ['workflows', params],
    queryFn: () => workflowsApi.list(params).then(r => r.data),
  })
}

export function useWorkflow(id) {
  return useQuery({
    queryKey: ['workflow', id],
    queryFn: () => workflowsApi.get(id).then(r => r.data),
    enabled: !!id,
  })
}

export function useCreateWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => workflowsApi.create(data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workflows'] }),
  })
}

export function useUpdateWorkflow(id) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => workflowsApi.update(id, data).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workflow', id] })
      qc.invalidateQueries({ queryKey: ['workflows'] })
    },
  })
}

export function useDeleteWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id) => workflowsApi.delete(id).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workflows'] }),
  })
}

export function useRunWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, params }) => workflowsApi.run(id, params).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['runs'] }),
  })
}
