"use client"

import React, { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"

import { ExecutionPlan } from "@/lib/plan-types"
import { cn } from "@/lib/utils"

import { PlanExecutionView } from "./plan-execution-view"

interface ChatMessageWithPlanProps {
  content: string
  plan?: ExecutionPlan
  isUser?: boolean
  timestamp?: Date
  className?: string
}

export function ChatMessageWithPlan({
  content,
  plan,
  isUser = false,
  timestamp,
  className,
}: ChatMessageWithPlanProps) {
  const [isPlanExpanded, setIsPlanExpanded] = useState(true)

  if (isUser) {
    return (
      <div className={cn("mb-4 flex justify-end", className)}>
        <div className="max-w-[80%] rounded-lg bg-blue-500 px-4 py-2 text-white">
          <p>{content}</p>
          {timestamp && (
            <div className="mt-1 text-xs text-blue-100">
              {timestamp.toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={cn("mb-4 flex justify-start", className)}>
      <div className="max-w-[90%] space-y-3">
        {/* Assistant Message */}
        <div className="rounded-lg bg-gray-100 px-4 py-3">
          <div className="prose prose-sm max-w-none">{content}</div>
          {timestamp && (
            <div className="mt-2 text-xs text-gray-500">
              {timestamp.toLocaleTimeString()}
            </div>
          )}
        </div>

        {/* Execution Plan */}
        {plan && (
          <div className="rounded-lg border bg-white shadow-sm">
            {/* Plan Header - Collapsible */}
            <button
              onClick={() => setIsPlanExpanded(!isPlanExpanded)}
              className="flex w-full items-center justify-between p-3 text-left transition-colors hover:bg-gray-50"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-900">
                  Execution Plan
                </span>
                <span className="text-sm text-gray-500">
                  ({plan.assets.filter((a) => a.status === "completed").length}/
                  {plan.assets.length} completed)
                </span>
              </div>
              {isPlanExpanded ? (
                <ChevronUp className="h-4 w-4 text-gray-400" />
              ) : (
                <ChevronDown className="h-4 w-4 text-gray-400" />
              )}
            </button>

            {/* Plan Content */}
            {isPlanExpanded && (
              <div className="border-t">
                <PlanExecutionView
                  plan={plan}
                  showDetails={true}
                  compact={false}
                />
              </div>
            )}

            {/* Compact View When Collapsed */}
            {!isPlanExpanded && (
              <div className="border-t p-3">
                <PlanExecutionView plan={plan} compact={true} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// Example usage in chat component
export function ChatMessage({
  content,
  plan,
  isUser,
  timestamp,
}: {
  content: string
  plan?: ExecutionPlan
  isUser?: boolean
  timestamp?: Date
}) {
  return (
    <ChatMessageWithPlan
      content={content}
      plan={plan}
      isUser={isUser}
      timestamp={timestamp}
    />
  )
}
