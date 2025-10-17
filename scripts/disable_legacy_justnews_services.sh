#!/bin/bash
# disable_legacy_justnews_services.sh
# Stops and disables all legacy JustNews systemd services so they do not
# auto-start on boot. Run with sudo/root privileges.

set -euo pipefail

REQUIRED_SERVICES=(
  "justnews@analyst.service"
  "justnews@analytics.service"
  "justnews@archive.service"
  "justnews@balancer.service"
  "justnews@chief_editor.service"
  "justnews@crawler.service"
  "justnews@crawler_control.service"
  "justnews@critic.service"
  "justnews@dashboard.service"
  "justnews@fact_checker.service"
  "justnews@gpu_orchestrator.service"
  "justnews@mcp_bus.service"
  "justnews@memory.service"
  "justnews@newsreader.service"
  "justnews@reasoning.service"
  "justnews@scout.service"
  "justnews@synthesizer.service"
  "justnews-preview-postboot.service"
)

MARKER_FILE="/var/lib/justnews/preview-postboot.marker"

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "[ERROR] This script must be run as root (try: sudo $0)" >&2
    exit 1
  fi
}

stop_services() {
  echo "[INFO] Stopping legacy JustNews services..."
  systemctl stop "${REQUIRED_SERVICES[@]}" 2>/dev/null || true
}

disable_services() {
  echo "[INFO] Disabling legacy JustNews services at boot..."
  systemctl disable "${REQUIRED_SERVICES[@]}" 2>/dev/null || true
}

remove_marker() {
  if [[ -f "$MARKER_FILE" ]]; then
    echo "[INFO] Removing preview post-boot marker at $MARKER_FILE"
    rm -f "$MARKER_FILE"
  fi
}

cleanup_symlinks() {
  local wants_dir="/etc/systemd/system/multi-user.target.wants"
  echo "[INFO] Removing multi-user.target.wants symlinks if present..."
  for service in "${REQUIRED_SERVICES[@]}"; do
    local symlink="$wants_dir/$service"
    if [[ -L "$symlink" ]]; then
      rm -f "$symlink"
      echo "  [REMOVED] $symlink"
    fi
  done
}

reload_systemd() {
  echo "[INFO] Reloading systemd daemon..."
  systemctl daemon-reload
}

main() {
  require_root
  stop_services
  disable_services
  cleanup_symlinks
  remove_marker
  reload_systemd
  echo "[SUCCESS] Legacy JustNews services disabled. They will no longer auto-start on boot."
  echo "          Start an individual service manually with: sudo systemctl start justnews@<agent>.service"
}

main "$@"
