"use client"

import { useState } from "react"

import { Button } from "@/registry/default/ui/button"
import { FilePreview } from "@/registry/default/ui/file-preview"

export default function FilePreviewDemo() {
  const [files, setFiles] = useState<File[]>([])

  const handleFileSelect = () => {
    const input = document.createElement("input")
    input.type = "file"
    input.multiple = true
    input.onchange = (e) => {
      const files = (e.target as HTMLInputElement).files
      if (files) {
        setFiles(Array.from(files))
      }
    }
    input.click()
  }

  return (
    <div className="w-full space-y-4">
      <div className="flex flex-wrap gap-3">
        {files.map((file) => (
          <FilePreview
            key={file.name + file.lastModified}
            file={file}
            onRemove={() => {
              setFiles((files) => files.filter((f) => f !== file))
            }}
          />
        ))}
      </div>
      <Button onClick={handleFileSelect}>Select Files</Button>
    </div>
  )
}
