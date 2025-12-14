import { Loader2 } from "lucide-react"

interface TypingIndicatorProps {
  streamStatus?: {
    goal: string
    current_agent: string
    is_active: boolean
  }
}

export function TypingIndicator({ streamStatus }: TypingIndicatorProps) {
  return (
    <div className="justify-left flex space-x-1">
      <div className="rounded-lg bg-muted p-3">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-xs">
            {streamStatus?.is_active && streamStatus?.current_agent
              ? streamStatus.current_agent === "orchestrator"
                ? "Planning..."
                : `Running ${streamStatus.current_agent}...`
              : "Thinking..."}
          </span>
          {streamStatus?.is_active && streamStatus?.goal && (
            <span className="text-xs opacity-70">
              •{" "}
              {streamStatus.goal.length > 50
                ? streamStatus.goal.substring(0, 50) + "..."
                : streamStatus.goal}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
