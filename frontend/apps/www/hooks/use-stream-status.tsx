"use client"

import { useCallback, useEffect, useState } from "react"

interface StreamStatus {
  goal: string
  current_agent: string
  is_active: boolean
}

interface UseStreamStatusProps {
  streamId: string
  isGenerating?: boolean
}

export function useStreamStatus({ streamId, isGenerating }: UseStreamStatusProps) {
  // Default status when not actively streaming
  const defaultStatus: StreamStatus = {
    goal: "",
    current_agent: "",
    is_active: false,
  }

  const [status, setStatus] = useState<StreamStatus>(defaultStatus)
  const [isLoading, setIsLoading] = useState(false)

  const fetchStatus = useCallback(async () => {
    if (!streamId || !isGenerating) {
      setStatus(defaultStatus)
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch("/api/status", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ stream_id: streamId }),
      })

      if (response.ok) {
        const statusData = await response.json()
        setStatus(statusData)
      } else if (response.status === 404) {
        // Stream doesn't exist yet, set default status
        setStatus(defaultStatus)
      }
    } catch (error) {
      console.error("Error fetching status:", error)
      setStatus(defaultStatus)
    } finally {
      setIsLoading(false)
    }
  }, [streamId, isGenerating])

  useEffect(() => {
    if (streamId && isGenerating) {
      // Immediately set an active status when generation starts
      setStatus({
        goal: "",
        current_agent: "orchestrator",
        is_active: true,
      })
      
      // Fetch immediately when generation starts
      fetchStatus()
      
      // Poll for status updates every 2 seconds while generating
      const interval = setInterval(() => {
        fetchStatus()
      }, 2000)

      return () => clearInterval(interval)
    } else {
      // Not generating, set default status
      setStatus(defaultStatus)
    }
  }, [streamId, isGenerating, fetchStatus])

  return { status, isLoading }
}