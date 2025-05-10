import { ChatMessage } from "@/registry/default/ui/chat-message"

export default function ChatMessageAnimationsDemo() {
  return (
    <div className="w-full space-y-4">
      <ChatMessage
        id="1"
        role="user"
        content="Slide animation"
        animation="slide"
      />
      <ChatMessage
        id="2"
        role="assistant"
        content="Scale animation"
        animation="scale"
      />
      <ChatMessage
        id="3"
        role="user"
        content="Fade animation"
        animation="fade"
      />
      <ChatMessage
        id="4"
        role="assistant"
        content="No animation"
        animation="none"
      />
    </div>
  )
}
