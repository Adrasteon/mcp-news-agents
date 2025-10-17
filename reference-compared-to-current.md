# Mapping and Functional Summary: Reference Project vs Current MCP Agents

This document summarizes the expected functionality for each current MCP server/agent, based on a deep-dive into the reference project's documentation, catalogue, and agent design.

---
## Reference Analyst Agent: Model Handling & OOM Response

### Model Handling, OOM, and Exception Management

The analyst agent implements a robust, production-grade approach to model and GPU management, which should serve as the gold standard for all agents:

- **Orchestrator Consultation:** At startup, the agent consults the orchestrator for permission and resource allocation. If allowed, it requests a GPU and memory allocation (default ~2GB).
- **Explicit Device Management:** Sets the CUDA device explicitly and logs device/memory info at startup and before/after major operations.
- **Device-Aware Model Loading:** Loads models (sentiment, bias) using Hugging Face Transformers, with explicit device and dtype (float16) for efficiency. Uses `safetensors` for reliability. Validates that models are loaded onto the correct device.
- **Per-Agent Memory Allocation:** Requests only as much GPU memory as needed for the agent’s models. Tracks and respects per-agent memory caps.
- **Memory Circuit Breaker:** Before each operation, checks available GPU memory. If free memory drops below a safe threshold (default 1GB), disables further GPU processing and logs a warning. Resets when memory recovers.
- **Proactive Cache Management:** Calls `torch.cuda.empty_cache()` before and after model operations, and on error, to free up unused memory.
- **Critical Memory Warnings:** Logs warnings if free memory drops below 2GB, and tracks recovery.
- **Fallback Logic:** If models are not loaded, CUDA is unavailable, or the circuit breaker is active, falls back to CPU or returns `None`.
- **OOM and Exception Handling:** All GPU operations are wrapped in try/except blocks. On any exception, clears the CUDA cache, logs the error, emits a failure event, and falls back to CPU. Relies on PyTorch to raise OOM exceptions and handles all exceptions the same way, ensuring the agent does not crash and memory is reclaimed.
- **Structured Logging and Metrics:** Emits structured events and Prometheus metrics for all GPU/model operations, including failures and fallbacks.
- **Documentation and Consistency:** All model/GPU handling logic is documented and follows a consistent, maintainable pattern.

#### Analyst vs Other Reference Agents: GPU/Model Handling

| Feature/Pattern                | Analyst Agent | Other Reference Agents |
|-------------------------------|:-------------:|:---------------------:|
| Orchestrator consultation      |      Yes      |          No           |
| Explicit device management     |      Yes      |          No           |
| Per-agent memory allocation    |      Yes      |          No           |
| Model loading on device        |      Yes      |          No           |
| Memory circuit breaker         |      Yes      |          No           |
| Proactive cache clearing       |      Yes      |          No           |
| OOM/fallback handling          |      Yes      |          No           |
| Try/except for GPU ops         |      Yes      |          No           |
| Structured GPU events/logging  |      Yes      |          No           |
| CPU fallback                   |      Yes      |          No           |
| Robust error logging           |      Yes      |          No           |

---

**Summary:**

The analyst agent is designed to never crash on OOM. It proactively checks memory, clears cache, and falls back to CPU if memory is low or an error occurs. All model loading and inference is device-aware and guarded by both orchestrator policy and local circuit breakers. This methodology is unique among reference agents and should be generalized for all agents in the MCP project.

---

## Best-Practice Extraction: Cross-Agent Model/GPU Handling

To ensure robust, production-grade model and GPU management across all agents, adopt the following best practices (as exemplified by the analyst agent):

1. **Orchestrator Consultation:**
	- Always check with the orchestrator/memory agent before allocating GPU resources or loading models.

2. **Explicit Device Management:**
	- Set the CUDA device explicitly for all model operations.
	- Log device and memory info at startup and before/after major operations.

3. **Per-Agent Memory Allocation:**
	- Request only as much GPU memory as needed for the agent’s models.
	- Track and respect per-agent memory caps.

4. **Device-Aware Model Loading:**
	- Load all models onto the correct device (GPU/CPU) and dtype (e.g., float16 for efficiency).
	- Validate that models are on the intended device.

5. **Memory Circuit Breaker:**
	- Before each operation, check available GPU memory.
	- If free memory drops below a safe threshold, disable further GPU processing and log a warning.
	- Reset when memory recovers.

6. **Proactive Cache Management:**
	- Call `torch.cuda.empty_cache()` before and after model operations, and on error, to free up unused memory.

7. **OOM and Exception Handling:**
	- Wrap all GPU operations in try/except blocks.
	- On any exception, clear the CUDA cache, log the error, and fall back to CPU or safe mode.

8. **Fallback Logic:**
	- If models are not loaded, CUDA is unavailable, or the circuit breaker is active, fall back to CPU or return a safe default.

9. **Structured Logging and Metrics:**
	- Emit structured events and Prometheus metrics for all GPU/model operations, including failures and fallbacks.

10. **Documentation and Consistency:**
	 - Document all model/GPU handling logic and ensure all agents follow the same robust pattern for maintainability and reliability.

By generalizing and enforcing these practices, your MCP project will achieve high reliability, observability, and resilience to OOM and resource contention across all agents.

## 1. news-analyzer-agent
**Reference Basis:** `analyst`  
**Expected Functionality:**
- Performs sentiment analysis, bias detection, entity recognition, and persuasion technique identification on news articles.
- Uses specialized models (e.g., BERT, RoBERTa, spaCy) for high-accuracy NLP tasks.
- Provides both single and batch analysis endpoints.
- Designed for GPU acceleration and high throughput.
- Exposes health and engine info endpoints for monitoring.

---

## 2. news-research-agent (and/or news-scraper-agent)
**Reference Basis:** `crawler`, `scout`  
**Expected Functionality:**
- Crawls news websites using intelligent, multi-strategy approaches (ultra-fast, AI-enhanced, generic).
- Integrates with other agents for content analysis during crawling.
- Handles robots.txt, rate limiting, and ethical scraping.
- Provides endpoints for launching crawls, monitoring progress, and retrieving results.
- Can orchestrate multi-site, concurrent crawls with performance monitoring.

---

## 3. news-database-server
**Reference Basis:** `db_worker`, `archive`  
**Expected Functionality:**
- Manages storage and retrieval of articles, analysis results, and metadata in PostgreSQL.
- Handles schema migrations, connection pooling, and vector search.
- Provides endpoints for inserting, querying, and updating articles.
- Supports compliance features (audit logging, data minimization, retention policies).

---

## 4. news-cluster-agent
**Reference Basis:** `analytics`, `balancer`  
**Expected Functionality:**
- Clusters articles by topic using models like BERTopic or KMeans.
- Assigns group titles and manages topic evolution.
- Supports batch clustering and real-time updates.
- Provides endpoints for clustering, retrieving clusters, and updating assignments.

---

## 5. news-cleaner-agent
**Reference Basis:** `synthesizer`  
**Expected Functionality:**
- Synthesizes, neutralizes, and cleans articles for bias, offensive content, and redundancy.
- Uses summarization (BART, T5), topic modeling, and quote extraction.
- Produces a single, neutral article from a group of related articles.
- Provides metrics on cleaning (e.g., number of variants, quotes, average score).

---

## 6. news-factcheck-agent
**Reference Basis:** `fact_checker`  
**Expected Functionality:**
- Fact-checks claims and statements in articles using neural and symbolic models.
- Integrates with reasoning agents for contradiction detection and explainability.
- Provides endpoints for fact-checking single or multiple claims.
- Supports audit logging and compliance with legal standards.

---

## 7. news-editor-agent
**Reference Basis:** `chief_editor`  
**Expected Functionality:**
- Edits, approves, and publishes articles.
- Manages editorial workflow, attribution, and publishing logic.
- Integrates with other agents for quality control and compliance.
- Provides endpoints for editing, approving, and publishing articles.

---

## 8. news-memory-agent
**Reference Basis:** `memory`  
**Expected Functionality:**
- Monitors and manages system resources (RAM, GPU, disk) for all agents.
- Handles model caching (e.g., Hugging Face), preloading, and eviction.
- Provides endpoints for resource status, cache management, and optimization.
- Supports pre-download and caching strategies to avoid rate limits.

---

## 9. news-orchestrator-agent
**Reference Basis:** `gpu_orchestrator`  
**Expected Functionality:**
- Manages job control, workflow orchestration, and GPU resource allocation.
- Coordinates agent startup, health checks, and dependency management.
- Provides endpoints for workflow management, job status, and orchestration commands.
- Integrates with systemd for unified startup and recovery.

---

## 10. news-training-agent
**Reference Basis:** `training_system`  
**Expected Functionality:**
- Aggregates outputs from all agents to generate and refine AI model training data.
- Manages training, fine-tuning, and evaluation of models.
- Provides endpoints for triggering training, monitoring progress, and retrieving results.
- Integrates with production feedback for continuous learning.

---

## 11. news-admin-client
**Reference Basis:** `dashboard`  
**Expected Functionality:**
- Provides a web or CLI dashboard for monitoring, control, and admin actions.
- Displays real-time metrics, agent status, and system health.
- Allows triggering workflows, viewing logs, and managing configurations.
- Integrates with Prometheus and other monitoring tools.

---

### Model Management & Versioning: Best Practices for MCP Agents

To ensure robust, reproducible, and maintainable AI model management in the MCP project:

- **Centralize all models** in a `model_store/` directory, with strict versioning and metadata for each model.
- **Never overwrite models in-place**; use atomic updates and config-driven selection of active versions.
- **Drive model assignment via config files** (`model_config.json`), specifying defaults, overrides, and agent assignments.
- **Integrate with the orchestrator** for resource gating, safe mode, and upgrade coordination.
- **Provide utilities and APIs** for querying model versions, validating integrity, and exposing this info for monitoring.
- **Maintain isolation** between agents, but enforce shared conventions for model storage and versioning.
- **Document all changes** and expose model info via agent endpoints for audit and debugging.


This approach combines the best of the reference project’s robust model management with the strict isolation and reproducibility required by MCP architecture, preventing model sprawl and ensuring safe, maintainable upgrades.

---

## Draft API Specification: Managed Model Access (Orchestrator/Memory Agent)


### Overview

This API enables MCP agents to request, load, and manage AI models via the orchestrator or memory agent, ensuring all model access is centralized, auditable, resource-aware, and robust to OOM and resource contention. Direct file access is prohibited; all model operations must go through this API. The API is designed to support explicit device/memory requests, circuit breaker/fallback signaling, and structured error/metrics reporting for observability and reliability.


### Core Principles

- **Centralized Control:** All model access, versioning, and resource allocation are managed by the orchestrator/memory agent.
- **Auditability:** Every model load, unload, and update is logged and queryable.
- **Resource Awareness:** API enforces resource limits (RAM, GPU, disk) and can deny, queue, or throttle requests.
- **Explicit Device/Memory Requests:** Agents must specify required device (CPU/GPU), memory, and dtype for each model load.
- **Circuit Breaker & Fallback:** API can signal agents to fallback to CPU or safe mode if resources are low or OOM is imminent.
- **Structured Error & Metrics Reporting:** All failures, fallbacks, and resource events are reported in a structured, machine-readable way for observability.
- **Atomicity & Consistency:** Model updates are atomic; agents always receive a consistent, validated model.
- **Extensibility:** API supports future features (e.g., preloading, eviction, distributed cache).

### API Endpoints (REST/gRPC Example)

#### 1. `GET /models`

**Description:** List all available models, versions, and metadata.

**Response:**

```json
[
	{
		"model_id": "analyst-bert-base-1.2.0",
		"agent": "news-analyzer-agent",
		"version": "1.2.0",
		"status": "available",
		"current": true,
		"resources": {"ram": "2GB", "gpu": "1xA100"},
		"manifest": { "...": "..." }
	},
	{ "...": "..." }
]
```


#### 2. `POST /models/load`

**Description:** Request to load a specific model version for an agent, specifying device, memory, and dtype requirements. API may grant, deny, or suggest fallback.

**Request:**

```json
{
	"agent": "news-analyzer-agent",
	"model_id": "analyst-bert-base-1.2.0",
	"device": "cuda:0",  // or "cpu"
	"memory_gb": 2.0,
	"dtype": "float16"
}
```

**Response (success):**

```json
{
	"status": "success",
	"model_path": "/mnt/models/analyst/1.2.0/",
	"resources_allocated": {"ram": "2GB", "gpu": "1xA100"},
	"expires_in": 3600
}
```

**Response (fallback/circuit breaker):**

```json
{
	"status": "fallback",
	"reason": "circuit_breaker_triggered",
	"suggested_device": "cpu",
	"message": "GPU memory critically low, use CPU fallback."
}
```

**Response (error):**

```json
{
	"status": "error",
	"error_type": "oom",
	"message": "CUDA out of memory. Model load denied."
}
```

#### 3. `POST /models/unload`

**Description:** Release resources and unload a model.

**Request:**

```json
{
	"agent": "news-analyzer-agent",
	"model_id": "analyst-bert-base-1.2.0"
}
```

**Response:**

```json
{ "status": "success" }
```

#### 4. `GET /models/status`

**Description:** Query status of loaded models, resource usage, and cache state.

**Response:**

```json
{
	"loaded_models": [
		{"model_id": "analyst-bert-base-1.2.0", "agent": "news-analyzer-agent", "status": "active", "since": "2025-10-12T12:00:00Z"}
	],
	"resources": {"ram": "12GB/32GB", "gpu": "2/4 used"}
}
```

#### 5. `POST /models/validate`

**Description:** Validate model integrity, version, and manifest.

**Request:**

```json
{ "model_id": "analyst-bert-base-1.2.0" }
```

**Response:**

```json
{ "status": "valid", "details": "SHA256 OK, manifest matches" }
```

#### 6. `GET /models/audit`

**Description:** Retrieve audit logs for model loads, unloads, and updates.

**Response:**

```json
[
	{"timestamp": "2025-10-12T12:00:00Z", "event": "load", "agent": "news-analyzer-agent", "model_id": "analyst-bert-base-1.2.0"},
	{ "...": "..." }
]
```

### Security & Compliance

- All requests authenticated and authorized (API keys, mTLS, or JWT).
- Audit logs are immutable and queryable for compliance.
- Model manifests and hashes are validated before serving.


### Example Agent Workflow

1. Agent requests available models: `GET /models?agent=news-analyzer-agent`
2. Agent requests to load model: `POST /models/load` (specifying device, memory, dtype)
3. Agent receives model path and resource grant, or fallback/error response
4. Agent loads model on granted device, or falls back to CPU if instructed
5. Agent notifies API when done: `POST /models/unload`
6. Agent (or admin) queries audit/status endpoints as needed

---

---

**General Notes:**
- The reference project is more monolithic and interconnected, while the current project enforces strict MCP isolation and separate environments.
- Many advanced features (compliance, audit, orchestration, resource management) are present in the reference and should be ported/refactored for MCP compliance.
- The documentation in the reference project is extremely detailed and should be used as the primary source for expected agent/server behavior, endpoints, and integration patterns.


