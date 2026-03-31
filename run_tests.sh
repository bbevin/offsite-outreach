#!/usr/bin/env bash
# Run the full test suite for offsite-outreach.
# Exit code 0 = all tests pass, non-zero = failures.
#
# Usage:
#   ./run_tests.sh              # run all tests
#   ./run_tests.sh -v           # verbose output
#   ./run_tests.sh tests/test_classifier.py  # run one file

set -euo pipefail
cd "$(dirname "$0")"

# Load credentials from .env if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

RESULTS_DIR="test_results"
mkdir -p "$RESULTS_DIR"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
RESULTS_FILE="$RESULTS_DIR/test_run_${TIMESTAMP}.txt"

python3 -m pytest tests/ "$@" 2>&1 | tee "$RESULTS_FILE"
exit_code=${PIPESTATUS[0]}

echo ""
echo "Results saved to: $RESULTS_FILE"
exit "$exit_code"
