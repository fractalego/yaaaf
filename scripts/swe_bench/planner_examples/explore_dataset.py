#!/usr/bin/env python3
"""
Explore the SWE-bench/SWE-smith-trajectories dataset structure.

This script downloads a small sample and analyzes the structure to understand
how to convert trajectories into planner dataset format.

Usage:
    python explore_dataset.py [--num-samples N] [--split SPLIT] [--output FILE]
"""

import argparse
import json
import sys
from collections import Counter

from datasets import load_dataset


def explore_message_structure(messages: list) -> dict:
    """Analyze the structure of messages in a trajectory."""
    stats = {
        "total_messages": len(messages),
        "roles": Counter(),
        "message_types": Counter(),
        "agents": Counter(),
        "has_tool_calls": 0,
        "has_thought": 0,
        "has_action": 0,
        "actions": Counter(),
    }

    for msg in messages:
        stats["roles"][msg.get("role", "unknown")] += 1
        stats["message_types"][msg.get("message_type", "unknown")] += 1
        stats["agents"][msg.get("agent", "unknown")] += 1

        if msg.get("tool_calls"):
            stats["has_tool_calls"] += 1
        if msg.get("thought"):
            stats["has_thought"] += 1
        if msg.get("action"):
            stats["has_action"] += 1
            # Extract action name/type
            action = msg.get("action", "")
            if isinstance(action, str) and action:
                # Try to extract action type from the action string
                action_type = action.split("(")[0].split()[0] if action else "unknown"
                stats["actions"][action_type[:50]] += 1  # Truncate long actions

    return stats


def extract_tools_from_trajectory(messages: list) -> list:
    """Extract all tools/actions used in a trajectory."""
    tools = []
    for msg in messages:
        if msg.get("role") == "assistant":
            if msg.get("tool_calls"):
                for tool_call in msg["tool_calls"]:
                    if isinstance(tool_call, dict):
                        tools.append({
                            "name": tool_call.get("name", tool_call.get("function", {}).get("name", "unknown")),
                            "type": "tool_call"
                        })
            if msg.get("action"):
                tools.append({
                    "name": str(msg["action"])[:100],
                    "type": "action"
                })
    return tools


def print_sample_trajectory(example: dict, index: int):
    """Print a detailed view of a single trajectory."""
    print(f"\n{'='*80}")
    print(f"SAMPLE {index + 1}")
    print(f"{'='*80}")
    print(f"Instance ID: {example.get('instance_id', 'N/A')}")
    print(f"Resolved: {example.get('resolved', 'N/A')}")
    print(f"Model: {example.get('model', 'N/A')}")
    print(f"Trajectory ID: {example.get('traj_id', 'N/A')}")

    # Parse messages
    messages_raw = example.get("messages", "[]")
    try:
        if isinstance(messages_raw, str):
            messages = json.loads(messages_raw)
        else:
            messages = messages_raw
    except json.JSONDecodeError:
        print(f"Could not parse messages as JSON")
        print(f"Messages type: {type(messages_raw)}")
        print(f"Messages preview: {str(messages_raw)[:500]}")
        return None

    print(f"\nTotal messages: {len(messages)}")

    # Analyze structure
    stats = explore_message_structure(messages)
    print(f"\nMessage roles: {dict(stats['roles'])}")
    print(f"Message types: {dict(stats['message_types'])}")
    print(f"Messages with tool_calls: {stats['has_tool_calls']}")
    print(f"Messages with thought: {stats['has_thought']}")
    print(f"Messages with action: {stats['has_action']}")

    if stats['actions']:
        print(f"\nActions used (top 10):")
        for action, count in stats['actions'].most_common(10):
            print(f"  - {action}: {count}")

    # Show first few messages in detail
    print(f"\n--- First 3 messages ---")
    for i, msg in enumerate(messages[:3]):
        print(f"\n[Message {i+1}]")
        print(f"  Role: {msg.get('role')}")
        print(f"  Type: {msg.get('message_type')}")
        print(f"  Agent: {msg.get('agent')}")

        content = msg.get("content", "")
        if isinstance(content, list):
            content = str(content)
        content_preview = content[:300] if content else "(empty)"
        print(f"  Content preview: {content_preview}...")

        if msg.get("thought"):
            thought_preview = str(msg["thought"])[:200]
            print(f"  Thought: {thought_preview}...")
        if msg.get("action"):
            action_preview = str(msg["action"])[:200]
            print(f"  Action: {action_preview}...")
        if msg.get("tool_calls"):
            print(f"  Tool calls: {msg['tool_calls'][:2]}...")  # First 2

    # Show a middle assistant message with action
    print(f"\n--- Sample assistant action message ---")
    for msg in messages:
        if msg.get("role") == "assistant" and (msg.get("action") or msg.get("tool_calls")):
            print(f"  Thought: {str(msg.get('thought', ''))[:300]}...")
            print(f"  Action: {str(msg.get('action', ''))[:500]}...")
            if msg.get("tool_calls"):
                print(f"  Tool calls: {json.dumps(msg['tool_calls'], indent=2)[:500]}...")
            break

    # Extract tools summary
    tools = extract_tools_from_trajectory(messages)
    print(f"\n--- Tools/Actions used in trajectory ({len(tools)} total) ---")
    tool_names = Counter([t["name"].split("(")[0][:30] for t in tools])
    for name, count in tool_names.most_common(10):
        print(f"  - {name}: {count}")

    # Show patch preview if available
    patch = example.get("patch", "")
    if patch:
        print(f"\n--- Patch preview ---")
        print(patch[:500] if len(patch) > 500 else patch)
        print("..." if len(patch) > 500 else "")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Explore the SWE-bench/SWE-smith-trajectories dataset structure"
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=3,
        help="Number of samples to examine (default: 3)",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="tool",
        choices=["tool", "xml", "ticks"],
        help="Which split to examine (default: tool)",
    )
    parser.add_argument(
        "--resolved-only",
        action="store_true",
        help="Only show resolved trajectories",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (default: stdout)",
    )

    args = parser.parse_args()

    # Redirect stdout to file if specified
    if args.output:
        sys.stdout = open(args.output, "w", encoding="utf-8")

    print(f"Loading SWE-bench/SWE-smith-trajectories dataset (split: {args.split})...")
    print("This may take a moment on first run...\n")

    # Load only a small slice to avoid memory issues
    # Using split with range to limit download size
    max_to_fetch = args.num_samples * 10 if args.resolved_only else args.num_samples
    dataset = load_dataset(
        "SWE-bench/SWE-smith-trajectories",
        split=f"{args.split}[:{max_to_fetch}]",
    )

    # Collect samples
    all_stats = []
    all_tools = Counter()
    count = 0

    for example in dataset:
        if args.resolved_only and not example.get("resolved"):
            continue

        stats = print_sample_trajectory(example, count)
        if stats:
            all_stats.append(stats)
            all_tools.update(stats["actions"])

        count += 1
        if count >= args.num_samples:
            break

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY ACROSS ALL SAMPLES")
    print(f"{'='*80}")

    print(f"\nAll actions/tools found:")
    for action, count in all_tools.most_common(20):
        print(f"  - {action}: {count}")

    print(f"\n--- Mapping to YAAAF Agents ---")
    print("""
Based on the actions found, here's a suggested mapping:

SWE-bench Action          → YAAAF Agent (existing or new)
─────────────────────────────────────────────────────────
find_file, search_dir     → CodeSearchAgent (NEW)
open_file, view_file      → BashAgent (cat/read)
edit_file, str_replace    → CodeEditAgent (NEW)
bash, execute_bash        → BashAgent
create_file               → BashAgent (echo/write)
submit                    → (final output)
scroll_up, scroll_down    → (navigation - may not need)
    """)

    # Close file if we redirected stdout
    if args.output:
        sys.stdout.close()
        sys.stdout = sys.__stdout__
        print(f"Output written to: {args.output}")


if __name__ == "__main__":
    main()
