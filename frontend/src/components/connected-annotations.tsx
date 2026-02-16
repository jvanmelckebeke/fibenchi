import { AnnotationsList } from "@/components/annotations-list"
import type { Annotation, AnnotationCreate } from "@/lib/api"
import type { UseQueryResult, UseMutationResult } from "@tanstack/react-query"

interface ConnectedAnnotationsProps {
  useAnnotationsQuery: () => UseQueryResult<Annotation[]>
  useCreateMutation: () => UseMutationResult<Annotation, Error, AnnotationCreate>
  useDeleteMutation: () => UseMutationResult<void, Error, number>
}

export function ConnectedAnnotations({
  useAnnotationsQuery,
  useCreateMutation,
  useDeleteMutation,
}: ConnectedAnnotationsProps) {
  const { data: annotations } = useAnnotationsQuery()
  const createAnnotation = useCreateMutation()
  const deleteAnnotation = useDeleteMutation()

  return (
    <AnnotationsList
      annotations={annotations}
      onCreate={(data) => createAnnotation.mutate(data)}
      onDelete={(id) => deleteAnnotation.mutate(id)}
      isCreating={createAnnotation.isPending}
    />
  )
}
