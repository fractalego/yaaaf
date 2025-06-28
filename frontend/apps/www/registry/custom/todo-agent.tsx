"use client"

import * as React from "react"

import { ModelIndicator } from "./model-indicator"

function TodoAgent(element: { text: string; modelName?: string }) {
  // Parse JSON if the text looks like a todo list
  let todos = [];
  let displayText = element.text;
  
  try {
    const parsed = JSON.parse(element.text);
    if (Array.isArray(parsed)) {
      todos = parsed;
    }
  } catch {
    // If not valid JSON, display as plain text
  }

  return (
    <div className="inline-block bg-slate-200 dark:bg-slate-700 dark:text-white p-3 text-xl rounded-sm">
      <div className="flex items-center gap-2 mb-1">
        <div className="inline-block">
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
            className="lucide lucide-list-checks"
          >
            <path d="M3 17l2 2l4-4" />
            <path d="M3 7l2 2l4-4" />
            <path d="M13 6h8" />
            <path d="M13 12h8" />
            <path d="M13 18h8" />
          </svg>
        </div>
        <span className="flex-1 text-xs text-slate-600 dark:text-slate-400 opacity-70 font-mono">
          Todo Agent
        </span>
        {element.modelName && (
          <ModelIndicator
            modelName={element.modelName}
            variant="compact"
            className="text-slate-600 dark:text-slate-400"
          />
        )}
      </div>
      <div>
        {todos.length > 0 ? (
          <div className="space-y-2">
            {todos.map((todo, index) => (
              <div key={index} className="flex items-center gap-2 text-sm">
                <div className={`w-2 h-2 rounded-full ${
                  todo.status === 'completed' ? 'bg-green-500' :
                  todo.status === 'in_progress' ? 'bg-yellow-500' :
                  'bg-gray-400'
                }`} />
                <span className={`flex-1 ${
                  todo.status === 'completed' ? 'line-through opacity-70' : ''
                }`}>
                  {todo.content}
                </span>
                <span className={`text-xs px-2 py-1 rounded ${
                  todo.priority === 'high' ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' :
                  todo.priority === 'medium' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300' :
                  'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                }`}>
                  {todo.priority}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div>{displayText}</div>
        )}
      </div>
    </div>
  )
}

TodoAgent.displayName = "TodoAgent"
export { TodoAgent }
