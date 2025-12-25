"use client"

import React, { useCallback, useEffect, useRef, useState } from "react"
import { Loader2, Send } from "lucide-react"

import { ExecutionPlan } from "@/lib/plan-types"
import { streamingClient } from "@/lib/streaming-client"
import { usePlanExecution } from "@/hooks/use-plan-execution"

import { ChatMessageWithPlan } from "./chat-message-with-plan"

interface ChatMessage {
  id: string
  content: string
  isUser: boolean
  timestamp: Date
  plan?: ExecutionPlan
}

interface EnhancedChatProps {
  className?: string
  placeholder?: string
  onMessage?: (message: string) => void
}

export function EnhancedChat({
  className = "",
  placeholder = "Ask me anything...",
  onMessage,
}: EnhancedChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [currentResponse, setCurrentResponse] = useState("")

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { currentPlan, handlePlanUpdate, clearCurrentPlan } = usePlanExecution()

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, currentResponse, currentPlan, scrollToBottom])

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (!input.trim() || isLoading) return

      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        content: input.trim(),
        isUser: true,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, userMessage])
      setInput("")
      setIsLoading(true)
      setCurrentResponse("")
      clearCurrentPlan()

      // Notify parent component
      onMessage?.(userMessage.content)

      try {
        await streamingClient.streamChat(userMessage.content, {
          onMessage: (content: string) => {
            setCurrentResponse((prev) => prev + content)
          },

          onPlanUpdate: (update) => {
            handlePlanUpdate(update)
          },

          onError: (error: Error) => {
            console.error("Streaming error:", error)
            setCurrentResponse(
              "Sorry, there was an error processing your request."
            )
          },

          onComplete: () => {
            // Finalize the assistant message
            const assistantMessage: ChatMessage = {
              id: `assistant-${Date.now()}`,
              content: currentResponse,
              isUser: false,
              timestamp: new Date(),
              plan: currentPlan || undefined,
            }

            setMessages((prev) => [...prev, assistantMessage])
            setCurrentResponse("")
            setIsLoading(false)
          },
        })
      } catch (error) {
        console.error("Chat error:", error)
        setCurrentResponse("Sorry, there was an error processing your request.")
        setIsLoading(false)
      }
    },
    [
      input,
      isLoading,
      currentResponse,
      currentPlan,
      handlePlanUpdate,
      clearCurrentPlan,
      onMessage,
    ]
  )

  const handleKeyPress = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        handleSubmit(e)
      }
    },
    [handleSubmit]
  )

  return (
    <div className={`flex h-full flex-col ${className}`}>
      {/* Messages Container */}
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((message) => (
          <ChatMessageWithPlan
            key={message.id}
            content={message.content}
            plan={message.plan}
            isUser={message.isUser}
            timestamp={message.timestamp}
          />
        ))}

        {/* Current Response with Live Plan Updates */}
        {(currentResponse || currentPlan) && (
          <ChatMessageWithPlan
            content={currentResponse || "Processing your request..."}
            plan={currentPlan || undefined}
            isUser={false}
            timestamp={new Date()}
          />
        )}

        {/* Loading Indicator */}
        {isLoading && !currentResponse && !currentPlan && (
          <div className="mb-4 flex justify-start">
            <div className="rounded-lg bg-gray-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-gray-600">Thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <div className="border-t p-4">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={placeholder}
              disabled={isLoading}
              className="w-full resize-none rounded-lg border border-gray-300 px-3 py-2 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              rows={1}
              style={{
                minHeight: "40px",
                maxHeight: "120px",
                height: "auto",
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement
                target.style.height = "auto"
                target.style.height = `${Math.min(target.scrollHeight, 120)}px`
              }}
            />
          </div>
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="rounded-lg bg-blue-500 px-4 py-2 text-white transition-colors hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </form>
      </div>
    </div>
  )
}

// Export for backward compatibility
export { EnhancedChat as Chat }
