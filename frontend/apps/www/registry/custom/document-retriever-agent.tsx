"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function DocumentRetrieverAgent(element: { text: string; modelName?: string }) {
  return (
    <div className="block bg-slate-100 dark:bg-slate-800 dark:text-white p-3 text-xl rounded-sm my-2">
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
              d="M13.5 4.6736V9.09116L15 10.7065V4.44907C15 4.16343 14.8779 3.89142 14.6644 3.70166L10.7842 0.252591C10.6011 0.0898786 10.3647 0 10.1198 0H2.5H1V1.5V13.5C1 14.8807 2.11929 16 3.5 16H11.7275L11.3016 15.5414L10.3346 14.5H3.5C2.94772 14.5 2.5 14.0523 2.5 13.5V1.5H9.9297L13.5 4.6736ZM8 6C6.89543 6 6 6.89543 6 8C6 9.10457 6.89543 10 8 10C9.10457 10 10 9.10457 10 8C10 6.89543 9.10457 6 8 6ZM4.5 8C4.5 6.067 6.067 4.5 8 4.5C9.933 4.5 11.5 6.067 11.5 8C11.5 8.63488 11.331 9.23028 11.0354 9.74364L14.0496 12.9897L14.5599 13.5393L13.4607 14.5599L12.9504 14.0103L10.0223 10.857C9.4512 11.262 8.7534 11.5 8 11.5C6.067 11.5 4.5 9.933 4.5 8Z"
              fill="currentColor"
            ></path>
          </svg>
        </div>
        <span className="flex-1 text-xs text-slate-600 dark:text-slate-400 opacity-70 font-mono">
          Document Retriever Agent
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-slate-600 dark:text-slate-400"
          />
        )}
      </div>
      <div className="whitespace-pre-wrap break-words">{element.text}</div>
    </div>
  )
}

DocumentRetrieverAgent.displayName = "DocumentRetrieverAgent"
export { DocumentRetrieverAgent }
