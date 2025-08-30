"use client"

import { useCallback, useEffect, useState } from "react"
import { CheckCircle, Circle, Clock } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/registry/default/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/registry/default/ui/dialog"

interface TodoItem {
  id: string
  task: string
  status: "pending" | "in_progress" | "completed"
  agentTool: string
}

interface TodoListModalProps {
  isOpen: boolean
  onClose: () => void
  streamId: string
}

export function TodoListModal({
  isOpen,
  onClose,
  streamId,
}: TodoListModalProps) {
  const [todoItems, setTodoItems] = useState<TodoItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchLatestTodo = useCallback(async () => {
    if (!streamId) return

    console.log(`TodoListModal: Fetching todos for stream_id: ${streamId}`)
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch("http://localhost:4000/get_latest_todo", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          stream_id: streamId,
        }),
      })

      console.log(`TodoListModal: API response status: ${response.status}`)

      if (!response.ok) {
        if (response.status === 404) {
          setError("No todo list found for this conversation")
        } else {
          setError("Failed to fetch todo list")
        }
        return
      }

      const result = await response.json()
      console.log("TodoListModal: Raw artifact data:", result.data)

      // Parse HTML table from artifact data
      const parser = new DOMParser()
      const doc = parser.parseFromString(result.data, "text/html")
      const table = doc.querySelector("table")

      if (!table) {
        setError("Invalid todo list format")
        return
      }

      const rows = Array.from(table.querySelectorAll("tbody tr"))
      const items: TodoItem[] = rows.map((row) => {
        const cells = Array.from(row.querySelectorAll("td"))
        const rawStatus = cells[2]?.textContent?.trim() || "pending"
        console.log(`TodoListModal: Task "${cells[1]?.textContent?.trim()}" has status: "${rawStatus}"`)
        return {
          id: cells[0]?.textContent?.trim() || "",
          task: cells[1]?.textContent?.trim() || "",
          status: (rawStatus) as TodoItem["status"],
          agentTool: cells[3]?.textContent?.trim() || "",
        }
      })

      console.log("TodoListModal: Parsed todo items:", items)
      setTodoItems(items)
    } catch (err) {
      console.error("Error fetching todo list:", err)
      setError("Failed to load todo list")
    } finally {
      setIsLoading(false)
    }
  }, [streamId])

  useEffect(() => {
    if (isOpen && streamId) {
      fetchLatestTodo()
    }
  }, [isOpen, streamId, fetchLatestTodo])

  const getStatusIcon = (status: TodoItem["status"]) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-600" />
      case "in_progress":
        return <Clock className="h-4 w-4 text-blue-600" />
      case "pending":
      default:
        return <Circle className="h-4 w-4 text-gray-400" />
    }
  }

  const getStatusColor = (status: TodoItem["status"]) => {
    switch (status) {
      case "completed":
        return "text-green-600"
      case "in_progress":
        return "text-blue-600"
      case "pending":
      default:
        return "text-gray-600"
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-h-[80vh] max-w-2xl overflow-hidden">
        <DialogHeader>
          <DialogTitle>Task Progress</DialogTitle>
        </DialogHeader>

        <div className="overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <div className="text-muted-foreground">Loading todo list...</div>
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center py-8">
              <div className="text-destructive">{error}</div>
            </div>
          )}

          {!isLoading && !error && todoItems.length > 0 && (
            <div className="space-y-3">
              {todoItems.map((item, index) => (
                <div
                  key={item.id || index}
                  className={cn(
                    "flex items-start gap-3 rounded-lg border p-3",
                    item.status === "completed" &&
                      "border-green-200 bg-green-50",
                    item.status === "in_progress" &&
                      "border-blue-200 bg-blue-50",
                    item.status === "pending" && "border-gray-200 bg-gray-50"
                  )}
                >
                  <div className="shrink-0 pt-0.5">
                    {getStatusIcon(item.status)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-foreground">
                      {item.task}
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
                      <span className={getStatusColor(item.status)}>
                        {item.status.replace("_", " ")}
                      </span>
                      <span>•</span>
                      <span>{item.agentTool}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!isLoading && !error && todoItems.length === 0 && (
            <div className="flex items-center justify-center py-8">
              <div className="text-muted-foreground">
                No todo list available for this conversation
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t pt-4">
          <Button
            variant="outline"
            onClick={fetchLatestTodo}
            disabled={isLoading}
          >
            Refresh
          </Button>
          <Button onClick={onClose}>Close</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
