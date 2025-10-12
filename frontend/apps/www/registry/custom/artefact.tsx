"use client"

import { createHash } from "crypto"
import * as React from "react"
import { Brain, Code, FileImage, ListTodo, Table } from "lucide-react"

function Artefact(element: {
  id: string
  type?: string
  onArtifactClick?: (artifactId: string) => void
}) {
  const url: string = "/artefacts/" + element.id

  // Get emoji and color based on artifact type
  const getEmojiAndColor = () => {
    switch (element.type) {
      case "thinking":
        return {
          emoji: "🧠",
          colors: [
            "text-purple-500",
            "text-purple-600",
            "text-purple-700",
            "text-indigo-500",
            "text-violet-500",
          ],
        }
      case "table":
        return {
          emoji: "📊",
          colors: [
            "text-blue-500",
            "text-blue-600",
            "text-blue-700",
            "text-cyan-500",
            "text-sky-500",
          ],
        }
      case "image":
        return {
          emoji: "🖼️",
          colors: [
            "text-green-500",
            "text-green-600",
            "text-green-700",
            "text-emerald-500",
            "text-teal-500",
          ],
        }
      case "todo-list":
        return {
          emoji: "📝",
          colors: [
            "text-orange-500",
            "text-orange-600",
            "text-orange-700",
            "text-amber-500",
            "text-yellow-500",
          ],
        }
      case "model":
        return {
          emoji: "💻",
          colors: [
            "text-pink-500",
            "text-pink-600",
            "text-pink-700",
            "text-rose-500",
            "text-red-500",
          ],
        }
      case "search-result":
        return {
          emoji: "🔍",
          colors: [
            "text-emerald-500",
            "text-emerald-600",
            "text-emerald-700",
            "text-teal-500",
            "text-green-500",
          ],
        }
      case "numerical-sequences-table":
        return {
          emoji: "📈",
          colors: [
            "text-blue-500",
            "text-blue-600",
            "text-blue-700",
            "text-cyan-500",
            "text-sky-500",
          ],
        }
      case "called-tools-table":
        return {
          emoji: "🛠️",
          colors: [
            "text-slate-500",
            "text-slate-600",
            "text-slate-700",
            "text-gray-500",
            "text-gray-600",
          ],
        }
      default:
        // Default to document emoji for unknown types
        return {
          emoji: "📄",
          colors: [
            "text-gray-500",
            "text-gray-600",
            "text-gray-700",
            "text-slate-500",
            "text-slate-600",
          ],
        }
    }
  }

  const { emoji, colors } = getEmojiAndColor()
  const color_number =
    createHash("md5").update(url).digest("hex").slice(0, 1).charCodeAt(0) %
    colors.length

  const handleClick = () => {
    if (element.onArtifactClick) {
      element.onArtifactClick(element.id)
    } else {
      // Fallback to opening in new tab if no click handler is provided
      window.open(url, "_blank")
    }
  }

  return (
    <div className="inline-block">
      <button onClick={handleClick} className="cursor-pointer">
        <div
          className={`${colors[color_number]} text-2xl transition-colors hover:opacity-80`}
        >
          {emoji}
        </div>
      </button>
    </div>
  )
}

Artefact.displayName = "Artefact"
export { Artefact }
