import { ThumbsDown, ThumbsUp } from "lucide-react"

import { Button } from "@/registry/default/ui/button"
import { ChatMessage } from "@/registry/default/ui/chat-message"
import { CopyButton } from "@/registry/default/ui/copy-button"

export default function ChatMessageActionsDemo() {
  return (
    <div className="w-full space-y-4">
      <ChatMessage
        id="1"
        role="assistant"
        content="Here's a message with actions"
        actions={
          <>
            <div className="border-r pr-1">
              <CopyButton
                content="Here's a message with actions"
                copyMessage="Copied response to clipboard!"
              />
            </div>
            <Button size="icon" variant="ghost" className="h-6 w-6">
              <ThumbsUp className="h-4 w-4" />
            </Button>
            <Button size="icon" variant="ghost" className="h-6 w-6">
              <ThumbsDown className="h-4 w-4" />
            </Button>
          </>
        }
      />
    </div>
  )
}
