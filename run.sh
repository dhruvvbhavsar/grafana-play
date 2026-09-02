#!/usr/bin/env bash
# Starts the single public-health Grafana dashboard with Homebrew Grafana.
# Ctrl+C stops Grafana.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BREW="$(brew --prefix)"
LOG_DIR="$ROOT/.logs"
mkdir -p "$LOG_DIR"

for variable in HIS_QA_DB_HOST HIS_QA_DB_USER HIS_QA_DB_NAME HIS_QA_DB_SSLMODE HIS_QA_DB_PASSWORD; do
  if [ -z "${!variable:-}" ]; then
    echo "ERROR: set $variable before starting Grafana." >&2
    exit 1
  fi
done

GRAFANA_BIN="$BREW/opt/grafana/bin/grafana"
GRAFANA_ARGS=(server --homepath="$BREW/opt/grafana/share/grafana")
if [ -f "$BREW/etc/grafana/grafana.ini" ]; then
  GRAFANA_ARGS+=(--config="$BREW/etc/grafana/grafana.ini")
fi

echo "==> Starting Grafana on :3000 ..."
GF_PATHS_PROVISIONING="$ROOT/provisioning" \
GF_PATHS_PLUGINS="$BREW/var/lib/grafana/plugins" \
GF_DASHBOARD_PATH="$ROOT/provisioning/dashboards" \
  "$GRAFANA_BIN" "${GRAFANA_ARGS[@]}" >"$LOG_DIR/grafana.log" 2>&1 &
GRAFANA_PID=$!

cleanup() {
  echo ""
  echo "==> Stopping Grafana..."
  kill "$GRAFANA_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 2
echo ""
echo "================================================"
echo "  Grafana     : http://localhost:3000  (admin/admin)"
echo "  Logs        : $LOG_DIR/"
echo "================================================"
echo ""
wait "$GRAFANA_PID"
