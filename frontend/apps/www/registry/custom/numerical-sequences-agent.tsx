"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function NumericalSequencesAgent(element: {
  text: string
  modelName?: string
}) {
  return (
    <div className="inline-block bg-blue-300 dark:bg-blue-600 dark:text-white p-3 text-xl rounded-sm">
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
            className="lucide lucide-trending-up"
          >
            <polyline points="22,7 13.5,15.5 8.5,10.5 2,17" />
            <polyline points="16,7 22,7 22,13" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-blue-600 dark:text-blue-400 opacity-70 font-mono">
          Numerical Sequences Agent
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-blue-600 dark:text-blue-400"
          />
        )}
      </div>
      <div>{element.text}</div>
    </div>
  )
}

NumericalSequencesAgent.displayName = "NumericalSequencesAgent"
export { NumericalSequencesAgent }
