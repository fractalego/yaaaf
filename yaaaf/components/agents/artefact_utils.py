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


def create_prompt_from_sources(
    sources: List,
    prompt_template: PromptTemplate,
) -> str:
    """Create a completed prompt from SQL sources.
    
    Args:
        sources: List of SQL sources (e.g., SqliteSource objects)
        prompt_template: The prompt template to complete
        
    Returns:
        Completed prompt with schema information
    """
    schema_descriptions = []
    
    for source in sources:
        if hasattr(source, 'get_schema_description'):
            schema_desc = source.get_schema_description()
            if schema_desc:
                schema_descriptions.append(f"Source: {source.name}\n{schema_desc}")
        elif hasattr(source, 'schema'):
            schema_descriptions.append(f"Source: {getattr(source, 'name', 'Unknown')}\n{source.schema}")
    
    # Join all schema descriptions
    full_schema = "\n\n".join(schema_descriptions) if schema_descriptions else "No schema information available"
    
    return prompt_template.complete(schema=full_schema)


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
    
    # Generate artifact list for prompts that need it
    artifact_list = _generate_artifact_list(artefact_list)

    # Convert table to markdown for prompts that expect {table} placeholder
    table_markdown = ""
    if hasattr(table_artefacts[0].data, 'to_markdown'):
        try:
            table_markdown = table_artefacts[0].data.to_markdown(index=False)
        except Exception:
            table_markdown = str(table_artefacts[0].data)
    else:
        table_markdown = str(table_artefacts[0].data)

    if not models_artefacts or not prompt_with_model:
        return prompt_without_model.complete(
            data_source_name=data_source_name,
            data_source_type="pandas.DataFrame",
            schema=schema,
            filename=filename,
            artifact_list=artifact_list,
            table=table_markdown,
        )

    return prompt_with_model.complete(
        data_source_name=data_source_name,
        data_source_type="pandas.DataFrame",
        schema=schema,
        model_name="sklearn_model",
        sklearn_model=models_artefacts[0].model,
        training_code=models_artefacts[0].code,
        filename=filename,
        artifact_list=artifact_list,
        table=table_markdown,
    )


def _generate_artifact_list(artefact_list: List[Artefact]) -> str:
    """Generate a formatted list of artifacts for inclusion in prompts."""
    if not artefact_list:
        return ""
    
    artifact_strings = []
    for artifact in artefact_list:
        content = ""
        
        if artifact.type == Artefact.Types.TABLE and hasattr(artifact.data, 'to_markdown'):
            # Convert DataFrame to markdown
            try:
                content = artifact.data.to_markdown(index=False)
            except Exception as e:
                content = f"Table artifact: {artifact.description or 'Unable to display table'}"
        elif artifact.type == Artefact.Types.IMAGE:
            content = f"Image artifact: {artifact.description or 'Image data'}"
        elif artifact.type == Artefact.Types.TODO_LIST and hasattr(artifact.data, 'to_markdown'):
            # Todo lists are also tables
            try:
                content = artifact.data.to_markdown(index=False)
            except Exception as e:
                content = f"Todo list artifact: {artifact.description or 'Unable to display todo list'}"
        elif artifact.code:
            # For artifacts with code (like models)
            content = f"{artifact.type} artifact:\n{artifact.code[:500]}..." if len(artifact.code) > 500 else artifact.code
        else:
            content = artifact.description or f"{artifact.type} artifact"
        
        artifact_strings.append(f'<item source="{artifact.id}">\n{content}\n</item>')
    
    return "\n\n".join(artifact_strings)
