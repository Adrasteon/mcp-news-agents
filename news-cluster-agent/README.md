# News Cluster Agent

This MCP server (news-cluster-agent) uses AI to assign news articles to topic clusters. It receives analyzed articles (from the news-analyzer-agent), determines which articles belong to the same story/topic, and assigns a group story title to each cluster. The group allocation is then added to the database record for each article. It is fully MCP SDK conformant and exposes its tools via FastMCP.

## Features

- Receives analyzed news articles from the analyzer agent
- Uses AI to cluster articles by topic/story
- Assigns a group story title to each cluster
- Updates the database record for each article with its group allocation
- Exposes MCP tools via FastMCP

## Setup (Conda/MCP SDK)

1. **Create and activate the conda environment:**

   ```bash
   conda env update -f environment.yml --prune
   conda activate news-cluster-agent-env
   conda install numpy scikit-learn psycopg2-binary transformers torch
   conda run -n news-cluster-agent-env pip install "mcp[cli]"  # Only if MCP is not available via conda
   ```

2. Configure database connection in `main.py` as needed.

## Usage

Run the MCP server:

```bash
conda activate news-cluster-agent-env
python main.py
```

---

## MCP SDK Best Practices

- Uses `FastMCP` and `@mcp.tool()` decorators for tool registration.
- Tool schemas are defined by function signatures and docstrings (no ToolInput/ToolOutput).
- All dependencies (except MCP) are installed via conda for maximum reliability.

## License

MIT
