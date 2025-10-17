# News Editor Agent

This MCP server (news-editor-agent) uses the new article and data accumulated by the agents to edit, approve, and publish the article to the system's website. It ensures all attributions and links to original articles are included, along with any other relevant data. It is fully MCP SDK conformant and exposes its tools via FastMCP.

## Features

- Edits and approves new articles
- Publishes articles to the system website
- Includes all attributions and links to sources
- Integrates additional relevant data from agents
- Exposes MCP tools via FastMCP

## Setup (Conda/MCP SDK)

1. **Create and activate the conda environment:**

   ```bash
   conda env update -f environment.yml --prune
   conda activate news-editor-agent-env
   conda run -n news-editor-agent-env pip install mcp fastmcp
   ```

2. Configure any additional settings in `main.py` as needed.

## Usage

Run the MCP server (FastMCP):

```bash
conda activate news-editor-agent-env
python main.py
```

---

## Integration

- Consumes new articles and agent data
- Publishes to the system website

## License

MIT
