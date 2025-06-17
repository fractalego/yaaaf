import { createDataStreamResponse } from "ai";
import {complete_tag, create_stream_url, get_utterances_url} from "@/app/settings";

// Define the Note interface to match the backend structure
interface Note {
  message: string;
  artefact_id: string | null;
  agent_name: string | null;
}

export async function POST(req: Request) {
  const { messages, session_id } = await req.json();
  const stream_id = session_id;
  messages.forEach(
    (item: string) => {
      // @ts-ignore
      delete(item["parts"]);
    }
  )
  try {
    await createStream(stream_id, messages);
  } catch (error) {
    console.error(`Frontend: Failed to create stream ${stream_id}:`, error);
    // Continue with streaming even if initial creation had issues
  }
  const result = createDataStreamResponse({
    async execute(dataStream) {
      dataStream.write('0:"Thinking... <br/><br/>"\n');

      let stopIterations: boolean = false;
      let current_index = 0;
      const max_time_in_chat = 360000; // seconds, see timeout below
      for(let i=0; i < max_time_in_chat; i++) {
        const notes: Array<Note> = await getUtterances(stream_id);
        const new_notes = notes.slice(current_index);
        current_index += new_notes.length;
        new_notes.forEach(
          (note: Note) => {
            // Convert Note to formatted string
            let utterance = formatNoteToString(note);
            if(utterance.indexOf(complete_tag) !== -1) {
              stopIterations = true;
            }
            utterance = utterance.replaceAll("\n", "<br/>");
            utterance = utterance.replaceAll("\"", "&quot;");
            utterance = utterance.replaceAll("\t", "&nbsp;&nbsp;&nbsp;&nbsp;");
            console.log(`Frontend: Processing utterance from ${note.agent_name}:`, utterance)
            dataStream.write(`0:"${utterance}<br/><br/>"\n`);
          }
        );
        if(stopIterations) {
          break;
        }
        await new Promise(r => setTimeout(r, 1000));
      }
    }
  })
  return result;
}

async function createStream(stream_id: string, messages: Array<Map<string, string>>): Promise<string> {
  const url = create_stream_url;
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: JSON.stringify({
        stream_id,
        messages,
      }),
    });
    if (response.ok) {
      return await response.json();
    } else {
      console.error(`Frontend: Create stream failed with status ${response.status}: ${response.statusText}`);
      throw new Error(`Error: ${response.statusText}`);
    }
  } catch (error) {
    console.error(`Frontend: Error creating stream for ${stream_id}:`, error);
    throw error;
  }
}

// Function to format Note object to string with agent name tags and artefact info
function formatNoteToString(note: Note): string {
  let result = "";

  // Wrap message in agent name tags if agent name exists
  if (note.agent_name) {
    result = `<${note.agent_name}>${note.message}</${note.agent_name}>`;
  } else {
    result = note.message;
  }
  return result;
}

async function getUtterances(stream_id: string): Promise<Array<Note>> {
  const url = get_utterances_url;
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: JSON.stringify({
        stream_id,
      }),
    });
    if (response.ok) {
      return await response.json();
    } else {
      console.error(`Frontend: Get utterances failed with status ${response.status}: ${response.statusText}`);
      throw new Error(`Error: ${response.statusText}`);
    }
  } catch (error) {
    console.error(`Frontend: Error fetching utterances for ${stream_id}:`, error);
    return [{ message: `Error in getting utterances: ${error}`, artefact_id: null, agent_name: "System" }];
  }
}
