"use client"

import {useChat, type UseChatOptions} from "@ai-sdk/react"
import {cn} from "@/lib/utils"
import {transcribeAudio} from "@/lib/utils/audio"
import {Chat} from "@/registry/default/ui/chat"
import {getSessionId} from "./session"
import {query_suggestions} from "@/app/settings";

export default  function ChatDemo() {

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
    api: "/api/chat",
    body: {
      session_id: getSessionId()
    },
  })

  return (
    <div className="mx-auto grid h-[90vh] w-full max-w-4xl place-items-center bg-background">
      <div className={cn("flex", "flex-col", "h-[80vh]", "w-full", 'overflow-none')}>
        <Chat
          className="grow"
           // @ts-expect-error @ts-ignore
          messages={messages}
          handleSubmit={handleSubmit}
          input={input}
          handleInputChange={handleInputChange}
          isGenerating={isLoading}
          stop={stop}
          append={append}
          setMessages={setMessages}
          transcribeAudio={transcribeAudio}
          suggestions={query_suggestions.split(',')}
        />
      </div>
    </div>
  )
}
