"use client"

import { useEffect, useState } from "react"
import { useChat, type UseChatOptions } from "@ai-sdk/react"
import { Database } from "lucide-react"

import { cn } from "@/lib/utils"
import { InfoButton } from "@/components/ui/info-button"
import { SourcesModal } from "@/components/ui/sources-modal"
import { useStreamStatus } from "@/hooks/use-stream-status"
import { ArtefactPanel } from "@/registry/custom/artefact-panel"
import { Button } from "@/registry/default/ui/button"
import { Chat } from "@/registry/default/ui/chat"
import {
  info_button_message,
  info_button_title,
  query_suggestions,
  submit_user_response_url,
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
  const [isSourcesModalOpen, setIsSourcesModalOpen] = useState<boolean>(false)
  const [isPaused, setIsPaused] = useState<boolean>(false)

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

  const { status: streamStatus } = useStreamStatus({ 
    streamId: currentSessionId,
    isGenerating: isLoading 
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
  // Also auto-open last artifact when task is finished
  useEffect(() => {
    const lastMessage = messages[messages.length - 1]
    if (lastMessage?.role === "assistant") {
      const isPausedMessage = lastMessage?.content?.includes("<taskpaused/>")
      const isCompletedMessage = lastMessage?.content?.includes("<taskcompleted/>")

      if (isPausedMessage || isCompletedMessage) {
        markSessionAsPaused()

        // Set paused state for UI
        setIsPaused(isPausedMessage)

        // Auto-open the last artifact when task is completed/paused
        if (lastMessage?.content) {
          // Extract artifact references from the last assistant message
          const artifactMatches = lastMessage.content.match(/<artefact[^>]*>([^<]+)<\/artefact>/g)

          if (artifactMatches && artifactMatches.length > 0) {
            // Get the last artifact ID from the matches
            const lastArtifactMatch = artifactMatches[artifactMatches.length - 1]
            const artifactIdMatch = lastArtifactMatch.match(/<artefact[^>]*>([^<]+)<\/artefact>/)

            if (artifactIdMatch) {
              const artifactId = artifactIdMatch[1]
              console.log('Auto-opening final artifact:', artifactId)
              setSelectedArtifactId(artifactId)
            }
          }
        }
      } else {
        // Clear paused state if not paused
        setIsPaused(false)
      }
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

  // Handle user response submission when execution is paused
  const handleUserResponseSubmit = async (userResponse: string) => {
    console.log(`Submitting user response for stream ${currentSessionId}: ${userResponse}`)

    try {
      // First, add the user's response as a message in the UI
      const userMessage = {
        id: `user-response-${Date.now()}`,
        role: "user" as const,
        content: userResponse,
      }
      setMessages([...messages, userMessage])

      const response = await fetch(submit_user_response_url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          stream_id: currentSessionId,
          user_response: userResponse,
        }),
      })

      if (response.ok) {
        const result = await response.json()
        console.log("User response submitted successfully:", result)

        // Clear paused state - execution will resume
        setIsPaused(false)

        // Start polling for new messages from the resumed execution
        await pollForResumedMessages(currentSessionId)
      } else {
        console.error("Failed to submit user response:", response.statusText)
        // You could show an error toast here
      }
    } catch (error) {
      console.error("Error submitting user response:", error)
      // You could show an error toast here
    }
  }

  // Poll for new messages after resuming from pause
  const pollForResumedMessages = async (streamId: string) => {
    console.log(`Starting to poll for resumed messages on stream ${streamId}`)

    // First, get the current note count to know where we're starting from
    let lastNoteCount = 0
    try {
      const initialResponse = await fetch("http://localhost:4000/get_utterances", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          stream_id: streamId,
        }),
      })
      if (initialResponse.ok) {
        const initialNotes = await initialResponse.json()
        lastNoteCount = initialNotes.length
        console.log(`Starting poll from note count: ${lastNoteCount}`)
      }
    } catch (error) {
      console.error("Error getting initial note count:", error)
    }

    let consecutiveEmptyPolls = 0
    const maxEmptyPolls = 10 // Stop after 10 seconds of no new messages

    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch("http://localhost:4000/get_utterances", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            stream_id: streamId,
          }),
        })

        if (response.ok) {
          const notes = await response.json()

          // Check if there are new notes since last poll
          if (notes.length > lastNoteCount) {
            const newNotes = notes.slice(lastNoteCount)
            console.log(`Found ${newNotes.length} new messages`)

            // Convert notes to messages and append
            const newMessages = newNotes.map((note: any, index: number) => {
              // Format the note message for display
              let content = note.message
              if (note.agent_name) {
                content = `<${note.agent_name}${note.model_name ? ` data-model="${note.model_name}"` : ""}>${note.message}</${note.agent_name}>`
              }

              return {
                id: `resumed-${Date.now()}-${index}`,
                role: "assistant" as const,
                content: content,
              }
            })

            setMessages((prevMessages) => [...prevMessages, ...newMessages])

            lastNoteCount = notes.length
            consecutiveEmptyPolls = 0

            // Check if execution completed or paused again
            const lastNote = notes[notes.length - 1]
            if (
              lastNote.message.includes("<taskcompleted/>") ||
              lastNote.message.includes("<taskpaused/>")
            ) {
              console.log("Execution completed or paused again, stopping poll")
              clearInterval(pollInterval)
            }
          } else {
            // No new notes, increment counter
            consecutiveEmptyPolls++
            if (consecutiveEmptyPolls >= maxEmptyPolls) {
              console.log("No new messages for 10 seconds, stopping poll")
              clearInterval(pollInterval)
            }
          }
        }
      } catch (error) {
        console.error("Error polling for messages:", error)
        clearInterval(pollInterval)
      }
    }, 1000) // Poll every second

    // Stop polling after 5 minutes max
    setTimeout(() => {
      console.log("Polling timeout reached")
      clearInterval(pollInterval)
    }, 300000)
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
              streamStatus={streamStatus}
              isPaused={isPaused}
              onUserResponseSubmit={handleUserResponseSubmit}
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

    </div>
  )
}
