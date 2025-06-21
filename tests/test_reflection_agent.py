#!/usr/bin/env python3
"""
Test script to verify that ReflectionAgent receives agents/sources/tools information correctly
"""

import sys
import os

# Add the current directory to Python path
sys.path.append(os.getcwd())

from yaaaf.components.client import OllamaClient
from yaaaf.components.agents.reflection_agent import ReflectionAgent
from yaaaf.components.orchestrator_builder import OrchestratorBuilder
from yaaaf.server.config import Settings, SourceSettings, ClientSettings


def test_reflection_agent_initialization():
    """Test that ReflectionAgent properly receives agents/sources/tools information."""

    print("🧪 Testing ReflectionAgent with Agents/Sources/Tools List")
    print("=" * 60)

    # Create a test client
    test_client = OllamaClient(model="test-model:latest", host="http://localhost:11434")

    # Test 1: Basic ReflectionAgent without list
    print("\n📦 Test 1: ReflectionAgent without agents list")
    basic_agent = ReflectionAgent(client=test_client)
    print(f"   Agents list: '{basic_agent._agents_and_sources_and_tools_list}'")

    # Test 2: ReflectionAgent with custom list
    test_list = """**Available Agents:**
• sql: SQL agent for database queries
• visualization: Visualization agent for charts

**Available Data Sources:**
• test_db (sqlite): ./test.db - Test database

**Available Tools:**
• File system operations
• Data visualization"""

    print("\n📦 Test 2: ReflectionAgent with custom agents list")
    custom_agent = ReflectionAgent(
        client=test_client, agents_and_sources_and_tools_list=test_list
    )
    print(
        f"   Agents list length: {len(custom_agent._agents_and_sources_and_tools_list)} characters"
    )
    print(
        f"   Contains 'SQL agent': {'SQL agent' in custom_agent._agents_and_sources_and_tools_list}"
    )
    print(
        f"   Contains 'visualization': {'visualization' in custom_agent._agents_and_sources_and_tools_list}"
    )

    return True


def test_orchestrator_builder_integration():
    """Test that OrchestratorBuilder passes agents/sources/tools info to ReflectionAgent."""

    print("\n🏗️ Testing OrchestratorBuilder Integration")
    print("-" * 40)

    # Create a test configuration
    config = Settings(
        client=ClientSettings(
            model="test-model:latest", temperature=0.7, max_tokens=1024
        ),
        agents=["reflection", "sql", "visualization"],
        sources=[SourceSettings(name="test_db", type="sqlite", path="./test.db")],
    )

    print("\n📋 Configuration:")
    print(f"   Agents: {config.agents}")
    print(f"   Sources: {[s.name for s in config.sources]}")
    print(f"   Client model: {config.client.model}")

    # Test the list generation method
    builder = OrchestratorBuilder(config)
    agents_sources_tools_list = builder._generate_agents_sources_tools_list()

    print("\n📝 Generated agents/sources/tools list:")
    print("-" * 30)
    print(agents_sources_tools_list)
    print("-" * 30)

    # Verify the list contains expected content
    expected_content = [
        "**Available Agents:**",
        "sql:",
        "visualization:",
        "**Available Data Sources:**",
        "test_db (sqlite)",
        "**Available Tools:**",
        "File system operations",
    ]

    print("\n✅ Content verification:")
    for expected in expected_content:
        contains = expected in agents_sources_tools_list
        print(f"   Contains '{expected}': {contains}")
        if not contains:
            print(f"   ❌ Missing expected content: {expected}")

    return True


def test_prompt_template_completion():
    """Test that the reflection agent prompt template gets properly completed."""

    print("\n📋 Testing Prompt Template Completion")
    print("-" * 40)

    from yaaaf.components.agents.prompts import reflection_agent_prompt_template

    test_list = """**Available Agents:**
• sql: Database queries with SQL
• visualization: Create charts and graphs

**Available Tools:**
• File operations
• Web search"""

    # Test prompt completion
    completed_prompt = reflection_agent_prompt_template.complete(
        agents_and_sources_and_tools_list=test_list
    )

    print("\n📄 Completed prompt preview:")
    print("-" * 30)
    print(
        completed_prompt[:500] + "..."
        if len(completed_prompt) > 500
        else completed_prompt
    )
    print("-" * 30)

    # Verify the test list was properly inserted
    contains_list = test_list in completed_prompt
    print(f"\n✅ Test list properly inserted: {contains_list}")

    if contains_list:
        print("   ✅ Prompt template completion successful!")
    else:
        print("   ❌ Prompt template completion failed!")

    return contains_list


if __name__ == "__main__":
    print("🎯 ReflectionAgent Integration Tests")
    print("=" * 60)

    try:
        # Run all tests
        test1_result = test_reflection_agent_initialization()
        test2_result = test_orchestrator_builder_integration()
        test3_result = test_prompt_template_completion()

        print("\n🎉 Test Results Summary:")
        print("=" * 30)
        print(
            f"   ReflectionAgent initialization: {'✅ PASS' if test1_result else '❌ FAIL'}"
        )
        print(
            f"   OrchestratorBuilder integration: {'✅ PASS' if test2_result else '❌ FAIL'}"
        )
        print(
            f"   Prompt template completion: {'✅ PASS' if test3_result else '❌ FAIL'}"
        )

        if all([test1_result, test2_result, test3_result]):
            print(
                "\n🎉 All tests passed! ReflectionAgent integration is working correctly."
            )
        else:
            print("\n❌ Some tests failed. Please check the implementation.")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
