"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function UserInputAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="block bg-neutral-100 dark:bg-neutral-800 dark:text-white p-3 text-xl rounded-sm my-2">
      <div className="flex items-center gap-2 mb-1">
        <div className="inline-block">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="lucide lucide-user-round-check"
          >
            <path d="M2 21a8 8 0 0 1 13.292-6" />
            <circle cx="10" cy="8" r="5" />
            <path d="m16 19 2 2 4-4" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-neutral-600 dark:text-neutral-400 opacity-70 font-mono">
          User Input Agent
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-neutral-600 dark:text-neutral-400"
          />
        )}
      </div>
      <div className="whitespace-pre-wrap break-words">{element.text}</div>
    </div>
  )
}

UserInputAgent.displayName = "UserInputAgent"
export { UserInputAgent }
