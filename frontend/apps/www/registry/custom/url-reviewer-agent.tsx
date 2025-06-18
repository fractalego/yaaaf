"use client"

import * as React from "react"

function UrlReviewerAgent(element: { text: string }) {
  return (
    <div className="inline-block bg-purple-100 dark:bg-purple-800 dark:text-white p-3 text-xl rounded-sm">
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
          className="lucide lucide-search-check"
        >
          <path d="m8 11 2 2 4-4" />
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
      </div>
      {element.text}
    </div>
  )
}

UrlReviewerAgent.displayName = "UrlReviewerAgent"
export { UrlReviewerAgent }
