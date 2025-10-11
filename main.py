import logging
from mcp.server import Server, Tool
from mcp.types import ToolInput, ToolOutput
import asyncio
from typing import List, Dict, Any
from crawl4ai import crawl
import psycopg
from prometheus_client import start_http_server, Counter, Gauge

# Metrics
REQUESTS = Counter('requests_total', 'Total requests')
AGENT_STATUS = Gauge('agent_status', 'Status of the agent (1=up, 0=down)')

# Configure logging to stderr (never stdout for MCP servers)
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

class CrawlNewsInput(ToolInput):
    pass

class CrawlNewsOutput(ToolOutput):
    articles: List[Dict[str, Any]]

async def store_articles_in_pg(articles: List[Dict[str, Any]]):
    conn_str = "postgresql://postgres:postgres@localhost:5432/newsdb"
    async with await psycopg.AsyncConnection.connect(conn_str) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS news_articles (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    metadata JSONB
                )
            """)
            for article in articles:
                await cur.execute(
                    """
                    INSERT INTO news_articles (title, content, metadata)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (title) DO NOTHING
                    """,
                    (article["title"], article["text"], article["metadata"])
                )
        await conn.commit()

def crawl_news(_: CrawlNewsInput) -> CrawlNewsOutput:
    try:
        results = crawl(
            query="top news",
            max_results=10,
            include_text=True,
            include_metadata=True,
            sources=["news"]
        )
        articles = []
        for r in results:
            articles.append({
                "title": r.get("title"),
                "text": r.get("text"),
                "metadata": r.get("metadata", {})
            })
        asyncio.create_task(store_articles_in_pg(articles))
        return CrawlNewsOutput(articles=articles)
    except Exception as e:
        logging.error(f"Failed to crawl or store news: {e}")
        return CrawlNewsOutput(articles=[])

server = Server(
    name="crawler-agent",
    version="1.0.0",
    tools=[
        Tool(
            name="crawl_top_news",
            description="Find the current top 10 news articles from major news websites and store them in a local vector database MCP server.",
            input_model=CrawlNewsInput,
            output_model=CrawlNewsOutput,
            callback=crawl_news,
        ),
    ],
)

if __name__ == "__main__":
    start_http_server(8001)  # Expose metrics on port 8001
    AGENT_STATUS.set(1)
    main()
