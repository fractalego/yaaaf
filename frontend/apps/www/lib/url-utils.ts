/**
 * Utility functions for URL detection and linking in table cells
 */
import React from "react"

const URL_REGEX = /https?:\/\/[^\s<>"]+/gi

/**
 * Detects if a string contains a URL
 */
export function containsUrl(text: string): boolean {
  return URL_REGEX.test(text)
}

/**
 * Converts URLs in text to clickable links that open in new tabs
 */
export function linkifyUrls(text: string): string {
  return text.replace(URL_REGEX, (url) => {
    return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="text-primary underline underline-offset-2 hover:text-primary/80">${url}</a>`
  })
}

/**
 * Creates a clickable link element for React components
 */
export function createUrlLink(
  url: string,
  className?: string
): React.ReactElement {
  return React.createElement(
    "a",
    {
      href: url,
      target: "_blank",
      rel: "noopener noreferrer",
      className:
        className ||
        "text-primary underline underline-offset-2 hover:text-primary/80",
    },
    url
  )
}

/**
 * Processes table cell content to make URLs clickable
 * Returns JSX element if URLs are found, otherwise returns original text
 */
export function processTableCellContent(content: any): any {
  if (typeof content !== "string") {
    return content
  }

  if (!containsUrl(content)) {
    return content
  }

  // Split content by URLs and create mixed content
  const parts = content.split(URL_REGEX)
  const urls = content.match(URL_REGEX) || []

  const result: (string | React.ReactElement)[] = []

  for (let i = 0; i < parts.length; i++) {
    if (parts[i]) {
      result.push(parts[i])
    }
    if (urls[i]) {
      result.push(createUrlLink(urls[i], `url-link-${i}`))
    }
  }

  return result.length === 1 ? result[0] : result
}
