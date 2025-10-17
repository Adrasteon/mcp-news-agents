# News Admin Client

This standalone MCP client provides a full-featured administrative front-end for the multi-agent news system. It can interact with all MCP servers/agents to trigger workflows, monitor metrics, resolve issues, and manage the system as a whole. This is a client, not an MCP server.

## Features

- Connects to all MCP servers/agents
- Triggers and manages agent workflows
- Monitors system and agent metrics
- Identifies and resolves issues
- Provides an administrative dashboard for the entire system

## Setup (Conda)

1. **Create and activate the conda environment:**

   ```bash
   conda env update -f environment.yml --prune
   conda activate news-admin-client-env
   ```

2. **Run the admin client:**

   ```bash
   python main.py
   ```

---

## License

MIT
