import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import type { Thesis } from "@/lib/api"

interface ThesisEditorProps {
  thesis: Thesis | undefined
  onSave: (content: string) => void
  isSaving: boolean
}

export function ThesisEditor({ thesis, onSave, isSaving }: ThesisEditorProps) {
  const [editing, setEditing] = useState(false)
  const [content, setContent] = useState("")

  const handleEdit = () => {
    setContent(thesis?.content ?? "")
    setEditing(true)
  }

  const handleSave = () => {
    onSave(content)
    setEditing(false)
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base">Investment Thesis</CardTitle>
        {editing ? (
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave} disabled={isSaving}>
              Save
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="ghost" onClick={handleEdit}>
            Edit
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {editing ? (
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="min-h-[200px] font-mono text-sm"
            placeholder="Write your investment thesis in markdown..."
          />
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none min-h-[100px]">
            {thesis?.content ? (
              <pre className="whitespace-pre-wrap font-sans text-sm">{thesis.content}</pre>
            ) : (
              <p className="text-muted-foreground italic">No thesis yet. Click Edit to write one.</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
