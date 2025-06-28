"use client"

import * as React from "react"
import { Copy, Check } from "lucide-react"

import { linkifyUrls } from "@/lib/url-utils"

function ArtefactPage(element: { data: string; code: string; image: string }) {
  const [copied, setCopied] = React.useState(false)

  const convertHtmlTableToMarkdown = (htmlString: string): string => {
    const parser = new DOMParser()
    const doc = parser.parseFromString(htmlString, 'text/html')
    const table = doc.querySelector('table')
    
    if (!table) return htmlString
    
    const rows = Array.from(table.querySelectorAll('tr'))
    let markdown = ''
    
    rows.forEach((row, rowIndex) => {
      const cells = Array.from(row.querySelectorAll('td, th'))
      const cellValues = cells.map(cell => cell.textContent?.trim() || '')
      markdown += '| ' + cellValues.join(' | ') + ' |\n'
      
      // Add header separator after first row
      if (rowIndex === 0 && cells.length > 0) {
        markdown += '| ' + Array(cells.length).fill('---').join(' | ') + ' |\n'
      }
    })
    
    return markdown
  }

  const copyTableAsMarkdown = async () => {
    try {
      const markdown = convertHtmlTableToMarkdown(element.data)
      await navigator.clipboard.writeText(markdown)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy table as markdown:', err)
    }
  }

  let data = element.data
  data = data.replaceAll('class="dataframe"', "")
  data = data.replaceAll("text-align: right;", "text-align: left;")
  data = data.replaceAll(
    "<table",
    '<table class="text-left text-sm font-light text-surface dark:text-white"'
  )
  data = data.replaceAll(
    "<tr",
    '<tr class="border-b border-neutral-200 dark:border-white/10"'
  )

  // Process table cell content to make URLs clickable
  data = linkifyUrls(data)
  return (
    <div>
      {element.data && (
        <div className="mb-4">
          <button
            onClick={copyTableAsMarkdown}
            className={`inline-flex items-center gap-2 px-3 py-1 text-sm rounded-md transition-colors ${
              copied 
                ? "bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300" 
                : "bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700"
            }`}
            title="Copy table as markdown"
          >
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? "Copied!" : "Copy as Markdown"}
          </button>
        </div>
      )}
      {element.image ? (
        <div>
          <div className="flex">
            <div className="m-5 align-baseline">
              <img alt="Image" src={`data:image/png;charset=utf-8;base64,${element.image}`} />
            </div>
            <div className="m-5 align-baseline">
              <pre>{element.code}</pre>
            </div>
          </div>
          <div className="columns-[70vw]">
            <div className="m-5 align-baseline" dangerouslySetInnerHTML={{ __html: data }} />
          </div>
        </div>
      ) : (
        <div>
          <div className="flex">
            <div className="m-5 align-baseline">
              <pre>{element.code}</pre>
            </div>
          </div>
          <div className="columns-[70vw]">
            <div className="m-5 align-baseline" dangerouslySetInnerHTML={{ __html: data }} />
          </div>
        </div>
      )}
    </div>
  )
}

ArtefactPage.displayName = "ArtefactPage"
export { ArtefactPage }
