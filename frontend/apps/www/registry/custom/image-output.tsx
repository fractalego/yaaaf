"use client"

import * as React from "react"

function ImageOutput(element: { id: string }) {
  const url: string = `/api/images/?id=${element.id}`
  return (
    <div>
      <img alt="Artefact output" src={url} />
    </div>
  )
}

ImageOutput.displayName = "ImageOutput"
export { ImageOutput }
