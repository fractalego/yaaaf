import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from yaaf.server.routes import create_stream, get_artifact, get_image, get_all_utterances
from yaaf.server.settings import settings
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_api_route("/create_stream", endpoint=create_stream, methods=["POST"])
app.add_api_route("/get_utterances", endpoint=get_all_utterances, methods=["POST"])
app.add_api_route("/get_artefact", endpoint=get_artifact, methods=["POST"])
app.add_api_route("/get_image", endpoint=get_image, methods=["POST"])


def run_server(host: str, port: int):
    """
    Run the FastAPI server with the specified host and port.
    """
    uvicorn.run(app, host=host, port=port)


if __name__ == '__main__':
    run_server(host=settings.host, port=settings.port)