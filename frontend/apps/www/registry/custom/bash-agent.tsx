"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function BashAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="block bg-green-100 dark:bg-green-800 dark:text-white p-3 text-xl rounded-sm my-2">
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
            className="lucide lucide-terminal"
          >
            <polyline points="4,17 10,11 4,5" />
            <line x1="12" x2="20" y1="19" y2="19" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-green-600 dark:text-green-400 opacity-70 font-mono">
          Bash Agent
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-green-600 dark:text-green-400"
          />
        )}
      </div>
      <div className="whitespace-pre-wrap break-words">{element.text}</div>
    </div>
  )
}

BashAgent.displayName = "BashAgent"
export { BashAgent }
