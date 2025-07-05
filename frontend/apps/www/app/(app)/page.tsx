"use client"

import { useState } from "react"
import { useChat, type UseChatOptions } from "@ai-sdk/react"

import { cn } from "@/lib/utils"
import { InfoButton } from "@/components/ui/info-button"
import { ArtefactPanel } from "@/registry/custom/artefact-panel"
import { Chat } from "@/registry/default/ui/chat"
import {
  info_button_message,
  info_button_title,
  query_suggestions,
} from "@/app/settings"

import { getSessionId } from "./session"

// Function to send feedback via frontend API route (avoids CORS issues)
async function sendFeedback(
  streamId: string,
  rating: "thumbs-up" | "thumbs-down"
) {
  try {
    console.log(`Sending feedback for stream ${streamId}: ${rating}`)
    const response = await fetch("/api/feedback", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        stream_id: streamId,
        rating: rating,
      }),
    })

    if (response.ok) {
      const result = await response.json()
      console.log("Feedback saved successfully:", result)
      // You could show a toast notification here
    } else {
      console.error("Failed to save feedback:", response.statusText)
    }
  } catch (error) {
    console.error("Error sending feedback:", error)
  }
}

export default function ChatDemo() {
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(
    null
  )

  const sessionId = getSessionId()

  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    append,
    stop,
    isLoading,
    setMessages,
  } = useChat({
    api: "/api/chat",
    body: {
      session_id: sessionId,
    },
  })

  // Handle feedback submission
  const handleRateResponse = async (
    messageId: string,
    rating: "thumbs-up" | "thumbs-down"
  ) => {
    console.log(`Rating message ${messageId} with ${rating}`)
    await sendFeedback(sessionId, rating)
  }

  return (
    <div className="h-[90vh] w-full bg-background">
      <div className="flex h-full">
        {/* Chat Panel - Left Side */}
        <div
          className={cn(
            "flex h-full flex-col border-r transition-all duration-300",
            selectedArtifactId
              ? "w-1/2 border-border"
              : "w-full border-transparent"
          )}
        >
          <div className="mx-auto flex h-full w-full max-w-6xl flex-col">
            {/* Header with Info Button */}
            <div className="flex items-center justify-between border-b border-border/50 p-4">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold text-foreground">
                  YAAAF Chat
                </h1>
              </div>
              <InfoButton
                title={info_button_title}
                message={info_button_message}
                className="text-muted-foreground hover:text-foreground"
              />
            </div>

            <Chat
              className="grow"
              messages={messages}
              handleSubmit={handleSubmit}
              input={input}
              handleInputChange={handleInputChange}
              isGenerating={isLoading}
              stop={stop}
              append={append}
              setMessages={setMessages}
              suggestions={query_suggestions.split(",")}
              onArtifactClick={setSelectedArtifactId}
              onRateResponse={handleRateResponse}
            />
          </div>
        </div>

        {/* Artifact Panel - Right Side */}
        {selectedArtifactId && (
          <div className="h-full w-1/2">
            <ArtefactPanel
              artifactId={selectedArtifactId}
              onClose={() => setSelectedArtifactId(null)}
            />
          </div>
        )}
      </div>
    </div>
  )
}
