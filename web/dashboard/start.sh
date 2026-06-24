#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cleanup() {
  echo ""
  echo "Shutting down..."
  kill $FLASK_PID $VITE_PID 2>/dev/null
  wait $FLASK_PID $VITE_PID 2>/dev/null
  echo "Done."
  exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║       The Apply Collector — Dev Mode        ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║  Flask API  →  http://127.0.0.1:5000        ║"
echo "  ║  Vite React →  http://localhost:3000         ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# Start Flask
cd "$PROJECT_ROOT"
python -m web.app --host 127.0.0.1 --port 5000 &
FLASK_PID=$!

# Start Vite
cd "$SCRIPT_DIR"
npx vite --host &
VITE_PID=$!

echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

wait $FLASK_PID $VITE_PID
