#!/bin/bash
# Load shared environment variables for the MCP agents if available.
ENV_FILE="${JUSTNEWS_ENV_FILE:-$HOME/.config/justnews/justnews.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "Warning: environment file '$ENV_FILE' not found."
fi

# Verify the primary PostgreSQL cluster is reachable before starting agents.
echo "Checking PostgreSQL connectivity..."
PSQL_USER=${JUSTNEWS_DB_USER:-justnews_user}
PSQL_HOST=${JUSTNEWS_DB_HOST:-localhost}
PSQL_PORT=${JUSTNEWS_DB_PORT:-5432}
PSQL_DB=${JUSTNEWS_DB_NAME:-justnews}

if command -v psql >/dev/null 2>&1; then
  PGPASSWORD="$JUSTNEWS_DB_PASSWORD" psql \
    --host="$PSQL_HOST" \
    --port="$PSQL_PORT" \
    --username="$PSQL_USER" \
    --dbname="$PSQL_DB" \
    --command "SELECT version();" \
    --tuples-only \
    --no-align >/dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "FATAL: Unable to reach PostgreSQL at $PSQL_HOST:$PSQL_PORT as $PSQL_USER." >&2
    exit 1
  fi
  echo "PostgreSQL connectivity OK."
else
  echo "Warning: 'psql' not found; skipping connectivity test."
fi

# Provide legacy NEWS_DB_* variables for agents that still expect them.
export NEWS_DB_HOST="${NEWS_DB_HOST:-$PSQL_HOST}"
export NEWS_DB_PORT="${NEWS_DB_PORT:-$PSQL_PORT}"
export NEWS_DB_NAME="${NEWS_DB_NAME:-$PSQL_DB}"
export NEWS_DB_USER="${NEWS_DB_USER:-$PSQL_USER}"
export NEWS_DB_PASS="${NEWS_DB_PASS:-$JUSTNEWS_DB_PASSWORD}"

# startup_all_agents.sh
# startup_all_agents.sh
# Starts all MCP news agents/servers on their canonical ports, waits, then checks health endpoints.
# Logs all results to agent_startup_log.txt and prints progress to the terminal.

AGENTS=(
  "news-analyzer-agent"
  "news-research-agent"
  "news-database-server"
  "news-cluster-agent"
  "news-cleaner-agent"
  "news-factcheck-agent"
  "news-editor-agent"
  "news-memory-agent"
  "news-orchestrator-agent"
  "news-training-agent"
  "news-admin-client"
)

PORTS=(
  9500
  9501
  9502
  9503
  9504
  9505
  9506
  9507
  9508
  9509
  9510
)

HEALTH_PATHS=(
  "/health"
  "/health"
  "/health"
  "/health"
  "/health"
  "/health"
  "/health"
  "/health"
  "/health"
  "/health"
  "/health"
)

LOGFILE="agent_startup_log.txt"
> "$LOGFILE"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

HEALTH_RETRIES=${HEALTH_RETRIES:-10}
HEALTH_RETRY_DELAY=${HEALTH_RETRY_DELAY:-2}

PIDS=()

for i in "${!AGENTS[@]}"; do
  AGENT="${AGENTS[$i]}"
  PORT="${PORTS[$i]}"
  AGENT_LOG="$LOG_DIR/${AGENT}.log"
  echo "Starting $AGENT on port $PORT..."
  echo "Starting $AGENT on port $PORT..." >> "$LOGFILE"
  : > "$AGENT_LOG"
  (
    cd "$AGENT" && \
      NEWS_AGENT_PORT="$PORT" \
      stdbuf -oL -eL conda run -n "$AGENT-env" python main.py >> "../$AGENT_LOG" 2>&1 &
  )
  PIDS+=("$!")
  sleep 0.5
  # Give each agent a moment to start
  # (Remove sleep for faster startup if desired)
done

# Wait for all agents to initialize
sleep 3

echo "\n--- Checking health of all agents ---" | tee -a "$LOGFILE"

for i in "${!AGENTS[@]}"; do
  AGENT="${AGENTS[$i]}"
  PORT="${PORTS[$i]}"
  HEALTH_PATH="${HEALTH_PATHS[$i]}"
  echo "Checking $AGENT at http://localhost:$PORT$HEALTH_PATH..."
  echo "Checking $AGENT at http://localhost:$PORT$HEALTH_PATH..." >> "$LOGFILE"
  STATUS=""
  for attempt in $(seq 1 "$HEALTH_RETRIES"); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT$HEALTH_PATH")
    if [ "$STATUS" = "200" ]; then
      break
    fi
    sleep "$HEALTH_RETRY_DELAY"
  done
  if [ "$STATUS" = "200" ]; then
    echo "$AGENT healthy (HTTP 200)" | tee -a "$LOGFILE"
  else
    echo "$AGENT health check failed (HTTP $STATUS)" | tee -a "$LOGFILE"
    echo "See $LOG_DIR/${AGENT}.log for details." | tee -a "$LOGFILE"
  fi
done

echo "\nAll agents started and health checked. See $LOGFILE for details."
