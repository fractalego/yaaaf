"use client"

import React, { useCallback, useEffect, useState } from "react"

import { cn } from "@/lib/utils"

interface StreamStatus {
  goal: string
  current_agent: string
  is_active: boolean
}

interface StatusDisplayProps {
  streamId: string
  className?: string
}

export function StatusDisplay({ streamId, className }: StatusDisplayProps) {
  const [status, setStatus] = useState<StreamStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const fetchStatus = useCallback(async () => {
    if (!streamId) return

    console.log("Fetching status for stream:", streamId)
    setIsLoading(true)
    try {
      const response = await fetch("/api/status", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ stream_id: streamId }),
      })

      console.log("Status response:", response.status, response.statusText)

      if (response.ok) {
        const statusData = await response.json()
        console.log("Status data received:", statusData)
        setStatus(statusData)
      } else {
        console.error(
          "Failed to fetch status:",
          response.status,
          response.statusText
        )
        const errorText = await response.text()
        console.error("Error response:", errorText)
      }
    } catch (error) {
      console.error("Error fetching status:", error)
    } finally {
      setIsLoading(false)
    }
  }, [streamId])

  useEffect(() => {
    if (streamId) {
      fetchStatus()
      // Poll for status updates every 2 seconds when active
      const interval = setInterval(() => {
        if (status?.is_active) {
          fetchStatus()
        }
      }, 2000)

      return () => clearInterval(interval)
    }
  }, [streamId, status?.is_active, fetchStatus])

  // Always show something for debugging
  if (!status) {
    return (
      <div
        className={cn(
          "flex items-center gap-3 rounded-lg border bg-background/95 p-3 text-sm opacity-60 shadow-md backdrop-blur-sm",
          className
        )}
      >
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-blue-400" />
          <span className="font-medium text-muted-foreground">
            {isLoading
              ? "Loading status..."
              : `Initializing... (Stream: ${streamId?.slice(0, 8)})`}
          </span>
        </div>
      </div>
    )
  }

  if (!status.is_active) {
    return (
      <div
        className={cn(
          "flex items-center gap-3 rounded-lg border bg-background/95 p-3 text-sm opacity-60 shadow-md backdrop-blur-sm",
          className
        )}
      >
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-gray-400" />
          <span className="font-medium text-muted-foreground">Ready</span>
        </div>

        {status.goal && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className="text-xs">Last goal:</span>
            <span className="max-w-96 truncate text-xs">{status.goal}</span>
          </div>
        )}
      </div>
    )
  }

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-lg border bg-background/95 p-3 text-sm shadow-md backdrop-blur-sm",
        className
      )}
    >
      <div className="flex items-center gap-2">
        <div className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
        <span className="font-medium text-foreground">
          {status.current_agent === "orchestrator"
            ? "Planning"
            : `Running ${status.current_agent}`}
        </span>
      </div>

      {status.goal && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <span className="text-xs">Goal:</span>
          <span className="max-w-96 truncate text-xs">{status.goal}</span>
        </div>
      )}
    </div>
  )
}
