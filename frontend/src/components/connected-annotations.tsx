import { AnnotationsList } from "@/components/annotations-list"
import type { Annotation, AnnotationCreate } from "@/lib/api"
import type { UseMutationResult } from "@tanstack/react-query"

interface ConnectedAnnotationsProps {
  annotations: Annotation[] | undefined
  createMutation: UseMutationResult<Annotation, Error, AnnotationCreate>
  deleteMutation: UseMutationResult<void, Error, number>
}

export function ConnectedAnnotations({
  annotations,
  createMutation,
  deleteMutation,
}: ConnectedAnnotationsProps) {
  return (
    <AnnotationsList
      annotations={annotations}
      onCreate={(data) => createMutation.mutate(data)}
      onDelete={(id) => deleteMutation.mutate(id)}
      isCreating={createMutation.isPending}
    />
  )
}
