"use client"

import { useState, useRef } from "react"
import { Upload, X, FileText, AlertCircle, CheckCircle2, Loader2 } from "lucide-react"

import { Button } from "@/registry/new-york/ui/button"
import { Badge } from "@/registry/new-york/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/registry/new-york/ui/dialog"

interface FileUploadProps {
  onFileUpload?: (sourceId: string, fileName: string) => void
  children?: React.ReactNode
}

type UploadStep = "select" | "uploading" | "description" | "complete"

export function FileUpload({ onFileUpload, children }: FileUploadProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [step, setStep] = useState<UploadStep>("select")
  const [file, setFile] = useState<File | null>(null)
  const [description, setDescription] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [uploadResult, setUploadResult] = useState<{
    sourceId: string
    filename: string
  } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const supportedTypes = [".txt", ".md", ".html", ".htm"]

  const resetState = () => {
    setStep("select")
    setFile(null)
    setDescription("")
    setError(null)
    setUploadResult(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  const handleDialogChange = (open: boolean) => {
    setIsOpen(open)
    if (!open) {
      resetState()
    }
  }

  const handleFileSelect = async (selectedFile: File) => {
    const fileExtension = "." + selectedFile.name.split(".").pop()?.toLowerCase()
    
    if (!supportedTypes.includes(fileExtension)) {
      setError(`Unsupported file type. Only ${supportedTypes.join(", ")} files are supported.`)
      return
    }

    setFile(selectedFile)
    setError(null)
    
    // Immediately start upload and indexing
    await uploadFile(selectedFile)
  }

  const uploadFile = async (fileToUpload: File) => {
    setStep("uploading")
    setError(null)

    try {
      const formData = new FormData()
      formData.append("file", fileToUpload)

      const response = await fetch("http://localhost:4000/upload_file_to_rag", {
        method: "POST",
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Upload failed")
      }

      const result = await response.json()
      setUploadResult({
        sourceId: result.source_id,
        filename: result.filename
      })
      
      // Move to description step
      setStep("description")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
      setStep("select")
    }
  }

  const updateDescription = async () => {
    if (!uploadResult || !description.trim()) return

    setStep("uploading") // Show loading while updating description

    try {
      const response = await fetch("http://localhost:4000/update_rag_description", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          source_id: uploadResult.sourceId,
          description: description.trim(),
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to update description")
      }

      // Success!
      setStep("complete")
      
      // Call the callback if provided
      if (onFileUpload) {
        onFileUpload(uploadResult.sourceId, uploadResult.filename)
      }

      // Auto-close after a short delay
      setTimeout(() => {
        handleDialogChange(false)
      }, 1500)
      
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update description")
      setStep("description")
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    
    if (step !== "select") return
    
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      handleFileSelect(files[0])
    }
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
                <Upload className="h-8 w-8 text-muted-foreground" />
                <div className="text-sm">
                  <span className="font-medium">Click to upload</span> or drag and drop
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

      case "uploading":
        return (
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="flex items-center gap-3">
              <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
              <span className="text-sm font-medium">
                {uploadResult ? "Updating description..." : "Uploading and indexing file..."}
              </span>
            </div>
            {file && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <FileText className="h-4 w-4" />
                {file.name}
              </div>
            )}
            <p className="text-center text-xs text-muted-foreground">
              Please wait while we process your document
            </p>
          </div>
        )

      case "description":
        return (
          <div className="space-y-4">
            {/* Upload Success */}
            <div className="flex items-center gap-2 rounded-md bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-400">
              <CheckCircle2 className="h-4 w-4" />
              File uploaded and indexed successfully!
            </div>

            {/* File Info */}
            {uploadResult && (
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <FileText className="h-8 w-8 text-blue-500" />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{uploadResult.filename}</div>
                  <div className="text-sm text-muted-foreground">
                    Ready for searching
                  </div>
                </div>
              </div>
            )}

            {/* Description Input */}
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Describe this document <span className="text-red-500">*</span>
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this document contains, its purpose, or key topics..."
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                rows={3}
                autoFocus
              />
              <p className="text-xs text-muted-foreground">
                This helps the AI understand your document and provide better search results.
              </p>
            </div>

            {/* Error Message */}
            {error && (
              <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" />
                {error}
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => handleDialogChange(false)}>
                Skip
              </Button>
              <Button
                onClick={updateDescription}
                disabled={!description.trim()}
              >
                Save Description
              </Button>
            </div>
          </div>
        )

      case "complete":
        return (
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-6 w-6 text-green-500" />
              <span className="text-sm font-medium text-green-700 dark:text-green-400">
                Document ready for searching!
              </span>
            </div>
            {uploadResult && (
              <div className="text-center">
                <p className="text-sm font-medium">{uploadResult.filename}</p>
                <p className="text-xs text-muted-foreground">
                  You can now ask questions about this document
                </p>
              </div>
            )}
          </div>
        )

      default:
        return null
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleDialogChange}>
      <DialogTrigger asChild>
        {children || (
          <Button variant="outline" size="sm" className="gap-2">
            <Upload className="h-4 w-4" />
            Upload Document
          </Button>
        )}
      </DialogTrigger>

      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {step === "select" && "Upload Document"}
            {step === "uploading" && "Processing..."}
            {step === "description" && "Describe Document"}
            {step === "complete" && "Upload Complete"}
          </DialogTitle>
        </DialogHeader>

        {renderContent()}
      </DialogContent>
    </Dialog>
  )
}