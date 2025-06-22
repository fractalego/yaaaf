import { createDataStreamResponse } from "ai"

import {
  complete_tag,
  create_stream_url,
  stream_utterances_url,
  paused_tag,
} from "@/app/settings"

// Define the Note interface to match the backend structure
interface Note {
  message: string
  artefact_id: string | null
  agent_name: string | null
  model_name: string | null
}

// Increase the max duration for this API route
export const maxDuration = 900; // 15 minutes
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  const { messages, session_id } = await req.json()
  const stream_id = session_id
  messages.forEach((item: string) => {
    // @ts-ignore
    delete item["parts"]
  })
  
  try {
    await createStream(stream_id, messages)
  } catch (error) {
    console.error(`Frontend: Failed to create stream ${stream_id}:`, error)
    // Continue with streaming even if initial creation had issues
  }

  const result = createDataStreamResponse({
    async execute(dataStream) {
      dataStream.write('0:"Thinking... <br/><br/>"\n')

      try {
        // Use real streaming instead of polling
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 1200000) // 20 minute timeout
        
        const response = await fetch(stream_utterances_url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            "Cache-Control": "no-cache",
          },
          body: JSON.stringify({
            stream_id,
          }),
          signal: controller.signal,
        })
        
        clearTimeout(timeoutId)

        if (!response.ok) {
          throw new Error(`Stream failed: ${response.statusText}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error("No reader available")
        }

        const decoder = new TextDecoder()
        let buffer = ""
        let lastActivityTime = Date.now()
        let lastMessageTime = Date.now()
        let stillWorkingShown = false
        let messageCount = 0

        try {
          while (true) {
            const { done, value } = await reader.read()
            if (done) {
              console.log('Frontend: Stream ended normally')
              break
            }

            lastActivityTime = Date.now()
            buffer += decoder.decode(value, { stream: true })
            
            // Process complete SSE messages
            let lines = buffer.split('\n')
            buffer = lines.pop() || "" // Keep incomplete line in buffer


            for (const line of lines) {
              // Handle SSE keep-alive comments (lines starting with ':')
              if (line.startsWith(':')) {
                console.log('Frontend: Received keep-alive signal')
                lastActivityTime = Date.now() // Reset activity timer on keep-alive
                continue
              }
              
              if (line.startsWith('data: ')) {
                try {
                  const jsonData = line.slice(6) // Remove 'data: ' prefix
                  if (jsonData.trim() === '') continue // Skip empty data
                  
                  const note: Note = JSON.parse(jsonData)
                  
                  // Convert Note to formatted string
                  let utterance = formatNoteToString(note)
                  let stopIterations = false
                  
                  if (utterance.indexOf(complete_tag) !== -1) {
                    stopIterations = true
                  }
                  
                  // Check if task is paused and needs user input
                  if (utterance.indexOf(paused_tag) !== -1) {
                    stopIterations = true
                    utterance += " 🤔 <em>(Waiting for your response...)</em>"
                  }
                  
                  utterance = utterance.replaceAll("\n", "<br/>")
                  utterance = utterance.replaceAll('"', "&quot;")
                  utterance = utterance.replaceAll("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")
                  
                  messageCount++
                  
                  console.log(
                    `Frontend: Message #${messageCount} - Processing utterance from ${note.agent_name} (${note.model_name})`
                  )
                  
                  try {
                    dataStream.write(`0:"${utterance}<br/><br/>"\n`)
                    console.log(`Frontend: Message #${messageCount} - Successfully wrote to dataStream`)
                  } catch (writeError) {
                    console.error(`Frontend: Message #${messageCount} - Error writing to dataStream:`, writeError)
                    console.error('Frontend: DataStream appears to be unresponsive - ending stream')
                    throw writeError
                  }
                  
                  lastMessageTime = Date.now() // Reset message timer
                  stillWorkingShown = false // Reset still working flag
                  
                  if (stopIterations) {
                    console.log('Frontend: Task completed, ending stream')
                    break // Use break instead of return to ensure proper cleanup
                  }
                } catch (parseError) {
                  console.error('Frontend: Error parsing SSE data:', parseError, 'Line:', line)
                  // Continue processing other lines instead of breaking
                }
              }
            }
            
            // Check for completion or paused flag to exit cleanly
            if (lines.some(line => line.includes('taskcompleted') || line.includes('taskpaused'))) {
              if (lines.some(line => line.includes('taskcompleted'))) {
                console.log('Frontend: Task completed detected, ending stream')
              } else {
                console.log('Frontend: Task paused detected, ending stream')
              }
              break
            }
            
            // Show "still working" message if no real messages for 2 minutes but connection is alive
            const timeSinceLastMessage = Date.now() - lastMessageTime
            if (timeSinceLastMessage > 120000 && !stillWorkingShown) {
              dataStream.write(`0:"<em>🔄 Still working on your request...</em><br/><br/>"\n`)
              stillWorkingShown = true
              console.log('Frontend: Showed still working indicator')
            }
            
            // Check for connection timeout (no activity for 10 minutes)
            if (Date.now() - lastActivityTime > 600000) {
              console.warn('Frontend: Stream timeout - no activity for 10 minutes')
              break
            }
          }
        } catch (readerError) {
          console.error('Frontend: Reader error:', readerError)
          throw readerError
        } finally {
          try {
            reader.releaseLock()
          } catch (lockError) {
            console.warn('Frontend: Error releasing reader lock:', lockError)
          }
        }
        
        // Streaming ended normally (not due to timeout)
        console.log('Frontend: Streaming ended normally')
      } catch (streamError) {
        console.error(`Frontend: Streaming error for ${stream_id}:`, streamError)
        dataStream.write(`0:"<em>Streaming error: ${streamError}</em><br/><br/>"\n`)
      }
    },
  })
  return result
}

async function createStream(
  stream_id: string,
  messages: Array<Map<string, string>>
): Promise<string> {
  const url = create_stream_url
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        stream_id,
        messages,
      }),
    })
    if (response.ok) {
      return await response.json()
    } else {
      console.error(
        `Frontend: Create stream failed with status ${response.status}: ${response.statusText}`
      )
      throw new Error(`Error: ${response.statusText}`)
    }
  } catch (error) {
    console.error(`Frontend: Error creating stream for ${stream_id}:`, error)
    throw error
  }
}

// Function to format Note object to string with agent name tags and artefact info
function formatNoteToString(note: Note): string {
  let result = ""

  // Check if message contains <markdown> tags - if so, extract content without agent wrapping
  const markdownRegex = /<markdown>([\s\S]*?)<\/markdown>/g
  const markdownMatches = note.message.match(markdownRegex)

  if (markdownMatches) {
    // Extract content from all <markdown> tags and return as plain text
    const markdownContent = markdownMatches
      .map((match) => match.replace(/<\/?markdown>/g, ""))
      .join("\n\n")

    // Remove the <markdown> tags from the original message
    const messageWithoutMarkdown = note.message
      .replace(markdownRegex, "")
      .trim()

    // Combine markdown content with the rest of the message
    if (messageWithoutMarkdown) {
      if (note.agent_name) {
        const modelInfo = note.model_name
          ? ` data-model="${note.model_name}"`
          : ""
        result =
          markdownContent +
          "\n\n" +
          `<${note.agent_name}${modelInfo}>${messageWithoutMarkdown}</${note.agent_name}>`
      } else {
        result = markdownContent + "\n\n" + messageWithoutMarkdown
      }
    } else {
      // Only markdown content, no agent wrapping
      result = markdownContent
    }
  } else {
    // No markdown tags, use original logic
    if (note.agent_name) {
      const modelInfo = note.model_name
        ? ` data-model="${note.model_name}"`
        : ""
      result = `<${note.agent_name}${modelInfo}>${note.message}</${note.agent_name}>`
    } else {
      result = note.message
    }
  }

  return result
}

