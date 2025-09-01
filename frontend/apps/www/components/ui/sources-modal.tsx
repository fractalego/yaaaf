"use client"

import { useCallback, useEffect, useState } from "react"
import { Database, FileText, Folder } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/registry/default/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/registry/default/ui/dialog"
import { Badge } from "@/registry/new-york/ui/badge"

interface UploadedDocument {
  source_id: string
  description: string
  filename: string
}

interface SqlSource {
  name: string
  path: string
  tables: string[]
}

interface AllSourcesResponse {
  uploaded_documents: UploadedDocument[]
  sql_sources: SqlSource[]
}

interface SourcesModalProps {
  isOpen: boolean
  onClose: () => void
}

export function SourcesModal({ isOpen, onClose }: SourcesModalProps) {
  const [sources, setSources] = useState<AllSourcesResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSources = useCallback(async () => {
    if (!isOpen) return

    console.log("SourcesModal: Fetching all sources")
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch("http://localhost:4000/get_all_sources", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      })

      console.log(`SourcesModal: API response status: ${response.status}`)

      if (!response.ok) {
        setError("Failed to fetch sources")
        return
      }

      const result = await response.json()
      console.log("SourcesModal: Received sources data:", result)
      setSources(result)
    } catch (err) {
      console.error("Error fetching sources:", err)
      setError("Failed to load sources")
    } finally {
      setIsLoading(false)
    }
  }, [isOpen])

  useEffect(() => {
    if (isOpen) {
      fetchSources()
    }
  }, [isOpen, fetchSources])

  const getDocumentIcon = (filename: string) => {
    if (filename === "persistent_storage") {
      return <Folder className="h-4 w-4 text-blue-600" />
    }
    return <FileText className="h-4 w-4 text-gray-600" />
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-h-[80vh] max-w-3xl overflow-hidden">
        <DialogHeader>
          <DialogTitle>Data Sources</DialogTitle>
        </DialogHeader>

        <div className="overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <div className="text-muted-foreground">Loading sources...</div>
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center py-8">
              <div className="text-destructive">{error}</div>
            </div>
          )}

          {!isLoading && !error && sources && (
            <div className="space-y-6">
              {/* Document Sources */}
              <div>
                <div className="mb-4 flex items-center gap-2">
                  <FileText className="h-5 w-5 text-blue-600" />
                  <h3 className="text-lg font-semibold">Document Sources</h3>
                  <Badge variant="secondary">
                    {sources.uploaded_documents.length}
                  </Badge>
                </div>

                {sources.uploaded_documents.length > 0 ? (
                  <div className="space-y-3">
                    {sources.uploaded_documents.map((doc, index) => (
                      <div
                        key={doc.source_id || index}
                        className="flex items-start gap-3 rounded-lg border p-4"
                      >
                        <div className="shrink-0 pt-0.5">
                          {getDocumentIcon(doc.filename)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="font-medium text-foreground">
                            {doc.filename}
                          </div>
                          <div className="mt-1 text-sm text-muted-foreground">
                            {doc.description}
                          </div>
                          <div className="mt-2">
                            <Badge variant="outline" className="text-xs">
                              ID: {doc.source_id}
                            </Badge>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed p-8 text-center">
                    <FileText className="mx-auto h-8 w-8 text-muted-foreground" />
                    <p className="mt-2 text-sm text-muted-foreground">
                      No document sources available
                    </p>
                  </div>
                )}
              </div>

              {/* SQL Sources */}
              <div>
                <div className="mb-4 flex items-center gap-2">
                  <Database className="h-5 w-5 text-green-600" />
                  <h3 className="text-lg font-semibold">SQL Databases</h3>
                  <Badge variant="secondary">
                    {sources.sql_sources.length}
                  </Badge>
                </div>

                {sources.sql_sources.length > 0 ? (
                  <div className="space-y-3">
                    {sources.sql_sources.map((sql, index) => (
                      <div
                        key={sql.name || index}
                        className="flex items-start gap-3 rounded-lg border p-4"
                      >
                        <div className="shrink-0 pt-0.5">
                          <Database className="h-4 w-4 text-green-600" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="font-medium text-foreground">
                            {sql.name}
                          </div>
                          <div className="mt-1 text-sm text-muted-foreground">
                            {sql.path}
                          </div>
                          {sql.tables.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {sql.tables.map((table, tableIndex) => (
                                <Badge
                                  key={tableIndex}
                                  variant="outline"
                                  className="text-xs"
                                >
                                  {table}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed p-8 text-center">
                    <Database className="mx-auto h-8 w-8 text-muted-foreground" />
                    <p className="mt-2 text-sm text-muted-foreground">
                      No SQL databases configured
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t pt-4">
          <Button
            variant="outline"
            onClick={fetchSources}
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