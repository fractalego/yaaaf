type SessionId = string

// Store session ID in memory for the browser session
let sessionId: SessionId | null = null
let lastSessionWasPaused = false

function generateSecureId(): string {
  // Use crypto.randomUUID() if available (modern browsers)
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  
  // Fallback: Use a more professional character set (no vowels to avoid forming words)
  const chars = '0123456789BCDFGHJKLMNPQRSTVWXZ' // Removed vowels to prevent word formation
  let result = ''
  const array = new Uint8Array(12)
  crypto.getRandomValues(array)
  
  for (let i = 0; i < array.length; i++) {
    result += chars[array[i] % chars.length]
  }
  
  return result
}

export function getSessionId(): SessionId {
  if (!sessionId) {
    sessionId = generateSecureId()
  }
  return sessionId
}

export function generateNewSessionId(): SessionId {
  sessionId = generateSecureId()
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
