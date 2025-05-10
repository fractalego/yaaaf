"use client"

import { toast } from "sonner"

import { PromptSuggestions } from "@/registry/default/ui/prompt-suggestions"

export default function PromptSuggestionsDemo() {
  return (
    <div className="w-full">
      <PromptSuggestions
        label="Try one of these prompts!"
        append={(message) => {
          toast(`Clicked on "${message.content}"`)
        }}
        suggestions={[
          "What is the capital of France?",
          "Who won the 2022 FIFA World Cup?",
          "Give me a vegan lasagna recipe for 3 people.",
        ]}
      />
    </div>
  )
}
