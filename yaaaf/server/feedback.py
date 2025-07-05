import json
import logging
import os
from datetime import datetime
from typing import Dict, Any

from pydantic import BaseModel

from yaaaf.components.agents.artefacts import ArtefactStorage
from yaaaf.server.accessories import get_utterances
from yaaaf.server.config import get_config, AgentSettings

_logger = logging.getLogger(__name__)


class FeedbackArguments(BaseModel):
    stream_id: str
    rating: str  # "thumbs-up" or "thumbs-down"


def save_feedback(arguments: FeedbackArguments) -> Dict[str, Any]:
    """Save feedback data including notes, artifacts, rating, and agent configuration to a JSON file"""
    try:
        _logger.info("=== FEEDBACK ENDPOINT CALLED ===")
        _logger.info(
            f"Received feedback request: stream_id={arguments.stream_id}, rating={arguments.rating}"
        )

        stream_id = arguments.stream_id
        rating = arguments.rating

        # Get configuration
        _logger.info("Getting configuration...")
        config = get_config()
        _logger.info("Configuration retrieved successfully")

        # Get all notes for this stream
        _logger.info(f"Getting utterances for stream {stream_id}...")
        notes = get_utterances(stream_id)
        _logger.info(f"Retrieved {len(notes)} notes for stream {stream_id}")

        # Debug: Check if any notes have artifact_ids
        notes_with_artifacts = [note for note in notes if note.artefact_id]
        _logger.info(
            f"Found {len(notes_with_artifacts)} notes with artifact IDs: {[note.artefact_id for note in notes_with_artifacts]}"
        )

        # Get all artifacts for this stream
        artifacts = []
        artifact_storage = ArtefactStorage()  # Singleton instance, no parameter needed
        processed_artifact_ids = set()  # Avoid duplicates

        for note in notes:
            if note.artefact_id and note.artefact_id not in processed_artifact_ids:
                try:
                    artifact = artifact_storage.retrieve_from_id(note.artefact_id)
                    if artifact:  # Make sure artifact exists
                        artifact_data = {
                            "id": note.artefact_id,
                            "type": artifact.type if artifact.type else "unknown",
                            "data": artifact.data.to_html(index=False)
                            if artifact.data is not None
                            else "",
                            "code": artifact.code if artifact.code is not None else "",
                            "image": artifact.image
                            if artifact.image is not None
                            else "",
                            "description": artifact.description
                            if artifact.description is not None
                            else "",
                        }
                        artifacts.append(artifact_data)
                        processed_artifact_ids.add(note.artefact_id)
                        _logger.info(
                            f"Successfully retrieved artifact {note.artefact_id} of type {artifact.type}"
                        )
                except Exception as e:
                    _logger.warning(
                        f"Could not retrieve artifact {note.artefact_id}: {e}"
                    )
                    # Add a placeholder for failed artifacts
                    artifacts.append(
                        {
                            "id": note.artefact_id,
                            "type": "error",
                            "data": "",
                            "code": "",
                            "image": "",
                            "description": f"Error retrieving artifact: {str(e)}",
                        }
                    )

        # Extract agent configuration details
        agent_configs = []
        for agent_config in config.agents:
            if isinstance(agent_config, AgentSettings):
                agent_info = {
                    "name": agent_config.name,
                    "model": agent_config.model or config.client.model,
                    "temperature": agent_config.temperature
                    if agent_config.temperature is not None
                    else config.client.temperature,
                    "max_tokens": agent_config.max_tokens
                    if agent_config.max_tokens is not None
                    else config.client.max_tokens,
                    "host": agent_config.host or config.client.host,
                }
            else:
                # String-based agent name, uses default settings
                agent_info = {
                    "name": agent_config,
                    "model": config.client.model,
                    "temperature": config.client.temperature,
                    "max_tokens": config.client.max_tokens,
                    "host": config.client.host,
                }
            agent_configs.append(agent_info)

        # Create feedback data
        feedback_data = {
            "timestamp": datetime.now().isoformat(),
            "stream_id": stream_id,
            "rating": rating,
            "system_configuration": {
                "default_client": {
                    "model": config.client.model,
                    "temperature": config.client.temperature,
                    "max_tokens": config.client.max_tokens,
                    "host": config.client.host,
                },
                "agents": agent_configs,
                "sources": [
                    {
                        "name": source.name,
                        "type": source.type,
                        "path": source.path,
                        "description": source.description,
                    }
                    for source in config.sources
                ],
                "safety_filter": {
                    "enabled": config.safety_filter.enabled,
                    "blocked_keywords": config.safety_filter.blocked_keywords,
                    "blocked_patterns": config.safety_filter.blocked_patterns,
                    "custom_message": config.safety_filter.custom_message,
                },
            },
            "notes": [
                {
                    "message": note.message,
                    "artefact_id": note.artefact_id,
                    "agent_name": note.agent_name,
                    "model_name": note.model_name,
                    "internal": getattr(
                        note, "internal", False
                    ),  # Handle backward compatibility
                }
                for note in notes
            ],
            "artifacts": artifacts,
        }

        # Ensure feedback directory exists in root folder
        _logger.info("Creating feedback directory...")
        feedback_dir = "feedback"
        os.makedirs(feedback_dir, exist_ok=True)
        _logger.info(f"Feedback directory created/exists: {feedback_dir}")

        # Save to JSON file with timestamp
        filename = (
            f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{stream_id}.json"
        )
        filepath = os.path.join(feedback_dir, filename)
        _logger.info(f"Saving feedback to file: {filepath}")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(feedback_data, f, indent=2, ensure_ascii=False)

        _logger.info(f"Feedback saved successfully to {filepath}")
        result = {"success": True, "filepath": filepath}
        _logger.info(f"Returning result: {result}")
        return result

    except Exception as e:
        import traceback

        _logger.error(f"Failed to save feedback for {arguments.stream_id}: {e}")
        _logger.error(f"Full traceback: {traceback.format_exc()}")
        # Return an error response instead of raising, so the frontend gets a proper response
        return {"success": False, "error": str(e)}
