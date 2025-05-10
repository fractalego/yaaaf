import { ChatMessage } from "@/registry/default/ui/chat-message"

export default function ChatMessageDemo() {
  return (
    <div className="w-full space-y-2">
      <ChatMessage id="1" role="user" content="Hello! What is your name?" />
      <ChatMessage
        id="2"
        role="assistant"
        content="Hello! I go by ChatGPT. How are you?"
      />
    </div>
  )
}
