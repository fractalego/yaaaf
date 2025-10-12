"use client"

import { useEffect, useState } from "react"
import { useChat, type UseChatOptions } from "@ai-sdk/react"
import { CheckSquare, Database } from "lucide-react"

import { cn } from "@/lib/utils"
import { InfoButton } from "@/components/ui/info-button"
import { SourcesModal } from "@/components/ui/sources-modal"
import { TodoListModal } from "@/components/ui/todo-list-modal"
import { ArtefactPanel } from "@/registry/custom/artefact-panel"
import { Button } from "@/registry/default/ui/button"
import { Chat } from "@/registry/default/ui/chat"
import {
  info_button_message,
  info_button_title,
  query_suggestions,
} from "@/app/settings"

import {
  getSessionId,
  getSessionIdForNewMessage,
  markSessionAsPaused,
} from "./session"

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
  const [hasDocumentRetrieverAgent, setHasDocumentRetrieverAgent] =
    useState<boolean>(false)
  const [hasSqlAgent, setHasSqlAgent] = useState<boolean>(false)
  const [isTodoModalOpen, setIsTodoModalOpen] = useState<boolean>(false)
  const [isSourcesModalOpen, setIsSourcesModalOpen] = useState<boolean>(false)

  const [currentSessionId, setCurrentSessionId] = useState<string>(
    getSessionIdForNewMessage()
  )

  const {
    messages,
    input,
    handleInputChange,
    handleSubmit: originalHandleSubmit,
    append: originalAppend,
    stop,
    isLoading,
    setMessages,
  } = useChat({
    api: "/api/chat",
    body: {
      session_id: currentSessionId,
    },
  })

  // Custom handlers that update session ID before calling original handlers
  const handleSubmit = (event?: { preventDefault?: () => void }) => {
    setCurrentSessionId(getSessionIdForNewMessage())
    originalHandleSubmit(event)
  }

  const append = (message: { role: "user"; content: string }) => {
    setCurrentSessionId(getSessionIdForNewMessage())
    originalAppend(message)
  }

  // Check for paused or completed messages and mark session accordingly
  useEffect(() => {
    const lastMessage = messages[messages.length - 1]
    if (
      lastMessage?.role === "assistant" &&
      (lastMessage?.content?.includes("<taskpaused/>") ||
        lastMessage?.content?.includes("<taskcompleted/>"))
    ) {
      markSessionAsPaused()
    }
  }, [messages])

  // Check for agents on component mount
  useEffect(() => {
    const checkAgents = async () => {
      try {
        const response = await fetch("http://localhost:4000/get_agents_config")
        if (response.ok) {
          const agents = await response.json()
          console.log("Received agents config:", agents)
          const documentRetrieverAgentPresent = agents.some(
            (agent: any) =>
              agent.name === "document_retriever" && agent.type === "agent"
          )
          const sqlAgentPresent = agents.some(
            (agent: any) => agent.name === "sql" && agent.type === "agent"
          )
          console.log(
            "Document retriever agent present:",
            documentRetrieverAgentPresent
          )
          console.log("SQL agent present:", sqlAgentPresent)
          setHasDocumentRetrieverAgent(documentRetrieverAgentPresent)
          setHasSqlAgent(sqlAgentPresent)
        }
      } catch (error) {
        console.error("Failed to check for agents:", error)
      }
    }

    checkAgents()
  }, [])

  // Handle feedback submission
  const handleRateResponse = async (
    messageId: string,
    rating: "thumbs-up" | "thumbs-down"
  ) => {
    console.log(`Rating message ${messageId} with ${rating}`)
    await sendFeedback(currentSessionId, rating)
  }

  // Handle file upload (for Document Retriever Agent)
  const handleFileUpload = (sourceId: string, fileName: string) => {
    console.log(`File uploaded: ${fileName} with source ID: ${sourceId}`)
    // You could add a toast notification here or update UI to show upload success
  }

  // Handle SQL upload
  const handleSqlUpload = (
    tableName: string,
    fileName: string,
    rowsInserted: number
  ) => {
    console.log(
      `SQL file uploaded: ${fileName} to table ${tableName} with ${rowsInserted} rows`
    )
    // You could add a toast notification here or update UI to show upload success
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
            {/* Header with Info Button and Todo Button */}
            <div className="flex items-center justify-between border-b border-border/50 p-4">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold text-foreground">
                  YAAAF Chat
                </h1>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsSourcesModalOpen(true)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <Database className="mr-2 h-4 w-4" />
                  Sources
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsTodoModalOpen(true)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <CheckSquare className="mr-2 h-4 w-4" />
                  Todo List
                </Button>
                <InfoButton
                  title={info_button_title}
                  message={info_button_message}
                  className="text-muted-foreground hover:text-foreground"
                />
              </div>
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
              hasDocumentRetrieverAgent={hasDocumentRetrieverAgent}
              hasSqlAgent={hasSqlAgent}
              onFileUpload={handleFileUpload}
              onSqlUpload={handleSqlUpload}
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

      {/* Sources Modal */}
      <SourcesModal
        isOpen={isSourcesModalOpen}
        onClose={() => setIsSourcesModalOpen(false)}
      />

      {/* Todo List Modal */}
      <TodoListModal
        isOpen={isTodoModalOpen}
        onClose={() => setIsTodoModalOpen(false)}
        streamId={currentSessionId}
      />
    </div>
  )
}
