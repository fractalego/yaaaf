"use client"

import * as React from "react"

function UrlRetrieverAgent(element: { text: string }) {
  return (
    <div className="inline-block bg-stone-200 dark:bg-stone-700 dark:text-white p-3 text-xl rounded-sm">
      <div className="inline-block pr-5">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="26"
          height="26"
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
      {element.text}
    </div>
  )
}

UrlRetrieverAgent.displayName = "UrlRetrieverAgent"
export { UrlRetrieverAgent }
