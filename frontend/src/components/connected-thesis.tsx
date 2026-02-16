import { ThesisEditor } from "@/components/thesis-editor"
import type { Thesis } from "@/lib/api"
import type { UseQueryResult, UseMutationResult } from "@tanstack/react-query"

interface ConnectedThesisProps {
  useThesisQuery: () => UseQueryResult<Thesis>
  useUpdateMutation: () => UseMutationResult<Thesis, Error, string>
}

export function ConnectedThesis({ useThesisQuery, useUpdateMutation }: ConnectedThesisProps) {
  const { data: thesis } = useThesisQuery()
  const updateThesis = useUpdateMutation()

  return (
    <ThesisEditor
      thesis={thesis}
      onSave={(content) => updateThesis.mutate(content)}
      isSaving={updateThesis.isPending}
    />
  )
}
