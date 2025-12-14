import os
import logging
import uvicorn

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from yaaaf.server.routes import (
    create_stream,
    get_artifact,
    get_image,
    get_all_utterances,
    get_query_suggestions,
    get_agents_config,
    upload_file_to_rag,
    update_rag_source_description,
    stream_utterances,
    get_sql_sources,
    update_sql_source,
    get_all_sources,
    get_persistent_documents,
    get_stream_status,
    submit_user_response,
)
from yaaaf.server.feedback import save_feedback
from yaaaf.server.server_settings import server_settings

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.add_api_route("/create_stream", endpoint=create_stream, methods=["POST"])
app.add_api_route("/get_utterances", endpoint=get_all_utterances, methods=["POST"])
app.add_api_route("/stream_utterances", endpoint=stream_utterances, methods=["POST"])
app.add_api_route("/get_artefact", endpoint=get_artifact, methods=["POST"])
app.add_api_route("/get_image", endpoint=get_image, methods=["POST"])
app.add_api_route(
    "/get_query_suggestions", endpoint=get_query_suggestions, methods=["POST"]
)
app.add_api_route("/get_agents_config", endpoint=get_agents_config, methods=["GET"])
app.add_api_route("/upload_file_to_rag", endpoint=upload_file_to_rag, methods=["POST"])
app.add_api_route(
    "/update_rag_description", endpoint=update_rag_source_description, methods=["POST"]
)
app.add_api_route("/get_sql_sources", endpoint=get_sql_sources, methods=["GET"])
app.add_api_route("/update_sql_source", endpoint=update_sql_source, methods=["POST"])
app.add_api_route("/get_all_sources", endpoint=get_all_sources, methods=["GET"])
app.add_api_route(
    "/get_persistent_documents", endpoint=get_persistent_documents, methods=["GET"]
)
app.add_api_route("/get_stream_status", endpoint=get_stream_status, methods=["POST"])
app.add_api_route("/submit_user_response", endpoint=submit_user_response, methods=["POST"])
app.add_api_route("/save_feedback", endpoint=save_feedback, methods=["POST"])


def run_server(host: str, port: int):
    # Configure logging to show INFO level messages from YAAAF components
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,  # Override any existing logging configuration
    )

    # Also set uvicorn's logging level to INFO
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.INFO)

    # Ensure YAAAF component loggers are at INFO level
    yaaaf_logger = logging.getLogger("yaaaf")
    yaaaf_logger.setLevel(logging.INFO)

    # Create server logger for startup messages
    server_logger = logging.getLogger("yaaaf.server")
    server_logger.info(f"🚀 Starting YAAAF backend server on {host}:{port}")
    server_logger.info(
        "📋 Agent registration logs will appear when first chat session starts"
    )

    os.environ["YAAF_API_PORT"] = str(port)

    # Configure uvicorn to use our logging setup
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",  # Ensure uvicorn uses info level
        access_log=True,  # Show access logs
    )


if __name__ == "__main__":
    if not os.environ.get("YAAF_CONFIG"):
        # Look for config.json in current directory, otherwise use default
        if os.path.exists("config.json"):
            os.environ["YAAF_CONFIG"] = "config.json"
        else:
            os.environ["YAAF_CONFIG"] = "default_config.json"
    run_server(host=server_settings.host, port=server_settings.port)
