"use client"

import { useState } from "react"
import { useChat, type UseChatOptions } from "@ai-sdk/react"

import { cn } from "@/lib/utils"
import { ArtefactPanel } from "@/registry/custom/artefact-panel"
import { Chat } from "@/registry/default/ui/chat"
import { query_suggestions } from "@/app/settings"

import { getSessionId } from "./session"

export default function ChatDemo() {
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(
    null
  )

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
      session_id: getSessionId(),
    },
  })

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
          <div className="mx-auto flex h-full w-full max-w-4xl flex-col">
            <Chat
              className="grow"
              // @ts-expect-error @ts-ignore
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
