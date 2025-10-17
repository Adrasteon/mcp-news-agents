# News Memory Agent

This MCP server (news-memory-agent) is AI-driven and controls/allocates system resources, including the GPU, to ensure all agents have the resources needed without bottlenecks, OOM events, or instability. It is fully MCP SDK conformant and exposes its tools via FastMCP.

## Features

- Monitors and manages system resources (CPU, GPU, RAM)
- Allocates resources to agents as needed
- Prevents bottlenecks and OOM/system instability
- Exposes MCP tools via FastMCP

## Setup (Conda/MCP SDK)

1. **Create and activate the conda environment:**

   ```bash
   conda env update -f environment.yml --prune
   conda activate news-memory-agent-env
   conda install -c conda-forge psutil pynvml
   conda run -n news-memory-agent-env pip install mcp fastmcp
   ```

2. Configure any additional settings in `main.py` as needed.

## Usage

Run the MCP server (FastMCP):

```bash
conda activate news-memory-agent-env
python main.py
```

---

## Integration

- Works with the orchestrator agent to optimize workflow
- Allocates resources to all agents

## License

MIT
