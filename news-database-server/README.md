# News Database MCP Server

This standalone MCP server manages a PostgreSQL database for storing news articles, metadata, and analysis results (bias, sentiment, vectors, etc). It is designed for extensibility and vector search using the pgvector extension. It is fully MCP SDK conformant and exposes its tools via FastMCP.

## Features

- Stores news articles, metadata, and analysis results (bias, sentiment, etc).
- Supports vector storage and search via pgvector.
- Extensible schema for future analysis fields.
- Exposes MCP tools for inserting and querying articles.

## Setup (Conda/MCP SDK)

1. **Install PostgreSQL and pgvector:**

   - On Ubuntu:

     ```bash
     sudo apt-get install postgresql postgresql-contrib
     sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS vector;"
     ```

   - Or see: https://github.com/pgvector/pgvector#installation

2. **Create and activate the conda environment:**

   ```bash
   conda env update -f environment.yml --prune
   conda activate news-database-server-env
   conda install numpy psycopg prometheus_client
   conda run -n news-database-server-env pip install "mcp[cli]"  # Only if MCP is not available via conda
   ```

3. **Run the server:**

   ```bash
   python main.py
   ```

   - Prometheus metrics will be available at http://localhost:8004/metrics

4. **Register this agent in your MCP client (e.g., VS Code) as a stdio MCP server.**

---

## MCP SDK Best Practices

- Uses `FastMCP` and `@mcp.tool()` decorators for tool registration.
- Tool schemas are defined by function signatures and docstrings (no ToolInput/ToolOutput).
- All dependencies (except MCP) are installed via conda for maximum reliability.

## Extending

- Add new columns to the schema for additional analysis fields.
- Implement more advanced vector search and retrieval tools.
