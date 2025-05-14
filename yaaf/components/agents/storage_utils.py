import re

from typing import List
from yaaf.components.agents.artefacts import Artefact, ArtefactStorage


def get_artefacts_from_utterance_content(utterance_content) -> List[Artefact]:
    artefact_matches = re.findall(
        rf"<artefact.*?>(.+?)</artefact>",
        utterance_content,
        re.MULTILINE | re.DOTALL,
    )
    if not artefact_matches:
        return []

    storage = ArtefactStorage()
    artefacts: List[Artefact] = []
    for match in artefact_matches:
        artefact_id: str = match
        try:
            artefacts.append(storage.retrieve_from_id(artefact_id))
        except ValueError:
            pass

    return artefacts