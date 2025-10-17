# News Cleaner Agent

This MCP server (news-cleaner-agent) uses AI to synthesize a balanced, neutral article from all variants of a story grouped by the cluster agent. It weighs each article's credibility using analysis scores, preserves attributed quotes/statements (with attribution), and ensures the final article is free from offensive or hateful content. The new article and process metrics are saved to the database.

## Features
- Receives grouped articles from the cluster agent
- Reads all variants and uses analysis scores to weigh credibility
- Preserves attributed quotes/statements with attribution
- Synthesizes a neutral, balanced article (no hate speech, racism, or offensive language)
- Saves the new article and metrics to the database


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
   conda activate news-cleaner-agent-env
   ```
3. Install additional dependencies (if not present):
   ```bash
   conda install -c conda-forge spacy textblob transformers
   conda run -n news-cleaner-agent-env pip install torch
   ```
   **Note:** If you encounter issues installing `torch` via conda, use pip as shown above.

4. (Optional) Download the spaCy English model (may fail in some conda environments):
   ```bash
   conda run -n news-cleaner-agent-env python -m spacy download en_core_web_sm
   ```
   **Known Issue:** In some conda environments, the spaCy model install may fail due to a Typer/Click incompatibility. If this occurs, see [spaCy GitHub issues](https://github.com/explosion/spaCy/issues) for workarounds, or install the model in a clean environment.

5. Configure database connection in `main.py` as needed.


## Usage
Run the MCP server (FastMCP):
```bash
conda activate news-cleaner-agent-env

# News Cleaner Agent

This MCP server (news-cleaner-agent) uses AI to synthesize a balanced, neutral article from all variants of a story grouped by the cluster agent. It weighs each article's credibility using analysis scores, preserves attributed quotes/statements (with attribution), and ensures the final article is free from offensive or hateful content. The new article and process metrics are saved to the database.

## Features

- Receives grouped articles from the cluster agent
- Reads all variants and uses analysis scores to weigh credibility
- Preserves attributed quotes/statements with attribution
- Synthesizes a neutral, balanced article (no hate speech, racism, or offensive language)
- Saves the new article and metrics to the database

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
   conda activate news-cleaner-agent-env
   ```

3. Install additional dependencies (if not present):

   ```bash
   conda install -c conda-forge spacy textblob transformers
   conda run -n news-cleaner-agent-env pip install torch
   ```

   **Note:** If you encounter issues installing `torch` via conda, use pip as shown above.

4. (Optional) Download the spaCy English model (may fail in some conda environments):

   ```bash
   conda run -n news-cleaner-agent-env python -m spacy download en_core_web_sm
   ```

   **Known Issue:** In some conda environments, the spaCy model install may fail due to a Typer/Click incompatibility. If this occurs, see [spaCy GitHub issues](https://github.com/explosion/spaCy/issues) for workarounds, or install the model in a clean environment.

5. Configure database connection in `main.py` as needed.

## Usage

Run the MCP server (FastMCP):

```bash
conda activate news-cleaner-agent-env
python main.py
```

This agent now uses the [FastMCP](https://github.com/modelcontext/fastmcp) server and exposes its tools via the MCP SDK. Entry point is `main.py`.

## Integration

- Expects input from the news-cluster-agent (grouped articles)
- Updates the news-database-server with cleaned articles and metrics

## License

MIT
