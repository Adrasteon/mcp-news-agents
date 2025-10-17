# News Training Agent

This MCP server (news-training-agent) aggregates outputs from all other agents to generate and refine AI model training data. It is now fully MCP SDK conformant and exposes its tools via FastMCP.


## Features

- Aggregates outputs from all other agents
- Generates training/refinement datasets
- Refines and updates AI models in the system
- Exposes MCP tools via FastMCP


## Setup (Conda/MCP SDK)

1. **Create and activate the conda environment:**

   ```bash
   conda env update -f environment.yml --prune
   conda activate news-training-agent-env
   ```

2. **Run the agent:**

   ```bash
   python main.py
   ```

3. **Register this agent in your MCP client (e.g., VS Code) as a stdio MCP server.**

---


## MCP SDK Best Practices

- Uses `FastMCP` and `@mcp.tool()` decorators for tool registration.
- Tool schemas are defined by function signatures and docstrings (no ToolInput/ToolOutput).
- All dependencies (except MCP) are installed via conda for maximum reliability.


## Integration

- Consumes outputs from all other agents
- Updates/refines models used by the system


## License

MIT
