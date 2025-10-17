# Model Store Alignment (MCP Agents)

This repository now uses per-agent model directories that match the MCP agent names (e.g. `news-cleaner-agent`). The legacy JustNewsAgent names (e.g. `synthesizer`) remain as symbolic links for backward compatibility, so any tooling that still expects the old layout will continue to work.

## Directory Mapping

| Legacy name       | MCP agent directory      |
|-------------------|--------------------------|
| `analyst`         | `news-analyzer-agent`    |
| `archive_storage` | `news-database-server`   |
| `balancer`        | `news-cluster-agent`     |
| `chief_editor`    | `news-editor-agent`      |
| `critic`          | `news-training-agent`    |
| `fact_checker`    | `news-factcheck-agent`   |
| `memory`          | `news-memory-agent`      |
| `scout`           | `news-research-agent`    |
| `synthesizer`     | `news-cleaner-agent`     |

Additional empty directories now exist for agents that currently have no stored artifacts (for example `news-orchestrator-agent`).

Each agent directory follows the existing atomic pattern:

```text
model_store/<agent>/
  current -> v1
  v1/
    manifest.json
    models--<org>--<model-id>/
```

The `current` symlinks were updated to be relative (`current -> v1`) to avoid future breakage during directory moves. This makes it safe to relocate or rename agent directories without rewriting absolute paths.

## Maintenance Notes

- When publishing a new model version for an agent, continue to stage it under `versions/<tag>` or the existing `vN` pattern and update `current` atomically.
- Tooling or scripts that still reference the legacy names (such as `model_store/analyst`) will transparently resolve to the new directories via symlink.
- To add a new MCP agent, create `model_store/<agent-name>/` and manage versions exactly as shown above. Add a compatibility symlink only if a legacy name must be preserved.
