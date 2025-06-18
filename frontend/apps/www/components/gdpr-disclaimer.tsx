"use client"

import { useEffect, useState } from "react"

import { Button } from "@/registry/default/ui/button"

export function GDPRDisclaimer() {
  const [isVisible, setIsVisible] = useState(false)
  const [shouldShow, setShouldShow] = useState(false)

  useEffect(() => {
    // Check if popup should be shown based on environment variable
    const activatePopup = process.env.NEXT_PUBLIC_YAAAF_ACTIVATE_POPUP

    // Show popup if env var is not set or is set to "true"
    const shouldActivate = activatePopup !== "false"

    if (!shouldActivate) {
      setShouldShow(false)
      return
    }

    // Check if user has already accepted the disclaimer
    const hasAccepted = localStorage.getItem("gdpr-disclaimer-accepted")

    if (!hasAccepted) {
      setShouldShow(true)
      // Small delay to ensure smooth animation
      setTimeout(() => setIsVisible(true), 100)
    }
  }, [])

  const handleAccept = () => {
    localStorage.setItem("gdpr-disclaimer-accepted", "true")
    setIsVisible(false)
    // Remove from DOM after animation completes
    setTimeout(() => setShouldShow(false), 300)
  }

  if (!shouldShow) {
    return null
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-50 bg-black/50 transition-opacity duration-300 ${
          isVisible ? "opacity-100" : "opacity-0"
        }`}
        onClick={handleAccept}
      />

      {/* Modal */}
      <div
        className={`fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 transform rounded-lg border bg-background p-6 shadow-lg transition-all duration-300 ${
          isVisible ? "scale-100 opacity-100" : "scale-95 opacity-0"
        }`}
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold">Privacy Notice</h2>
            <p className="text-sm text-muted-foreground">
              This application processes your conversations to provide
              AI-powered responses. Your data is handled in accordance with GDPR
              regulations. By using this service, you consent to the processing
              of your messages for the purpose of generating responses.
            </p>
            <p className="text-sm text-muted-foreground">
              No personal data is stored permanently, and all conversations are
              processed locally or through secure AI services.
            </p>
          </div>

          <div className="flex justify-end space-x-2">
            <Button onClick={handleAccept} className="w-full">
              I Understand & Accept
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}
