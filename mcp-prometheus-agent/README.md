# MCP Prometheus Agent

This agent runs a standalone Prometheus server to monitor all MCP agents and the admin client. It can be queried by the mcp-admin-client for real-time metrics and system health.

## Features
- Runs Prometheus as a standalone MCP monitoring agent
- Scrapes all MCP agents'/clients' `/metrics` endpoints
- Provides a central metrics store for dashboards and alerting
- Can be queried by the admin client for live data

## Setup
1. Download and extract Prometheus from https://prometheus.io/download/
2. Copy or symlink the `prometheus` binary into this directory
3. Edit `prometheus.yml` to configure scrape targets (all MCP agents/clients)
4. Start Prometheus:
   ```bash
   ./prometheus --config.file=prometheus.yml
   ```

## License
MIT
