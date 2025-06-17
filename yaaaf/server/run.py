import os
import uvicorn

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from yaaaf.server.routes import (
    create_stream,
    get_artifact,
    get_image,
    get_all_utterances, get_query_suggestions,
)
from yaaaf.server.server_settings import server_settings

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.add_api_route("/create_stream", endpoint=create_stream, methods=["POST"])
app.add_api_route("/get_utterances", endpoint=get_all_utterances, methods=["POST"])
app.add_api_route("/get_artefact", endpoint=get_artifact, methods=["POST"])
app.add_api_route("/get_image", endpoint=get_image, methods=["POST"])
app.add_api_route("/get_query_suggestions", endpoint=get_query_suggestions, methods=["POST"])

def run_server(host: str, port: int):
    os.environ["YAAF_API_PORT"] = str(port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    os.environ["YAAF_CONFIG"] = "default_config.json"
    run_server(host=server_settings.host, port=server_settings.port)
