"use client"

import * as React from "react"
import { Brain, Cpu } from "lucide-react"

import { cn } from "@/lib/utils"

interface ModelIndicatorProps {
  modelName?: string | null
  agentName?: string | null
  className?: string
  variant?: "inline" | "badge" | "compact"
}

function ModelIndicator({
  modelName,
  agentName,
  className,
  variant = "inline",
}: ModelIndicatorProps) {
  if (!modelName) {
    return null
  }

  const baseClasses = "flex items-center gap-1 text-xs text-muted-foreground"

  const variantClasses = {
    inline: "opacity-70",
    badge: "bg-muted px-2 py-1 rounded-md border",
    compact: "opacity-60",
  }

  return (
    <div className={cn(baseClasses, variantClasses[variant], className)}>
      <Cpu className="h-3 w-3" />
      <span className="font-mono">
        {modelName}
        {agentName && variant !== "compact" && (
          <span className="text-muted-foreground/70 ml-1">({agentName})</span>
        )}
      </span>
    </div>
  )
}

ModelIndicator.displayName = "ModelIndicator"
export { ModelIndicator }
