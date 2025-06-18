import re
import pandas as pd

from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    import sklearn.base
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.data_types import Utterance, PromptTemplate


def get_artefacts_from_utterance_content(utterance: Utterance | str) -> List[Artefact]:
    if isinstance(utterance, Utterance):
        utterance_content = utterance.content
    else:
        utterance_content = utterance

    artefact_matches = re.findall(
        r"<artefact.*?>(.+?)</artefact>",
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


def get_table_and_model_from_artefacts(
    artefact_list: List[Artefact],
) -> Tuple["pd.DataFrame", "sklearn.base.BaseEstimator"]:
    table_artefacts = [
        item
        for item in artefact_list
        if item.type == Artefact.Types.TABLE or item.type == Artefact.Types.IMAGE
    ]
    models_artefacts = [
        item for item in artefact_list if item.type == Artefact.Types.MODEL
    ]
    return table_artefacts[0].data if table_artefacts else None, models_artefacts[
        0
    ].model if models_artefacts else None


def create_prompt_from_artefacts(
    artefact_list: List[Artefact],
    filename: str,
    prompt_with_model: PromptTemplate | None,
    prompt_without_model: PromptTemplate,
) -> str:
    table_artefacts = [
        item
        for item in artefact_list
        if item.type == Artefact.Types.TABLE or item.type == Artefact.Types.IMAGE
    ]
    models_artefacts = [
        item for item in artefact_list if item.type == Artefact.Types.MODEL
    ]
    if not table_artefacts:
        table_artefacts = [
            Artefact(
                data=pd.DataFrame(),
                description="",
                type=Artefact.Types.TABLE,
            )
        ]

    if not models_artefacts or not prompt_with_model:
        return prompt_without_model.complete(
            data_source_name="dataframe",
            data_source_type=str(type(table_artefacts[0].data)),
            schema=table_artefacts[0].description,
            filename=filename,
        )

    return prompt_with_model.complete(
        data_source_name="dataframe",
        data_source_type=str(type(table_artefacts[0].data)),
        schema=table_artefacts[0].description,
        model_name="sklearn_model",
        sklearn_model=models_artefacts[0].model,
        training_code=models_artefacts[0].code,
        filename=filename,
    )
