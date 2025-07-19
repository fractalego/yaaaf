import asyncio
import logging
import threading
import os
import tempfile
import hashlib
import sqlite3
import pandas as pd

from typing import List, Optional
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from fastapi import UploadFile, HTTPException, Form

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.data_types import Utterance, Messages, Note
from yaaaf.components.orchestrator_builder import OrchestratorBuilder
from yaaaf.components.sources.rag_source import RAGSource
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
    summary: str

    @staticmethod
    def create_from_artefact(artefact: Artefact) -> "ArtefactOutput":
        return ArtefactOutput(
            data=artefact.data.to_html(index=False)
            if artefact.data is not None
            else "",
            code=artefact.code if artefact.code is not None else "",
            image=artefact.image if artefact.image is not None else "",
            summary=artefact.summary if artefact.summary is not None else "",
        )


class ImageArguments(BaseModel):
    image_id: str


def create_stream(arguments: CreateStreamArguments):
    try:
        stream_id = arguments.stream_id
        messages = Messages(utterances=arguments.messages)

        async def build_and_compute():
            orchestrator = await OrchestratorBuilder(get_config()).build()
            await do_compute(stream_id, messages, orchestrator)

        t = threading.Thread(target=asyncio.run, args=(build_and_compute(),))
        t.start()
    except Exception as e:
        _logger.error(f"Routes: Failed to create stream for {arguments.stream_id}: {e}")
        raise


def get_all_utterances(arguments: NewUtteranceArguments) -> List[Note]:
    try:
        all_notes = get_utterances(arguments.stream_id)
        # Filter out internal messages for frontend display
        return [note for note in all_notes if not getattr(note, "internal", False)]
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


class AgentInfo(BaseModel):
    name: str
    description: str
    type: str  # "agent" or "source" or "tool"


class FileUploadResponse(BaseModel):
    success: bool
    message: str
    source_id: str
    filename: str


class UpdateDescriptionRequest(BaseModel):
    source_id: str
    description: str


class UpdateDescriptionResponse(BaseModel):
    success: bool
    message: str


class SqlUpdateResponse(BaseModel):
    success: bool
    message: str
    table_name: str
    rows_inserted: int


class SqlSourceInfo(BaseModel):
    name: str
    path: str
    tables: List[str]


def get_agents_config() -> List[AgentInfo]:
    """Get list of configured agents and their information"""
    try:
        config = get_config()
        builder = OrchestratorBuilder(config)
        
        agent_info_list = []
        
        # Add configured agents
        for agent_config in config.agents:
            agent_name = builder._get_agent_name(agent_config)
            if agent_name in builder._agents_map:
                agent_class = builder._agents_map[agent_name]
                agent_info_list.append(AgentInfo(
                    name=agent_name,
                    description=agent_class.get_info(),
                    type="agent"
                ))
        
        # Add data sources
        for source_config in config.sources:
            agent_info_list.append(AgentInfo(
                name=source_config.name or "Unknown Source",
                description=f"{source_config.type} source: {source_config.path}",
                type="source"
            ))
        
        # Add tools
        for tool_config in config.tools:
            agent_info_list.append(AgentInfo(
                name=tool_config.name,
                description=tool_config.description,
                type="tool"
            ))
        
        return agent_info_list
    except Exception as e:
        _logger.error(f"Routes: Failed to get agents config: {e}")
        raise


# Global variable to store uploaded document sources
_uploaded_rag_sources = {}


async def upload_file_to_rag(file: UploadFile, pages_per_chunk: int = Form(-1)) -> FileUploadResponse:
    """Upload a file and add it to the document retriever agent sources"""
    try:
        # Check if document retriever agent is configured
        config = get_config()
        has_rag_agent = False
        for agent_config in config.agents:
            agent_name = agent_config if isinstance(agent_config, str) else agent_config.name
            if agent_name == "rag":
                has_rag_agent = True
                break
        
        if not has_rag_agent:
            raise HTTPException(status_code=400, detail="Document retriever agent is not configured")
        
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_extension = file.filename.lower().split('.')[-1]
        if file_extension not in ['txt', 'md', 'html', 'htm', 'pdf']:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Only .txt, .md, .html, .htm, .pdf files are supported"
            )
        
        # Read file content
        content = await file.read()
        
        # Create a unique source ID based on filename and content
        source_id = hashlib.md5(f"{file.filename}_{str(len(content))}".encode()).hexdigest()
        
        # Use filename as initial description
        initial_description = f"Uploaded file: {file.filename}"
        
        # Create document source and index the content
        rag_source = RAGSource(description=initial_description, source_path=f"uploaded_{source_id}")
        
        if file_extension == 'pdf':
            # Handle PDF files with configurable chunking
            rag_source.add_pdf(content, file.filename, pages_per_chunk=pages_per_chunk)
        else:
            # Handle text files
            # Try to decode as UTF-8, fallback to latin-1
            try:
                text_content = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    text_content = content.decode('latin-1')
                except UnicodeDecodeError:
                    raise HTTPException(status_code=400, detail="File encoding is not supported")
            
            rag_source.add_text(text_content)
        
        # Store the source globally so it can be used by the orchestrator
        _uploaded_rag_sources[source_id] = rag_source
        
        _logger.info(f"Successfully uploaded and indexed file {file.filename} with source ID {source_id}")
        
        return FileUploadResponse(
            success=True,
            message=f"File '{file.filename}' uploaded and indexed successfully",
            source_id=source_id,
            filename=file.filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        _logger.error(f"Routes: Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


def update_rag_source_description(request: UpdateDescriptionRequest) -> UpdateDescriptionResponse:
    """Update the description of an uploaded document source"""
    try:
        source_id = request.source_id
        new_description = request.description
        
        if source_id not in _uploaded_rag_sources:
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Update the description
        rag_source = _uploaded_rag_sources[source_id]
        rag_source._description = new_description
        
        _logger.info(f"Updated description for source {source_id}")
        
        return UpdateDescriptionResponse(
            success=True,
            message="Description updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        _logger.error(f"Routes: Failed to update description: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update description: {str(e)}")


def get_uploaded_rag_sources():
    """Get all uploaded document sources"""
    return list(_uploaded_rag_sources.values())


def get_sql_sources() -> List[SqlSourceInfo]:
    """Get list of configured SQL sources"""
    try:
        config = get_config()
        sql_sources = []
        
        for source_config in config.sources:
            if source_config.type == "sqlite":
                # Ensure database file exists - create empty one if it doesn't
                import os
                if not os.path.exists(source_config.path):
                    try:
                        # Create directory if it doesn't exist
                        os.makedirs(os.path.dirname(source_config.path), exist_ok=True)
                        # Create empty database file
                        with sqlite3.connect(source_config.path) as conn:
                            conn.execute("SELECT 1")  # Simple query to initialize the database
                        _logger.info(f"Created new database file at '{source_config.path}'")
                    except Exception as e:
                        _logger.error(f"Could not create database file at {source_config.path}: {e}")
                
                # Get table names from the database
                tables = []
                try:
                    with sqlite3.connect(source_config.path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        tables = [row[0] for row in cursor.fetchall()]
                except Exception as e:
                    _logger.warning(f"Could not read tables from {source_config.path}: {e}")
                
                sql_sources.append(SqlSourceInfo(
                    name=source_config.name,
                    path=source_config.path,
                    tables=tables
                ))
        
        return sql_sources
    except Exception as e:
        _logger.error(f"Routes: Failed to get SQL sources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get SQL sources: {str(e)}")


async def update_sql_source(
    file: UploadFile, 
    table_name: str = Form(...), 
    database_name: Optional[str] = Form(None),
    replace_table: bool = Form(False)
) -> SqlUpdateResponse:
    """Update SQL source by uploading CSV or Excel file"""
    try:
        # Check if SQL agent is configured
        config = get_config()
        sql_sources = [s for s in config.sources if s.type == "sqlite"]
        
        if not sql_sources:
            raise HTTPException(status_code=400, detail="No SQL sources configured")
        
        # Use specified database or default to first one
        if database_name:
            target_source = next((s for s in sql_sources if s.name == database_name), None)
            if not target_source:
                raise HTTPException(status_code=400, detail=f"Database '{database_name}' not found")
        else:
            target_source = sql_sources[0]
        
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_extension = file.filename.lower().split('.')[-1]
        if file_extension not in ['csv', 'xlsx', 'xls']:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file type. Only .csv, .xlsx, .xls files are supported"
            )
        
        # Read file content
        content = await file.read()
        
        # Parse file into DataFrame
        try:
            if file_extension == 'csv':
                # Try different encodings for CSV
                try:
                    df = pd.read_csv(pd.io.common.BytesIO(content), encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(pd.io.common.BytesIO(content), encoding='latin-1')
            else:  # Excel files
                df = pd.read_excel(pd.io.common.BytesIO(content))
                
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")
        
        if df.empty:
            raise HTTPException(status_code=400, detail="File contains no data")
        
        # Clean column names (remove spaces, special characters)
        df.columns = df.columns.str.strip().str.replace(' ', '_').str.replace('[^a-zA-Z0-9_]', '', regex=True)
        
        # Insert data into SQLite database
        try:
            # Ensure database file exists - create empty one if it doesn't
            import os
            if not os.path.exists(target_source.path):
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(target_source.path), exist_ok=True)
                # Create empty database file
                with sqlite3.connect(target_source.path) as conn:
                    conn.execute("SELECT 1")  # Simple query to initialize the database
                _logger.info(f"Created new database file at '{target_source.path}'")
            
            with sqlite3.connect(target_source.path) as conn:
                if replace_table:
                    # Drop table if it exists and replace_table is True
                    conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                    df.to_sql(table_name, conn, index=False, if_exists='replace')
                    action = "replaced"
                else:
                    # Append to existing table or create new one
                    df.to_sql(table_name, conn, index=False, if_exists='append')
                    action = "updated"
                
                rows_inserted = len(df)
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update database: {str(e)}")
        
        _logger.info(f"Successfully {action} table '{table_name}' in database '{target_source.name}' with {rows_inserted} rows")
        
        return SqlUpdateResponse(
            success=True,
            message=f"Successfully {action} table '{table_name}' with {rows_inserted} rows",
            table_name=table_name,
            rows_inserted=rows_inserted
        )
        
    except HTTPException:
        raise
    except Exception as e:
        _logger.error(f"Routes: Failed to update SQL source: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update SQL source: {str(e)}")


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
                        # Skip internal messages - don't send them to frontend
                        if getattr(note, "internal", False):
                            continue

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
