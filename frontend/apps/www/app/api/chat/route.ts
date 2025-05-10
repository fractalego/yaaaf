import { createDataStreamResponse } from "ai";
import {complete_tag, create_stream_url, get_utterances_url} from "@/app/api/chat/settings";

export async function POST(req: Request) {
  const { messages, session_id } = await req.json();
  const stream_id = session_id;
  messages.forEach(
    (item: string) => {
      delete(item["parts"]);
    }
  )
  await createStream(stream_id, messages);
  const result = createDataStreamResponse({
    async execute(dataStream) {
      dataStream.write('0:"Thinking... <br/><br/>"\n');

      let stopIterations: boolean = false;
      let current_index = 0;
      const max_time_in_chat = 360000; // seconds, see timeout below
      for(let i=0; i < max_time_in_chat; i++) {
        const utterances: Array<string> = await getUtterances(stream_id);
        const new_utterances = utterances.slice(current_index);
        current_index += new_utterances.length;
        new_utterances.forEach(
          (utterance: string) => {
            if(utterance.indexOf(complete_tag) !== -1) {
              stopIterations = true;
            }
            utterance = utterance.replaceAll("\n", "<br/>");
            utterance = utterance.replaceAll("\"", "&quot;");
            utterance = utterance.replaceAll("\t", "&nbsp;&nbsp;&nbsp;&nbsp;");
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
      throw new Error(`Error: ${response.statusText}`);
    }
  } catch (error) {
    console.error("Error fetching data:", error);
  }
  return "Error in creating stream";
}

async function getUtterances(stream_id: string): Promise<string> {
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
      throw new Error(`Error: ${response.statusText}`);
    }
  } catch (error) {
    console.error("Error fetching data:", error);
  }
  return "Error in getting utterances";
}
