import { ChatMessage } from "@/registry/default/ui/chat-message"

export default function ChatMessageTimestampDemo() {
  const createdAt = new Date("2024-11-28T11:37:00.000Z")

  return (
    <div className="w-full space-y-4">
      <ChatMessage
        id="1"
        role="user"
        content="Message with timestamp"
        createdAt={createdAt}
        showTimeStamp
      />
    </div>
  )
}
