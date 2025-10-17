
# News Analyzer MCP Agent

This standalone MCP server analyzes news articles for bias, sentiment, entities, persuasion, and more using local AI models.

## Features

- Accepts article text and metadata as input.
- Returns analysis including bias, sentiment, named entities, and persuasion techniques.
- Designed for local, private, and fast operation.

## Setup (Conda)

1. Create the conda environment (if not already created):

   ```bash
   conda env create -f environment.yml
   ```

   Or, to update an existing environment:

   ```bash
   conda env update -f environment.yml --prune
   ```

2. Activate the environment:

   ```bash
   conda activate news-analyzer-agent-env
   ```

3. Install additional dependencies (if not present):

   ```bash
   conda install -c conda-forge spacy textblob
   conda run -n news-analyzer-agent-env pip install mcp fastmcp
   ```

4. (Optional) Download the spaCy English model (may fail in some conda environments):

   ```bash
   conda run -n news-analyzer-agent-env python -m spacy download en_core_web_sm
   ```

   **Known Issue:** In some conda environments, the spaCy model install may fail due to a Typer/Click incompatibility. If this occurs, see [spaCy GitHub issues](https://github.com/explosion/spaCy/issues) for workarounds, or install the model in a clean environment.

5. Configure any additional settings in `main.py` as needed.

## Usage

Run the MCP server (FastMCP):

```bash
conda activate news-analyzer-agent-env
python main.py
```

This agent now uses the [FastMCP](https://github.com/modelcontext/fastmcp) server and exposes its tools via the MCP SDK. Entry point is `main.py`.

## Integration

- Register this agent in your MCP client (e.g., VS Code) as a stdio MCP server.

---

## Extending

- Swap out or add models for more advanced analysis.
- Integrate with other MCP servers for multi-agent workflows.
