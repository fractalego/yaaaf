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

        // Check if this is the last assistant message
        const isLastMessage = message.role === "assistant" && index === messages.length - 1

        // Pass streamStatus only to the last assistant message (the one being generated)
        const shouldPassStatus = isLastMessage && streamStatus?.is_active

        return (
          <ChatMessage
            key={index}
            showTimeStamp={showTimeStamps}
            {...message}
            {...additionalOptions}
            onArtifactClick={onArtifactClick}
            streamStatus={shouldPassStatus ? streamStatus : undefined}
            isLastMessage={isLastMessage}
          />
        )
      })}
      {isTyping && <TypingIndicator streamStatus={streamStatus} />}
    </div>
  )
}
