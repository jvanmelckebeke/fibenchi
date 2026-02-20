import { ThesisEditor } from "@/components/thesis-editor"
import type { Thesis } from "@/lib/api"
import type { UseMutationResult } from "@tanstack/react-query"

interface ConnectedThesisProps {
  thesis: Thesis | undefined
  updateMutation: UseMutationResult<Thesis, Error, string>
}

export function ConnectedThesis({ thesis, updateMutation }: ConnectedThesisProps) {
  return (
    <ThesisEditor
      thesis={thesis}
      onSave={(content) => updateMutation.mutate(content)}
      isSaving={updateMutation.isPending}
    />
  )
}
