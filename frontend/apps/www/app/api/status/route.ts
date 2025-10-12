import { NextRequest, NextResponse } from "next/server"

export async function POST(req: NextRequest) {
  try {
    const { stream_id } = await req.json()

    if (!stream_id) {
      return NextResponse.json(
        { error: "stream_id is required" },
        { status: 400 }
      )
    }

    // Get the backend port from environment or default to 4000
    const backendPort = process.env.YAAAF_API_PORT || "4000"
    const backendUrl = `http://localhost:${backendPort}/get_stream_status`

    const response = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ stream_id }),
    })

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json({ error: "Stream not found" }, { status: 404 })
      }
      throw new Error(`Backend responded with status: ${response.status}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error fetching stream status:", error)
    return NextResponse.json(
      { error: "Failed to fetch stream status" },
      { status: 500 }
    )
  }
}
