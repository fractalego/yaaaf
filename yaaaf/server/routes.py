import asyncio
import logging
import threading

from typing import List
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.data_types import Utterance, Messages, Note
from yaaaf.components.orchestrator_builder import OrchestratorBuilder
from yaaaf.server.accessories import do_compute, get_utterances
from yaaaf.server.config import get_config

_logger = logging.getLogger(__name__)


class CreateStreamArguments(BaseModel):
    stream_id: str
    messages: List[Utterance]


class NewUtteranceArguments(BaseModel):
    stream_id: str


class ArtefactArguments(BaseModel):
    artefact_id: str


class ArtefactOutput(BaseModel):
    data: str
    code: str
    image: str

    @staticmethod
    def create_from_artefact(artefact: Artefact) -> "ArtefactOutput":
        return ArtefactOutput(
            data=artefact.data.to_html(index=False)
            if artefact.data is not None
            else "",
            code=artefact.code if artefact.code is not None else "",
            image=artefact.image if artefact.image is not None else "",
        )


class ImageArguments(BaseModel):
    image_id: str


def create_stream(arguments: CreateStreamArguments):
    try:
        stream_id = arguments.stream_id
        messages = Messages(utterances=arguments.messages)
        orchestrator = OrchestratorBuilder(get_config()).build()
        t = threading.Thread(
            target=asyncio.run, args=(do_compute(stream_id, messages, orchestrator),)
        )
        t.start()
    except Exception as e:
        _logger.error(f"Routes: Failed to create stream for {arguments.stream_id}: {e}")
        raise


def get_all_utterances(arguments: NewUtteranceArguments) -> List[Note]:
    try:
        return get_utterances(arguments.stream_id)
    except Exception as e:
        _logger.error(
            f"Routes: Failed to get utterances for {arguments.stream_id}: {e}"
        )
        raise


def get_artifact(arguments: ArtefactArguments) -> ArtefactOutput:
    try:
        artefact_id = arguments.artefact_id
        artefact_storage = ArtefactStorage(artefact_id)
        artefact = artefact_storage.retrieve_from_id(artefact_id)
        return ArtefactOutput.create_from_artefact(artefact)
    except Exception as e:
        _logger.error(f"Routes: Failed to get artifact {arguments.artefact_id}: {e}")
        raise


def get_image(arguments: ImageArguments) -> str:
    try:
        image_id = arguments.image_id
        artefact_storage = ArtefactStorage(image_id)
        try:
            artefact = artefact_storage.retrieve_from_id(image_id)
            return artefact.image
        except ValueError as e:
            _logger.warning(f"Routes: Artefact with id {image_id} not found: {e}")
            return f"WARNING: Artefact with id {image_id} not found."
    except Exception as e:
        _logger.error(f"Routes: Failed to get image {arguments.image_id}: {e}")
        raise


def get_query_suggestions(query: str) -> List[str]:
    try:
        return get_config().query_suggestions
    except Exception as e:
        _logger.error(f"Routes: Failed to get query suggestions: {e}")
        raise


async def stream_utterances(arguments: NewUtteranceArguments):
    """Real-time streaming endpoint for utterances"""

    async def generate_stream():
        stream_id = arguments.stream_id
        current_index = 0
        max_iterations = 1200  # 20 minutes max (increased from 6)
        consecutive_empty_checks = 0
        max_empty_checks = 10  # Send keep-alive after 5 seconds of no data

        for i in range(max_iterations):
            try:
                notes = get_utterances(stream_id)
                new_notes = notes[current_index:]
                current_index += len(new_notes)

                if new_notes:
                    # Reset empty check counter when we have data
                    consecutive_empty_checks = 0

                    for note in new_notes:
                        # Send each note as SSE
                        import json

                        note_data = {
                            "message": note.message,
                            "artefact_id": note.artefact_id,
                            "agent_name": note.agent_name,
                            "model_name": note.model_name,
                        }
                        yield f"data: {json.dumps(note_data)}\n\n"

                        # Check for completion or paused state
                        if (
                            "taskcompleted" in note.message
                            or "taskpaused" in note.message
                        ):
                            return
                else:
                    # No new data, increment empty check counter
                    consecutive_empty_checks += 1

                    # Send keep-alive message every 5 seconds when no data
                    if consecutive_empty_checks >= max_empty_checks:
                        yield ": keep-alive\n\n"  # SSE comment for keep-alive
                        consecutive_empty_checks = 0

                # Shorter delay for more responsive streaming
                await asyncio.sleep(0.5)

            except Exception as e:
                _logger.error(f"Routes: Error in streaming for {stream_id}: {e}")
                yield f'data: {{"error": "Stream error: {str(e)}"}}\n\n'
                return

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",  # Proper SSE media type
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx directive to disable buffering
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )
