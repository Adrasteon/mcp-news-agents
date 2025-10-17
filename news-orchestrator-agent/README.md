# News Orchestrator Agent

This MCP server (news-orchestrator-agent) is an AI-driven job control and flow manager. In tandem with the memory agent, it triggers the workflows of each agent and ensures optimal resource use and workflow efficiency. It is fully MCP SDK conformant and exposes its tools via FastMCP.

## Features

- Manages and triggers agent workflows
- Coordinates with the memory agent for resource allocation
- Maximizes overall workflow efficiency
- Exposes MCP tools via FastMCP

## Setup (Conda/MCP SDK)

1. **Create and activate the conda environment:**

   ```bash
   conda env update -f environment.yml --prune
   conda activate news-orchestrator-agent-env
   conda install -c conda-forge psutil
   conda run -n news-orchestrator-agent-env pip install mcp fastmcp
   ```

2. Configure any additional settings in `main.py` as needed.

## Usage

Run the MCP server (FastMCP):

```bash
conda activate news-orchestrator-agent-env
python main.py
```

---

## Integration

- Works with the memory agent to manage jobs and resources
- Triggers and monitors agent workflows

## License

MIT
