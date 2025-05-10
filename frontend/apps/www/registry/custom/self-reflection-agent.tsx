"use client"

import * as React from "react"

function SelfReflectionAgent(element: {text: string}) {
  return (
    <div className="inline-block bg-green-100 p-3 text-xl rounded-sm">
      <div className="inline-block pr-5">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
             className="lucide lucide-route-icon lucide-route">
          <circle cx="6" cy="19" r="3"/>
          <path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/>
          <circle cx="18" cy="5" r="3"/>
        </svg>
      </div>
      {element.text}
    </div>
  )
}

SelfReflectionAgent.displayName = "SelfReflectionAgent";
export {SelfReflectionAgent};

