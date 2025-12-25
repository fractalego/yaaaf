"use client"

import { useCallback, useState } from "react"

import { ExecutionPlan, PlanAsset, AssetStatus } from "@/lib/plan-types"

export function usePlanExecution() {
  const [currentPlan, setCurrentPlan] = useState<ExecutionPlan | null>(null)

  const handlePlanUpdate = useCallback((planUpdate: Partial<ExecutionPlan>) => {
    setCurrentPlan((prev) => {
      if (!prev) {
        return planUpdate as ExecutionPlan
      }
      return { ...prev, ...planUpdate }
    })
  }, [])

  const updateAssetStatus = useCallback(
    (assetName: string, status: AssetStatus, additionalData?: Partial<PlanAsset>) => {
      setCurrentPlan((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          assets: prev.assets.map((asset) =>
            asset.name === assetName
              ? { ...asset, status, ...additionalData }
              : asset
          ),
          updatedAt: Date.now(),
        }
      })
    },
    []
  )

  const clearCurrentPlan = useCallback(() => {
    setCurrentPlan(null)
  }, [])

  return {
    currentPlan,
    handlePlanUpdate,
    updateAssetStatus,
    clearCurrentPlan,
  }
}
