# Web Search Agent

A self-contained agent that uses BrowserOS browser automation and a local LLM to perform web searches and information retrieval from natural language prompts.

## Features

- Accepts natural language prompts
- Uses local LLM (Ollama) to interpret and generate search queries
- Automates web browsing using BrowserOS via Playwright CDP connection
- Synthesizes responses using the local LLM

## Prerequisites

- Python 3.11+
- BrowserOS installed and running with CDP enabled
- Ollama installed and running with llama3.2 model
- **CRITICAL**: Ollama must be configured for CPU-only mode to prevent GPU memory conflicts
- Conda (for environment management)

## Setup

1. Download BrowserOS AppImage:

   ```bash
   wget -O BrowserOS.AppImage https://files.browseros.com/download/BrowserOS.AppImage
   chmod +x BrowserOS.AppImage
   ```

2. Install Ollama and pull the model:

   ```bash
   # Install Ollama if not already installed
   curl -fsSL https://ollama.ai/install.sh | sh
   ollama pull llama3.2
   ```

3. Create conda environment:

   ```bash
   conda env create -f environment.yml
   conda activate web_search_agent-env
   ```

4. Install Playwright browsers:

   ```bash
   playwright install
   ```

5. Run the agent:

   ```bash
   python main.py
   ```

The agent will automatically start BrowserOS when needed if it's not already running.

## Monitoring & Troubleshooting

Use the included monitoring script to check resource usage:

```bash
# Monitor resources in real-time
python monitor_resources.py

# Force cleanup of BrowserOS processes
python monitor_resources.py cleanup
```

### Common Issues

- **Hardware crashes**: Check GPU memory usage with `nvidia-smi`
- **BrowserOS not starting**: Ensure `--no-sandbox` flag is working
- **Memory issues**: Monitor with `python monitor_resources.py`
- **Multiple processes**: Use cleanup command to remove orphaned processes

## Usage

The agent exposes a FastMCP tool `web_search_info` that takes a natural language prompt and returns synthesized information from web searches.

Example prompt: "What are the latest developments in AI safety?"

## Configuration

- `AGENT_PORT`: Port to run the server (default: 9502)
- `AGENT_HOST`: Host to bind (default: 127.0.0.1)
- CDP URL: Currently hardcoded to `http://127.0.0.1:9222` - adjust if BrowserOS uses different CDP endpoint

## Architecture

- **Prompt Processing**: Ollama generates search queries from natural language
- **Web Search**: Playwright connects to BrowserOS CDP for browser automation
- **Data Extraction**: Extracts search results from DuckDuckGo
- **Response Synthesis**: Ollama synthesizes final response from extracted data

## MCP-driven Plan Flow (new)

- The agent now prefers a BrowserOS MCP-driven flow where the LLM returns a structured JSON action plan.
- Flow: LLM -> JSON action plan -> BrowserOS MCP `plan` endpoint -> BrowserOS executes actions and returns extracted data -> Agent synthesizes final response.
- The agent validates the JSON plan and will fall back to the existing CDP/Playwright search flow if the plan cannot be parsed or execution fails.

### Local MCP (preferred)

- The default integration prefers direct local MCP HTTP calls to a BrowserOS MCP server (default base URL: `http://127.0.0.1:9225/mcp`).
- Klavis gateway support remains available in the client but is disabled by default to keep the stack self-hosted and avoid 3rd-party API keys/costs.

### What changed (summary)

- New client wrapper: `web_search_agent/browseros_client.py` — supports direct MCP and optional Klavis adapter. Default is direct-MCP (self-hosted).
- Executor refactor: `web_search_agent/executor.py` — `validate_plan()` and `execute_plan()` (step-by-step execution).
- Robust execution: per-action retries, exponential backoff, artifact (screenshot) capture on failure, stop-on-error behavior.
- Tests: unit tests and an integration test with a lightweight mock MCP server under `web_search_agent/tests/`.

### Files added/modified

- `web_search_agent/browseros_client.py` — BrowserOS MCP client (direct MCP default, Klavis optional).
- `web_search_agent/executor.py` — Plan validation and executor helpers.
- `web_search_agent/main.py` — Uses LLM to request JSON action plans and calls the executor; falls back to Playwright/CDP search flow on errors.
- `web_search_agent/tests/` — unit tests and `mock_mcp_server.py` for integration testing.

### Executor API & behavior

#### validate_plan(plan: List[Dict]) -> List[Dict]

Validates that the LLM output is a list of action objects and that each action uses an allowed action name.

#### execute_plan(plan: List[Dict], client, stop_on_error: bool = True) -> Dict

Executes the provided plan using `client.send_action(action)` for each action in order.

Key behavior:

- Per-action options supported in the action dict:
  - `retries` (int): number of retry attempts (default 2).
  - `backoff` (float): base backoff seconds (default 0.5).
  - `session_id` (str): optional identifier used to request screenshots/artifacts from the client.
- On transient failure the executor retries with exponential backoff.
- When an action fails the executor will attempt best-effort artifact capture via `client.get_screenshot(session_id)` and include a base64-encoded screenshot in the outputs for diagnostics.
- The executor returns a dict of the form: `{ "executed": N, "outputs": [ {action, result, artifact_screenshot_base64?}, ... ] }`.

### Sample LLM prompt and plan

Prompt to LLM (example):

```text
You are an assistant that outputs a JSON array of browser actions to perform. Only return valid JSON.
Allowed actions: goto, wait, click, fill, press, extract, extract_list, eval_js, screenshot.
Limit plan length to 12 actions.
Task: produce an action plan to find authoritative information and extract key content to answer: [USER_PROMPT]
```

Example plan (JSON):

```json
[
   {"action": "goto", "value": "https://duckduckgo.com"},
   {"action": "fill", "selector": "input[name=q]", "value": "latest AI safety research"},
   {"action": "press", "selector": "input[name=q]", "value": "Enter"},
   {"action": "wait", "value": 3000},
   {"action": "extract_list", "selector": "a.result__a", "limit": 5}
]
```

The agent will validate this plan, execute it step-by-step through the MCP client, and synthesize the results using the local LLM.

### Running the agent (dev)

Ensure BrowserOS AppImage is present and executable and Ollama is installed for the local LLM. Then:

```bash
conda activate news-research-agent-env
python web-search-agent/main.py
```

### Running unit and integration tests

Install pytest and run the tests (mock MCP server will be used by integration tests):

```bash
conda activate news-research-agent-env
pip install -U pytest
pytest -q web_search_agent/tests
```

Note:

- The integration tests spin up a lightweight mock MCP HTTP server on an ephemeral port and exercise the direct-MCP client behavior. They don't require real BrowserOS or Klavis.

- If you run tests in CI, ensure the repository root is on PYTHONPATH so imports like `web_search_agent` resolve.

### Environment variables & configuration

- `AGENT_PORT` (default 9502) — control FastMCP host port.
- `AGENT_HOST` (default 127.0.0.1) — control FastMCP host.
- `KLAVIS_API_KEY` — if you choose to route through Klavis (disabled by default). If set, you can create a client with `BrowserOSClient(use_klavis=True)`.
- BrowserOS MCP base URL: default `http://127.0.0.1:9225/mcp`. You can override by passing `base_url` to `BrowserOSClient`.

### Artifacts & diagnostics

- Executor currently returns base64-encoded screenshots in outputs when available. For production, consider storing artifacts to disk or object storage and returning URLs instead of large base64 blobs.

### CI recommendation (quick)

Add a GitHub Actions job that:

- Sets up Python 3.11

- Installs dependencies from environment.yml or pip

- Runs `pytest -q web-search-agent/tests`

Example (workflow snippet):

```yaml
jobs:
   test:
      runs-on: ubuntu-latest
      steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v4
            with:
               python-version: '3.11'
         - run: python -m pip install -U pip
         - run: pip install pytest
         - run: pytest -q web_search_agent/tests
```


This approach keeps the model in control of browsing strategy while the agent enforces validation, retries, and observability.



## Resource Management & Cleanup

The agent includes robust resource management to prevent hardware crashes:

- **Process Tracking**: Single BrowserOS instance with global process tracking
- **Memory Monitoring**: Automatic monitoring of BrowserOS memory usage (2GB limit)
- **Connection Limiting**: Maximum 3 concurrent browser connections
- **Graceful Cleanup**: Automatic cleanup on shutdown, errors, and high memory usage
- **System Resource Checks**: Validates available memory before operations
- **Signal Handling**: Proper shutdown on SIGTERM/SIGINT signals
- **GPU Safety**: Ollama forced to CPU-only mode to prevent GPU memory conflicts

### GPU/CPU Configuration

**CRITICAL FOR HARDWARE STABILITY**: The agent forces Ollama to use CPU-only mode to prevent GPU memory conflicts with BrowserOS:

- Environment variables: `OLLAMA_GPU_LAYERS=0`, `OLLAMA_NUM_GPU=0`
- All Ollama calls include `options={'num_gpu': 0}`
- This prevents the 2GB Llama model from loading into GPU VRAM
- BrowserOS handles web rendering on GPU, Ollama uses CPU for text processing

### Memory Management Flags

BrowserOS is started with memory optimization flags:

- `--max_old_space_size=4096`: Limits V8 heap to 4GB
- `--memory-pressure-off`: Reduces memory pressure handling overhead
- `--disable-dev-shm-usage`: Uses disk for shared memory instead of RAM

### Cleanup Behavior

- BrowserOS processes are tracked globally and cleaned up on exit
- Failed connections trigger cleanup attempts
- High memory usage (>1.5GB) triggers warnings and potential restarts
- All browser contexts and pages are explicitly closed after use
