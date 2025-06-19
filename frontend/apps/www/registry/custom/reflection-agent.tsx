"use client"

import * as React from "react"
import { ModelIndicator } from "./model-indicator"

function ReflectionAgent(element: { text: string; modelName?: string }) {
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
            className="lucide lucide-route-icon lucide-route"
          >
            <circle cx="6" cy="19" r="3" />
            <path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15" />
            <circle cx="18" cy="5" r="3" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-slate-600 dark:text-slate-400 opacity-70 font-mono">Reflection Agent</span>
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

ReflectionAgent.displayName = "ReflectionAgent"
export { ReflectionAgent }
