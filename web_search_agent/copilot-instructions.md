# Web Search Agent Copilot Instructions

This agent performs web searches and information retrieval using BrowserOS browser automation and a local LLM.

## Key Components

- **BrowserOS Integration**: Connects to BrowserOS via Chrome DevTools Protocol (CDP) for browser automation
- **Local LLM**: Integrates with Ollama for prompt processing and response synthesis
- **Playwright**: Uses Playwright for CDP connection and web automation
- **FastMCP**: Exposes tools via MCP protocol for seamless integration

## Development Guidelines

- Ensure BrowserOS is installed and running with CDP enabled before testing
- Verify Ollama is running with the llama3.2 model
- Test CDP connection URL (currently hardcoded to 127.0.0.1:9222)
- Handle connection errors gracefully when BrowserOS is not available
- Optimize LLM calls for efficiency and relevance

## Best Practices

- Use async operations for browser interactions to avoid blocking
- Validate CDP connection before performing searches
- Log search queries, browser actions, and results for debugging
- Implement retry logic for transient connection issues
- Consider fallback to local browser if BrowserOS is unavailable

## Architecture Notes

- Prompt → Ollama query generation → Playwright CDP to BrowserOS → Google search → Result extraction → Ollama synthesis → Response
- CDP connection allows full browser control through BrowserOS
- Agent remains self-contained but requires external BrowserOS instance
- Can be extended to use BrowserOS MCP tools for more advanced automation