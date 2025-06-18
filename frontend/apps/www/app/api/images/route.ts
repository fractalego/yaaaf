import { get_image_url } from "@/app/settings"

export async function GET(request: Request) {
  const imageID: string | unknown = request.url.split("=").pop()
  if (typeof imageID !== "string") {
    return new Response("Invalid image ID", { status: 400 })
  }
  const base64_image = await getImage(imageID)
  const image = Buffer.from(base64_image, "base64")
  return new Response(image)
}

async function getImage(imageID: string): Promise<string> {
  const url = get_image_url
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        image_id: imageID,
      }),
    })
    if (response.ok) {
      return await response.json()
    } else {
      throw new Error(`Error: ${response.statusText}`)
    }
  } catch (error) {
    console.error("Error fetching data:", error)
  }
  return "Error in getting image"
}
