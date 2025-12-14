"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function ReviewerAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="block bg-slate-100 dark:bg-slate-800 dark:text-white p-3 text-xl rounded-sm my-2">
      <div className="flex items-center gap-2 mb-1">
        <div className="inline-block">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            className="lucide lucide-search-check-icon lucide-search-check"
          >
            <path d="m8 11 2 2 4-4" />
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-slate-600 dark:text-slate-400 opacity-70 font-mono">
          Reviewer Agent
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-slate-600 dark:text-slate-400"
          />
        )}
      </div>
      <div className="whitespace-pre-wrap break-words">{element.text}</div>
    </div>
  )
}

ReviewerAgent.displayName = "ReviewerAgent"
export { ReviewerAgent }
