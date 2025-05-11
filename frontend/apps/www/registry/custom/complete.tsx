"use client"

import * as React from "react"

function Complete() {
  return (
    <div className="inline-block">
      <div className="text-black dark:text-white pt-5">
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
          className="lucide lucide-check-check-icon lucide-check-check"
        >
          <path d="M18 6 7 17l-5-5" />
          <path d="m22 10-7.5 7.5L13 16" />
        </svg>
      </div>
    </div>
  )
}

Complete.displayName = "Complete"
export { Complete }
