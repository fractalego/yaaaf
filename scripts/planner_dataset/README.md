# Planner Dataset Generation

This directory contains scripts for generating synthetic planning datasets using GPT-4o-mini.

## Overview

The `generate_dataset.py` script creates a stratified dataset of planning examples (default: 100), where each example consists of:
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

3. (Optional) Configure generation settings in `config.json`:
```bash
nano config.json  # Edit configuration
```

## Configuration

The script uses `config.json` for all settings. You can override any setting via command-line arguments.

### config.json Structure

```json
{
  "generation": {
    "total_examples": 1000,
    "model": "gpt-4o-mini",
    "output_path": "planner_dataset.csv",
    "save_debug_info": false,
    "scenario_temperature": 0.9,
    "workflow_temperature": 0.7,
    "max_workflow_retries": 2
  },
  "stratification": {
    "buckets": [
      {
        "name": "simple_2agent_chain",
        "min_agents": 2,
        "max_agents": 2,
        "min_steps": 2,
        "max_steps": 2,
        "complexity": "simple_chain",
        "proportion": 0.15
      }
      // ... more buckets
    ]
  }
}
```

### Configuration Parameters

**Generation Settings:**
- `total_examples`: Number of examples to generate (e.g., 100, 1000)
- `model`: OpenAI model (e.g., `gpt-4o-mini`, `gpt-4-turbo-preview`, `gpt-4`)
- `output_path`: Output CSV file path
- `save_debug_info`: Save debug info for failed workflows (true/false)
- `scenario_temperature`: Creativity for scenario generation (0.0-2.0, higher = more creative)
- `workflow_temperature`: Creativity for workflow generation (0.0-2.0)
- `max_workflow_retries`: Retries if workflow validation fails

**Stratification Settings:**
- `buckets`: List of complexity buckets
  - `name`: Bucket identifier
  - `min_agents`/`max_agents`: Agent count range
  - `min_steps`/`max_steps`: Workflow step range
  - `complexity`: `simple_chain`, `multi_branch`, or `complex_tree`
  - `proportion`: Fraction of total examples (should sum to 1.0)

## Usage

### Basic usage (uses config.json):
```bash
python generate_dataset.py
```

### Override config via CLI:
```bash
python generate_dataset.py \
  --total 500 \
  --model "gpt-4-turbo-preview" \
  --output "my_dataset.csv" \
  --debug
```

### Use custom config file:
```bash
python generate_dataset.py --config my_config.json
```

### CLI Arguments (override config.json):
- `--config`: Path to config file (default: config.json)
- `--api-key`: OpenAI API key (or set OPENAI_API_KEY env var)
- `--model`: GPT-4 model to use (overrides config)
- `--total`: Total number of examples (overrides config)
- `--output`: Output CSV file path (overrides config)
- `--debug`: Enable debug mode (overrides config)

### Testing the generation:
Before generating the full dataset, test with a small sample:
```bash
python test_generation.py
```
This generates 6 examples (2 from each complexity bucket) to verify everything works correctly.

## Dataset Structure

The generated dataset is stratified across multiple dimensions:

### Stratification Buckets

The buckets scale proportionally with `--total`. For 100 examples:

1. **Simple 2-Agent Chain** (~15 examples)
   - 2 agents, 2 steps
   - Linear workflow (A → B)

2. **Medium Chain** (~20 examples)
   - 3-5 agents, 3-5 steps
   - Linear workflow (A → B → C → D)

3. **Medium Branch** (~25 examples)
   - 3-5 agents, 3-6 steps
   - Multi-branch workflow (A → B, A → C → D)

4. **Complex Tree Small** (~20 examples)
   - 6-8 agents, 6-10 steps
   - Complex dependency graph

5. **Complex Tree Large** (~20 examples)
   - 9-12 agents, 9-15 steps
   - Very complex dependency graph

For 1000 examples, the distribution is: [150, 200, 250, 200, 200]

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

Generated workflows follow the asset-based YAML format with descriptive names and data quality checks:

```yaml
assets:
  customer_sales_data:  # Descriptive, semantic name
    agent: SqlAgent
    description: "Extract customer purchase history from sales database"
    type: table
    checks:  # Data quality acceptance conditions (Prefect/Dagster style)
      - "row_count > 0"
      - "columns: [customer_id, purchase_date, amount, product_id]"
      - "amount >= 0"
      - "no_null_values: [customer_id, purchase_date]"

  validated_sales_data:
    agent: ReviewerAgent
    description: "Validate and clean sales data for outliers"
    type: table
    inputs: [customer_sales_data]
    checks:
      - "row_count >= customer_sales_data.row_count * 0.95"
      - "amount between 0 and 1000000"

  monthly_revenue_chart:
    agent: VisualizationAgent
    description: "Create monthly revenue trend visualization"
    type: image
    inputs: [validated_sales_data]
    checks:
      - "file_size < 5MB"
      - "format: png"
```

### Key Features:
- **Descriptive Asset Names**: Uses semantic names like `customer_sales_data` instead of generic `asset1`
- **Acceptance Conditions**: Each asset includes `checks` field with Prefect/Dagster-style data quality validations
- **Dependency Graph**: `inputs` field creates explicit data flow dependencies

## Debugging and Troubleshooting

If you see warnings about invalid workflows:

1. **Run with debug flag** to save failed workflows for inspection:
   ```bash
   python generate_dataset.py --total 100 --debug
   ```
   This creates a `*_debug.json` file with details about failed workflows.

2. **Check the debug file** to see what GPT-4o-mini is generating:
   ```bash
   cat planner_dataset_debug.json | head -50
   ```

3. **Common issues:**
   - **Missing 'assets' section**: GPT-4 didn't follow the YAML format. The script now has retry logic.
   - **Unknown agent names**: GPT-4 invented agent names. Retrying usually fixes this.
   - **Invalid YAML**: Syntax errors in generated YAML. Retrying usually fixes this.

4. **The script automatically retries** up to 2 times per workflow if validation fails.

## Notes

- The script uses GPT-4o-mini for both scenario generation and workflow planning (much cheaper than GPT-4)
- Generation takes approximately 3-5 minutes for 100 examples (depending on API rate limits)
- For 1000 examples, expect ~30-50 minutes
- Invalid workflows are flagged but included in the dataset for analysis
- The script has retry logic to handle API errors and invalid workflows
- Progress is displayed with tqdm progress bars
- Use `--debug` flag to save detailed information about failed workflows
- Output is saved as CSV format (no pyarrow dependency required)
