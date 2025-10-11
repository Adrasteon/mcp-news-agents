<<<<<<< HEAD
# News Research MCP Agent

This standalone MCP server crawls the top 10 news articles from major news sites and stores them in a local PostgreSQL vector database MCP server.

## Features
- Uses crawl4ai to fetch current top news articles.
- Stores article title, text, and metadata in a PostgreSQL database.
- Designed for integration in multi-agent workflows.

## Usage

1. **Create and activate a virtual environment:**
   ```bash
   uv venv
   source .venv/bin/activate
   uv add "mcp[cli]" crawl4ai psycopg[binary]
   ```

2. **Run the server:**
   ```bash
   python3 main.py
   ```

3. **Register this agent in your MCP client (e.g., VS Code) as a stdio MCP server.**

---

## Extending
- Adjust the PostgreSQL connection string in `main.py` as needed.
- Add more tools or logic for advanced research workflows.
=======
# mcp-news-agents
Multi-agent Model Context Protocol (MCP) news system with modular agents for crawling, analysis, clustering, cleaning, fact-checking, editing, orchestration, and resource management.
>>>>>>> 505356e603903c9f7db0b5a23cead989e28b9289
