"use client"

import * as React from "react"

function BraveSearchAgent(element: { text: string }) {
  return (
    <div className="inline-block bg-orange-100 dark:bg-orange-800 dark:text-white p-3 text-xl rounded-sm">
      <div className="inline-block pr-5">
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
          className="lucide lucide-shield-check"
        >
          <path d="M20 13c0 5-3.5 7.5-8 10.5-4.5-3-8-5.5-8-10.5 0-3.5 2.5-7 8-7s8 3.5 8 7z" />
          <path d="m9 12 2 2 4-4" />
        </svg>
      </div>
      {element.text}
    </div>
  )
}

BraveSearchAgent.displayName = "BraveSearchAgent"
export { BraveSearchAgent }
