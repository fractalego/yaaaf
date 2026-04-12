from dataclasses import dataclass
from typing import List


@dataclass
class IntensityLevel:
    name: str
    ideal_palette: List[str]
    directive: str
    description: str


INTENSITY_LEVELS: List[IntensityLevel] = [
    IntensityLevel(
        name="Easy",
        ideal_palette=["answerer"],
        directive=(
            "Use only your internal knowledge. "
            "Generate a single-step plan with just the answerer."
        ),
        description="Internal knowledge only — no external lookups",
    ),
    IntensityLevel(
        name="Moderate",
        ideal_palette=["brave_search", "answerer"],
        directive=(
            "Perform one or two web searches to gather up-to-date information, "
            "then synthesise a direct answer."
        ),
        description="Single web search pass + answer",
    ),
    IntensityLevel(
        name="Hard",
        ideal_palette=["brave_search", "url", "url_reviewer", "answerer"],
        directive=(
            "Use multiple searches across different angles and fetch specific URLs "
            "for detail. Do not rely on internal knowledge."
        ),
        description="Multi-search + URL fetching",
    ),
    IntensityLevel(
        name="Expert",
        ideal_palette=[
            "brave_search", "url", "url_reviewer",
            "sql", "document_retriever", "reviewer", "answerer",
        ],
        directive=(
            "Cross-reference multiple information sources: web search, local documents, "
            "and structured databases. Use a reviewer to validate intermediate results "
            "before synthesising."
        ),
        description="Multi-source cross-referencing with intermediate validation",
    ),
    IntensityLevel(
        name="Elite",
        ideal_palette=[
            "brave_search", "url", "url_reviewer",
            "sql", "document_retriever", "reviewer",
            "numerical_sequences", "visualization", "answerer",
        ],
        directive=(
            "Build a multi-branch DAG with parallel information-gathering paths. "
            "Include quantitative analysis or visualisation where relevant. "
            "All branches must converge into a final synthesised answer."
        ),
        description="Parallel branches with quantitative analysis and visualisation",
    ),
    IntensityLevel(
        name="Master",
        ideal_palette=[
            "brave_search", "url", "url_reviewer",
            "sql", "document_retriever", "reviewer",
            "numerical_sequences", "visualization",
            "bash", "mle", "code_edit", "tool", "answerer",
        ],
        directive=(
            "Use any combination of agents. Computation, code generation, machine learning, "
            "and external tool calls are all available. Build the most thorough plan possible."
        ),
        description="Full agent set — unconstrained",
    ),
]
