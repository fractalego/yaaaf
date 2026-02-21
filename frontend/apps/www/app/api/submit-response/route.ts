import { NextRequest, NextResponse } from "next/server"

export async function POST(req: NextRequest) {
  try {
    const { stream_id, user_response } = await req.json()

    if (!stream_id || !user_response) {
      return NextResponse.json(
        { error: "stream_id and user_response are required" },
        { status: 400 }
      )
    }

    // Get the backend port from environment or default to 4000
    const backendPort = process.env.YAAAF_API_PORT || "4000"
    const backendUrl = `http://localhost:${backendPort}/submit_user_response`

    const response = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ stream_id, user_response }),
    })

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: "No paused execution found for this stream" },
          { status: 404 }
        )
      }
      throw new Error(`Backend responded with status: ${response.status}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error submitting user response:", error)
    return NextResponse.json(
      { error: "Failed to submit user response" },
      { status: 500 }
    )
  }
}
