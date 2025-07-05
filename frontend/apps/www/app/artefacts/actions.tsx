"use server"

import { get_artefact_url } from "@/app/settings"

interface ArtefactOutput {
  data: string
  code: string
  image: string
  summary: string
}

export async function get_artefact(
  artefact_id: string
): Promise<ArtefactOutput> {
  const url = get_artefact_url
  console.log("Fetching artifact from URL:", url, "with ID:", artefact_id)

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        artefact_id: artefact_id,
      }),
    })

    console.log("Response status:", response.status, response.statusText)

    if (response.ok) {
      const data = await response.json()
      console.log("Response data:", data)
      return data
    } else {
      const errorText = await response.text()
      console.error(
        "API Error:",
        response.status,
        response.statusText,
        errorText
      )
      throw new Error(
        `API Error ${response.status}: ${response.statusText} - ${errorText}`
      )
    }
  } catch (error) {
    console.error("Error fetching artefact:", error)
    throw error // Re-throw the error instead of swallowing it
  }
}
