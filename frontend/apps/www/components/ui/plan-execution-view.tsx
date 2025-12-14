"use client"

import React from "react"
import {
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  ChevronRight,
} from "lucide-react"

import { ExecutionPlan, PlanAsset } from "@/lib/plan-types"
import { cn } from "@/lib/utils"

interface PlanExecutionViewProps {
  plan: ExecutionPlan
  compact?: boolean
  showDetails?: boolean
  onAssetClick?: (asset: PlanAsset) => void
}

const statusIcons = {
  pending: Circle,
  in_progress: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
}

const statusColors = {
  pending: "text-gray-400",
  in_progress: "text-blue-500",
  completed: "text-green-500",
  failed: "text-red-500",
}

export function PlanExecutionView({
  plan,
  compact = false,
  showDetails = false,
  onAssetClick,
}: PlanExecutionViewProps) {
  if (!plan || !plan.assets) {
    return null
  }

  if (compact) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-500">Plan:</span>
        <div className="flex items-center gap-1">
          {plan.assets.map((asset, index) => {
            const StatusIcon = statusIcons[asset.status]
            return (
              <React.Fragment key={asset.name}>
                {index > 0 && (
                  <ChevronRight className="h-3 w-3 text-gray-300" />
                )}
                <div
                  className={cn(
                    "flex items-center gap-1",
                    statusColors[asset.status]
                  )}
                  title={`${asset.name}: ${asset.status}`}
                >
                  <StatusIcon
                    className={cn(
                      "h-4 w-4",
                      asset.status === "in_progress" && "animate-spin"
                    )}
                  />
                </div>
              </React.Fragment>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-2 p-2">
      <div className="mb-3 text-sm font-medium text-gray-700">
        {plan.goal}
      </div>
      <div className="space-y-1">
        {plan.assets.map((asset) => {
          const StatusIcon = statusIcons[asset.status]
          return (
            <div
              key={asset.name}
              className={cn(
                "flex items-center gap-3 rounded-md p-2 transition-colors",
                onAssetClick && "cursor-pointer hover:bg-gray-100",
                asset.status === "in_progress" && "bg-blue-50"
              )}
              onClick={() => onAssetClick?.(asset)}
            >
              <StatusIcon
                className={cn(
                  "h-5 w-5",
                  statusColors[asset.status],
                  asset.status === "in_progress" && "animate-spin"
                )}
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{asset.name}</span>
                  <span className="rounded bg-gray-200 px-1.5 py-0.5 text-xs text-gray-600">
                    {asset.agent}
                  </span>
                </div>
                {showDetails && (
                  <div className="mt-0.5 text-sm text-gray-500">
                    {asset.description}
                  </div>
                )}
              </div>
              {asset.executionTime && (
                <span className="text-xs text-gray-400">
                  {(asset.executionTime / 1000).toFixed(1)}s
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
