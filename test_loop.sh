#!/usr/bin/env bash
# Test-Fix Loop runner for Offsite Outreach system
# Usage: ./test_loop.sh [max_iterations]
#
# Runs claude in a test-fix loop. Each iteration:
# 1. Runs integration tests
# 2. Analyzes output CSV for data quality issues
# 3. Fixes one issue
# 4. Verifies fix + no regressions
# 5. Commits and loops
#
# Stop with Ctrl+C, or set a max iteration count.

set -euo pipefail

MAX_ITERATIONS=${1:-10}  # Default to 10 (safety net against infinite loops)
ITERATION=0
FIXES_LOG="test_results/fixes.log"

# Initialize fixes log if it doesn't exist
mkdir -p test_results
if [ ! -f "$FIXES_LOG" ]; then
    echo "# Test-Fix Loop — Fix Ledger" > "$FIXES_LOG"
    echo "# Format: YYYY-MM-DD HH:MM | SEVERITY | domain_or_pattern | description" >> "$FIXES_LOG"
    echo "" >> "$FIXES_LOG"
fi

echo "=== Test-Fix Loop: Offsite Outreach ==="
echo "Max iterations: $MAX_ITERATIONS"
echo "Fixes log: $FIXES_LOG"
echo "Press Ctrl+C to stop"
echo ""

while true; do
    ITERATION=$((ITERATION + 1))
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Test-Fix Iteration $ITERATION  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Feed the test-fix prompt to claude
    cat PROMPT_TESTFIX.md | claude --print --dangerously-skip-permissions

    EXIT_CODE=$?

    # Count fixes so far
    FIX_COUNT=$(grep -c "^[0-9]" "$FIXES_LOG" 2>/dev/null || echo "0")
    echo "[test-fix] Iteration $ITERATION complete. Total fixes logged: $FIX_COUNT"

    if [ $EXIT_CODE -ne 0 ]; then
        echo "[test-fix] Claude exited with code $EXIT_CODE"
    fi

    # Check if max iterations reached
    if [ "$ITERATION" -ge "$MAX_ITERATIONS" ]; then
        echo "[test-fix] Reached max iterations ($MAX_ITERATIONS). Stopping."
        echo "[test-fix] Review $FIXES_LOG for all fixes applied."
        break
    fi

    # Brief pause between iterations
    sleep 2
done
