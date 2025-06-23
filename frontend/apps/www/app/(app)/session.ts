type SessionId = string

// Store session ID in memory for the browser session
let sessionId: SessionId | null = null

export function getSessionId(): SessionId {
  if (!sessionId) {
    sessionId = Math.random().toString(36).substring(2, 15)
  }
  return sessionId
}
