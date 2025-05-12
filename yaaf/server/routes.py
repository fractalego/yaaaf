import asyncio
import threading

from typing import List
from pydantic import BaseModel

from yaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaf.components.data_types import Utterance, Messages
from yaaf.server.accessories import do_compute, get_utterances


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
    stream_id = arguments.stream_id
    messages = Messages(utterances=arguments.messages)
    t = threading.Thread(target=asyncio.run, args=(do_compute(stream_id, messages),))
    t.start()


def get_all_utterances(arguments: NewUtteranceArguments) -> List[str]:
    return get_utterances(arguments.stream_id)


def get_artifact(arguments: ArtefactArguments) -> ArtefactOutput:
    artefact_id = arguments.artefact_id
    artefact_storage = ArtefactStorage(artefact_id)
    artefact = artefact_storage.retrieve_from_id(artefact_id)
    return ArtefactOutput.create_from_artefact(artefact)


def get_image(arguments: ImageArguments) -> str:
    image_id = arguments.image_id
    artefact_storage = ArtefactStorage(image_id)
    try:
        artefact = artefact_storage.retrieve_from_id(image_id)
        return artefact.image
    except ValueError:
        return f"WARNING: Artefact with id {image_id} not found."
