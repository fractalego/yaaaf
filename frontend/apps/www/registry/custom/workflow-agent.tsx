"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function WorkflowAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="block bg-slate-200 dark:bg-slate-700 dark:text-white p-3 text-xl rounded-sm my-2 border-l-4 border-slate-400 dark:border-slate-500">
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
            className="lucide lucide-workflow"
          >
            <rect width="8" height="8" x="3" y="3" rx="2" />
            <path d="M7 11v4a2 2 0 0 0 2 2h4" />
            <rect width="8" height="8" x="13" y="13" rx="2" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-slate-600 dark:text-slate-300 opacity-90 font-mono">
          Workflow
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-slate-600 dark:text-slate-300"
          />
        )}
      </div>
      <div className="whitespace-pre-wrap break-words">{element.text}</div>
    </div>
  )
}

WorkflowAgent.displayName = "WorkflowAgent"
export { WorkflowAgent }
