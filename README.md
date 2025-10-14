# News Research Agent

This MCP server (news-research-agent) crawls the top news articles from configured sources and stores them in the production `justnews` PostgreSQL 18 cluster. It is fully MCP SDK conformant and exposes its tools via FastMCP.

## Features

- Uses crawl4ai to fetch current top news articles.
- Normalizes output with canonical URLs, provenance metadata, and persists into `public.articles` and `public.article_source_map`.
- Optionally generates GPU-backed embeddings (pgvector) with guarded memory allocation.
- Emits Prometheus instrumentation for ingestion throughput, failures, and latency.
- Designed for integration in multi-agent workflows and exposed via FastMCP.

## Setup (Conda/MCP SDK)

1. **Create and activate the conda environment:**

   ```bash
   conda env update -f environment.yml --prune
   conda activate news-research-agent-env
   ```

2. **Provide database credentials:**

   ```bash
   export JUSTNEWS_DB_PASSWORD="<production-password>"
   ```

   Alternatively, run `./setup_env.sh` to generate a reusable environment file and
   source it before startup.

3. **Run the agent:**

   ```bash
   python main.py
   ```

4. **Register this agent in your MCP client (e.g., VS Code) as a stdio MCP server.**

---

## MCP SDK Best Practices

- Uses `FastMCP` and `app.tool()` for tool registration.
- Tool schemas are defined by function signatures and docstrings (no ToolInput/ToolOutput).
- All dependencies (except MCP) are installed via the provided conda environment for reliability and reproducibility.

## Configuration

The agent loads configuration values from the following sources (highest precedence first):

1. Environment variables.
2. `config.json` (optional, same directory).
3. Dataclass defaults.

Key environment variables:

| Variable | Description | Default |
| --- | --- | --- |
| `JUSTNEWS_DB_PASSWORD` | Required password for the `justnews_user` role. Use `./setup_env.sh` to generate/store securely. | _None (required)_ |
| `JUSTNEWS_DB_HOST` | Database host. | `localhost` |
| `JUSTNEWS_DB_PORT` | Database port. | `5432` |
| `JUSTNEWS_DB_NAME` | Database name. | `justnews` |
| `JUSTNEWS_DB_USER` | Database user. | `justnews_user` |
| `NEWS_SOURCE_BATCH_SIZE` | Number of sources fetched per batch. | `5` |
| `NEWS_CRAWL_PARALLELISM` | Concurrent crawl jobs. | `1` |
| `NEWS_CRAWL_TIMEOUT_SECONDS` | Timeout per crawl (seconds). | `120` |
| `NEWS_MAX_SOURCE_FAILURES` | Max tolerated failures before abort. | `5` |
| `NEWS_EMBEDDING_ENABLED` | Toggle embedding updates. | `true` |
| `NEWS_EMBEDDING_MODEL` | Sentence-transformers model id. | `sentence-transformers/all-mpnet-base-v2` |
| `NEWS_EMBEDDING_BATCH` | Embedding batch size. | `8` |
| `NEWS_EMBEDDING_GPU_FRACTION` | GPU memory fraction cap. | `0.65` |
| `NEWS_LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, etc.). | `INFO` |

See `agent_config.py` for comprehensive defaults and type validation.

## Pipeline Overview

1. Fetch a batch of candidate sources from `public.sources`.
2. Crawl each source asynchronously (respecting configured parallelism and timeouts) via `crawl4ai`.
3. Normalize article payloads, ensuring canonical URLs, provenance metadata, and duplicate detection against `public.articles`.
4. Persist new articles and provenance rows (`public.article_source_map`) with automatic recovery on transient failures.
5. Optionally generate vector embeddings on GPU, honoring the configured memory ceiling, and mark articles as analyzed.
6. Emit Prometheus metrics throughout ingestion for observability.

## Operational Runbook

- **Mandatory credentials**: set `JUSTNEWS_DB_PASSWORD` before boot. Other connection overrides may be supplied via environment or `config.json`.
- **GPU embeddings**: install `torch` and `sentence-transformers` (see `requirements.txt`) to enable embeddings. Without them the agent degrades gracefully.
- **Health endpoints**: `/health` returns `ok`; `/shutdown` triggers a graceful exit.
- **Metrics**: Prometheus exported on `:9601` (configurable in `main.py`). Key counters: `research_articles_stored_total`, `research_sources_failed_total`, `research_embedding_failures_total`.
- **Failure handling**: ingestion aborts once `NEWS_MAX_SOURCE_FAILURES` is exceeded; review logs for the offending source URLs.
- **Reference docs**: local reference material should be stored beneath `./reference/` (ignored by git).

## Extending

- Adjust the PostgreSQL connection string in `main.py` as needed.
- Add more tools or logic for advanced research workflows.
- Extend `agent_config.py` with new typed configuration values and reference them in `main.py`.
- For custom GPU models, override `NEWS_EMBEDDING_MODEL` and adjust batch size/memory fraction accordingly.

## License

MIT
