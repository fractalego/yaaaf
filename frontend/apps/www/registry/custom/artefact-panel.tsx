"use client"

import * as React from "react"
import { useEffect, useState } from "react"
import { X } from "lucide-react"

import { Button } from "@/registry/default/ui/button"
import { ArtefactPage } from "@/registry/custom/artefact-page"
import { get_artefact } from "@/app/artefacts/actions"

interface ArtefactPanelProps {
  artifactId: string
  onClose: () => void
}

function ArtefactPanel({ artifactId, onClose }: ArtefactPanelProps) {
  const [artifactData, setArtifactData] = useState<{
    data: string
    code: string
    image: string
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchArtifact = async () => {
      try {
        setLoading(true)
        setError(null)
        console.log("Fetching artifact with ID:", artifactId)
        const data = await get_artefact(artifactId)
        console.log("Raw artifact response:", data)
        
        if (data && (data.data !== undefined || data.code !== undefined || data.image !== undefined)) {
          console.log("Setting artifact data to:", data)
          setArtifactData(data)
        } else {
          console.error("Invalid artifact data structure:", data)
          throw new Error("Invalid artifact data structure received from server")
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to load artifact"
        setError(errorMessage)
        console.error("Error fetching artifact:", err)
      } finally {
        setLoading(false)
      }
    }

    if (artifactId) {
      fetchArtifact()
    }
  }, [artifactId])

  const renderArtifactContent = () => {
    if (!artifactData) {
      console.log("No artifact data available")
      return null
    }

    console.log("Artifact data:", artifactData)
    
    return (
      <ArtefactPage
        data={artifactData.data}
        code={artifactData.code}
        image={artifactData.image}
      />
    )
  }

  return (
    <div className="h-full flex flex-col bg-background border-l border-border">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h2 className="text-lg font-semibold">Artifact: {artifactId}</h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          className="h-8 w-8 p-0"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {loading && (
          <div className="flex items-center justify-center h-32">
            <div className="text-muted-foreground">Loading artifact...</div>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center h-32">
            <div className="text-red-500">{error}</div>
          </div>
        )}

        {!loading && !error && artifactData && renderArtifactContent()}
        
        {!loading && !error && !artifactData && (
          <div className="flex items-center justify-center h-32">
            <div className="text-muted-foreground">No artifact data found</div>
          </div>
        )}
      </div>
    </div>
  )
}

ArtefactPanel.displayName = "ArtefactPanel"
export { ArtefactPanel }
