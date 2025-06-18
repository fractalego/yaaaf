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
}

export function MessageList({
  messages,
  showTimeStamps = true,
  isTyping = false,
  messageOptions,
  onArtifactClick,
}: MessageListProps) {
  return (
    <div className="space-y-4 overflow-visible">
      {messages.map((message, index) => {
        const additionalOptions =
          typeof messageOptions === "function"
            ? messageOptions(message)
            : messageOptions

        return (
          <ChatMessage
            key={index}
            showTimeStamp={showTimeStamps}
            {...message}
            {...additionalOptions}
            onArtifactClick={onArtifactClick}
          />
        )
      })}
      {isTyping && <TypingIndicator />}
    </div>
  )
}
