import re
import pandas as pd

from typing import List, Tuple, Optional, TYPE_CHECKING

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
    data_source_name: Optional[str] = None,
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

    # Generate data source name if not provided
    if data_source_name is None:
        data_source_name = f"df_{table_artefacts[0].id[:8]}" if table_artefacts[0].id else "dataframe"
    
    # Get actual schema from DataFrame if available
    schema = table_artefacts[0].description
    if hasattr(table_artefacts[0].data, 'dtypes'):
        schema = table_artefacts[0].data.dtypes.to_string()
    
    if not models_artefacts or not prompt_with_model:
        return prompt_without_model.complete(
            data_source_name=data_source_name,
            data_source_type="pandas.DataFrame",
            schema=schema,
            filename=filename,
        )

    return prompt_with_model.complete(
        data_source_name=data_source_name,
        data_source_type="pandas.DataFrame",
        schema=schema,
        model_name="sklearn_model",
        sklearn_model=models_artefacts[0].model,
        training_code=models_artefacts[0].code,
        filename=filename,
    )
