type SessionId = string
export function getSessionId(): SessionId {
  return Math.random().toString(36).substring(2, 15)
}
