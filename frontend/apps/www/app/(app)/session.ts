type SessionId = string

// Store session ID in memory for the browser session
let sessionId: SessionId | null = null
let lastSessionWasPaused = false

export function getSessionId(): SessionId {
  if (!sessionId) {
    sessionId = Math.random().toString(36).substring(2, 15)
  }
  return sessionId
}

export function generateNewSessionId(): SessionId {
  sessionId = Math.random().toString(36).substring(2, 15)
  lastSessionWasPaused = false
  return sessionId
}

export function markSessionAsPaused(): void {
  lastSessionWasPaused = true
}

export function wasLastSessionPaused(): boolean {
  return lastSessionWasPaused
}

export function getSessionIdForNewMessage(): SessionId {
  // If the last session was paused, generate a new session ID
  if (lastSessionWasPaused) {
    return generateNewSessionId()
  }
  return getSessionId()
}
