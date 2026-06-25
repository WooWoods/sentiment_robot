#!/usr/bin/env bash
set -euo pipefail

# ---- Configuration ----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env file if present
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Activate virtual environment if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Command: daily (default) or breaking
CMD="${1:-daily}"

# Pre-flight: check LLM prerequisites when enabled
if [ "${SENTIMENT_ROBOT_LLM_ENABLED:-true}" != "false" ]; then
    if [ -z "${OPENAI_API_KEY:-}" ]; then
        echo "⚠️  WARNING: LLM is enabled (SENTIMENT_ROBOT_LLM_ENABLED=true) but OPENAI_API_KEY is not set."
        echo "   Feishu cards will show English raw data. Set OPENAI_API_KEY for Chinese content."
        echo ""
    fi
    if [ -n "${OPENAI_BASE_URL:-}" ] && [ -z "${SENTIMENT_ROBOT_LLM_MODEL:-}" ]; then
        echo "⚠️  WARNING: OPENAI_BASE_URL is set but SENTIMENT_ROBOT_LLM_MODEL is not."
        echo "   Specify your model name (e.g. export SENTIMENT_ROBOT_LLM_MODEL=qwen2.5:7b)"
        echo ""
    fi
fi

# Logging
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d)-$CMD.log"

echo "=== Sentiment Robot: $CMD run started at $(date) ===" | tee -a "$LOG_FILE"
python -m sentiment_robot "$CMD" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
echo "=== Finished at $(date), exit code: $EXIT_CODE ===" | tee -a "$LOG_FILE"

exit "$EXIT_CODE"
