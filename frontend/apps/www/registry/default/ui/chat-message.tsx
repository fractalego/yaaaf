"use client"

import React, { useMemo, useState } from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { motion } from "framer-motion"
import { Ban, Brain, ChevronRight, Code2, Loader2, Terminal } from "lucide-react"

import { unescapeHtmlContent } from "@/lib/html-escape"
import { cn } from "@/lib/utils"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/registry/default/ui/collapsible"
import { FilePreview } from "@/registry/default/ui/file-preview"
import { MarkdownRenderer } from "@/registry/default/ui/markdown-renderer"
import { complete_tag, paused_tag } from "@/app/settings"

const chatBubbleVariants = cva(
  "group/message relative break-words rounded-xl p-4 text-sm sm:max-w-[85%] shadow-sm border",
  {
    variants: {
      isUser: {
        true: "bg-primary text-primary-foreground border-primary/20 shadow-md",
        false:
          "bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-900 text-foreground border-border/40 shadow-lg",
      },
      animation: {
        none: "",
        slide: "duration-300 animate-in fade-in-0",
        scale: "duration-300 animate-in fade-in-0 zoom-in-75",
        fade: "duration-500 animate-in fade-in-0",
      },
    },
    compoundVariants: [
      {
        isUser: true,
        animation: "slide",
        class: "slide-in-from-right",
      },
      {
        isUser: false,
        animation: "slide",
        class: "slide-in-from-left",
      },
      {
        isUser: true,
        animation: "scale",
        class: "origin-bottom-right",
      },
      {
        isUser: false,
        animation: "scale",
        class: "origin-bottom-left",
      },
    ],
  }
)

type Animation = VariantProps<typeof chatBubbleVariants>["animation"]

interface Attachment {
  name?: string
  contentType?: string
  url: string
}

interface PartialToolCall {
  state: "partial-call"
  toolName: string
}

interface ToolCall {
  state: "call"
  toolName: string
}

interface ToolResult {
  state: "result"
  toolName: string
  result: {
    __cancelled?: boolean
    [key: string]: any
  }
}

type ToolInvocation = PartialToolCall | ToolCall | ToolResult

interface ReasoningPart {
  type: "reasoning"
  reasoning: string
}

interface ThinkingPart {
  type: "thinking"
  thinking: string
}

interface ToolInvocationPart {
  type: "tool-invocation"
  toolInvocation: ToolInvocation
}

interface TextPart {
  type: "text"
  text: string
}

// For compatibility with AI SDK types, not used
interface SourcePart {
  type: "source"
}

type MessagePart =
  | TextPart
  | ReasoningPart
  | ThinkingPart
  | ToolInvocationPart
  | SourcePart

export interface Message {
  id: string
  role: "user" | "assistant" | (string & {})
  content: string
  createdAt?: Date
  experimental_attachments?: Attachment[]
  toolInvocations?: ToolInvocation[]
  parts?: MessagePart[]
}

export interface ChatMessageProps extends Message {
  showTimeStamp?: boolean
  animation?: Animation
  actions?: React.ReactNode
  onArtifactClick?: (artifactId: string) => void
}

// Function to extract thinking artifacts from content and convert to parts
function extractThinkingParts(
  content: string,
  onArtifactClick?: (artifactId: string) => void
): MessagePart[] {
  const parts: MessagePart[] = []

  // Regex to find thinking artifacts at the beginning of the message
  const thinkingArtifactRegex =
    /<artefact type=['"]thinking['"]>([^<]+)<\/artefact>/g
  let lastIndex = 0
  let match

  console.log("extractThinkingParts: checking content:", content.substring(0, 100))

  while ((match = thinkingArtifactRegex.exec(content)) !== null) {
    const artifactId = match[1]
    console.log("extractThinkingParts: found thinking artifact:", artifactId)

    // Add text before this artifact if any
    if (match.index > lastIndex) {
      const textContent = content.slice(lastIndex, match.index).trim()
      if (textContent) {
        parts.push({ type: "text", text: textContent })
      }
    }

    // Fetch thinking content from backend
    // For now, we'll create a placeholder thinking part
    // TODO: Fetch actual thinking content from the artifact API
    parts.push({
      type: "thinking",
      thinking: `Thinking artifact: ${artifactId}`,
    })

    lastIndex = thinkingArtifactRegex.lastIndex
  }

  // Add remaining text content
  if (lastIndex < content.length) {
    const remainingContent = content.slice(lastIndex).trim()
    if (remainingContent) {
      parts.push({ type: "text", text: remainingContent })
    }
  }

  // If no thinking artifacts found, return single text part
  if (parts.length === 0) {
    parts.push({ type: "text", text: content })
  }

  console.log("extractThinkingParts: returning parts:", parts.length, parts.map(p => p.type))
  return parts
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  role,
  content,
  createdAt,
  showTimeStamp = false,
  animation = "scale",
  actions,
  experimental_attachments,
  toolInvocations,
  parts,
  onArtifactClick,
}) => {
  console.log(content)
  const addSpinner: boolean =
    content.indexOf(complete_tag) == -1 && content.indexOf(paused_tag) == -1

  const files = useMemo(() => {
    return experimental_attachments?.map((attachment) => {
      const dataArray = dataUrlToUint8Array(attachment.url)
      const file = new File([dataArray], attachment.name ?? "Unknown")
      return file
    })
  }, [experimental_attachments])

  const isUser = role === "user"

  const formattedTime = createdAt?.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  })

  if (isUser) {
    return (
      <div
        className={cn("flex flex-col", isUser ? "items-end" : "items-start")}
      >
        {files ? (
          <div className="mb-1 flex flex-wrap gap-2">
            {files.map((file, index) => {
              return <FilePreview file={file} key={index} />
            })}
          </div>
        ) : null}

        <div className={cn(chatBubbleVariants({ isUser, animation }))}>
          <MarkdownRenderer onArtifactClick={onArtifactClick}>
            {content}
          </MarkdownRenderer>
        </div>

        {showTimeStamp && createdAt ? (
          <time
            dateTime={createdAt.toISOString()}
            className={cn(
              "mt-1 block px-1 text-xs opacity-50",
              animation !== "none" && "duration-500 animate-in fade-in-0"
            )}
          >
            {formattedTime}
          </time>
        ) : null}
      </div>
    )
  }

  if (parts && parts.length > 0) {
    return parts.map((part, index) => {
      if (part.type === "text") {
        let text = unescapeHtmlContent(part.text)
        return (
          <div
            className={cn(
              "flex flex-col",
              isUser ? "items-end" : "items-start"
            )}
            key={`text-${index}`}
          >
            <div className={cn(chatBubbleVariants({ isUser, animation }))}>
              <MarkdownRenderer onArtifactClick={onArtifactClick}>
                {text}
              </MarkdownRenderer>
              {actions ? (
                <div className="absolute -bottom-3 right-3 flex space-x-1 rounded-lg border bg-background/95 backdrop-blur-sm p-1.5 text-foreground opacity-0 transition-all duration-200 group-hover/message:opacity-100 shadow-md">
                  {actions}
                </div>
              ) : null}
              {role == "assistant" && addSpinner ? (
                <div className="mt-4 flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-xs">Thinking...</span>
                </div>
              ) : null}
            </div>

            {showTimeStamp && createdAt ? (
              <time
                dateTime={createdAt.toISOString()}
                className={cn(
                  "mt-1 block px-1 text-xs opacity-50",
                  animation !== "none" && "duration-500 animate-in fade-in-0"
                )}
              >
                {formattedTime}
              </time>
            ) : null}
          </div>
        )
      } else if (part.type === "reasoning") {
        return <ReasoningBlock key={`reasoning-${index}`} part={part} />
      } else if (part.type === "thinking") {
        return <ThinkingBlock key={`thinking-${index}`} part={part} />
      } else if (part.type === "tool-invocation") {
        return (
          <ToolCall
            key={`tool-${index}`}
            toolInvocations={[part.toolInvocation]}
          />
        )
      }
      return null
    })
  }

  if (toolInvocations && toolInvocations.length > 0) {
    return <ToolCall toolInvocations={toolInvocations} />
  }

  // Extract thinking parts from content for assistant messages
  if (role === "assistant") {
    const extractedParts = extractThinkingParts(content, onArtifactClick)
    if (
      extractedParts.length > 1 ||
      (extractedParts.length === 1 && extractedParts[0].type !== "text")
    ) {
      return extractedParts.map((part, index) => {
        if (part.type === "text") {
          let text = unescapeHtmlContent(part.text)
          return (
            <div
              className={cn(
                "flex flex-col",
                isUser ? "items-end" : "items-start"
              )}
              key={`extracted-text-${index}`}
            >
              <div className={cn(chatBubbleVariants({ isUser, animation }))}>
                <MarkdownRenderer onArtifactClick={onArtifactClick}>
                  {text}
                </MarkdownRenderer>
                {actions ? (
                  <div className="absolute -bottom-3 right-3 flex space-x-1 rounded-lg border bg-background/95 backdrop-blur-sm p-1.5 text-foreground opacity-0 transition-all duration-200 group-hover/message:opacity-100 shadow-md">
                    {actions}
                  </div>
                ) : null}
              </div>
            </div>
          )
        } else if (part.type === "thinking") {
          return (
            <ThinkingBlock key={`extracted-thinking-${index}`} part={part} />
          )
        }
        return null
      })
    }
  }

  return (
    <div className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
      <div className={cn(chatBubbleVariants({ isUser, animation }))}>
        <MarkdownRenderer onArtifactClick={onArtifactClick}>
          {content}
        </MarkdownRenderer>
        {actions ? (
          <div className="absolute -bottom-3 right-3 flex space-x-1 rounded-lg border bg-background/95 backdrop-blur-sm p-1.5 text-foreground opacity-0 transition-all duration-200 group-hover/message:opacity-100 shadow-md">
            {actions}
          </div>
        ) : null}
      </div>

      {showTimeStamp && createdAt ? (
        <time
          dateTime={createdAt.toISOString()}
          className={cn(
            "mt-1 block px-1 text-xs opacity-50",
            animation !== "none" && "duration-500 animate-in fade-in-0"
          )}
        >
          {formattedTime}
        </time>
      ) : null}
    </div>
  )
}

function dataUrlToUint8Array(data: string) {
  const base64 = data.split(",")[1]
  const buf = Buffer.from(base64, "base64")
  return new Uint8Array(buf)
}

const ReasoningBlock = ({ part }: { part: ReasoningPart }) => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="mb-3 flex flex-col items-start sm:max-w-[85%]">
      <Collapsible
        open={isOpen}
        onOpenChange={setIsOpen}
        className="group w-full overflow-hidden rounded-xl border bg-gradient-to-br from-blue-50/80 to-indigo-50/80 dark:from-blue-950/30 dark:to-indigo-950/30 shadow-sm"
      >
        <div className="flex items-center p-3">
          <CollapsibleTrigger asChild>
            <button className="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300 hover:text-blue-800 dark:hover:text-blue-200 transition-colors">
              <ChevronRight className="h-4 w-4 transition-transform group-data-[state=open]:rotate-90" />
              <span className="font-medium">💭 Thinking</span>
            </button>
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent forceMount>
          <motion.div
            initial={false}
            animate={isOpen ? "open" : "closed"}
            variants={{
              open: { height: "auto", opacity: 1 },
              closed: { height: 0, opacity: 0 },
            }}
            transition={{ duration: 0.3, ease: [0.04, 0.62, 0.23, 0.98] }}
            className="border-t border-blue-200/50 dark:border-blue-800/50"
          >
            <div className="p-3 bg-white/50 dark:bg-slate-900/50">
              <div className="whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {part.reasoning}
              </div>
            </div>
          </motion.div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

const ThinkingBlock = ({ part }: { part: ThinkingPart }) => {
  const [isOpen, setIsOpen] = useState(false)
  const [thinkingContent, setThinkingContent] = useState<string>("")
  const [isLoading, setIsLoading] = useState(false)

  // Extract artifact ID from thinking content (assuming format "Thinking artifact: {id}")
  const artifactId = part.thinking.includes("Thinking artifact: ")
    ? part.thinking.replace("Thinking artifact: ", "")
    : null

  const fetchThinkingContent = async () => {
    if (!artifactId || thinkingContent) return

    setIsLoading(true)
    try {
      const { get_artefact } = await import("@/app/artefacts/actions")
      const data = await get_artefact(artifactId)
      // Use code field for thinking content (as it's stored in the code field)
      setThinkingContent(data.code || "No thinking content available")
    } catch (error) {
      console.error("Error fetching thinking content:", error)
      setThinkingContent("Error loading thinking content")
    } finally {
      setIsLoading(false)
    }
  }

  // Fetch content when opened
  React.useEffect(() => {
    if (isOpen && !thinkingContent && !isLoading) {
      fetchThinkingContent()
    }
  }, [isOpen])

  return (
    <div className="mb-3 flex flex-col items-start sm:max-w-[85%]">
      <Collapsible
        open={isOpen}
        onOpenChange={setIsOpen}
        className="group w-full overflow-hidden rounded-xl border bg-gradient-to-br from-purple-50/80 to-pink-50/80 dark:from-purple-950/30 dark:to-pink-950/30 shadow-sm"
      >
        <div className="flex items-center p-3">
          <CollapsibleTrigger asChild>
            <button className="flex items-center gap-2 text-sm text-purple-700 dark:text-purple-300 hover:text-purple-800 dark:hover:text-purple-200 transition-colors">
              <ChevronRight className="h-4 w-4 transition-transform group-data-[state=open]:rotate-90" />
              <Brain className="h-4 w-4" />
              <span className="font-medium">Thinking</span>
            </button>
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent forceMount>
          <motion.div
            initial={false}
            animate={isOpen ? "open" : "closed"}
            variants={{
              open: { height: "auto", opacity: 1 },
              closed: { height: 0, opacity: 0 },
            }}
            transition={{ duration: 0.3, ease: [0.04, 0.62, 0.23, 0.98] }}
            className="border-t border-purple-200/50 dark:border-purple-800/50"
          >
            <div className="p-3 bg-white/50 dark:bg-slate-900/50">
              {isLoading ? (
                <div className="flex items-center gap-2 text-sm text-purple-600 dark:text-purple-400">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Loading thinking...</span>
                </div>
              ) : (
                <div className="whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                  {thinkingContent || part.thinking}
                </div>
              )}
            </div>
          </motion.div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

function ToolCall({
  toolInvocations,
}: Pick<ChatMessageProps, "toolInvocations">) {
  if (!toolInvocations?.length) return null

  return (
    <div className="flex flex-col items-start gap-3">
      {toolInvocations.map((invocation, index) => {
        const isCancelled =
          invocation.state === "result" &&
          invocation.result.__cancelled === true

        if (isCancelled) {
          return (
            <div
              key={index}
              className="flex items-center gap-2 rounded-xl border bg-gradient-to-r from-red-50 to-orange-50 dark:from-red-950/30 dark:to-orange-950/30 px-4 py-3 text-sm text-red-700 dark:text-red-300 shadow-sm"
            >
              <Ban className="h-4 w-4" />
              <span>
                Cancelled{" "}
                <span className="font-mono bg-red-100 dark:bg-red-900/50 px-1.5 py-0.5 rounded text-xs">
                  {invocation.toolName}
                </span>
              </span>
            </div>
          )
        }

        switch (invocation.state) {
          case "partial-call":
          case "call":
            return (
              <div
                key={index}
                className="flex items-center gap-2 rounded-xl border bg-gradient-to-r from-blue-50 to-cyan-50 dark:from-blue-950/30 dark:to-cyan-950/30 px-4 py-3 text-sm text-blue-700 dark:text-blue-300 shadow-sm"
              >
                <Terminal className="h-4 w-4" />
                <span>
                  Calling{" "}
                  <span className="font-mono bg-blue-100 dark:bg-blue-900/50 px-1.5 py-0.5 rounded text-xs">
                    {invocation.toolName}
                  </span>
                  ...
                </span>
                <Loader2 className="h-3 w-3 animate-spin" />
              </div>
            )
          case "result":
            return (
              <div
                key={index}
                className="flex flex-col gap-2 rounded-xl border bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/30 dark:to-emerald-950/30 px-4 py-3 text-sm shadow-sm"
              >
                <div className="flex items-center gap-2 text-green-700 dark:text-green-300">
                  <Code2 className="h-4 w-4" />
                  <span>
                    Result from{" "}
                    <span className="font-mono bg-green-100 dark:bg-green-900/50 px-1.5 py-0.5 rounded text-xs">
                      {invocation.toolName}
                    </span>
                  </span>
                </div>
                <pre className="overflow-x-auto whitespace-pre-wrap text-slate-700 dark:text-slate-300 bg-white/50 dark:bg-slate-900/50 p-3 rounded-lg text-xs leading-relaxed">
                  {JSON.stringify(invocation.result, null, 2)}
                </pre>
              </div>
            )
          default:
            return null
        }
      })}
    </div>
  )
}
