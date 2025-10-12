import {
  ChatMessage,
  type ChatMessageProps,
  type Message,
} from "@/registry/default/ui/chat-message"
import { TypingIndicator } from "@/registry/default/ui/typing-indicator"

type AdditionalMessageOptions = Omit<ChatMessageProps, keyof Message>

interface MessageListProps {
  messages: Message[]
  showTimeStamps?: boolean
  isTyping?: boolean
  messageOptions?:
    | AdditionalMessageOptions
    | ((message: Message) => AdditionalMessageOptions)
  onArtifactClick?: (artifactId: string) => void
  streamStatus?: {
    goal: string
    current_agent: string
    is_active: boolean
  }
}

export function MessageList({
  messages,
  showTimeStamps = true,
  isTyping = false,
  messageOptions,
  onArtifactClick,
  streamStatus,
}: MessageListProps) {
  return (
    <div className="space-y-4 overflow-visible">
      {messages.map((message, index) => {
        const additionalOptions =
          typeof messageOptions === "function"
            ? messageOptions(message)
            : messageOptions

        // Pass streamStatus only to the last assistant message (the one being generated)
        const isLastAssistantMessage = 
          message.role === "assistant" && 
          index === messages.length - 1 &&
          streamStatus?.is_active

        return (
          <ChatMessage
            key={index}
            showTimeStamp={showTimeStamps}
            {...message}
            {...additionalOptions}
            onArtifactClick={onArtifactClick}
            streamStatus={isLastAssistantMessage ? streamStatus : undefined}
          />
        )
      })}
      {isTyping && <TypingIndicator streamStatus={streamStatus} />}
    </div>
  )
}
