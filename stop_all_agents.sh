#!/bin/bash
# stop_all_agents.sh
# Stops all MCP news agents/servers and ensures their ports are clear.
# Logs all results to agent_stop_log.txt and prints progress to the terminal.

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

LOGFILE="agent_stop_log.txt"
> "$LOGFILE"

# Graceful shutdown via /shutdown endpoint
for i in "${!AGENTS[@]}"; do
  AGENT="${AGENTS[$i]}"
  PORT="${PORTS[$i]}"
  echo "Requesting shutdown for $AGENT (port $PORT)..."
  echo "Requesting shutdown for $AGENT (port $PORT)..." >> "$LOGFILE"
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/shutdown")
  if [ "$STATUS" = "200" ]; then
    echo "$AGENT shutdown endpoint responded (HTTP 200)" | tee -a "$LOGFILE"
  else
    echo "$AGENT shutdown endpoint failed (HTTP $STATUS)" | tee -a "$LOGFILE"
  fi
done

# Wait for processes to exit
sleep 3

# Check and force kill any remaining processes on the ports
for i in "${!AGENTS[@]}"; do
  AGENT="${AGENTS[$i]}"
  PORT="${PORTS[$i]}"
  PIDS=$(lsof -t -i :$PORT)
  if [ -n "$PIDS" ]; then
    echo "$AGENT still running on port $PORT. Killing PIDs: $PIDS" | tee -a "$LOGFILE"
    kill $PIDS
    sleep 0.5
    # Double-check and force kill if needed
    PIDS2=$(lsof -t -i :$PORT)
    if [ -n "$PIDS2" ]; then
      echo "Force killing $AGENT PIDs: $PIDS2" | tee -a "$LOGFILE"
      kill -9 $PIDS2
    fi
  else
    echo "$AGENT successfully stopped and port $PORT is clear." | tee -a "$LOGFILE"
  fi
done

echo "\nAll agents stopped and ports cleared. See $LOGFILE for details."
