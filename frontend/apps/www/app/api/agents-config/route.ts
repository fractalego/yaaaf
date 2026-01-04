import { NextResponse } from "next/server"

export async function GET() {
  try {
    const backendPort = process.env.YAAAF_API_PORT || "4000"
    const backendUrl = `http://localhost:${backendPort}/get_agents_config`

    const response = await fetch(backendUrl)

    if (!response.ok) {
      throw new Error(`Backend responded with status: ${response.status}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error fetching agents config:", error)
    return NextResponse.json([], { status: 200 }) // Return empty array on error
  }
}
