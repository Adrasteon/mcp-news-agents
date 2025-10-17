#!/bin/bash
# Script to start each MCP server/agent one at a time and check health/availability
# Usage: bash check_agents_health.sh



AGENTS=(
  news-analyzer-agent
  news-research-agent
  news-database-server
  news-cluster-agent
  news-cleaner-agent
  news-factcheck-agent
  news-editor-agent
  news-memory-agent
  news-orchestrator-agent
  news-training-agent
  news-admin-client
)

# Function to extract conda env name from environment.yml
get_conda_env() {
  grep -m1 '^name:' "$1" | awk '{print $2}'
}

for AGENT in "${AGENTS[@]}"; do
  echo "\n==============================="
  echo "Starting $AGENT..."
  pushd "$AGENT" > /dev/null

  # Find conda env name
  if [ -f environment.yml ]; then
    ENV_NAME=$(get_conda_env environment.yml)
  else
    echo "No environment.yml found for $AGENT, skipping."
    popd > /dev/null
    continue
  fi

  # Start agent in background
  conda run -n "$ENV_NAME" python main.py &
  AGENT_PID=$!
  sleep 5  # Give the server time to start

  # Check health endpoint (default: http://localhost:8000/health, override per agent if needed)
  HEALTH_URL="http://localhost:8000/health"
  if [ "$AGENT" == "news-orchestrator-agent" ]; then
    HEALTH_URL="http://localhost:8014/health"
  fi
  if [ "$AGENT" == "news-admin-client" ]; then
    HEALTH_URL="http://localhost:8080/health"
  fi

  echo "Checking health at $HEALTH_URL..."
  curl --max-time 5 -s "$HEALTH_URL" | grep -q 'ok' && echo "$AGENT is healthy!" || echo "$AGENT health check failed."

  # Kill the agent process
  kill $AGENT_PID 2>/dev/null || echo "(Info) Agent process already exited."
  wait $AGENT_PID 2>/dev/null || true
  popd > /dev/null
done

echo "\nAll agents checked."
