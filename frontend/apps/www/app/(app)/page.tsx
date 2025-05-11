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
    <div className="mx-auto grid min-h-screen w-full max-w-4xl place-items-center bg-background">
      <div className={cn("flex", "flex-col", "h-2/3", "w-full")}>
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
            "what are the most common types of finds in the dataset?",
            "Plot the distribution of finds by type",
          ]}
        />
      </div>
    </div>
  )
}
