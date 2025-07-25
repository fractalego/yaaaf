"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function DuckDuckGoSearchAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="inline-block bg-gray-200 dark:bg-gray-700 dark:text-white p-3 text-xl rounded-sm">
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
            <path
              fill-rule="evenodd"
              clip-rule="evenodd"
              d="M1.5 6.5C1.5 3.73858 3.73858 1.5 6.5 1.5C9.26142 1.5 11.5 3.73858 11.5 6.5C11.5 9.26142 9.26142 11.5 6.5 11.5C3.73858 11.5 1.5 9.26142 1.5 6.5ZM6.5 0C2.91015 0 0 2.91015 0 6.5C0 10.0899 2.91015 13 6.5 13C8.02469 13 9.42677 12.475 10.5353 11.596L13.9697 15.0303L14.5 15.5607L15.5607 14.5L15.0303 13.9697L11.596 10.5353C12.475 9.42677 13 8.02469 13 6.5C13 2.91015 10.0899 0 6.5 0Z"
              fill="currentColor"
            ></path>
          </svg>
        </div>
        <span className="flex-1 text-xs text-gray-600 dark:text-gray-400 opacity-70 font-mono">
          Web Search Agent
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

DuckDuckGoSearchAgent.displayName = "DuckDuckGoSearchAgent"
export { DuckDuckGoSearchAgent }
