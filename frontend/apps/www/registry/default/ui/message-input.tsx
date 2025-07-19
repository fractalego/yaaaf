"use client"

import React, { useEffect, useRef, useState } from "react"
import {
  ArrowUp,
  Database,
  Paperclip,
  Square,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { FileUpload } from "@/components/file-upload"
import { SqlUpload } from "@/components/sql-upload"
import { useAutosizeTextArea } from "@/registry/default/hooks/use-autosize-textarea"
import { Button } from "@/registry/default/ui/button"
import { InterruptPrompt } from "@/registry/default/ui/interrupt-prompt"

interface MessageInputProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  value: string
  submitOnEnter?: boolean
  stop?: () => void
  isGenerating: boolean
  enableInterrupt?: boolean
  onRateResponse?: (
    messageId: string,
    rating: "thumbs-up" | "thumbs-down"
  ) => void
  lastMessageId?: string
  hasRagAgent?: boolean
  hasSqlAgent?: boolean
  onFileUpload?: (sourceId: string, fileName: string) => void
  onSqlUpload?: (
    tableName: string,
    fileName: string,
    rowsInserted: number
  ) => void
}

export function MessageInput({
  placeholder = "Ask AI...",
  className,
  onKeyDown: onKeyDownProp,
  submitOnEnter = true,
  stop,
  isGenerating,
  enableInterrupt = true,
  onRateResponse,
  lastMessageId,
  hasRagAgent = false,
  hasSqlAgent = false,
  onFileUpload,
  onSqlUpload,
  ...props
}: MessageInputProps) {
  const [showInterruptPrompt, setShowInterruptPrompt] = useState(false)

  useEffect(() => {
    if (!isGenerating) {
      setShowInterruptPrompt(false)
    }
  }, [isGenerating])

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (submitOnEnter && event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()

      if (isGenerating && stop && enableInterrupt) {
        if (showInterruptPrompt) {
          stop()
          setShowInterruptPrompt(false)
          event.currentTarget.form?.requestSubmit()
        } else if (props.value) {
          setShowInterruptPrompt(true)
          return
        }
      }

      event.currentTarget.form?.requestSubmit()
    }

    onKeyDownProp?.(event)
  }

  const textAreaRef = useRef<HTMLTextAreaElement>(null)
  const [textAreaHeight, setTextAreaHeight] = useState<number>(0)

  useEffect(() => {
    if (textAreaRef.current) {
      setTextAreaHeight(textAreaRef.current.offsetHeight)
    }
  }, [props.value])

  useAutosizeTextArea({
    ref: textAreaRef,
    maxHeight: 240,
    borderWidth: 1,
    dependencies: [props.value],
  })

  return (
    <div className="relative flex w-full">
      {enableInterrupt && (
        <InterruptPrompt
          isOpen={showInterruptPrompt}
          close={() => setShowInterruptPrompt(false)}
        />
      )}

      <div className="relative flex w-full items-center space-x-2">
        {/* Feedback buttons - always visible */}
        {onRateResponse && lastMessageId && (
          <div className="flex gap-1">
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-muted-foreground hover:text-green-600"
              aria-label="Rate response positively"
              onClick={() => onRateResponse(lastMessageId, "thumbs-up")}
            >
              <ThumbsUp className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-muted-foreground hover:text-red-600"
              aria-label="Rate response negatively"
              onClick={() => onRateResponse(lastMessageId, "thumbs-down")}
            >
              <ThumbsDown className="h-4 w-4" />
            </Button>
          </div>
        )}

        <div className="relative flex-1">
          <textarea
            aria-label="Write your prompt here"
            placeholder={placeholder}
            ref={textAreaRef}
            onKeyDown={onKeyDown}
            className={cn(
              "z-10 w-full grow resize-none rounded-xl border border-input bg-background p-3 pr-24 text-sm ring-offset-background transition-[border] placeholder:text-muted-foreground focus-visible:border-primary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50",
              className
            )}
            {...props}
          />
        </div>
      </div>

      <div className="absolute right-3 top-3 z-20 flex gap-1">
        {/* File Upload Button - Show only if RAG agent is present */}
        {hasRagAgent && (
          <FileUpload onFileUpload={onFileUpload}>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              aria-label="Upload document"
            >
              <Paperclip className="h-4 w-4" />
            </Button>
          </FileUpload>
        )}

        {/* SQL Upload Button - Show only if SQL agent is present */}
        {hasSqlAgent && (
          <SqlUpload onFileUpload={onSqlUpload}>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              aria-label="Upload CSV/Excel to database"
            >
              <Database className="h-4 w-4" />
            </Button>
          </SqlUpload>
        )}

        {isGenerating && stop ? (
          <Button
            type="button"
            size="icon"
            className="h-8 w-8"
            aria-label="Stop generating"
            onClick={stop}
          >
            <Square className="h-3 w-3 animate-pulse" fill="currentColor" />
          </Button>
        ) : (
          <Button
            type="submit"
            size="icon"
            className="h-8 w-8 transition-opacity"
            aria-label="Send message"
            disabled={props.value === "" || isGenerating}
          >
            <ArrowUp className="h-5 w-5" />
          </Button>
        )}
      </div>
    </div>
  )
}
MessageInput.displayName = "MessageInput"
