"use client"

import React, { useEffect, useState } from "react"

import { ExecutionPlan, PlanAsset } from "@/lib/plan-types"

import { Button } from "./button"
import { PlanExecutionView } from "./plan-execution-view"

// Demo plan data
const createDemoPlan = (): ExecutionPlan => ({
  id: "demo_plan_001",
  goal: "Create sales visualization with trend analysis",
  targetType: "IMAGE",
  overallStatus: "executing",
  createdAt: Date.now(),
  updatedAt: Date.now(),
  executionOrder: [
    "sales_data",
    "data_validation",
    "trend_analysis",
    "sales_visualization",
  ],
  attempt: 1,
  assets: [
    {
      name: "sales_data",
      description: "Extract sales data from database",
      agent: "SqlAgent",
      type: "TABLE",
      status: "completed",
      inputs: [],
      validation: ["row_count > 0", "columns: [date, sales, region]"],
      executionTime: 1250,
      startTime: Date.now() - 5000,
      endTime: Date.now() - 3750,
    },
    {
      name: "data_validation",
      description: "Validate data quality and clean records",
      agent: "ReviewerAgent",
      type: "TABLE",
      status: "completed",
      inputs: ["sales_data"],
      validation: ["no_nulls: [sales]", "date_range_valid"],
      executionTime: 850,
      startTime: Date.now() - 3750,
      endTime: Date.now() - 2900,
    },
    {
      name: "trend_analysis",
      description: "Analyze sales trends and patterns",
      agent: "NumericalSequencesAgent",
      type: "TABLE",
      status: "in_progress",
      inputs: ["data_validation"],
      conditions: [
        {
          if: "data_validation.row_count > 1000",
          params: { algorithm: "advanced" },
        },
        { else: true, params: { algorithm: "standard" } },
      ],
      startTime: Date.now() - 2900,
    },
    {
      name: "sales_visualization",
      description: "Create interactive sales dashboard",
      agent: "VisualizationAgent",
      type: "IMAGE",
      status: "pending",
      inputs: ["trend_analysis"],
      conditions: [
        {
          if: "trend_analysis.trend_detected",
          params: { chart_type: "line_with_trend" },
        },
        { else: true, params: { chart_type: "standard_line" } },
      ],
      validation: ["file_size < 5MB", "format: PNG"],
    },
  ],
})

export function PlanDemo() {
  const [plan, setPlan] = useState<ExecutionPlan>(createDemoPlan())
  const [isAnimating, setIsAnimating] = useState(false)

  const simulateProgress = () => {
    if (isAnimating) return

    setIsAnimating(true)
    const newPlan = createDemoPlan()

    // Simulate execution steps
    const steps = [
      () => {
        // Start trend analysis
        setPlan((prev) => ({
          ...prev,
          currentStep: "trend_analysis",
          assets: prev.assets.map((asset) =>
            asset.name === "trend_analysis"
              ? { ...asset, status: "in_progress" as const }
              : asset
          ),
        }))
      },
      () => {
        // Complete trend analysis
        setPlan((prev) => ({
          ...prev,
          assets: prev.assets.map((asset) =>
            asset.name === "trend_analysis"
              ? {
                  ...asset,
                  status: "completed" as const,
                  executionTime: 2100,
                  endTime: Date.now(),
                }
              : asset
          ),
        }))
      },
      () => {
        // Start visualization
        setPlan((prev) => ({
          ...prev,
          currentStep: "sales_visualization",
          assets: prev.assets.map((asset) =>
            asset.name === "sales_visualization"
              ? {
                  ...asset,
                  status: "in_progress" as const,
                  startTime: Date.now(),
                }
              : asset
          ),
        }))
      },
      () => {
        // Complete visualization
        setPlan((prev) => ({
          ...prev,
          overallStatus: "completed" as const,
          currentStep: undefined,
          assets: prev.assets.map((asset) =>
            asset.name === "sales_visualization"
              ? {
                  ...asset,
                  status: "completed" as const,
                  executionTime: 3200,
                  endTime: Date.now(),
                }
              : asset
          ),
        }))
      },
    ]

    // Execute steps with delays
    steps.forEach((step, index) => {
      setTimeout(step, index * 2000)
    })

    // Reset animation flag
    setTimeout(() => setIsAnimating(false), steps.length * 2000 + 1000)
  }

  const simulateFailure = () => {
    setPlan((prev) => ({
      ...prev,
      overallStatus: "failed" as const,
      assets: prev.assets.map((asset) =>
        asset.name === "trend_analysis"
          ? {
              ...asset,
              status: "failed" as const,
              error:
                "Insufficient data for trend analysis. Need at least 30 days of data.",
              endTime: Date.now(),
            }
          : asset
      ),
    }))
  }

  const simulateReplanning = () => {
    setPlan((prev) => ({
      ...prev,
      overallStatus: "replanning" as const,
      replanReason: "Trend analysis failed, switching to basic statistics",
      attempt: 2,
    }))

    setTimeout(() => {
      setPlan((prev) => ({
        ...prev,
        overallStatus: "executing" as const,
        assets: [
          ...prev.assets.slice(0, 2), // Keep completed assets
          {
            name: "basic_statistics",
            description: "Calculate basic sales statistics",
            agent: "ReviewerAgent",
            type: "TABLE",
            status: "in_progress" as const,
            inputs: ["data_validation"],
            startTime: Date.now(),
          },
          {
            name: "simple_visualization",
            description: "Create simple sales chart",
            agent: "VisualizationAgent",
            type: "IMAGE",
            status: "pending" as const,
            inputs: ["basic_statistics"],
          },
        ],
      }))
    }, 2000)
  }

  const resetDemo = () => {
    setPlan(createDemoPlan())
    setIsAnimating(false)
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-bold">Plan Execution Demo</h1>
        <p className="text-gray-600">
          See how the plan-driven orchestrator visualizes workflow execution
        </p>
      </div>

      {/* Demo Controls */}
      <div className="flex flex-wrap justify-center gap-2">
        <Button
          onClick={simulateProgress}
          disabled={isAnimating}
          variant="default"
        >
          Simulate Progress
        </Button>
        <Button onClick={simulateFailure} variant="destructive">
          Simulate Failure
        </Button>
        <Button onClick={simulateReplanning} variant="secondary">
          Simulate Replanning
        </Button>
        <Button onClick={resetDemo} variant="outline">
          Reset Demo
        </Button>
      </div>

      {/* Plan Execution View */}
      <div className="rounded-lg border bg-gray-50 p-1">
        <PlanExecutionView
          plan={plan}
          showDetails={true}
          onAssetClick={(asset) => {
            console.log("Clicked asset:", asset)
          }}
        />
      </div>

      {/* Status Information */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
        <h3 className="mb-2 font-medium text-blue-900">Current Status</h3>
        <div className="space-y-1 text-sm text-blue-800">
          <div>
            Overall Status:{" "}
            <span className="font-medium capitalize">{plan.overallStatus}</span>
          </div>
          <div>
            Current Step:{" "}
            <span className="font-medium">{plan.currentStep || "None"}</span>
          </div>
          <div>
            Attempt: <span className="font-medium">#{plan.attempt}</span>
          </div>
          {plan.replanReason && (
            <div>
              Replan Reason:{" "}
              <span className="font-medium">{plan.replanReason}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
