export type AssetStatus = "pending" | "in_progress" | "completed" | "failed"

export type PlanStatus = "planning" | "executing" | "completed" | "failed" | "replanning"

export interface PlanCondition {
  if?: string
  else?: boolean
  params: Record<string, unknown>
}

export interface PlanAsset {
  name: string
  description: string
  agent: string
  type: string
  status: AssetStatus
  inputs: string[]
  validation?: string[]
  conditions?: PlanCondition[]
  executionTime?: number
  startTime?: number
  endTime?: number
  error?: string
  result?: string
}

export interface ExecutionPlan {
  id: string
  goal: string
  targetType: string
  overallStatus: PlanStatus
  createdAt: number
  updatedAt: number
  executionOrder: string[]
  attempt: number
  assets: PlanAsset[]
  error?: string
  replanReason?: string
  currentStep?: string
}

export interface PlanUpdate {
  type?: string
  plan?: ExecutionPlan
  asset?: string
  executionTime?: number
  error?: string
  reason?: string
  attempt?: number
  timestamp?: number
  assetUpdate?: {
    name: string
    status?: AssetStatus
    executionTime?: number
    error?: string
    result?: string
  }
}
