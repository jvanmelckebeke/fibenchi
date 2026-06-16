import { NoteEditor } from "@/components/note-editor"
import type { Note } from "@/lib/api"
import type { UseMutationResult } from "@tanstack/react-query"

interface ConnectedNoteProps {
  note: Note | undefined
  updateMutation: UseMutationResult<Note, Error, string>
}

export function ConnectedNote({ note, updateMutation }: ConnectedNoteProps) {
  return (
    <NoteEditor
      note={note}
      onSave={(content) => updateMutation.mutate(content)}
      isSaving={updateMutation.isPending}
    />
  )
}
