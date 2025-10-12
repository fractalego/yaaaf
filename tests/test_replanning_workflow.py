#!/usr/bin/env python3
"""
Test script to verify the replanning workflow with status extractor and orchestrator
"""

import asyncio
from unittest.mock import Mock, AsyncMock
import pandas as pd

from yaaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.client import OllamaClient


async def test_replanning_workflow():
    """Test the complete replanning workflow."""
    print("🧪 Testing Replanning Workflow")
    print("=" * 50)

    # Setup
    mock_client = Mock(spec=OllamaClient)
    orchestrator = OrchestratorAgent(mock_client)
    storage = ArtefactStorage()

    # Create initial todo list
    df = pd.DataFrame(
        {
            "ID": ["1", "2", "3"],
            "Task": ["Query user table", "Process results", "Create visualization"],
            "Status": ["completed", "in_progress", "pending"],
            "Agent/Tool": ["SQLAgent", "SQLAgent", "VisualizationAgent"],
        }
    )

    artifact = Artefact(
        type=Artefact.Types.TODO_LIST,
        data=df,
        description="Initial todo list",
        id="initial_todo_123",
    )
    storage.store_artefact("initial_todo_123", artifact)

    # Set the todo artifact in orchestrator
    orchestrator._current_todo_artifact_id = "initial_todo_123"

    print("\n📋 Initial Todo List:")
    print(df.to_markdown(index=False))

    # Test 1: Normal status update (no plan change)
    print("\n🔍 Test 1: Normal agent response (no plan change)")
    mock_response1 = Mock()
    mock_response1.message = "no"  # No plan change
    mock_client.predict = AsyncMock(return_value=mock_response1)

    normal_response = "Processing complete: Found 100 user records"
    (
        artifact_id,
        needs_replanning,
    ) = await orchestrator._status_extractor.extract_and_update_status(
        normal_response, "SQLAgent", "initial_todo_123"
    )

    print(f"   Needs replanning: {needs_replanning}")
    print(f"   Artifact ID: {artifact_id}")

    # Test 2: Response that triggers plan change
    print("\n🔄 Test 2: Agent response requiring plan change")
    mock_response2 = Mock()
    mock_response2.message = "yes"  # Plan change needed
    mock_client.predict = AsyncMock(return_value=mock_response2)

    plan_change_response = "Error: User table doesn't exist. Found 'customers' table instead with different schema."
    (
        artifact_id,
        needs_replanning,
    ) = await orchestrator._status_extractor.extract_and_update_status(
        plan_change_response, "SQLAgent", "initial_todo_123"
    )

    print(f"   Needs replanning: {needs_replanning}")
    print(f"   Artifact ID: {artifact_id}")

    # Test 3: Orchestrator replanning state
    print("\n📝 Test 3: Orchestrator replanning state")
    orchestrator._needs_replanning = True
    progress_section = orchestrator._get_task_progress_section()

    print("   Replanning progress section:")
    print("   " + progress_section.replace("\n", "\n   "))

    print("\n✅ Replanning workflow tests completed!")


if __name__ == "__main__":
    asyncio.run(test_replanning_workflow())
