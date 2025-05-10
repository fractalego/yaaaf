"use client"

import { useEffect, useState } from "react"

import { MarkdownRenderer } from "@/registry/default/ui/markdown-renderer"

export default function MarkdownRendererDemo() {
  const [content, setContent] = useState("")

  useEffect(() => {
    setContent(`# Hello World
 
This is a paragraph with **bold** and *italic* text.

## Lists
- Item 1
- Item 2
- Nested item

## Code
\`\`\`tsx
console.log("Hello World")
\`\`\`

## Tables
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
 `)
  }, [])

  return (
    <div className="w-full">
      <MarkdownRenderer>{content}</MarkdownRenderer>
    </div>
  )
}
