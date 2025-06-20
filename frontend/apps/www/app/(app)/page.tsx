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
            {/* Header with Info Button */}
            <div className="flex items-center justify-between p-4 border-b border-border/50">
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
