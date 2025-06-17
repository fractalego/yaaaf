import os
from typing import List

from pydantic_settings import BaseSettings


class ClientSettings(BaseSettings):
    model: str | None = None
    temperature: float = 0.5
    max_tokens: int = 1024


class SourceSettings(BaseSettings):
    name: str | None = None
    type: str | None = None
    path: str | None = None


class Settings(BaseSettings):
    client: ClientSettings
    sources: List[SourceSettings] = []
    agents: List[str] = []


def _get_simple_config() -> Settings:
    client_settings: ClientSettings = ClientSettings(
        model="qwen2.5:32b",
        temperature=0.7,
        max_tokens=100,
    )
    config: Settings = Settings(
        client=client_settings,
        sources=[],
        agents=["reflection", "visualization", "sql", "reviewer", "websearch", "url_reviewer"],
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
            raise FileNotFoundError(f"Configuration file '{config_path}' does not exist.")
        return Settings.model_validate_json(open(config_path).read())

    return _get_simple_config()