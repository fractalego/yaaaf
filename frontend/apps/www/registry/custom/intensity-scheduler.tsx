"use client"

import * as React from "react"

const LEVEL_STYLES: Record<string, string> = {
  Easy:     "border-green-400  bg-green-50  dark:bg-green-950  dark:border-green-600  text-green-800  dark:text-green-200",
  Moderate: "border-blue-400   bg-blue-50   dark:bg-blue-950   dark:border-blue-600   text-blue-800   dark:text-blue-200",
  Hard:     "border-yellow-400 bg-yellow-50 dark:bg-yellow-950 dark:border-yellow-600 text-yellow-800 dark:text-yellow-200",
  Expert:   "border-orange-400 bg-orange-50 dark:bg-orange-950 dark:border-orange-600 text-orange-800 dark:text-orange-200",
  Elite:    "border-red-400    bg-red-50    dark:bg-red-950    dark:border-red-600    text-red-800    dark:text-red-200",
  Master:   "border-purple-400 bg-purple-50 dark:bg-purple-950 dark:border-purple-600 text-purple-800 dark:text-purple-200",
}

const DEFAULT_STYLE =
  "border-gray-400 bg-gray-50 dark:bg-gray-900 dark:border-gray-600 text-gray-700 dark:text-gray-300"
const ESCALATION_STYLE =
  "border-amber-400 bg-amber-50 dark:bg-amber-950 dark:border-amber-600 text-amber-800 dark:text-amber-200"

function IntensityScheduler(element: { text: string }) {
  // children arrives as a plain string (note messages have no markdown)
  const text = typeof element.text === "string" ? element.text : ""
  const isEscalation = text.startsWith("Escalating")

  // Extract level name for colour lookup: "Intensity: Hard — ..." → "Hard"
  const levelMatch = text.match(/^Intensity:\s*(\w+)/)
  const level = levelMatch ? levelMatch[1] : null
  const style = isEscalation
    ? ESCALATION_STYLE
    : (level ? LEVEL_STYLES[level] ?? DEFAULT_STYLE : DEFAULT_STYLE)

  return (
    <div className={`flex items-center gap-2 p-2 my-1 rounded-sm border-l-4 text-xs font-mono ${style}`}>
      <span>{isEscalation ? "⬆️" : "🎯"}</span>
      <span>{text}</span>
    </div>
  )
}

IntensityScheduler.displayName = "IntensityScheduler"
export { IntensityScheduler }
