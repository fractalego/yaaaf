/**
 * HTML escaping utilities for chat message content
 */

/**
 * Escapes special characters in text for safe HTML display
 * @param text - The text to escape
 * @returns The escaped text
 */
export function escapeHtmlContent(text: string): string {
  return text
    .replaceAll("\n", "<br/>")
    .replaceAll('"', "&quot;")
    .replaceAll("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")
}

/**
 * Unescapes HTML entities back to original characters
 * @param html - The HTML content to unescape
 * @returns The unescaped text
 */
export function unescapeHtmlContent(html: string): string {
  return html
    .replaceAll("<br/>", "\n")
    .replaceAll("&quot;", '"')
    .replaceAll("&nbsp;&nbsp;&nbsp;&nbsp;", "\t")
}
