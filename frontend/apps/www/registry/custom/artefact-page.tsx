"use client"

import * as React from "react"
import { Check, Copy, Download, FileText } from "lucide-react"

import { linkifyUrls } from "@/lib/url-utils"

function ArtefactPage(element: {
  data: string
  code: string
  image: string
  summary: string
}) {
  const [copied, setCopied] = React.useState(false)
  const [summaryCopied, setSummaryCopied] = React.useState(false)
  const [downloadingPdf, setDownloadingPdf] = React.useState(false)

  const convertHtmlTableToMarkdown = (htmlString: string): string => {
    const parser = new DOMParser()
    const doc = parser.parseFromString(htmlString, "text/html")
    const table = doc.querySelector("table")

    if (!table) return htmlString

    const rows = Array.from(table.querySelectorAll("tr"))
    let markdown = ""

    rows.forEach((row, rowIndex) => {
      const cells = Array.from(row.querySelectorAll("td, th"))
      const cellValues = cells.map((cell) => cell.textContent?.trim() || "")
      markdown += "| " + cellValues.join(" | ") + " |\n"

      // Add header separator after first row
      if (rowIndex === 0 && cells.length > 0) {
        markdown += "| " + Array(cells.length).fill("---").join(" | ") + " |\n"
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
      console.error("Failed to copy table as markdown:", err)
    }
  }

  const copySummaryAsMarkdown = async () => {
    try {
      await navigator.clipboard.writeText(element.summary)
      setSummaryCopied(true)
      setTimeout(() => setSummaryCopied(false), 2000)
    } catch (err) {
      console.error("Failed to copy summary as markdown:", err)
    }
  }

  const downloadSummaryAsPdf = async () => {
    try {
      setDownloadingPdf(true)

      // Dynamically import jsPDF to avoid SSR issues
      const { default: jsPDF } = await import("jspdf")

      const doc = new jsPDF()

      // Set title
      doc.setFontSize(16)
      doc.setFont("helvetica", "bold")
      doc.text("Conversation Summary", 20, 20)

      // Process the summary text to handle basic markdown
      let processedText = element.summary
        .replace(/^# (.*$)/gim, "$1") // Remove header markdown
        .replace(/^## (.*$)/gim, "$1") // Remove header markdown
        .replace(/^### (.*$)/gim, "$1") // Remove header markdown
        .replace(/\*\*(.*?)\*\*/g, "$1") // Remove bold markdown
        .replace(/\*(.*?)\*/g, "$1") // Remove italic markdown
        .replace(/\[(.*?)\]\((.*?)\)/g, "$1 ($2)") // Convert links to text

      // Split text into lines and add to PDF
      doc.setFontSize(12)
      doc.setFont("helvetica", "normal")

      const splitText = doc.splitTextToSize(processedText, 170) // 170mm width
      let yPosition = 35

      splitText.forEach((line: string) => {
        if (yPosition > 280) {
          // Add new page if needed
          doc.addPage()
          yPosition = 20
        }
        doc.text(line, 20, yPosition)
        yPosition += 7
      })

      // Download the PDF
      doc.save("conversation-summary.pdf")
    } catch (err) {
      console.error("Failed to generate PDF:", err)
    } finally {
      setDownloadingPdf(false)
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

  // Render markdown function for summary
  const renderMarkdown = (markdown: string) => {
    // Simple markdown renderer for basic formatting
    let html = markdown
      .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mb-4">$1</h1>')
      .replace(/^## (.*$)/gim, '<h2 class="text-xl font-semibold mb-3">$1</h2>')
      .replace(/^### (.*$)/gim, '<h3 class="text-lg font-medium mb-2">$1</h3>')
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(
        /\[(.*?)\]\((.*?)\)/g,
        '<a href="$2" class="text-blue-600 hover:text-blue-800 underline" target="_blank" rel="noopener noreferrer">$1</a>'
      )
      .replace(/\n\n/g, '</p><p class="mb-3">')
      .replace(/\n/g, "<br>")

    // Wrap in paragraph tags if not already wrapped in block elements
    if (
      !html.includes("<h1>") &&
      !html.includes("<h2>") &&
      !html.includes("<h3>")
    ) {
      html = `<p class="mb-3">${html}</p>`
    }

    return html
  }

  return (
    <div>
      {element.summary && (
        <div className="mb-6 p-4 bg-gray-50 dark:bg-gray-900 rounded-lg border">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">
              Conversation Summary
            </h2>
            <div className="flex gap-2">
              <button
                onClick={copySummaryAsMarkdown}
                className={`inline-flex items-center gap-2 px-3 py-1 text-sm rounded-md transition-colors ${
                  summaryCopied
                    ? "bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300"
                    : "bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700"
                }`}
                title="Copy summary as markdown"
              >
                {summaryCopied ? (
                  <Check className="h-4 w-4" />
                ) : (
                  <FileText className="h-4 w-4" />
                )}
                {summaryCopied ? "Copied!" : "Copy MD"}
              </button>
              <button
                onClick={downloadSummaryAsPdf}
                disabled={downloadingPdf}
                className={`inline-flex items-center gap-2 px-3 py-1 text-sm rounded-md transition-colors ${
                  downloadingPdf
                    ? "bg-gray-200 dark:bg-gray-700 text-gray-500 cursor-not-allowed"
                    : "bg-blue-100 dark:bg-blue-900 hover:bg-blue-200 dark:hover:bg-blue-800 text-blue-700 dark:text-blue-300"
                }`}
                title="Download summary as PDF"
              >
                <Download className="h-4 w-4" />
                {downloadingPdf ? "Generating..." : "PDF"}
              </button>
            </div>
          </div>
          <div
            className="prose prose-sm max-w-none dark:prose-invert text-gray-700 dark:text-gray-300"
            dangerouslySetInnerHTML={{
              __html: renderMarkdown(element.summary),
            }}
          />
        </div>
      )}
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
            {copied ? (
              <Check className="h-4 w-4" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
            {copied ? "Copied!" : "Copy as Markdown"}
          </button>
        </div>
      )}
      {element.image ? (
        <div>
          <div className="flex">
            <div className="m-5 align-baseline">
              <img
                alt="Image"
                src={`data:image/png;charset=utf-8;base64,${element.image}`}
              />
            </div>
            <div className="m-5 align-baseline">
              <pre>{element.code}</pre>
            </div>
          </div>
          <div className="columns-[70vw]">
            <div
              className="m-5 align-baseline"
              dangerouslySetInnerHTML={{ __html: data }}
            />
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
            <div
              className="m-5 align-baseline"
              dangerouslySetInnerHTML={{ __html: data }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

ArtefactPage.displayName = "ArtefactPage"
export { ArtefactPage }
