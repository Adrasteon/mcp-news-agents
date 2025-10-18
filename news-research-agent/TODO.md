# Research Agent Integration TODO

- [x] Align database connectivity with the production `justnews` PostgreSQL 18 cluster using the `justnews_user` role and environment-driven credentials.
- [x] Normalize crawler output to capture canonical URL, title, summary, content, metadata, and source provenance.
- [x] Implement robust insertion logic into `public.articles` and `public.article_source_map`, including duplicate detection and conflict handling.
- [x] Build a source-driven crawl loop that batches `public.sources` records, schedules crawl jobs, and respects backoff for failed sources.
- [x] Add GPU-aware embedding job enqueueing for unanalyzed articles, ensuring deterministic memory bounds.
- [x] Emit Prometheus metrics and structured logs for ingestion throughput, failures, and latency.
- [x] Provide configuration surface (config file + env overrides) for crawl cadence, batch sizing, and parallelism.
- [x] Harden error handling and retries so that transient crawler or database failures do not crash the agent.
- [x] Document the end-to-end pipeline and provide operational runbooks.
