# Canonical Port Map for MCP News Agents

This document defines the canonical (default) port assignments for all MCP servers/agents in this project. Each agent/server should be configured to use its assigned port for robust isolation and predictable orchestration. Ports start at 9500 to avoid common conflicts.

| Agent/Server Name           | Canonical Port |
|----------------------------|:-------------:|
| news-analyzer-agent        | 9500          |
| news-research-agent        | 9501          |
| news-database-server       | 9502          |
| news-cluster-agent         | 9503          |
| news-cleaner-agent         | 9504          |
| news-factcheck-agent       | 9505          |
| news-editor-agent          | 9506          |
| news-memory-agent          | 9507          |
| news-orchestrator-agent    | 9508          |
| news-training-agent        | 9509          |
| news-admin-client          | 9510          |

**Notes:**
- Each agent/server should default to its assigned port in code/config, but may allow override via environment variable or CLI argument for dev/test.
- This map should be updated if new agents are added or ports are changed.
- Ports 9500-9599 are reserved for MCP news system agents in this deployment.
