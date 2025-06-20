"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function UrlRetrieverAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="inline-block bg-stone-200 dark:bg-stone-700 dark:text-white p-3 text-xl rounded-sm">
      <div className="flex items-center gap-2 mb-1">
        <div className="inline-block">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="-2 -2 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1"
            stroke-linecap="round"
            stroke-linejoin="round"
            className="lucide lucide-search-check-icon lucide-search-check"
          >
            <path d="m8 11 2 2 4-4" />
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-stone-600 dark:text-stone-400 opacity-70 font-mono">
          URL Retriever Agent
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-stone-600 dark:text-stone-400"
          />
        )}
      </div>
      <div>{element.text}</div>
    </div>
  )
}

UrlRetrieverAgent.displayName = "UrlRetrieverAgent"
export { UrlRetrieverAgent }
