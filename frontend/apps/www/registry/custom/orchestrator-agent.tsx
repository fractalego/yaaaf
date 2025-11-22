"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function OrchestratorAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="block bg-zinc-100 dark:bg-zinc-800 dark:text-white p-3 text-xl rounded-sm my-2 border-l-4 border-zinc-400 dark:border-zinc-500">
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
            className="lucide lucide-check-circle"
          >
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-zinc-600 dark:text-zinc-300 opacity-90 font-mono">
          Result
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-zinc-600 dark:text-zinc-300"
          />
        )}
      </div>
      <div className="whitespace-pre-wrap break-words">{element.text}</div>
    </div>
  )
}

OrchestratorAgent.displayName = "OrchestratorAgent"
export { OrchestratorAgent }
