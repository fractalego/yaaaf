"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function BraveSearchAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="inline-block bg-gray-100 dark:bg-gray-800 dark:text-white p-3 text-xl rounded-sm">
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
            className="lucide lucide-shield-check"
          >
            <path d="M20 13c0 5-3.5 7.5-8 10.5-4.5-3-8-5.5-8-10.5 0-3.5 2.5-7 8-7s8 3.5 8 7z" />
            <path d="m9 12 2 2 4-4" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-gray-600 dark:text-gray-400 opacity-70 font-mono">
          Brave Search Agent
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-gray-600 dark:text-gray-400"
          />
        )}
      </div>
      <div>{element.text}</div>
    </div>
  )
}

BraveSearchAgent.displayName = "BraveSearchAgent"
export { BraveSearchAgent }
