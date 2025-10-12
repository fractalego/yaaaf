"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function AnswererAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="block bg-blue-50 dark:bg-blue-900/20 dark:text-white p-3 text-xl rounded-sm border border-blue-200 dark:border-blue-800 my-2">
      <div className="flex items-center gap-2 mb-1">
        <div className="inline-block">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1"
            stroke-linecap="round"
            stroke-linejoin="round"
            className="lucide lucide-message-square-text"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            <path d="M13 8H7" />
            <path d="M17 12H7" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-blue-600 dark:text-blue-400 opacity-70 font-mono">
          Answerer Agent
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-blue-600 dark:text-blue-400"
          />
        )}
      </div>
      <div className="whitespace-pre-wrap break-words">{element.text}</div>
    </div>
  )
}

AnswererAgent.displayName = "AnswererAgent"
export { AnswererAgent }
