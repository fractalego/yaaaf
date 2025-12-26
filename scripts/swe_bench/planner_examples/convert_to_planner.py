#!/usr/bin/env python3
"""
Convert SWE-bench/SWE-smith-trajectories to planner dataset format.

This script:
1. Loads trajectories from the SWE-bench dataset
2. Extracts the problem description and tools used
3. Maps tools to YAAAF agents
4. Generates planner-compatible YAML workflows
5. Outputs a CSV in the planner_dataset format

Usage:
    python convert_to_planner.py [--num-samples N] [--output FILE] [--resolved-only]
"""

import argparse
import csv
import json
import re
from collections import Counter
from typing import Any

from datasets import load_dataset


# Mapping from SWE-bench tools/actions to YAAAF agents
TOOL_TO_AGENT = {
    # str_replace_editor operations -> CodeEditAgent
    "str_replace_editor": "CodeEditAgent",
    "view": "CodeEditAgent",
    "create": "CodeEditAgent",
    "str_replace": "CodeEditAgent",

    # bash operations -> BashAgent
    "bash": "BashAgent",
    "find": "BashAgent",
    "grep": "BashAgent",
    "cd": "BashAgent",
    "python": "BashAgent",
    "pytest": "BashAgent",
    "rm": "BashAgent",
    "head": "BashAgent",
    "tail": "BashAgent",
    "cat": "BashAgent",
    "ls": "BashAgent",
    "mkdir": "BashAgent",

    # submit is final output, not an agent
    "submit": None,
}


def extract_problem_description(messages: list) -> str:
    """Extract the problem description from the user message."""
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                # Extract text from content list
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        # Extract PR description
                        pr_match = re.search(
                            r"<pr_description>(.*?)</pr_description>",
                            text,
                            re.DOTALL
                        )
                        if pr_match:
                            return pr_match.group(1).strip()
                        # Fallback to first part of text
                        return text[:500].strip()
            elif isinstance(content, str):
                return content[:500].strip()
    return "Fix the bug described in the issue"


def extract_tools_from_trajectory(messages: list) -> list[dict]:
    """Extract all tools/actions used in a trajectory."""
    tools = []
    for msg in messages:
        if msg.get("role") == "assistant":
            # Check for tool_calls
            if msg.get("tool_calls"):
                for tool_call in msg["tool_calls"]:
                    if isinstance(tool_call, dict):
                        func = tool_call.get("function", {})
                        name = func.get("name", tool_call.get("name", "unknown"))
                        args = func.get("arguments", "{}")
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {"raw": args}
                        tools.append({
                            "name": name,
                            "args": args,
                            "type": "tool_call"
                        })

            # Check for action field
            action = msg.get("action", "")
            if action:
                # Parse action to get tool name
                action_str = str(action)
                # Extract first word/command
                first_word = action_str.split()[0] if action_str.split() else "unknown"
                tools.append({
                    "name": first_word,
                    "action": action_str[:200],
                    "type": "action"
                })

    return tools


def analyze_tool_usage(tools: list[dict]) -> dict:
    """Analyze tool usage patterns."""
    tool_counts = Counter()
    tool_sequence = []

    for tool in tools:
        name = tool.get("name", "unknown").lower()

        # Normalize tool names
        if "str_replace" in name:
            normalized = "str_replace_editor"
        elif name in ["find", "grep", "cd", "python", "pytest", "rm", "ls", "head", "tail", "cat", "mkdir"]:
            normalized = "bash"
        elif name == "bash":
            # Check if it's a specific bash command
            args = tool.get("args", {})
            cmd = args.get("command", "") if isinstance(args, dict) else ""
            if "python" in cmd.lower():
                normalized = "bash_python"
            elif "pytest" in cmd.lower() or "unittest" in cmd.lower():
                normalized = "bash_test"
            else:
                normalized = "bash"
        elif name == "submit":
            normalized = "submit"
        else:
            normalized = name

        tool_counts[normalized] += 1
        tool_sequence.append(normalized)

    return {
        "counts": dict(tool_counts),
        "sequence": tool_sequence,
        "total": len(tools)
    }


def map_to_yaaaf_agents(tool_analysis: dict) -> list[str]:
    """Map tool usage to YAAAF agents."""
    agents = set()

    for tool_name in tool_analysis["counts"].keys():
        if tool_name in TOOL_TO_AGENT:
            agent = TOOL_TO_AGENT[tool_name]
            if agent:
                agents.add(agent)
        elif tool_name.startswith("bash"):
            agents.add("BashAgent")

    # Always include AnswererAgent for synthesizing results
    agents.add("AnswererAgent")

    return sorted(list(agents))


def generate_workflow_yaml(
    problem_description: str,
    agents_used: list[str],
    tool_analysis: dict
) -> str:
    """Generate a planner-compatible YAML workflow."""

    # Determine workflow pattern based on tool usage
    has_code_edit = "CodeEditAgent" in agents_used
    has_bash = "BashAgent" in agents_used
    has_tests = "bash_test" in tool_analysis["counts"] or "bash_python" in tool_analysis["counts"]

    yaml_parts = ["assets:"]
    step_num = 0
    previous_asset = None

    # Step 1: Problem analysis (always first)
    step_num += 1
    yaml_parts.append(f"""
  problem_analysis:
    agent: AnswererAgent
    description: "Analyze the bug report and identify what needs to be fixed"
    type: text""")
    previous_asset = "problem_analysis"

    # Step 2: Code exploration (if bash is used)
    if has_bash:
        step_num += 1
        yaml_parts.append(f"""
  relevant_files:
    agent: BashAgent
    description: "Find relevant source files using find and grep"
    type: text
    inputs: [{previous_asset}]""")
        previous_asset = "relevant_files"

    # Step 3: Code viewing (if code_edit is used)
    if has_code_edit:
        step_num += 1
        yaml_parts.append(f"""
  code_analysis:
    agent: CodeEditAgent
    description: "View the relevant source files to understand the code"
    type: text
    inputs: [{previous_asset}]""")
        previous_asset = "code_analysis"

    # Step 4: Code fix (if code_edit is used)
    if has_code_edit:
        step_num += 1
        yaml_parts.append(f"""
  code_fix:
    agent: CodeEditAgent
    description: "Apply the fix using str_replace to modify the buggy code"
    type: text
    inputs: [{previous_asset}, problem_analysis]""")
        previous_asset = "code_fix"

    # Step 5: Verification (if tests are run)
    if has_tests:
        step_num += 1
        yaml_parts.append(f"""
  verification:
    agent: BashAgent
    description: "Run tests to verify the fix works correctly"
    type: text
    inputs: [{previous_asset}]""")
        previous_asset = "verification"

    # Step 6: Final summary
    step_num += 1
    yaml_parts.append(f"""
  fix_summary:
    agent: AnswererAgent
    description: "Summarize the fix and its verification results"
    type: text
    inputs: [{previous_asset}]""")

    return "".join(yaml_parts)


def determine_complexity(tool_analysis: dict, agents_used: list[str]) -> str:
    """Determine workflow complexity."""
    num_agents = len(agents_used)
    num_tools = tool_analysis["total"]

    if num_agents <= 2 and num_tools <= 10:
        return "simple_chain"
    elif num_agents <= 3 and num_tools <= 30:
        return "medium_chain"
    else:
        return "complex_chain"


def convert_trajectory_to_planner_entry(example: dict) -> dict | None:
    """Convert a single SWE-bench trajectory to planner dataset entry."""
    # Parse messages
    messages_raw = example.get("messages", "[]")
    try:
        if isinstance(messages_raw, str):
            messages = json.loads(messages_raw)
        else:
            messages = messages_raw
    except json.JSONDecodeError:
        return None

    # Extract problem description
    problem_desc = extract_problem_description(messages)

    # Clean up the description for CSV
    problem_desc = problem_desc.replace('"', '""')  # Escape quotes
    problem_desc = re.sub(r'\s+', ' ', problem_desc)  # Normalize whitespace
    problem_desc = problem_desc[:1000]  # Limit length

    # Extract and analyze tools
    tools = extract_tools_from_trajectory(messages)
    tool_analysis = analyze_tool_usage(tools)

    # Map to YAAAF agents
    agents_used = map_to_yaaaf_agents(tool_analysis)

    # Generate workflow YAML
    workflow_yaml = generate_workflow_yaml(problem_desc, agents_used, tool_analysis)

    # Count steps (assets in the YAML)
    num_steps = workflow_yaml.count("agent:")

    # Determine complexity
    complexity = determine_complexity(tool_analysis, agents_used)

    return {
        "scenario": problem_desc,
        "workflow_yaml": workflow_yaml,
        "agents_used": str(agents_used),
        "num_agents": len(agents_used),
        "num_steps": num_steps,
        "complexity": complexity,
        "is_valid": True,
        "error_message": "",
        # Extra metadata
        "instance_id": example.get("instance_id", ""),
        "resolved": example.get("resolved", False),
        "tool_counts": str(tool_analysis["counts"]),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Convert SWE-bench trajectories to planner dataset format"
    )
    parser.add_argument(
        "--num-samples",
        "-n",
        type=int,
        default=100,
        help="Number of samples to convert (default: 100)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="swe_bench_planner_dataset.csv",
        help="Output CSV file path (default: swe_bench_planner_dataset.csv)",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="tool",
        choices=["tool", "xml", "ticks"],
        help="Which split to use (default: tool)",
    )
    parser.add_argument(
        "--resolved-only",
        action="store_true",
        help="Only include resolved trajectories",
    )
    parser.add_argument(
        "--include-metadata",
        action="store_true",
        help="Include extra metadata columns (instance_id, resolved, tool_counts)",
    )

    args = parser.parse_args()

    print(f"Loading SWE-bench/SWE-smith-trajectories dataset (split: {args.split})...")

    # Load dataset slice
    max_to_fetch = args.num_samples * 2 if args.resolved_only else args.num_samples
    dataset = load_dataset(
        "SWE-bench/SWE-smith-trajectories",
        split=f"{args.split}[:{max_to_fetch}]",
    )

    print(f"Converting trajectories to planner dataset format...")

    entries = []
    for example in dataset:
        if args.resolved_only and not example.get("resolved"):
            continue

        entry = convert_trajectory_to_planner_entry(example)
        if entry:
            entries.append(entry)

        if len(entries) >= args.num_samples:
            break

        if len(entries) % 10 == 0:
            print(f"  Converted {len(entries)} entries...")

    print(f"\nConverted {len(entries)} trajectories")

    # Determine columns to write
    base_columns = [
        "scenario", "workflow_yaml", "agents_used", "num_agents",
        "num_steps", "complexity", "is_valid", "error_message"
    ]
    extra_columns = ["instance_id", "resolved", "tool_counts"]

    columns = base_columns + extra_columns if args.include_metadata else base_columns

    # Write CSV
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for entry in entries:
            # Filter to only requested columns
            row = {k: entry[k] for k in columns}
            writer.writerow(row)

    print(f"Output written to: {args.output}")

    # Print summary
    print(f"\n--- Summary ---")
    agent_counts = Counter()
    complexity_counts = Counter()
    for entry in entries:
        agents = eval(entry["agents_used"])
        for agent in agents:
            agent_counts[agent] += 1
        complexity_counts[entry["complexity"]] += 1

    print(f"Agent usage:")
    for agent, count in agent_counts.most_common():
        print(f"  - {agent}: {count}")

    print(f"\nComplexity distribution:")
    for complexity, count in complexity_counts.most_common():
        print(f"  - {complexity}: {count}")


if __name__ == "__main__":
    main()
