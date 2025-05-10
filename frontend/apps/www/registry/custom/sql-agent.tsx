"use client"

import * as React from "react"

function SqlAgent(element: {text: string}) {
  return (
    <div className="inline-block">
      <div className="text-black dark:text-white pt-5">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
             className="lucide lucide-database-icon lucide-database">
          <ellipse cx="12" cy="5" rx="9" ry="3"/>
          <path d="M3 5V19A9 3 0 0 0 21 19V5"/>
          <path d="M3 12A9 3 0 0 0 21 12"/>
        </svg>
      </div>
      {element.text}
    </div>
  )
}

SqlAgent.displayName = "SqlAgent";
export {SqlAgent};
