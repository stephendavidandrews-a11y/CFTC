#!/usr/bin/env bash
# Canonical startup script for all CFTC services.
# Sources .env, sets up log directory, starts services with proper stdout capture.
#
# Usage:
#   ./scripts/start_services.sh          # start all
#   ./scripts/start_services.sh tracker  # start one
#   ./scripts/start_services.sh stop     # stop all

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"
ENV_FILE="$REPO_DIR/.env"

# Source .env
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
    echo "Loaded env from $ENV_FILE"
else
    echo "WARNING: $ENV_FILE not found — services may start without credentials"
fi

mkdir -p "$LOG_DIR"

start_service() {
    local name="$1"
    local dir="$2"
    local port="$3"
    local module="$4"

    # Kill existing
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "Stopping existing $name (PIDs: $pids)..."
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi

    echo "Starting $name on port $port..."
    cd "$dir"
    nohup .venv/bin/uvicorn "$module" --host 127.0.0.1 --port "$port" \
        >> "$LOG_DIR/$name.log" 2>&1 &
    local pid=$!
    echo "  PID: $pid, log: $LOG_DIR/$name.log"

    # Wait for health
    local attempts=0
    while [ $attempts -lt 10 ]; do
        if curl -sf "http://127.0.0.1:$port/$name/health" -o /dev/null 2>/dev/null || curl -sf "http://127.0.0.1:$port/${name}/api/health" -o /dev/null 2>/dev/null; then
            echo "  $name is UP"
            return 0
        fi
        sleep 1
        attempts=$((attempts + 1))
    done
    echo "  WARNING: $name did not respond within 10s"
    return 1
}

stop_all() {
    echo "Stopping all services..."
    for port in 8004 8005 8006; do
        local pids
        pids=$(lsof -ti :"$port" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "  Killing port $port (PIDs: $pids)"
            echo "$pids" | xargs kill -9 2>/dev/null || true
        fi
    done
    echo "All services stopped."
}

case "${1:-all}" in
    tracker)
        start_service tracker "$REPO_DIR/services/tracker" 8004 "app.main:app"
        ;;
    ai)
        start_service ai "$REPO_DIR/services/ai" 8006 "app.main:app"
        ;;
    intake)
        start_service intake "$REPO_DIR/services/intake" 8005 "main:app"
        ;;
    stop)
        stop_all
        ;;
    all)
        start_service tracker "$REPO_DIR/services/tracker" 8004 "app.main:app"
        start_service ai "$REPO_DIR/services/ai" 8006 "app.main:app"
        start_service intake "$REPO_DIR/services/intake" 8005 "main:app"
        echo ""
        echo "All services started. Logs in $LOG_DIR/"
        ;;
    *)
        echo "Usage: $0 [tracker|ai|intake|stop|all]"
        exit 1
        ;;
esac
