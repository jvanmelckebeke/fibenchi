import { Component, useState, type ReactNode } from "react"
import Markdown from "react-markdown"
import { AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import type { Thesis } from "@/lib/api"

interface ThesisEditorProps {
  thesis: Thesis | undefined
  onSave: (content: string) => void
  isSaving: boolean
}

class MarkdownErrorBoundary extends Component<
  { fallback: ReactNode; children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  render() {
    return this.state.hasError ? this.props.fallback : this.props.children
  }
}

function RawFallback({ content }: { content: string }) {
  return (
    <>
      <div className="flex items-center gap-2 rounded-md bg-amber-500/10 border border-amber-500/30 px-3 py-2 text-xs text-amber-600 dark:text-amber-400 mb-3">
        <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
        <span>Markdown rendering failed. Showing raw text.</span>
      </div>
      <pre className="whitespace-pre-wrap text-sm">{content}</pre>
    </>
  )
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
        ) : thesis?.content ? (
          <MarkdownErrorBoundary fallback={<RawFallback content={thesis.content} />}>
            <div className="prose prose-sm dark:prose-invert max-w-none min-h-[100px]">
              <Markdown>{thesis.content}</Markdown>
            </div>
          </MarkdownErrorBoundary>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none min-h-[100px]">
            <p className="text-muted-foreground italic">No thesis yet. Click Edit to write one.</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
