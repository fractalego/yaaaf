import os
from typing import List

from pydantic_settings import BaseSettings


class ClientSettings(BaseSettings):
    model: str | None = None
    temperature: float = 0.5
    max_tokens: int = 1024
    host: str = "http://localhost:11434"


class SourceSettings(BaseSettings):
    name: str | None = None
    type: str | None = None
    path: str | None = None
    description: str | None = None


class SafetyFilterSettings(BaseSettings):
    enabled: bool = False
    blocked_keywords: List[str] = []
    blocked_patterns: List[str] = []
    custom_message: str = "I cannot answer that"


class APISettings(BaseSettings):
    brave_search_api_key: str | None = None


class AgentSettings(BaseSettings):
    name: str
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    host: str | None = None


class Settings(BaseSettings):
    client: ClientSettings
    sources: List[SourceSettings] = []
    agents: List[str | AgentSettings] = []
    safety_filter: SafetyFilterSettings = SafetyFilterSettings()
    api_keys: APISettings = APISettings()


def _get_simple_config() -> Settings:
    client_settings: ClientSettings = ClientSettings(
        model="qwen2.5:32b",
        temperature=0.7,
        max_tokens=100,
    )
    safety_filter_settings: SafetyFilterSettings = SafetyFilterSettings(
        enabled=True,
        blocked_keywords=[
            "harmful",
            "dangerous",
            "illegal",
            "violence",
            "weapon",
        ],
        blocked_patterns=[
            "how to .*? (hack|break|crack)",
            "create.*?(virus|malware)",
            "bypass.*?(security|safety)",
        ],
        custom_message="I cannot answer that <taskcompleted/>",
    )
    api_settings: APISettings = APISettings(brave_search_api_key=None)
    config: Settings = Settings(
        client=client_settings,
        sources=[],
        agents=[
            "reflection",
            "visualization",
            "sql",
            "reviewer",
            "websearch",
            "url_reviewer",
            "user_input",
            "url",
        ],
        safety_filter=safety_filter_settings,
        api_keys=api_settings,
    )
    return config


def get_config() -> Settings:
    """
    Returns the default configuration for the orchestrator.
    unless an environment variable `YAAF_CONFIG` is set to a different configuration json file.
    If so, Load that configuration file and return it.
    """
    if os.environ.get("YAAF_CONFIG"):
        config_path = os.environ["YAAF_CONFIG"]
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Configuration file '{config_path}' does not exist."
            )
        return Settings.model_validate_json(open(config_path).read())

    return _get_simple_config()
