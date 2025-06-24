import { save_feedback_url } from "@/app/settings"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { stream_id, rating } = body

    console.log(`Frontend API: Proxying feedback request - stream_id: ${stream_id}, rating: ${rating}`)

    const response = await fetch(save_feedback_url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        stream_id,
        rating,
      }),
    })

    if (response.ok) {
      const result = await response.json()
      console.log("Frontend API: Feedback saved successfully:", result)
      return Response.json(result)
    } else {
      console.error("Frontend API: Failed to save feedback:", response.statusText)
      return Response.json(
        { success: false, error: response.statusText },
        { status: response.status }
      )
    }
  } catch (error) {
    console.error("Frontend API: Error proxying feedback:", error)
    return Response.json(
      { success: false, error: "Internal server error" },
      { status: 500 }
    )
  }
}