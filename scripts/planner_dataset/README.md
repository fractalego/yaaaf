# Planner Dataset Generation

This directory contains scripts for generating synthetic planning datasets using GPT-4.

## Overview

The `generate_dataset.py` script creates a stratified dataset of 1000 planning examples, where each example consists of:
- A realistic user scenario
- A YAML workflow plan using agents from the YAAAF framework
- Metadata about agents used, complexity, and validation status

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set your OpenAI API key:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Usage

### Basic usage (generates 1000 examples):
```bash
python generate_dataset.py
```

### Custom configuration:
```bash
python generate_dataset.py \
  --api-key "your-api-key" \
  --model "gpt-4-turbo-preview" \
  --total 1000 \
  --output "planner_dataset.parquet"
```

### Arguments:
- `--api-key`: OpenAI API key (optional if OPENAI_API_KEY env var is set)
- `--model`: GPT-4 model to use (default: gpt-4-turbo-preview)
- `--total`: Total number of examples to generate (default: 1000)
- `--output`: Output Parquet file path (default: planner_dataset.parquet)

## Dataset Structure

The generated dataset is stratified across multiple dimensions:

### Stratification Buckets

1. **Simple 2-Agent Chain** (150 examples)
   - 2 agents, 2 steps
   - Linear workflow (A → B)

2. **Medium Chain** (200 examples)
   - 3-5 agents, 3-5 steps
   - Linear workflow (A → B → C → D)

3. **Medium Branch** (250 examples)
   - 3-5 agents, 3-6 steps
   - Multi-branch workflow (A → B, A → C → D)

4. **Complex Tree Small** (200 examples)
   - 6-8 agents, 6-10 steps
   - Complex dependency graph

5. **Complex Tree Large** (200 examples)
   - 9-12 agents, 9-15 steps
   - Very complex dependency graph

### Output Columns

- `scenario`: User query/scenario description
- `workflow_yaml`: Generated YAML workflow plan
- `agents_used`: List of agent names used in the workflow
- `num_agents`: Number of unique agents used
- `num_steps`: Number of workflow steps (assets)
- `complexity`: Complexity type (simple_chain, multi_branch, complex_tree)
- `is_valid`: Whether the workflow passed validation
- `error_message`: Validation error message (if invalid)

## Available Agents

The script uses all agents defined in the YAAAF framework:

**Extractors (Sources):**
- SqlAgent
- DocumentRetrieverAgent
- BraveSearchAgent
- DuckDuckGoSearchAgent
- UrlAgent
- UserInputAgent

**Transformers:**
- ReviewerAgent
- NumericalSequencesAgent
- MleAgent
- ToolAgent

**Synthesizers:**
- AnswererAgent
- UrlRetrieverAgent

**Generators (Sinks):**
- VisualizationAgent
- BashAgent

## Workflow Format

Generated workflows follow the asset-based YAML format:

```yaml
assets:
  asset_name:
    agent: AgentName
    description: "What this step does"
    type: artifact_type  # table, text, image, model, json
    inputs: [dependency1, dependency2]  # optional
    conditions: [...]  # optional
```

## Notes

- The script uses GPT-4 for both scenario generation and workflow planning
- Generation takes approximately 30-60 minutes for 1000 examples (depending on API rate limits)
- Invalid workflows are flagged but included in the dataset for analysis
- The script has retry logic to handle API errors
- Progress is displayed with tqdm progress bars
