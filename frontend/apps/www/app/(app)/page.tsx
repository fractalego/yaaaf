"use client"

import {useChat, type UseChatOptions} from "@ai-sdk/react"
import {cn} from "@/lib/utils"
import {transcribeAudio} from "@/lib/utils/audio"
import {Chat} from "@/registry/default/ui/chat"
import {getSessionId} from "./session"

type ChatDemoProps = {
  initialMessages?: UseChatOptions["initialMessages"]
}

export default function ChatDemo(props: ChatDemoProps) {

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
    ...props,
    api: "/api/chat",
    body: {
      session_id: getSessionId()
    },
  })

  return (
    <div className="mx-auto grid h-screen w-full max-w-4xl place-items-center bg-background">
      <div className={cn("flex", "flex-col", "h-[500px]", "w-full")}>
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
          transcribeAudio={transcribeAudio}
          suggestions={[
            "What is the weather in San Francisco?",
            "Explain step-by-step how to solve this math problem: If x² + 6x + 9 = 25, what is x?",
            "Design a simple algorithm to find the longest palindrome in a string.",
          ]}
        />
      </div>
    </div>
  )
}
