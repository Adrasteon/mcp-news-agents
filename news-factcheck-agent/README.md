# News FactCheck Agent

This MCP server (news-factcheck-agent) is an AI-driven fact checker for all facts in new articles, including those in quotes and statements. It is fully MCP SDK conformant and exposes its tools via FastMCP.

## Features

- Checks all facts in new articles
- Fact-checks quotes and statements
- Uses AI and external sources for verification
- Exposes MCP tools via FastMCP

## Setup (Conda/MCP SDK)

1. **Create and activate the conda environment:**

   ```bash
   conda env update -f environment.yml --prune
   conda activate news-factcheck-agent-env
   conda install transformers torch requests
   conda run -n news-factcheck-agent-env pip install "mcp[cli]"  # Only if MCP is not available via conda
   ```

## Usage

Run the MCP server:

```bash
conda activate news-factcheck-agent-env
python main.py
```

---

## MCP SDK Best Practices

- Uses `FastMCP` and `@mcp.tool()` decorators for tool registration.
- Tool schemas are defined by function signatures and docstrings (no ToolInput/ToolOutput).
- All dependencies (except MCP) are installed via conda for maximum reliability.

## License

MIT
