"use client"

import * as React from "react"

function UserInputAgent(element: { text: string }) {
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
          className="lucide lucide-user-round-check"
        >
          <path d="M2 21a8 8 0 0 1 13.292-6" />
          <circle cx="10" cy="8" r="5" />
          <path d="m16 19 2 2 4-4" />
        </svg>
      </div>
      {element.text}
    </div>
  )
}

UserInputAgent.displayName = "UserInputAgent"
export { UserInputAgent }