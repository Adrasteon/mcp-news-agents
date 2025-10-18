"""Typed configuration loader for the news research agent."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

_DEFAULT_CONFIG_PATH = "config.json"


@dataclass(eq=True)
class AgentConfig:
    """Runtime configuration values for the research ingestion pipeline."""

    source_batch_size: int = 5
    crawl_parallelism: int = 1
    crawl_timeout_seconds: int = 120
    max_source_failures: int = 5000
    articles_per_source: int = 50

    embedding_enabled: bool = True
    embedding_model: str = "sentence-transformers/all-mpnet-base-v2"
    embedding_batch_size: int = 8
    embedding_gpu_fraction: float = 0.65
    embedding_min_gpu_free_mb: int = 1024

    orchestrator_url: str = "http://127.0.0.1:9508"
    memory_agent_url: str = "http://127.0.0.1:9507"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "justnews"
    db_user: str = "justnews_user"


def _load_config_file(path: str) -> Dict[str, Any]:
    if not path or not os.path.isfile(path):
        return {}

    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError(f"Configuration file '{path}' must contain a JSON object.")

    return payload


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


def load_config(path: Optional[str] = None) -> AgentConfig:
    """Load configuration from JSON + environment overrides.

    Priority order (highest precedence first):
    1. Dedicated environment variables.
    2. Values in the JSON config file.
    3. Dataclass defaults.
    """

    config_path = path or os.getenv("NEWS_AGENT_CONFIG_PATH", _DEFAULT_CONFIG_PATH)
    data = _load_config_file(config_path)

    cfg = AgentConfig()

    # File-level overrides
    if data:
        cfg.source_batch_size = int(data.get("source_batch_size", cfg.source_batch_size))
        cfg.crawl_parallelism = int(data.get("crawl_parallelism", cfg.crawl_parallelism))
        cfg.crawl_timeout_seconds = int(data.get("crawl_timeout_seconds", cfg.crawl_timeout_seconds))
        cfg.max_source_failures = int(data.get("max_source_failures", cfg.max_source_failures))
        cfg.articles_per_source = int(data.get("articles_per_source", cfg.articles_per_source))

        cfg.embedding_enabled = bool(data.get("embedding_enabled", cfg.embedding_enabled))
        cfg.embedding_model = str(data.get("embedding_model", cfg.embedding_model))
        cfg.embedding_batch_size = int(data.get("embedding_batch_size", cfg.embedding_batch_size))
        cfg.embedding_gpu_fraction = float(data.get("embedding_gpu_fraction", cfg.embedding_gpu_fraction))
        cfg.embedding_min_gpu_free_mb = int(data.get("embedding_min_gpu_free_mb", cfg.embedding_min_gpu_free_mb))

        cfg.orchestrator_url = str(data.get("orchestrator_url", cfg.orchestrator_url))
        cfg.memory_agent_url = str(data.get("memory_agent_url", cfg.memory_agent_url))

        cfg.db_host = str(data.get("db_host", cfg.db_host))
        cfg.db_port = int(data.get("db_port", cfg.db_port))
        cfg.db_name = str(data.get("db_name", cfg.db_name))
        cfg.db_user = str(data.get("db_user", cfg.db_user))

    # Environment overrides
    cfg.source_batch_size = _env_int("NEWS_SOURCE_BATCH_SIZE", cfg.source_batch_size)
    cfg.crawl_parallelism = max(1, _env_int("NEWS_CRAWL_PARALLELISM", cfg.crawl_parallelism))
    cfg.crawl_timeout_seconds = _env_int("NEWS_CRAWL_TIMEOUT_SECONDS", cfg.crawl_timeout_seconds)
    cfg.max_source_failures = _env_int("NEWS_MAX_SOURCE_FAILURES", cfg.max_source_failures)
    cfg.articles_per_source = _env_int("NEWS_ARTICLES_PER_SOURCE", cfg.articles_per_source)

    cfg.embedding_enabled = _env_bool("NEWS_EMBEDDING_ENABLED", cfg.embedding_enabled)
    cfg.embedding_model = os.getenv("NEWS_EMBEDDING_MODEL", cfg.embedding_model)
    cfg.embedding_batch_size = _env_int("NEWS_EMBEDDING_BATCH", cfg.embedding_batch_size)
    cfg.embedding_gpu_fraction = _env_float("NEWS_EMBEDDING_GPU_FRACTION", cfg.embedding_gpu_fraction)
    cfg.embedding_min_gpu_free_mb = _env_int("NEWS_EMBEDDING_MIN_GPU_FREE_MB", cfg.embedding_min_gpu_free_mb)

    cfg.orchestrator_url = os.getenv("NEWS_ORCHESTRATOR_URL", cfg.orchestrator_url)
    cfg.memory_agent_url = os.getenv("NEWS_MEMORY_AGENT_URL", cfg.memory_agent_url)

    cfg.db_host = os.getenv("JUSTNEWS_DB_HOST", cfg.db_host)
    cfg.db_port = _env_int("JUSTNEWS_DB_PORT", cfg.db_port)
    cfg.db_name = os.getenv("JUSTNEWS_DB_NAME", cfg.db_name)
    cfg.db_user = os.getenv("JUSTNEWS_DB_USER", cfg.db_user)

    return cfg


__all__ = ["AgentConfig", "load_config"]
