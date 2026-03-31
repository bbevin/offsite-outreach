#!/usr/bin/env bash
# Ralph Loop runner for Offsite Outreach system
# Usage: ./loop.sh [max_iterations]
#
# Runs claude in a loop, feeding PROMPT.md each iteration.
# Each iteration gets fresh context — state persists via files on disk.
# Stop with Ctrl+C, or set a max iteration count.

set -euo pipefail

MAX_ITERATIONS=${1:-0}  # 0 = unlimited
ITERATION=0

echo "=== Ralph Loop: Offsite Outreach ==="
echo "Max iterations: ${MAX_ITERATIONS:-unlimited}"
echo "Press Ctrl+C to stop"
echo ""

while true; do
    ITERATION=$((ITERATION + 1))
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Iteration $ITERATION  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Feed the prompt to claude (skip permissions for autonomous operation)
    cat PROMPT.md | claude --print --dangerously-skip-permissions

    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "[loop] Claude exited with code $EXIT_CODE"
    fi

    # Check if max iterations reached
    if [ "$MAX_ITERATIONS" -gt 0 ] && [ "$ITERATION" -ge "$MAX_ITERATIONS" ]; then
        echo "[loop] Reached max iterations ($MAX_ITERATIONS). Stopping."
        break
    fi

    # Brief pause between iterations
    sleep 2
done
