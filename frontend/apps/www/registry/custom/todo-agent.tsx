"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function TodoAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="inline-block bg-slate-200 dark:bg-slate-700 dark:text-white p-3 text-xl rounded-sm">
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
            className="lucide lucide-list-checks"
          >
            <path d="M3 17l2 2l4-4" />
            <path d="M3 7l2 2l4-4" />
            <path d="M13 6h8" />
            <path d="M13 12h8" />
            <path d="M13 18h8" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-slate-600 dark:text-slate-400 opacity-70 font-mono">
          Todo Agent
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-slate-600 dark:text-slate-400"
          />
        )}
      </div>
      <div>{element.text}</div>
    </div>
  )
}

TodoAgent.displayName = "TodoAgent"
export { TodoAgent }
