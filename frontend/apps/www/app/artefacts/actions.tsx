"use server"

import {get_artefact_url} from "@/app/settings";

interface ArtefactOutput {
  params: {
    data: string,
    code: string,
    image: string,
  }
}

export async function get_artefact(artefact_id: string): Promise<ArtefactOutput> {
  const url = get_artefact_url;
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: JSON.stringify({
        artefact_id: artefact_id,
      }),
    });
    if (response.ok) {
      return await response.json();
    } else {
      throw new Error(`Error: ${response.statusText}`);
    }
  } catch (error) {
    console.error("Error fetching artefact:", error);
  }
  return {params: {data: "", code: "", image: ""}}
}
