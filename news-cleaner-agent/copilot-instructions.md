# Copilot Instructions for news-cleaner-agent

- This agent receives grouped articles (from the news-cluster-agent) and synthesizes a new, neutral article for each group.
- It weighs each article's credibility using analysis scores, preserves attributed quotes/statements (with attribution), and ensures the final article is free from offensive or hateful content.
- The new article and process metrics are saved to the database using the news-database-server.
- The agent expects a PostgreSQL database with a `news_articles` table and a `cleaned_articles` table (or similar) for storing the new articles and metrics.
- Configure database connection via environment variables: `NEWS_DB_HOST`, `NEWS_DB_PORT`, `NEWS_DB_NAME`, `NEWS_DB_USER`, `NEWS_DB_PASS`.
- To update the cleaning or synthesis logic, edit `main.py`.
- To update dependencies, edit `requirements.txt` and run `pip install -r requirements.txt` in the `.venv`.
