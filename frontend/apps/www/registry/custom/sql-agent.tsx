"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function SqlAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="inline-block bg-slate-300 dark:bg-slate-600 dark:text-white p-3 text-xl rounded-sm">
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
            className="lucide lucide-database-icon lucide-database"
          >
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M3 5V19A9 3 0 0 0 21 19V5" />
            <path d="M3 12A9 3 0 0 0 21 12" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-slate-600 dark:text-slate-400 opacity-70 font-mono">
          SQL Agent
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

SqlAgent.displayName = "SqlAgent"
export { SqlAgent }
