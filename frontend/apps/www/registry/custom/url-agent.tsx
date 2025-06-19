"use client"

import * as React from "react"
import { ModelIndicator } from "./model-indicator"

function UrlAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="inline-block bg-stone-100 dark:bg-stone-800 dark:text-white p-3 text-xl rounded-sm">
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
            className="lucide lucide-link"
          >
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-stone-600 dark:text-stone-400 opacity-70 font-mono">URL Agent</span>
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

UrlAgent.displayName = "UrlAgent"
export { UrlAgent }
