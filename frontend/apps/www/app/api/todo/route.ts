import { get_latest_todo_url } from "@/app/settings"

export async function POST(req: Request) {
  try {
    const { stream_id } = await req.json()

    const response = await fetch(get_latest_todo_url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        stream_id,
      }),
    })

    if (!response.ok) {
      return Response.json(
        { error: "Failed to fetch todo list" },
        { status: response.status }
      )
    }

    const result = await response.json()
    return Response.json(result)
  } catch (error) {
    console.error("Error proxying todo request:", error)
    return Response.json({ error: "Internal server error" }, { status: 500 })
  }
}
