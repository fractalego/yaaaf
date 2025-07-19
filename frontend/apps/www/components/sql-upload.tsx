"use client"

import { useRef, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  Database,
  FileSpreadsheet,
  Loader2,
  Upload,
  X,
} from "lucide-react"

import { Badge } from "@/registry/new-york/ui/badge"
import { Button } from "@/registry/new-york/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/registry/new-york/ui/dialog"

interface SqlUploadProps {
  onFileUpload?: (
    tableName: string,
    fileName: string,
    rowsInserted: number
  ) => void
  children?: React.ReactNode
}

type UploadStep = "select" | "configure" | "uploading" | "complete"

interface SqlSource {
  name: string
  path: string
  tables: string[]
}

export function SqlUpload({ onFileUpload, children }: SqlUploadProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [step, setStep] = useState<UploadStep>("select")
  const [file, setFile] = useState<File | null>(null)
  const [tableName, setTableName] = useState("")
  const [selectedDatabase, setSelectedDatabase] = useState("")
  const [replaceTable, setReplaceTable] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadResult, setUploadResult] = useState<{
    tableName: string
    fileName: string
    rowsInserted: number
  } | null>(null)
  const [sqlSources, setSqlSources] = useState<SqlSource[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const supportedTypes = [".csv", ".xlsx", ".xls"]

  const resetState = () => {
    setStep("select")
    setFile(null)
    setTableName("")
    setSelectedDatabase("")
    setReplaceTable(false)
    setError(null)
    setUploadResult(null)
    setSqlSources([])
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  const handleDialogChange = (open: boolean) => {
    setIsOpen(open)
    if (!open) {
      resetState()
    } else {
      // Fetch SQL sources when dialog opens
      fetchSqlSources()
    }
  }

  const fetchSqlSources = async () => {
    try {
      const response = await fetch("http://localhost:4000/get_sql_sources")
      if (!response.ok) {
        throw new Error("Failed to fetch SQL sources")
      }
      const sources = await response.json()
      setSqlSources(sources)
      if (sources.length > 0) {
        setSelectedDatabase(sources[0].name) // Default to first database
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch SQL sources"
      )
    }
  }

  const handleFileSelect = (selectedFile: File) => {
    const fileExtension =
      "." + selectedFile.name.split(".").pop()?.toLowerCase()

    if (!supportedTypes.includes(fileExtension)) {
      setError(
        `Unsupported file type. Only ${supportedTypes.join(
          ", "
        )} files are supported.`
      )
      return
    }

    setFile(selectedFile)
    setError(null)

    // Suggest table name from filename (without extension)
    const baseName = selectedFile.name.replace(/\.[^/.]+$/, "")
    const cleanTableName = baseName.replace(/[^a-zA-Z0-9_]/g, "_").toLowerCase()
    setTableName(cleanTableName)

    // Move to configuration step
    setStep("configure")
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (step !== "select") return

    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      handleFileSelect(files[0])
    }
  }

  const uploadFile = async () => {
    if (!file || !tableName.trim()) {
      setError("Please provide a table name")
      return
    }

    setStep("uploading")
    setError(null)

    try {
      const formData = new FormData()
      formData.append("file", file)
      formData.append("table_name", tableName.trim())
      if (selectedDatabase) {
        formData.append("database_name", selectedDatabase)
      }
      formData.append("replace_table", replaceTable.toString())

      const response = await fetch("http://localhost:4000/update_sql_source", {
        method: "POST",
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Upload failed")
      }

      const result = await response.json()
      setUploadResult({
        tableName: result.table_name,
        fileName: file.name,
        rowsInserted: result.rows_inserted,
      })

      // Move to completion step
      setStep("complete")

      // Notify parent component
      if (onFileUpload) {
        onFileUpload(result.table_name, file.name, result.rows_inserted)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
      setStep("configure")
    }
  }

  const handleClose = () => {
    setIsOpen(false)
    setTimeout(resetState, 300) // Reset after dialog closes
  }

  const renderContent = () => {
    switch (step) {
      case "select":
        return (
          <div className="space-y-4">
            {/* File Drop Zone */}
            <div
              className="relative rounded-lg border-2 border-dashed border-muted-foreground/25 p-8 text-center transition-colors hover:border-muted-foreground/50"
              onDragOver={handleDragOver}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept={supportedTypes.join(",")}
                onChange={(e) => {
                  const selectedFile = e.target.files?.[0]
                  if (selectedFile) {
                    handleFileSelect(selectedFile)
                  }
                }}
                className="absolute inset-0 cursor-pointer opacity-0"
              />
              <div className="flex flex-col items-center gap-2">
                <FileSpreadsheet className="h-8 w-8 text-muted-foreground" />
                <div className="text-sm">
                  <span className="font-medium">Click to upload</span> or drag
                  and drop
                </div>
                <div className="flex flex-wrap gap-1">
                  {supportedTypes.map((type) => (
                    <Badge key={type} variant="secondary" className="text-xs">
                      {type}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" />
                {error}
              </div>
            )}
          </div>
        )

      case "configure":
        return (
          <div className="space-y-4">
            {/* File Info */}
            {file && (
              <div className="rounded-lg bg-accent/30 p-3">
                <div className="flex items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4" />
                  <span className="text-sm font-medium">{file.name}</span>
                  <Badge variant="outline" className="text-xs">
                    {(file.size / 1024).toFixed(1)} KB
                  </Badge>
                </div>
              </div>
            )}

            {/* Database Selection */}
            {sqlSources.length > 1 && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Target Database</label>
                <select
                  value={selectedDatabase}
                  onChange={(e) => setSelectedDatabase(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  {sqlSources.map((source) => (
                    <option key={source.name} value={source.name}>
                      {source.name} ({source.tables.length} tables)
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Table Name */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Table Name</label>
              <input
                type="text"
                value={tableName}
                onChange={(e) => setTableName(e.target.value)}
                placeholder="Enter table name"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Letters, numbers, and underscores only
              </p>
            </div>

            {/* Replace Table Option */}
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="replace-table"
                checked={replaceTable}
                onChange={(e) => setReplaceTable(e.target.checked)}
                className="h-4 w-4"
              />
              <label htmlFor="replace-table" className="text-sm">
                Replace existing table (if it exists)
              </label>
            </div>
            <p className="text-xs text-muted-foreground">
              {replaceTable
                ? "This will completely replace the existing table with new data"
                : "Data will be appended to existing table or create a new one"}
            </p>

            {/* Action Buttons */}
            <div className="flex gap-2">
              <Button
                onClick={() => setStep("select")}
                variant="outline"
                className="flex-1"
              >
                Back
              </Button>
              <Button
                onClick={uploadFile}
                className="flex-1"
                disabled={!tableName.trim()}
              >
                Upload to Database
              </Button>
            </div>

            {/* Error Message */}
            {error && (
              <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" />
                {error}
              </div>
            )}
          </div>
        )

      case "uploading":
        return (
          <div className="flex flex-col items-center gap-4 py-8">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <div className="text-center">
              <div className="text-sm font-medium">
                Uploading and processing...
              </div>
              <div className="text-xs text-muted-foreground">
                {file?.name} → {tableName}
              </div>
            </div>
          </div>
        )

      case "complete":
        return (
          <div className="space-y-4">
            <div className="flex flex-col items-center gap-4 py-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-400">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <div className="text-center">
                <div className="text-sm font-medium">Upload Successful!</div>
                {uploadResult && (
                  <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                    <div>
                      Table:{" "}
                      <span className="font-medium">
                        {uploadResult.tableName}
                      </span>
                    </div>
                    <div>
                      File:{" "}
                      <span className="font-medium">
                        {uploadResult.fileName}
                      </span>
                    </div>
                    <div>
                      Rows:{" "}
                      <span className="font-medium">
                        {uploadResult.rowsInserted}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <Button onClick={handleClose} className="w-full">
              Done
            </Button>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleDialogChange}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Upload to SQL Database
          </DialogTitle>
        </DialogHeader>
        {renderContent()}
      </DialogContent>
    </Dialog>
  )
}
