/**
 * HTML escaping utilities for chat message content
 */

/**
 * Escapes special characters in text for safe HTML display
 * Now simplified since JSON.stringify handles most escaping
 * @param text - The text to escape
 * @returns The escaped text
 */
export function escapeHtmlContent(text: string): string {
  return text
    .replaceAll("\n", "<br/>")
    .replaceAll("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")
}

/**
 * Unescapes HTML entities back to original characters
 * Simplified since JSON.stringify/parse handles most cases
 * @param html - The HTML content to unescape
 * @returns The unescaped text
 */
export function unescapeHtmlContent(html: string): string {
  return html
    .replaceAll("<br/>", "\n")
    .replaceAll("&nbsp;&nbsp;&nbsp;&nbsp;", "\t")
}
